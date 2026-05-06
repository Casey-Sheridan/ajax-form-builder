import streamlit as st
st.set_page_config(page_title="Flyer Generator", layout="wide")

import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
import json
from io import BytesIO
from datetime import date

# -------------------------
# LOAD ENV (safe placement)
# -------------------------
load_dotenv(override=True)

import auth
user = auth.require_login()

# -------------------------
# SIDEBAR USER PANEL
# -------------------------
st.sidebar.markdown("### 👤 User")

st.sidebar.image(user["picture"], width=50)
st.sidebar.markdown(f"**{user['name']}**")
st.sidebar.caption(user["email"])

st.sidebar.success("Authenticated")
st.sidebar.divider()

auth.logout_button()

# -------------------------
# CONFIG
# -------------------------

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_PATH = os.path.join(BASE_DIR, "master_template.png")
LOGO_DIR = os.path.join(BASE_DIR, "logos")
FONT_DIR = os.path.join(BASE_DIR, "fonts")
PARTNERS_FILE = os.path.join(BASE_DIR, "partners.txt")

# -------------------------
# TEMPLATES
# -------------------------


TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

@st.cache_data
def load_template(name="default.json"):
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path, "r") as f:
        return json.load(f)

template = load_template()

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
        "subtitle": ImageFont.truetype(os.path.join(FONT_DIR, "Orbitron-Regular.ttf"), 62),
        "title": ImageFont.truetype(os.path.join(FONT_DIR, "Orbitron-Bold.ttf"), 72)
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
        if len(p) >= 3 and any(chunk in text for chunk in [p.lower()[:3], p.lower()[:4]]):
            return p

    return None

# -------------------------
# GENERATOR
# -------------------------
def generate_flyer(data, template):
    try:
        bg_path = os.path.join(BASE_DIR, template["background"])
        img = Image.open(bg_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        colors = {
            "white": (255, 255, 255),
            "gray": (180, 180, 180)
        }

        # -------------------------
        # RENDER ELEMENTS
        # -------------------------
        for el in template["elements"]:

            if el["type"] == "text":
                value = el.get("value") or data.get(el.get("source", ""), "")
                draw.text(
                    (el["x"], el["y"]),
                    value,
                    font=fonts[el["font"]],
                    fill=colors[el["color"]]
                )

            elif el["type"] == "logo":
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
                    logo_img.thumbnail((el["max_width"], el["max_height"]))
                    img.paste(
                        logo_img,
                        (el["x"], el["y"] - logo_img.height // 2),
                        logo_img
                    )

            elif el["type"] == "qr":
                link = data.get(el["source"], "")

                if not link:
                    raise ValueError("Registration link is required.")

                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_Q,
                    box_size=10,
                    border=1
                )

                qr.add_data(link)
                qr.make(fit=True)

                qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                qr_img = qr_img.resize((el["size"], el["size"]))

                img.paste(
                    qr_img,
                    (el["x"] - qr_img.width // 2, el["y"] - qr_img.height // 2)
                )

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
    times = []

    for hour in range(6, 23):  # include 10 PM
        for minute in [0, 30]:
            if hour == 22 and minute == 30:
                continue
            suffix = "AM" if hour < 12 else "PM"
            display_hour = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
            times.append(f"{display_hour}:{minute:02d} {suffix}")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.selectbox("Start Time", times, index=8)
    with col_t2:
        end_time = st.selectbox("End Time", times, index=16)

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
if "generate" in locals() and generate:

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
        result, error = generate_flyer(data, template)

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