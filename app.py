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
# SESSION STATE
# -------------------------
if "flyer_result" not in st.session_state:
    st.session_state.flyer_result = None

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
        qx, qy = 887, 1381  # center point

        # TEXT
        draw.text((tx, ty), data["date"], font=fonts["bold"], fill=white)
        draw.text((tx, ty + 50), data["time"], font=fonts["regular"], fill=gray)
        draw.text((tx, ty + 110), data["location"], font=fonts["bold"], fill=white)
        draw.text((tx, ty + 160), data["address1"], font=fonts["regular"], fill=white)
        draw.text((tx, ty + 200), data["address2"], font=fonts["regular"], fill=white)

        # -------------------------
        # LOGO
        # -------------------------
        logo_img = None

        try:
            if data["uploaded_logo"] is not None:
                logo_img = Image.open(data["uploaded_logo"]).convert("RGBA")

            elif data["partner"] == "Custom" and data["custom_logo_url"]:
                r = requests.get(data["custom_logo_url"], timeout=5)
                r.raise_for_status()
                logo_img = Image.open(BytesIO(r.content)).convert("RGBA")

            elif data["partner"] != "Custom":
                logo_path = os.path.join(LOGO_DIR, f"{data['partner'].lower()}.png")
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
        # QR CODE (140x140, centered)
        # -------------------------
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_Q,
            box_size=10,
            border=1
        )

        qr.add_data(data["registration_link"])
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        qr_img = qr_img.resize((140, 140), Image.Resampling.LANCZOS)

        img.paste(
            qr_img,
            (
                qx - qr_img.width // 2,
                qy - qr_img.height // 2
            )
        )

        # -------------------------
        # OUTPUT
        # -------------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer, None

    except Exception as e:
        return None, "Error generating flyer: " + str(e)

# -------------------------
# STYLE
# -------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 1rem;
}
h1 {
    margin-top: 0rem;
    padding-top: 0rem;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# UI
# -------------------------
st.title("AJAX Training Flyer Generator")

col_form, col_preview = st.columns([1, 1])

with col_form:

    partner = st.selectbox(
        "Partner",
        ["ADI", "Advantage", "APD", "ENS", "Lonestar",
         "Mountain West", "SDS", "SDI", "SES", "SS&SI", "Wesco", "Custom"]
    )

    uploaded_logo = None
    custom_logo_url = ""

    if partner == "Custom":
        st.markdown("**Custom Logo (required)**")
        uploaded_logo = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"])
        custom_logo_url = st.text_input("or Logo URL")

    location = st.text_input("Location / Name", "SES - Detroit")

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        address1 = st.text_input("Address Line 1", "25181 Dequindre Rd")
    with col_a2:
        address2 = st.text_input("Address Line 2", "Madison Heights, MI 48071")

    col_d, col_t = st.columns(2)
    with col_d:
        date = st.text_input("Date", "Tuesday, May 12th")
    with col_t:
        time = st.text_input("Time", "10:00 AM - 3:00 PM")

    registration_link = st.text_input(
        "Registration Link",
        "https://forms.gle/27N37sA1TrrJAEwDA"
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        generate = st.button("Generate Flyer")

    with col_btn2:
        if st.button("Reset"):
            st.session_state.flyer_result = None
            st.rerun()

# -------------------------
# GENERATE
# -------------------------
if generate:

    if partner == "Custom" and not (uploaded_logo or custom_logo_url):
        st.error("Please upload a logo or provide a URL for custom partners.")
        st.stop()

    data = {
        "location": location,
        "address1": address1,
        "address2": address2,
        "date": date,
        "time": time,
        "partner": partner,
        "uploaded_logo": uploaded_logo,
        "custom_logo_url": custom_logo_url,
        "registration_link": registration_link,
    }

    with st.spinner("Generating flyer..."):
        result, error = generate_flyer(data)

    if error:
        st.error(error)
    else:
        st.session_state.flyer_result = result

# -------------------------
# PREVIEW (persistent)
# -------------------------
if st.session_state.flyer_result:

    with col_preview:
        st.subheader("Preview")

        st.download_button(
            "⬇️ Download",
            data=st.session_state.flyer_result,
            file_name="Final_Flyer.png",
            mime="image/png"
        )

        st.image(st.session_state.flyer_result, width=400)