import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import os

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Flyer Generator", layout="centered")

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_PATH = os.path.join(BASE_DIR, "master_template.png")
LOGO_DIR = os.path.join(BASE_DIR, "logos")
FONT_DIR = os.path.join(BASE_DIR, "fonts")

# -------------------------
# LOAD FONTS (cached)
# -------------------------
@st.cache_resource
def load_fonts():
    return {
        "bold": ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Bold.ttf"), 38),
        "regular": ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Regular.ttf"), 30),
    }

fonts = load_fonts()

# -------------------------
# UI
# -------------------------
st.title("AJAX Training Flyer Generator")

with st.form("flyer_form"):
    st.subheader("Event Details")

    col1, col2 = st.columns(2)

    with col1:
        location = st.text_input("Location", "SES - Detroit")
        date = st.text_input("Date", "Tuesday, May 12th")
        address1 = st.text_input("Address Line 1", "25181 Dequindre Rd")

    with col2:
        time = st.text_input("Time", "10:00 AM - 3:00 PM")
        address2 = st.text_input("Address Line 2", "Madison Heights, MI 48071")

    st.subheader("Partner")

    partner = st.selectbox(
        "Partner",
        ["ADI", "Advantage", "APD", "ENS", "Lonestar",
         "Mountain West", "SDS", "SDI", "SES", "SS&SI", "Wesco", "Custom"]
    )

    custom_logo_url = ""
    if partner == "Custom":
        custom_logo_url = st.text_input("Custom Logo URL")

    registration_link = st.text_input(
        "Registration Link",
        "https://forms.gle/27N37sA1TrrJAEwDA"
    )

    submitted = st.form_submit_button("Generate Flyer")

# -------------------------
# CORE FUNCTION
# -------------------------
def generate_flyer():
    if not os.path.exists(TEMPLATE_PATH):
        st.error("Template image not found.")
        return None

    try:
        img = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(img)

        white, gray = (255, 255, 255), (180, 180, 180)

        tx, ty = 130, 545
        qx, qy = 812, 1308

        # Text rendering
        draw.text((tx, ty), date, font=fonts["bold"], fill=white)
        draw.text((tx, ty + 50), time, font=fonts["regular"], fill=gray)
        draw.text((tx, ty + 110), location, font=fonts["bold"], fill=white)
        draw.text((tx, ty + 160), address1, font=fonts["regular"], fill=white)
        draw.text((tx, ty + 200), address2, font=fonts["regular"], fill=white)

        # -------------------------
        # LOGO HANDLING
        # -------------------------
        logo_img = None

        try:
            if partner == "Custom" and custom_logo_url:
                r = requests.get(custom_logo_url, timeout=5)
                r.raise_for_status()
                logo_img = Image.open(BytesIO(r.content)).convert("RGBA")

            elif partner != "Custom":
                logo_path = os.path.join(LOGO_DIR, f"{partner.lower()}_logo.png")
                if os.path.exists(logo_path):
                    logo_img = Image.open(logo_path).convert("RGBA")

        except Exception as e:
            st.warning("Logo could not be loaded.")

        if logo_img:
            logo_img.thumbnail((350, 100), Image.Resampling.LANCZOS)
            img.paste(
                logo_img,
                (280, round(1450 - (logo_img.height / 2))),
                logo_img
            )

        # -------------------------
        # QR CODE
        # -------------------------
        qr_img = qrcode.make(registration_link).resize((150, 150)).convert("RGB")
        img.paste(qr_img, (qx, qy))

        # -------------------------
        # EXPORT TO MEMORY
        # -------------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer

    except Exception as e:
        st.error("Something went wrong while generating the flyer.")
        return None

# -------------------------
# RUN
# -------------------------
if submitted:
    with st.spinner("Generating flyer..."):
        result = generate_flyer()

    if result:
        st.success("Flyer ready!")

        st.download_button(
            label="Download Flyer",
            data=result,
            file_name="Final_Flyer.png",
            mime="image/png"
        )