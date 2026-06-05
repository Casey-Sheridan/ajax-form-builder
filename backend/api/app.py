import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from PIL import Image

from models.template import TemplateModel
from repositories.template_repository import (
    init_db,
    get_template as repo_get_template,
    save_template as repo_save_template,
    list_templates as repo_list_templates,
    delete_template as repo_delete_template,
    save_revision as repo_save_revision,
    list_revisions as repo_list_revisions,
    get_revision as repo_get_revision,
)
from fastapi import APIRouter, HTTPException
from models.template import TemplateModel
router = APIRouter()

app = FastAPI()

# ---------------------------
# GLOBAL ERROR HANDLER (prevents CORS-masked 500s)
# ---------------------------
from fastapi.responses import JSONResponse
import traceback

@app.middleware("http")
async def catch_all_exceptions(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print("🔥 Backend error:", str(e))
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers={"Access-Control-Allow-Origin": "http://localhost:5173"},
        )
app.include_router(router)

# ---------------------------
# CORS (React dev support)
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.base import BaseHTTPMiddleware

class CORSSafeStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if request.url.path.startswith("/static"):
            response.headers["Access-Control-Allow-Origin"] = "*"

        return response

app.add_middleware(CORSSafeStaticMiddleware)

class CORSMediaStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)

        response.headers["Access-Control-Allow-Origin"] = "*"

        return response
    
# ---------------------------
# SERVE STATIC FILES
# ---------------------------
from pathlib import Path
import re
import uuid

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
BACKGROUNDS_DIR = STATIC_DIR / "backgrounds"
FONTS_DIR = BASE_DIR / "assets" / "fonts"

app.mount("/fonts", CORSMediaStaticFiles(directory=str(FONTS_DIR)), name="fonts")
app.mount("/static", CORSMediaStaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------
# INIT DB ON STARTUP
# ---------------------------
@app.on_event("startup")
def startup():
    init_db()


# ---------------------------
# ROOT
# ---------------------------
@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/backgrounds")
async def upload_background(request: Request):
    filename = request.headers.get("x-filename") or "background"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported background image type")

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(filename).stem).strip("-") or "background"
    stored_name = f"{safe_stem}-{uuid.uuid4().hex}{suffix}"
    data = await request.body()

    if not data:
        raise HTTPException(status_code=400, detail="Empty background image")

    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKGROUNDS_DIR / stored_name
    target.write_bytes(data)

    return {"path": f"/static/backgrounds/{stored_name}"}


# ---------------------------
# LIST PARTNERS
# ---------------------------
@app.get("/partners")
def list_partners():
    """
    Load partners list from partners.txt file.
    Returns a list of partner names.
    """
    partners_file = BASE_DIR / "partners.txt"
    
    if not partners_file.exists():
        return [{"name": "Custom"}]
    
    with open(partners_file, "r") as f:
        partners = [line.strip() for line in f if line.strip()]
    
    return [{"name": p} for p in partners] + [{"name": "Custom"}]


# ---------------------------
# GET SINGLE TEMPLATE
# ---------------------------
@app.get("/templates/{template_id}")
def get_template(template_id: str):
    template = repo_get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template.model_dump(by_alias=True)


# ---------------------------
# LIST TEMPLATES
# ---------------------------
@app.get("/templates")
def list_templates():
    templates = repo_list_templates()
    return [t.model_dump(by_alias=True) for t in templates]


# ---------------------------
# UPSERT TEMPLATE
# ---------------------------
@app.put("/templates/{template_id}")
def update_template(template_id: str, payload: dict):
    try:
        # enforce ID consistency
        payload["id"] = template_id

        template = TemplateModel(**payload)
        repo_save_template(template)

        return {"status": "ok", "id": template_id}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------
# DELETE TEMPLATE
# ---------------------------
@app.delete("/templates/{template_id}")
def delete_template(template_id: str):
    repo_delete_template(template_id)
    return {"status": "deleted", "id": template_id}

