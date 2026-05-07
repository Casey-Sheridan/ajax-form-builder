import streamlit as st
st.set_page_config(page_title="Flyer Generator", layout="wide")

import os
import json
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
from io import BytesIO
from datetime import date
from db import fetch_all, create_template, get_templates

# -------------------------
# LOAD ENV
# -------------------------
load_dotenv(override=True)

import auth
from auth import is_admin
user = auth.require_login()

# -------------------------
# SIDEBAR USER PANEL
# -------------------------
is_admin_flag = user.get("is_admin", 0) == 1
admin_tag = " (Admin)" if is_admin_flag else ""
st.sidebar.markdown(f"### 👤 User{admin_tag}")
st.sidebar.image(user.get("picture_url", "https://via.placeholder.com/40"), width=50)
st.sidebar.markdown(f"**{user.get('name', '')}**")
st.sidebar.caption(user.get("email", ""))
st.sidebar.divider()
auth.logout_button()

# =========================================================
# ADMIN TEMPLATE DESIGNER (STABLE v1)
# =========================================================
if is_admin(user):

    st.sidebar.markdown("## 🎨 Template Designer")

    # -------------------------
    # INIT STATE (NEVER RESET)
    # -------------------------
    if "layout_builder" not in st.session_state:
        st.session_state.layout_builder = {
            "background": None,
            "elements": []
        }

    layout = st.session_state.layout_builder

    # =========================
    # TWO-COLUMN SIDEBAR LAYOUT
    # =========================
    col_left, col_right = st.sidebar.columns(2)

    # -------------------------
    # LEFT: CONTROLS
    # -------------------------
    with col_left:

        st.markdown("### Controls")

        bg_file = st.file_uploader(
            "Background",
            type=["png", "jpg", "jpeg"],
            key="tpl_bg"
        )

        if bg_file is not None:
            layout["background"] = bg_file.name
            st.session_state["tpl_bg_file"] = bg_file

        field = st.selectbox(
            "Field",
            ["location", "date", "time", "address", "registration_link"],
            key="tpl_field"
        )

        x = st.number_input("X", value=100, key="tpl_x")
        y = st.number_input("Y", value=100, key="tpl_y")

        if st.button("Add Element", key="tpl_add"):

            layout["elements"].append({
                "type": "text",
                "field": field,
                "x": int(x),
                "y": int(y),
                "font": "bold",
                "size": 35,
                "color": "white"
            })

            st.rerun()

        if st.button("Save Template", key="tpl_save"):

            import json
            create_template(
                name=f"template_{len(layout['elements'])}",
                layout_json=json.dumps(layout),
                created_by=user["email"]
            )

            st.success("Template saved")

    # -------------------------
    # RIGHT: PREVIEW (STABLE)
    # -------------------------
    with col_right:

        st.markdown("### Preview")

        if layout["background"]:

            bg_file = st.session_state.get("tpl_bg_file")

            if bg_file:
                from PIL import Image, ImageDraw

                img = Image.open(bg_file).convert("RGB")
                draw = ImageDraw.Draw(img)

                for el in layout["elements"]:
                    draw.text(
                        (el["x"], el["y"]),
                        el["field"],
                        fill="white"
                    )

                st.image(img, width=250)

        else:
            st.info("Upload a background to start preview")

    # -------------------------
    # DEBUG (OPTIONAL)
    # -------------------------
    with st.sidebar.expander("Debug Layout"):
        st.json(layout)

# =========================================================
# TEMPLATE BUILDER (STEP 7)
# =========================================================
if is_admin(user):

    st.sidebar.markdown("## 🧩 Templates")

    with st.sidebar.expander("Create Template"):

        tpl_name = st.text_input("Template Name")

        layout_text = st.text_area(
            "Layout JSON",
            value='{"fields": [{"type": "text", "label": "Field 1"}]}',
            height=160
        )

        if st.button("Save Template"):

            try:
                import json
                parsed = json.loads(layout_text)

                create_template(
                    tpl_name,
                    json.dumps(parsed),
                    user["email"]
                )

                st.success("Template saved")
                st.rerun()

            except Exception as e:
                st.error(f"Invalid JSON: {e}")

    with st.sidebar.expander("View Templates"):

        templates = get_templates()

        for t in templates:
            st.markdown(f"### {t['name']}")
            st.caption(t.get("created_by", "unknown"))
            st.code(t["layout_json"], language="json")

