import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Query
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
from repositories.catalog_repository import (
    list_orgs as repo_list_orgs,
    get_default_org_id,
    get_org_by_id,
    list_catalogs as repo_list_catalogs,
    list_catalog_items as repo_list_catalog_items,
    create_catalog_item as repo_create_catalog_item,
    delete_catalog_item as repo_delete_catalog_item,
    save_item_asset as repo_save_item_asset,
    get_catalog_item as repo_get_catalog_item,
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
UPLOADS_DIR = STATIC_DIR / "uploads"
FONTS_DIR = BASE_DIR / "assets" / "fonts"
ASSETS_DIR = BASE_DIR / "assets"

app.mount("/fonts", CORSMediaStaticFiles(directory=str(FONTS_DIR)), name="fonts")
app.mount("/static", CORSMediaStaticFiles(directory=str(STATIC_DIR)), name="static")
# Serves existing logo/asset files that pre-date the catalog system
app.mount("/assets", CORSMediaStaticFiles(directory=str(ASSETS_DIR)), name="assets")

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


@app.post("/uploads/temp")
async def upload_temp_asset(request: Request):
    """
    Upload an image for use in the current render session.
    Accepts any image file; stores it under static/uploads/ and returns
    a URL the frontend can embed in render data for image fields.
    Suitable for custom/one-off assets that don't belong to a catalog item.
    """
    filename = request.headers.get("x-filename", "upload")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file body")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    (UPLOADS_DIR / stored_name).write_bytes(data)

    return {"url": f"/static/uploads/{stored_name}"}


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
# ORGS
# ---------------------------

def _resolve_org(org_id: Optional[str]) -> str:
    """Return the requested org_id or fall back to the default org."""
    if org_id:
        if not get_org_by_id(org_id):
            raise HTTPException(status_code=404, detail=f"Org '{org_id}' not found")
        return org_id
    default = get_default_org_id()
    if not default:
        raise HTTPException(status_code=503, detail="No organizations exist yet")
    return default


@app.get("/orgs")
def list_orgs():
    return repo_list_orgs()


# ---------------------------
# CATALOGS — list all catalogs for an org
# ---------------------------

@app.get("/orgs/{org_id}/catalogs")
def list_catalogs(org_id: str):
    if not get_org_by_id(org_id):
        raise HTTPException(status_code=404, detail="Org not found")
    return repo_list_catalogs(org_id)


# ---------------------------
# CATALOG ITEMS — the main endpoint used by the form
# GET  /catalogs/{name}?org_id=xxx   returns items for that catalog
# POST /catalogs/{name}/items        adds an item
# DELETE /catalogs/{name}/items/{id} removes an item
# POST /catalogs/{name}/items/{id}/asset  uploads an image asset
# ---------------------------

@app.get("/catalogs/{catalog_name}")
def get_catalog_items(
    catalog_name: str,
    org_id: Optional[str] = Query(default=None),
):
    resolved = _resolve_org(org_id)
    items = repo_list_catalog_items(resolved, catalog_name)
    return {"catalog": catalog_name, "org_id": resolved, "items": items}


@app.post("/catalogs/{catalog_name}/items")
async def add_catalog_item(
    catalog_name: str,
    request: Request,
    org_id: Optional[str] = Query(default=None),
):
    resolved = _resolve_org(org_id)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    value = body.get("value", "").strip()
    label = body.get("label", value).strip()
    if not value:
        raise HTTPException(status_code=400, detail="'value' is required")

    item = repo_create_catalog_item(
        org_id=resolved,
        catalog_name=catalog_name,
        value=value,
        label=label,
        meta=body.get("meta"),
        sort_order=int(body.get("sort_order", 0)),
    )
    return {"status": "ok", **item}


@app.delete("/catalogs/{catalog_name}/items/{item_id}")
def remove_catalog_item(
    catalog_name: str,
    item_id: str,
    org_id: Optional[str] = Query(default=None),
):
    resolved = _resolve_org(org_id)
    deleted = repo_delete_catalog_item(resolved, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted", "id": item_id}


@app.post("/catalogs/{catalog_name}/items/{item_id}/asset")
async def upload_catalog_item_asset(
    catalog_name: str,
    item_id: str,
    request: Request,
    org_id: Optional[str] = Query(default=None),
):
    resolved = _resolve_org(org_id)

    item = repo_get_catalog_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    filename = request.headers.get("x-filename", "asset")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file body")

    rel_path = repo_save_item_asset(resolved, catalog_name, item_id, data, suffix)
    image_url = f"/{rel_path}"
    return {"status": "ok", "image_url": image_url}


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
