from fastapi.testclient import TestClient
from pathlib import Path

from api.app import app

client = TestClient(app)


# =========================
# FULL LIFECYCLE TEST
# =========================

def test_template_lifecycle_and_render():
    """
    End-to-end test:

    1. Create template
    2. Fetch template
    3. Render preview
    4. Save output image
    """

    # -------------------------
    # TEMPLATE PAYLOAD
    # -------------------------

    template_payload = {
        "schema_version": 1,
        "id": "592ed4c1-c9f5-41ae-8376-caf319466ed1",
        "name": "Test Event",
        "canvas": {
            "width": 1080,
            "height": 1350
        },
        "background": "assets/test_bg.png",
        "elements": [
            {
                "id": "txt1",
                "type": "text",
                "field": "address",
                "label": "Venue Address",
                "x": 100,
                "y": 100,
                "style": {
                    "font": "Montserrat-Regular.ttf",
                    "size": 36,
                    "color": "#FFFFFF",
                    "align": "left"
                }
            },
            {
                "id": "qr1",
                "type": "qr",
                "field": "registration_link",
                "label": "Registration QR",
                "x": 700,
                "y": 700,
                "size": 180
            }
        ]
    }

    runtime_data = {
        "address": "Ajax Brewing Co",
        "registration_link": "https://example.com/register"
    }

    # -------------------------
    # 1. CREATE TEMPLATE
    # -------------------------

    resp = client.post("/templates", json=template_payload)

    print("\nCREATE RESPONSE:", resp.status_code, resp.text)

    assert resp.status_code == 200

    # -------------------------
    # 2. FETCH TEMPLATE
    # -------------------------

    resp = client.get("/templates/592ed4c1-c9f5-41ae-8376-caf319466ed1")

    print("\nFETCH RESPONSE:", resp.status_code)

    assert resp.status_code == 200

    template = resp.json()

    # -------------------------
    # 3. RENDER PREVIEW
    # -------------------------

    resp = client.post(
        "/render/preview",
        json={
            "template": template,
            "data": runtime_data
        }
    )

    print("\nRENDER RESPONSE:", resp.status_code)
    print("CONTENT TYPE:", resp.headers.get("content-type"))

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"

    # -------------------------
    # 4. SAVE OUTPUT IMAGE
    # -------------------------

    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "render_test.png"

    with open(output_path, "wb") as f:
        f.write(resp.content)

    print("\nIMAGE SAVED TO:", output_path)

    assert output_path.exists()