# -------------------------
# CONFIG
# -------------------------
BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
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
# TEMPLATE LOADING
# -------------------------
@st.cache_data
def list_templates():
    templates = []

    for d in os.listdir(TEMPLATE_DIR):
        path = os.path.join(TEMPLATE_DIR, d)

        if (
            not d.startswith(".")
            and os.path.isdir(path)
            and os.path.exists(os.path.join(path, "template.json"))
        ):
            templates.append(d)

    templates.sort()
    return templates


@st.cache_data
def load_template(name):
    template_path = os.path.join(TEMPLATE_DIR, name, "template.json")

    with open(template_path, "r") as f:
        template = json.load(f)

    template["_base_path"] = os.path.join(TEMPLATE_DIR, name)
    return template

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
def generate_flyer(data, template):
    try:
        bg_path = os.path.join(template["_base_path"], template["background"])
        img = Image.open(bg_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        colors = {
            "white": (255, 255, 255),
            "gray": (180, 180, 180)
        }

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

from db import get_templates
from template_engine import render_template
import json

with col_form:
    templates = get_templates()

    selected_template = st.selectbox(
        "Template (optional)",
        ["Default"] + [t["name"] for t in templates]
    )

    st.session_state["selected_template"] = selected_template

    active_template = None

    if selected_template != "Default":
        active_template = next(
            (t for t in templates if t["name"] == selected_template),
            None
        )

    if active_template:

        st.subheader("Template Mode")

        try:
            layout = json.loads(active_template["layout_json"])
            form_data = render_template(layout)

            st.session_state["template_data"] = form_data

        except Exception as e:
            st.error(f"Template error: {e}")

    else:
        st.info("Using default manual form")

    location = st.text_input("Location Name")
    guessed = fuzzy_match_partner(location, partners)

    if guessed:
        st.caption(f"Suggested partner: {guessed}")

    full_address = st.text_input("Full Address")
    address1, address2 = split_address(full_address)

    selected_date = st.date_input("Date", value=date.today())
    prettydate = format_pretty_date(selected_date)

    times = []
    for hour in range(6, 23):
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

    if "template_data" in st.session_state:
        tpl_data = st.session_state["template_data"]

        data = {
            "location": tpl_data.get("location", location),
            "address1": address1,
            "address2": address2,
            "date": prettydate,
            "time": time_range,
            "partner": partner,
            "uploaded_logo": uploaded_logo,
            "custom_logo_url": custom_logo_url,
            "registration_link": registration_link,
        }

    else:
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
        from layout_renderer import render_flyer_from_layout
        import json

        templates = get_templates()

        active = None
        if st.session_state.get("selected_template"):

            active = next(
                (t for t in templates if t["name"] == st.session_state["selected_template"]),
                None
            )

        if active:
            layout = json.loads(active["layout_json"])

            img = render_flyer_from_layout(layout, data, fonts)

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            result = buffer
            error = None

        else:
            result, error = generate_flyer(data)

    if error:
        st.error(error)
    else:
        st.session_state.flyer_result = result

# -------------------------
# PREVIEW (Overlay Button)
# -------------------------
if st.session_state.flyer_result:

    with col_preview:

        st.markdown("""
        <style>
        .image-container {
            position: relative;
            display: inline-block;
        }

        .download-overlay {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.2s ease-in-out;
        }

        .image-container:hover .download-overlay {
            opacity: 1;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("### Preview")

        st.markdown('<div class="image-container">', unsafe_allow_html=True)

        st.markdown('<div class="download-overlay">', unsafe_allow_html=True)
        st.download_button(
            "⬇ Download",
            data=st.session_state.flyer_result,
            file_name="Final_Flyer.png",
            mime="image/png",
            key="overlay_download"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.image(st.session_state.flyer_result, width=400)

        st.markdown('</div>', unsafe_allow_html=True)