import base64

import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import os
import traceback
import difflib
from datetime import time as dtime

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Flyer Generator", layout="wide")

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_PATH = os.path.join(BASE_DIR, "master_template.png")
LOGO_DIR = os.path.join(BASE_DIR, "logos")
FONT_DIR = os.path.join(BASE_DIR, "fonts")
PARTNERS_FILE = os.path.join(BASE_DIR, "partners.txt")

# -------------------------
# SESSION STATE
# -------------------------
if "flyer_result" not in st.session_state:
    st.session_state.flyer_result = None

if "partner" not in st.session_state:
    st.session_state.partner = None

if "partner_locked" not in st.session_state:
    st.session_state.partner_locked = False

# -------------------------
# LOAD FONTS
# -------------------------
@st.cache_resource
def load_fonts():
    return {
        "bold": ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Bold.ttf"), 35),
        "regular": ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Regular.ttf"), 30),
    }

fonts = load_fonts()

# -------------------------
# LOAD PARTNERS
# -------------------------
@st.cache_data
def load_partners():
    if not os.path.exists(PARTNERS_FILE):
        return ["Custom"]

    with open(PARTNERS_FILE, "r") as f:
        partners = [line.strip() for line in f if line.strip()]

    return partners + ["Custom"]

# -------------------------
# HELPERS
# -------------------------
def ordinal(n):
    return "%d%s" % (n, "tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])

def split_address(full_address):
    if not full_address:
        return "", ""

    parts = [p.strip() for p in full_address.split(",") if p.strip()]

    if len(parts) >= 3:
        return parts[0], ", ".join(parts[1:])

    if len(parts) == 2:
        return parts[0], parts[1]

    tokens = full_address.strip().split()

    if len(tokens) > 4:
        return " ".join(tokens[:-3]), " ".join(tokens[-3:])

    return full_address, ""

def guess_partner(location, partners):
    location_lower = location.lower()

    # Token match
    for p in partners:
        tokens = p.lower().replace("&", "").split()
        if all(token in location_lower for token in tokens):
            return p

    # Prefix match
    for word in location_lower.split():
        if len(word) < 3:
            continue
        for p in partners:
            if p.lower().replace("&", "").startswith(word):
                return p

    # Fuzzy match
    matches = difflib.get_close_matches(
        location_lower,
        [p.lower() for p in partners],
        n=1,
        cutoff=0.6
    )

    if matches:
        for p in partners:
            if p.lower() == matches[0]:
                return p

    return None

def handle_location_change():
    st.session_state.partner_locked = False

def snap_to_15(t):
    minutes = (t.minute // 15) * 15
    return t.replace(minute=minutes, second=0, microsecond=0)

def format_time_range(start, end):
    def fmt(t):
        return t.strftime("%I:%M %p").lstrip("0")
    return f"{fmt(start)} - {fmt(end)}"

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
        qx, qy = 887, 1381

        draw.text((tx, ty), data["date"], font=fonts["bold"], fill=white)
        draw.text((tx, ty + 50), data["time"], font=fonts["regular"], fill=gray)
        draw.text((tx, ty + 110), data["location"], font=fonts["bold"], fill=white)
        draw.text((tx, ty + 160), data["address1"], font=fonts["regular"], fill=white)
        draw.text((tx, ty + 200), data["address2"], font=fonts["regular"], fill=white)

        # LOGO
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
            logo_img.thumbnail((350, 75), Image.Resampling.LANCZOS)
            img.paste(logo_img, (280, round(1450 - (logo_img.height / 2))), logo_img)

        # QR
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

        img.paste(qr_img, (qx - qr_img.width // 2, qy - qr_img.height // 2))

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer, None

    except Exception as e:
        return None, "Error generating flyer:\n" + str(e) + "\n" + traceback.format_exc()

# -------------------------
# STYLE
# -------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem;
}

/* Preview layout */
.preview-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: -0.5rem;
}

/* REAL button styling */
.download-link {
    text-decoration: none !important;
    background-color: #f0f2f6 !important;
    color: black !important;
    padding: 3px 9px;
    font-size: 0.75rem;
    border-radius: 6px;
    border: 1px solid #ccc;
}

.download-link:hover {
    background-color: #e0e2e6;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# UI
# -------------------------
st.title("AJAX Training Flyer Generator")

col_form, col_preview = st.columns([1, 1])

with col_form:

    location = st.text_input("Location Name", "", key="location_input", on_change=handle_location_change)

    partner_list = load_partners()
    guessed = guess_partner(location, partner_list)

    if guessed and not st.session_state.partner_locked:
        st.session_state.partner = guessed

    if guessed:
        st.caption(f"Auto-detected partner: {guessed}")

    full_address = st.text_input("Address", "")

    if full_address:
        a1, a2 = split_address(full_address)
        st.caption(f"Parsed as: {a1} | {a2}")

    col_d, col_t = st.columns(2)

    with col_d:
        date = st.date_input("Date")
        prettydate = f"{date.strftime('%A, %B')} {ordinal(date.day)}"

    with col_t:
        start_time = snap_to_15(st.time_input("Start Time", value=dtime(10, 0)))
        end_time = snap_to_15(st.time_input("End Time", value=dtime(15, 0)))

        if end_time <= start_time:
            st.error("End time must be after start time.")
        else:
            st.caption(f"Time: {format_time_range(start_time, end_time)}")

    registration_link = st.text_input("Registration Link", "")

    partner = st.selectbox(
        "Partner",
        partner_list,
        index=partner_list.index(st.session_state.partner)
        if st.session_state.partner in partner_list else 0
    )

    if guessed and partner != guessed:
        st.session_state.partner_locked = True

    st.session_state.partner = partner

    uploaded_logo = None
    custom_logo_url = ""

    if partner == "Custom":
        st.markdown("**Custom Logo (required)**")
        uploaded_logo = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"])
        custom_logo_url = st.text_input("or Logo URL")

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        generate = st.button("Generate Flyer")

    with col_btn2:
        if st.button("Reset"):
            st.session_state.flyer_result = None
            st.session_state.partner_locked = False
            st.rerun()

# -------------------------
# GENERATE
# -------------------------
if generate:

    if end_time <= start_time:
        st.error("Fix time range before generating.")
        st.stop()

    if partner == "Custom" and not (uploaded_logo or custom_logo_url):
        st.error("Please upload a logo or provide a URL for custom partners.")
        st.stop()

    addr1, addr2 = split_address(full_address)

    data = {
        "location": location,
        "address1": addr1,
        "address2": addr2,
        "date": prettydate,
        "time": format_time_range(start_time, end_time),
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
# PREVIEW
# -------------------------
if st.session_state.flyer_result:

    with col_preview:

        img = Image.open(st.session_state.flyer_result)

        max_height = 650
        ratio = img.width / img.height
        display_height = min(max_height, img.height)
        display_width = int(display_height * ratio)

        # Center the preview area
        left_pad, center_col, right_pad = st.columns([1, 3, 1])

        with center_col:

            # Header (aligned to preview width)
            col_title, col_btn = st.columns([2.5, 1.2])

            with col_title:
                st.markdown("**Preview**")

            with col_btn:
                st.download_button(
                    "Download",
                    data=st.session_state.flyer_result,
                    file_name="Final_Flyer.png",
                    mime="image/png",
                    use_container_width=True  # keeps it tight
                )

            # Image (scaled, no scroll)
            st.image(img, width=display_width)