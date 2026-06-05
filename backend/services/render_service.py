from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
import qrcode
import math

from models.template import (
    TemplateModel,
    TextElement,
    QRElement,
    ImageElement,
)
from utils.font_resolver import resolve_font_path


# =========================
# PATH CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
STATIC_DIR = BASE_DIR / "static"
BACKGROUNDS_DIR = STATIC_DIR / "backgrounds"


# =========================
# PUBLIC ENTRYPOINT
# =========================


def render_template(
    template: TemplateModel,
    data: Dict[str, Any]
) -> Image.Image:
    """
    Render a full-resolution image from a template and runtime data.
    """

    # For now, backgrounds are in the static folder
    # This will eventually be defined by the template structure
    # Handle both bare filenames and full/absolute paths
    bg_filename = Path(template.background).name
    background_path = BACKGROUNDS_DIR / bg_filename

    if not background_path.exists():
        raise FileNotFoundError(
            f"Background image not found: {background_path}"
        )

    bg = Image.open(background_path).convert("RGBA")

    # Always resize the background to the template's canvas dimensions.
    # The canvas dimensions are the authoritative output size (they encode
    # both the intended pixel count and implied DPI for print, e.g. 2480×3508
    # for A4 at 300 DPI). A background image that is smaller or larger than
    # the canvas must be stretched to fill it — element coordinates are stored
    # in canvas space, so scale factors are trivially 1.0 after this resize.
    if bg.size != (template.canvas.width, template.canvas.height):
        bg = bg.resize(
            (template.canvas.width, template.canvas.height),
            Image.Resampling.LANCZOS
        )

    scale_x = 1.0
    scale_y = 1.0

    img = bg
    draw = ImageDraw.Draw(img)

    for element in template.elements:

        if isinstance(element, TextElement):
            render_text_element(draw, element, data, scale_x, scale_y)

        elif isinstance(element, QRElement):
            render_qr_element(img, element, data, scale_x, scale_y)

        elif isinstance(element, ImageElement):
            render_image_element(img, element, data, scale_x, scale_y)

    return img


# =========================
# TEXT RENDERING
# =========================


def render_text_element(
    draw: ImageDraw.ImageDraw,
    element: TextElement,
    data: Dict[str, Any],
    scale_x: float,
    scale_y: float,
):

    value = str(data.get(element.field, ""))

    value = apply_text_transform(
        value,
        element.style.get("textTransform", "")
    )

    font_family = element.style.get("fontFamily", "Montserrat")
    bold = bool(element.style.get("bold", False))
    font_name = resolve_font_path(font_family, bold=bold)
    align = element.style.get("align", "left")

    # Base position (canvas coordinates scaled to output)
    base_x = round(element.x * scale_x)
    base_y = round(element.y * scale_y)

    # If there's no bounding box, render as before (single line at scaled font size)
    if element.bounding_box is None:
        font_size = round(element.style.get("size", 12) * scale_y)
        font = load_font(font_name, font_size)

        draw.text(
            (base_x, base_y),
            value,
            fill=element.style.get("color", "#000000"),
            font=font,
            align=align,
        )
        return

    # Bounding box is defined — scale it to output space
    bb_width = round(element.bounding_box["width"] * scale_x)
    bb_height = round(element.bounding_box["height"] * scale_y)

    overflow = element.overflow or "shrink-to-fit"

    if overflow == "shrink-to-fit":
        _render_shrink_to_fit(draw, value, font_name, element.style.get("color", "#000000"),
                              align, base_x, base_y, bb_width, bb_height, scale_y, element.style)
    elif overflow == "wrap":
        _render_wrap(draw, value, font_name, element.style.get("color", "#000000"),
                     align, base_x, base_y, bb_width, bb_height, scale_y, element.style)
    elif overflow == "truncate":
        _render_truncate(draw, value, font_name, element.style.get("color", "#000000"),
                         align, base_x, base_y, bb_width, bb_height, scale_y)
    else:
        # Fallback: single line at base font size
        font_size = round(element.style.get("size", 12) * scale_y)
        font = load_font(font_name, font_size)
        draw.text((base_x, base_y), value, fill=element.style.get("color", "#000000"), font=font, align=align)


def _measure_text_size(font: ImageFont.FreeTypeFont, text: str) -> Tuple[int, int]:
    """Measure the rendered width and height of a single line of text."""
    bbox = font.getbbox(text)
    if bbox:
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return 0, 0


