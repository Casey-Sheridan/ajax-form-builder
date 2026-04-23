import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import os

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Flyer Generator", layout="wide")

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_PATH = os.path.join(BASE_DIR, "master_template.png")
LOGO_DIR = os.path.join(BASE_DIR, "logos")
FONT_DIR = os.path.join(BASE_DIR, "fonts")

# -------------------------
# LOAD FONTS
# -------------------------
@st.cache_resource
def load_fonts():
    return {
        "bold": ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Bold.ttf"), 38),
        "regular": ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Regular.ttf"), 30),
    }

fonts = load_fonts()

# -------------------------
# CORE FUNCTION
# -------------------------
def generate_flyer(data):
    if not os.path.exists(TEMPLATE_PATH):
        return None, "Template image not found."

    try:
        img = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(img)

        white, gray = (255, 255, 255), (180, 180, 180)

        tx, ty = 130, 545
        qx, qy = 812, 1308

        # TEXT
        draw.text((tx, ty), data["date"], font=fonts["bold"], fill=white)
        draw.text((tx, ty + 50), data["time"], font=fonts["regular"], fill=gray)
        draw.text((tx, ty + 110), data["location"], font=fonts["bold"], fill=white)
        draw.text((tx, ty + 160), data["address1"], font=fonts["regular"], fill=white)
        draw.text((tx, ty + 200), data["address2"], font=fonts["regular"], fill=white)

        # -------------------------
        # LOGO HANDLING
        # -------------------------
        logo_img = None

        try:
            # Upload takes priority (best UX)
            if data["uploaded_logo"] is not None:
                logo_img = Image.open(data["uploaded_logo"]).convert("RGBA")

            elif data["partner"] == "Custom" and data["custom_logo_url"]:
                r = requests.get(data["custom_logo_url"], timeout=5)
                r.raise_for_status()
                logo_img = Image.open(BytesIO(r.content)).convert("RGBA")

            elif data["partner"] != "Custom":
                logo_path = os.path.join(LOGO_DIR, f"{data['partner'].lower()}_logo.png")
                if os.path.exists(logo_path):
                    logo_img = Image.open(logo_path).convert("RGBA")

        except Exception:
            pass

        if logo_img:
            logo_img.thumbnail((350, 100), Image.Resampling.LANCZOS)
            img.paste(
                logo_img,
                (280, round(1450 - (logo_img.height / 2))),
                logo_img
            )

        # -------------------------
        # QR
        # -------------------------
        qr_img = qrcode.make(data["registration_link"]).resize((150, 150)).convert("RGB")
        img.paste(qr_img, (qx, qy))

        # -------------------------
        # OUTPUT
        # -------------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer, None

    except Exception as e:
        return None, "Error generating flyer."

# -------------------------
# UI LAYOUT
# -------------------------
st.title("AJAX Training Flyer Generator")

# Two-column layout: form (left) + preview (right)
col_form, col_preview = st.columns([1, 1])

with col_form:
    with st.form("flyer_form"):

        # -------------------------
        # ROW 1: NAME / LOCATION
        # -------------------------
        location = st.text_input("Location / Name", "SES - Detroit")

        # -------------------------
        # ROW 2: ADDRESS
        # -------------------------
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            address1 = st.text_input("Address Line 1", "25181 Dequindre Rd")
        with col_a2:
            address2 = st.text_input("Address Line 2", "Madison Heights, MI 48071")

        # -------------------------
        # ROW 3: DATE / TIME / PARTNER
        # -------------------------
        col_d, col_t, col_p = st.columns(3)

        with col_d:
            date = st.text_input("Date", "Tuesday, May 12th")
        with col_t:
            time = st.text_input("Time", "10:00 AM - 3:00 PM")
        with col_p:
            partner = st.selectbox(
                "Partner",
                ["ADI", "Advantage", "APD", "ENS", "Lonestar",
                 "Mountain West", "SDS", "SDI", "SES", "SS&SI", "Wesco", "Custom"]
            )

        # -------------------------
        # CUSTOM LOGO OPTIONS
        # -------------------------
        uploaded_logo = None
        custom_logo_url = ""

        if partner == "Custom":
            st.markdown("**Custom Logo**")

            uploaded_logo = st.file_uploader(
                "Upload Logo",
                type=["png", "jpg", "jpeg"]
            )

            custom_logo_url = st.text_input("or Logo URL")

        # -------------------------
        # LINK
        # -------------------------
        registration_link = st.text_input(
            "Registration Link",
            "https://forms.gle/27N37sA1TrrJAEwDA"
        )

        submitted = st.form_submit_button("Generate Flyer")

# -------------------------
# HANDLE SUBMISSION
# -------------------------
if submitted:
    data = {
        "location": location,
        "address1": address1,
        "address2": address2,
        "date": date,
        "time": time,
        "partner": partner,
        "custom_logo_url": custom_logo_url,
        "uploaded_logo": uploaded_logo,
        "registration_link": registration_link,
    }

    with st.spinner("Generating flyer..."):
        result, error = generate_flyer(data)

    if error:
        st.error(error)
    else:
        # PREVIEW
        with col_preview:
            st.subheader("Preview")
            st.image(result)

            st.download_button(
                "Download Flyer",
                data=result,
                file_name="Final_Flyer.png",
                mime="image/png"
            )