from models.template import TemplateModel


def test_template_model_parses():

    template_data = {
        "schema_version": 1,
        "id": "9e789a50-fd2e-4409-80fe-f4e813531015",
        "name": "Test Template",
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
                "y": 200,
                "style": {
                    "font": "Montserrat-Regular.ttf",
                    "size": 32,
                    "color": "#FFFFFF",
                    "align": "left"
                }
            }
        ]
    }

    template = TemplateModel.model_validate(template_data)

    assert template.id == "9e789a50-fd2e-4409-80fe-f4e813531015"
    assert len(template.elements) == 1