def _multiline_text_height(font: ImageFont.FreeTypeFont, lines: int) -> int:
    """Approximate height of multiple lines of text."""
    _, line_height = _measure_text_size(font, "Ag")
    return line_height * lines + (lines - 1) * 2  # 2px leading


def _render_shrink_to_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    color: str,
    align: str,
    x: int,
    y: int,
    bb_width: int,
    bb_height: int,
    scale_y: float,
    style: Dict[str, Any],
):
    """Reduce font size until text fits without exceeding the configured size."""
    configured_font_size = round(style.get("size", 12) * scale_y)
    max_font_size = max(1, configured_font_size)
    min_font_size = 6

    best_font_size = min_font_size
    best_font = load_font(font_name, best_font_size)

    for size in range(max_font_size, min_font_size - 1, -1):
        font = load_font(font_name, size)
        text_w, text_h = _measure_text_size(font, text)

        if text_w <= bb_width and text_h <= bb_height:
            best_font_size = size
            best_font = font
            break

    draw.text((x, y), text, fill=color, font=best_font, align=align)


def _render_wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    color: str,
    align: str,
    x: int,
    y: int,
    bb_width: int,
    bb_height: int,
    scale_y: float,
    style: Dict[str, Any],
):
    """Wrap text to fit the bounding box at the configured font size."""
    font_size = round(style.get("size", 12) * scale_y)
    font = load_font(font_name, font_size)

    wrapped_lines = _wrap_text(text, font, bb_width)

    # If even wrapped text doesn't fit vertically, shrink font size
    total_height = sum(_measure_text_size(font, line)[1] for line in wrapped_lines) + max(0, len(wrapped_lines) - 1) * 2
    if total_height > bb_height:
        # Shrink until it fits
        max_size = font_size
        for try_size in range(max_size, 5, -1):
            try_font = load_font(font_name, try_size)
            try_lines = _wrap_text(text, try_font, bb_width)
            try_height = sum(_measure_text_size(try_font, ln)[1] for ln in try_lines) + max(0, len(try_lines) - 1) * 2
            if try_height <= bb_height:
                font = try_font
                wrapped_lines = try_lines
                break

    # Draw each line
    current_y = y
    for line in wrapped_lines:
        _, line_h = _measure_text_size(font, line)
        draw.text((x, current_y), line, fill=color, font=font, align=align)
        current_y += line_h + 2  # 2px leading


