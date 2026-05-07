import streamlit as st
from datetime import date

# =========================================================
# FIELD RENDERER
# =========================================================
def render_field(field):

    ftype = field.get("type")
    label = field.get("label", "Field")

    if ftype == "text":
        return st.text_input(label)

    if ftype == "date":
        return st.date_input(label, value=date.today())

    if ftype == "textarea":
        return st.text_area(label)

    if ftype == "number":
        return st.number_input(label)

    if ftype == "time_range":
        times = []

        for hour in range(6, 22):
            for minute in [0, 30]:
                suffix = "AM" if hour < 12 else "PM"
                display_hour = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
                times.append(f"{display_hour}:{minute:02d} {suffix}")

        col1, col2 = st.columns(2)
        with col1:
            start = st.selectbox(f"{label} (Start)", times, key=f"{label}_start")
        with col2:
            end = st.selectbox(f"{label} (End)", times, key=f"{label}_end")

        return f"{start} - {end}"

    return st.text_input(label)


# =========================================================
# TEMPLATE RENDERER
# =========================================================
def render_template(layout_json):

    data = {}

    fields = layout_json.get("fields", [])

    for field in fields:
        key = field.get("label", "field").lower().replace(" ", "_")
        data[key] = render_field(field)

    return data