import streamlit as st
import auth
import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
from io import BytesIO
from datetime import date

# -------------------------
# LOAD ENV (safe placement)
# -------------------------
load_dotenv(override=True)

# -------------------------
# AUTH
# -------------------------
user = auth.require_login()

# -------------------------
# SIDEBAR USER PANEL
# -------------------------
st.sidebar.image(user["picture"], width=60)
st.sidebar.write(user["name"])
st.sidebar.caption(user["email"])

auth.logout_button()

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

partners = load_partners()

# -------------------------
# HELPERS
# -------------------------
def ordinal(n):
    return "%d%s" % (n, "tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])


def format_pretty_date(d):
    return d.strftime(f"%A, %B {ordinal(d.day)}")


def split_address(addr):
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) >= 2:
        return parts[0], ", ".join(parts[1:])
    return addr, ""


def fuzzy_match_partner(text, partner_list):
    text = text.lower()

    for p in partner_list:
        if p.lower() in text:
            return p

    for p in partner_list:
        if len(p) >= 3 and p.lower()[:3] in text:
            return p

    return None

# -------------------------
# GENERATOR
# -------------------------
def generate_flyer(data):
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

        except:
            pass

        if logo_img:
            logo_img.thumbnail((350, 75))
            img.paste(logo_img, (280, 1450 - logo_img.height // 2), logo_img)

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
        qr_img = qr_img.resize((140, 140))

        img.paste(qr_img, (qx - qr_img.width // 2, qy - qr_img.height // 2))

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer, None

    except Exception as e:
        return None, str(e)

# -------------------------
# UI
# -------------------------
st.title("AJAX Training Flyer Generator")

col_form, col_preview = st.columns([1, 1])

with col_form:

    location = st.text_input("Location Name")

    guessed = fuzzy_match_partner(location, partners)

    if guessed:
        st.caption(f"Suggested partner: {guessed}")

    full_address = st.text_input("Full Address")

    address1, address2 = split_address(full_address)

    selected_date = st.date_input("Date", value=date.today())
    prettydate = format_pretty_date(selected_date)

    # TIME PICKERS
    times = [f"{h}:{m:02d} {'AM' if h < 12 else 'PM'}"
             for h in range(1, 13)
             for m in [0, 15, 30, 45]]

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.selectbox("Start Time", times, index=4)
    with col_t2:
        end_time = st.selectbox("End Time", times, index=8)

    time_range = f"{start_time} - {end_time}"

    registration_link = st.text_input("Registration Link")

    partner = st.selectbox(
        "Partner",
        partners,
        index=partners.index(guessed) if guessed in partners else 0
    )

    uploaded_logo = None
    custom_logo_url = ""

    if partner == "Custom":
        uploaded_logo = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"])
        custom_logo_url = st.text_input("Logo URL")

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
        st.error("Custom partner requires a logo.")
        st.stop()

    data = {
        "location": location,
        "address1": address1,
        "address2": address2,
        "date": prettydate,
        "time": time_range,
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
        st.markdown("### Preview")

        st.download_button(
            "Download",
            data=st.session_state.flyer_result,
            file_name="Final_Flyer.png",
            mime="image/png"
        )

        st.image(st.session_state.flyer_result, width=400)