def _render_truncate(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    color: str,
    align: str,
    x: int,
    y: int,
    bb_width: int,
    bb_height: int,
    scale_y: float,
):
    """Truncate text with ellipsis to fit the bounding box."""
    font_size = round(36 * scale_y)  # reasonable render size
    font = load_font(font_name, font_size)

    # Check if it fits as-is
    text_w, text_h = _measure_text_size(font, text)
    if text_w <= bb_width and text_h <= bb_height:
        draw.text((x, y), text, fill=color, font=font, align=align)
        return

    # Gradually shorten text with ellipsis until it fits
    ellipsis = "…"
    for i in range(len(text), 0, -1):
        truncated = text[:i] + ellipsis
        tw, th = _measure_text_size(font, truncated)
        if tw <= bb_width and th <= bb_height:
            draw.text((x, y), truncated, fill=color, font=font, align=align)
            return

    # Last resort: just draw single character + ellipsis
    draw.text((x, y), text[:1] + ellipsis, fill=color, font=font, align=align)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap text into lines that fit within max_width pixels."""
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current_line = words[0]

    for word in words[1:]:
        test_line = current_line + " " + word
        tw, _ = _measure_text_size(font, test_line)
        if tw <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


# =========================
# IMAGE RENDERING
# =========================


def resolve_image_path(
    source_value: str,
    asset_type: Optional[str] = None
) -> Optional[Path]:
    """
    Resolve an image path from a source value and asset type.
    
    Examples:
    - resolve_image_path("SES", "logos") -> "assets/logos/ses.png"
    - resolve_image_path("/path/to/image.png") -> "/path/to/image.png"
    
    Args:
        source_value: The raw value (e.g., "SES", "my-photo.jpg", "/path/to/file.png")
        asset_type: Optional asset category (e.g., "logos", "photos")
    
    Returns:
        Path object if found, None otherwise
    """
    if not source_value:
        return None
    
    # If asset_type is specified, normalize the source value and look in assets folder
    if asset_type:
        # Normalize: "SES" -> "ses", "My Logo" -> "my-logo"
        normalized = source_value.lower().replace(" ", "-").replace("_", "-")
        
        # Try common image extensions
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            candidate = ASSETS_DIR / asset_type / f"{normalized}{ext}"
            if candidate.exists():
                return candidate
        
        return None
    
    # If no asset_type, treat source_value as a direct path
    image_path = Path(source_value)
    
    # Try as absolute/relative path first
    if image_path.exists():
        return image_path
    
    # Try relative to assets
    assets_path = ASSETS_DIR / source_value
    if assets_path.exists():
        return assets_path
    
    return None


def render_image_element(
    base_image: Image.Image,
    element: ImageElement,
    data: Dict[str, Any],
    scale_x: float,
    scale_y: float,
):
    """
    Render an image element into the template.
    
    Supports two modes:
    1. Direct image data: field value is a path string or PIL Image
    2. Mapped field + asset type: source_field maps to data, asset_type determines path resolution
    
    Example template element:
    {
        "type": "image",
        "field": "partner_logo",
        "sourceField": "partner",
        "assetType": "logos"
    }
    
    With data:
    {
        "partner": "SES"
    }
    
    Automatically resolves to: assets/logos/ses.png
    """
    # Determine the source value to use
    if element.source_field:
        # Use mapped field for data lookup
        source_value = data.get(element.source_field)
    else:
        # Use the element field directly
        source_value = data.get(element.field)
    
    if not source_value:
        # No image provided, skip rendering
        return
    
    # Try to resolve image path
    image_obj = None
    
    if isinstance(source_value, str):
        # Resolve path using asset_type if provided
        image_path = resolve_image_path(source_value, element.asset_type)
        
        if image_path:
            try:
                image_obj = Image.open(image_path).convert("RGBA")
            except Exception:
                return
        else:
            return
    elif isinstance(source_value, Image.Image):
        image_obj = source_value.convert("RGBA")
    else:
        return
    
    if not image_obj:
        return
    
    img = image_obj
    
    # Get the bounding box and scale it to output space
    bb = element.bounding_box or {"width": 200, "height": 200}
    bb_width = round(bb["width"] * scale_x)
    bb_height = round(bb["height"] * scale_y)
    
    # Calculate scaled image dimensions maintaining aspect ratio
    img_width, img_height = img.size
    maintain_ar = element.maintain_aspect_ratio
    
    if maintain_ar:
        # Calculate scale factor to fit within bounding box while maintaining aspect ratio
        scale_factor = min(bb_width / img_width, bb_height / img_height)
        new_width = round(img_width * scale_factor)
        new_height = round(img_height * scale_factor)
    else:
        # Stretch to fill bounding box
        new_width = bb_width
        new_height = bb_height
    
    # Resize the image
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Calculate position (top-left of bounding box, or centered if smaller)
    base_x = round(element.x * scale_x)
    base_y = round(element.y * scale_y)
    
    # Paste the image onto the base image
    base_image.paste(
        img,
        (base_x, base_y),
        img
    )


# =========================
# QR RENDERING
# =========================


def render_qr_element(
    base_image: Image.Image,
    element: QRElement,
    data: Dict[str, Any],
    scale_x: float,
    scale_y: float,
):
    qr_value = str(data.get(element.field, ""))

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=1,
    )

    qr.add_data(qr_value)
    qr.make(fit=True)

    qr_img = qr.make_image(
        fill_color="black",
        back_color="white"
    ).convert("RGBA")

    uniform_scale = scale_x
    qr_size = round(element.size * uniform_scale)

    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    # Center vertically within the space scale_y would have allocated
    y_allocated = round(element.size * scale_y)
    y_offset = (y_allocated - qr_size) // 2

    base_image.paste(
        qr_img,
        (round(element.x * scale_x), round(element.y * scale_y) + y_offset),
        qr_img
    )


# =========================
# FONT LOADING
# =========================


def load_font(font_name: str, size: int):
    p = Path(font_name)
    font_path = p if p.is_absolute() else FONTS_DIR / font_name

    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    return ImageFont.truetype(str(font_path), size)


# =========================
# TEXT TRANSFORMS
# =========================


def apply_text_transform(
    value: str,
    transform: str
) -> str:

    if transform == "upper":
        return value.upper()

    if transform == "lower":
        return value.lower()

    if transform == "title":
        return value.title()
    
    if transform == "sentence":
        return value.capitalize()

    return value