# ---------------------------
# QR PREVIEW GENERATOR
# ---------------------------
@app.get("/render/qr-preview")
def render_qr_preview(text: str = "Hello, world!", size: int = 180):
    """
    Generate a QR code preview image for use in the frontend editor.
    Returns a PNG image of the QR code.
    """
    from services.render_service import render_qr_element
    from models.template import QRElement
    from io import BytesIO

    # Create a blank white image
    img = Image.new("RGBA", (size, size), "white")

    # Create a mock QRElement
    qr_element = QRElement(
        id="preview",
        type="qr",
        field="preview",
        label="Preview",
        x=0,
        y=0,
        size=size
    )

    # Render QR code onto image
    render_qr_element(img, qr_element, {"preview": text}, 1, 1)

    # Return as PNG
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable"
        }
    )


# ---------------------------
# CREATE REVISION
# ---------------------------
@app.post("/templates/{template_id}/revisions")
async def create_revision(template_id: str, request: Request):
    """
    Save a full snapshot revision for a template.
    Accepts { snapshot: TemplateDTO, trigger: str }.
    Also handles navigator.sendBeacon requests (Content-Type: application/json blob).
    """
    try:
        body = await request.body()
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    snapshot = payload.get("snapshot")
    trigger = payload.get("trigger", "interval")

    if not snapshot or not isinstance(snapshot, dict):
        raise HTTPException(status_code=400, detail="snapshot is required")

    valid_triggers = {"interval", "switch", "unload", "manual"}
    if trigger not in valid_triggers:
        trigger = "interval"

    # Validate the snapshot as a real TemplateModel before persisting
    try:
        snapshot["id"] = template_id
        TemplateModel.model_validate(snapshot)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid snapshot: {e}")

    revision_id = repo_save_revision(template_id, snapshot, trigger)
    return {"id": revision_id, "templateId": template_id}


# ---------------------------
# LIST REVISIONS
# ---------------------------
@app.get("/templates/{template_id}/revisions")
def list_revisions(template_id: str):
    """
    Return revision metadata (no snapshot body) for a template,
    most-recent first.
    """
    return repo_list_revisions(template_id)


# ---------------------------
# GET SINGLE REVISION
# ---------------------------
@app.get("/templates/{template_id}/revisions/{revision_id}")
def get_revision(template_id: str, revision_id: str):
    """
    Return a single revision including its full snapshot.
    """
    revision = repo_get_revision(revision_id)

    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    if revision["templateId"] != template_id:
        raise HTTPException(status_code=404, detail="Revision not found")

    return revision


# ---------------------------
# VALIDATE TEMPLATE (NO SAVE)
# ---------------------------
@router.post("/templates/validate")
def validate_template(template: dict):
    try:
        validated = TemplateModel.model_validate(template)
        return {
            "valid": True,
            "template": validated.model_dump(by_alias=True)
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


# ---------------------------
# RENDER FLYER
# ---------------------------
@app.post("/render/flyer")
def render_flyer(payload: dict):
    """
    Render a flyer from a template and form data.
    
    Expects:
    {
        "template_id": "template-id",
        "data": {
            "location": "string",
            "address1": "string",
            "address2": "string",
            "date": "string",
            "time": "string",
            "partner": "string",
            "registration_link": "string",
            ...
        }
    }
    
    Returns: PNG image
    """
    from services.render_service import render_template
    from io import BytesIO
    
    template_id = payload.get("template_id")
    data = payload.get("data", {})
    
    if not template_id:
        raise HTTPException(status_code=400, detail="template_id is required")
    
    # Get template from repository
    template = repo_get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        # Render the flyer
        img = render_template(template, data)
        
        # Convert to PNG, embedding the template's DPI so print software
        # (Photoshop, Illustrator, etc.) interprets physical dimensions correctly.
        buffer = BytesIO()
        img.save(buffer, format="PNG", dpi=(template.canvas.dpi, template.canvas.dpi))
        buffer.seek(0)
        
        return Response(
            content=buffer.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "no-cache",
                "Content-Disposition": "inline; filename=flyer.png"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
