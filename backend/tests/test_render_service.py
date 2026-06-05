from pathlib import Path

from PIL import Image

from models.template import TemplateModel
from services.render_service import render_template


TEST_OUTPUT_DIR = Path("tests/output")
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)



def test_render_template_generates_image():

    template_data = {
        "schema_version": 1,
        "id": "b1091cbe-e107-4ef0-a44a-8b7a04984798",
        "name": "Render Test",
        "canvas": {
            "width": 1080,
            "height": 1350
        },
        "background": "static/backgrounds/test_bg.png",
        "elements": [
            {
                "id": "txt1",
                "type": "text",
                "field": "location",
                "label": "Location",
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
        "location": "Ajax Brewing",
        "registration_link": "https://example.com/register"
    }

    template = TemplateModel.model_validate(template_data)

    img = render_template(template, runtime_data)

    assert isinstance(img, Image.Image)

    output_path = TEST_OUTPUT_DIR / "render_test_output.png"

    img.save(output_path)

    assert output_path.exists()