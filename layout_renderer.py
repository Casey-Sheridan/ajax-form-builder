from PIL import Image, ImageDraw, ImageFont
import os

# expects:
# data = filled values
# layout = template json

def render_flyer_from_layout(layout, data, fonts):

    img = Image.open(layout["background"]).convert("RGB")
    draw = ImageDraw.Draw(img)

    for el in layout.get("elements", []):

        el_type = el.get("type")

        # -------------------------
        # TEXT ELEMENT
        # -------------------------
        if el_type == "text":

            value = data.get(el.get("field"), "")

            font_key = el.get("font", "regular")
            font_size = el.get("size", 30)

            font = fonts.get(font_key)
            if font:
                font = ImageFont.truetype(font.path, font_size)

            draw.text(
                (el["x"], el["y"]),
                str(value),
                font=font,
                fill=el.get("color", "white")
            )

        # -------------------------
        # QR ELEMENT
        # -------------------------
        if el_type == "qr":
            import qrcode

            qr = qrcode.QRCode(box_size=10, border=1)
            qr.add_data(data.get("registration_link", ""))
            qr.make(fit=True)

            qr_img = qr.make_image(fill="black", back_color="white").convert("RGB")

            size = el.get("size", 140)
            qr_img = qr_img.resize((size, size))

            img.paste(qr_img, (el["x"], el["y"]))

    return img