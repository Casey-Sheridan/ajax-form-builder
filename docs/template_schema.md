# Template Schema Specification (Draft v1)

## Purpose

This document defines the canonical template schema used by the flyer generation platform.

The schema acts as the shared contract between:

- Frontend editor (React/Konva)
- Backend API (FastAPI)
- Render engine (Pillow)
- Database storage
- Export pipeline

The goal is to stabilize:
- template structure
- coordinate systems
- rendering semantics
- element definitions

while allowing flexible event/business data fields.

---

# Core Design Principles

## 1. Templates are data-driven

Templates define layout and rendering behavior only.

Runtime event data is injected separately.

Templates should not contain event-specific values.

---

## 2. Frontend and backend share the same schema

The frontend editor manipulates template JSON directly.

The backend renderer consumes the same JSON without transformation.

---

## 3. Coordinate system is absolute and deterministic

All element positions use:

- top-left origin
- integer pixel coordinates
- fixed canvas dimensions

Coordinates are stored relative to the full-resolution render canvas.

---

## 4. Rendering is backend-authoritative

The frontend editor is only a visual editing interface.

Final rendering behavior is determined exclusively by the backend render engine.

---

# Top-Level Template Schema

```json
{
  "schema_version": 1,

  "id": "event_flyer",

  "title": "Event Flyer",

  "canvas": {
    "width": 1080,
    "height": 1350
  },

  "background": "templates/event_flyer/background.png",

  "elements": []
}
```

---

# Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| schema_version | integer | yes | Template schema version |
| id | string | yes | Unique template identifier |
| title | string | yes | Human-readable template name |
| canvas | object | yes | Defines render coordinate space |
| background | string | yes | Relative path to background asset |
| elements | array | yes | List of renderable elements |

---

# Canvas Schema

```json
{
  "width": 1080,
  "height": 1350
}
```

## Rules

- Coordinates are absolute pixels
- Origin is top-left
- Width and height represent full-resolution export dimensions
- Frontend display scaling must preserve aspect ratio
- Backend rendering always uses full-resolution coordinates

---

# Element Schema

All elements share a common base structure.

## Common Element Fields

```json
{
  "id": "uuid",
  "type": "text",
  "field": "address",
  "label": "Address",
  "x": 420,
  "y": 860
}
```

---

# Common Element Properties

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | yes | Stable unique element identifier |
| type | string | yes | Element renderer type |
| field | string | yes | Runtime data binding key |
| label | string | yes | Human-readable field name |
| x | integer | yes | X coordinate |
| y | integer | yes | Y coordinate |

---

# Supported Element Types (v1)

| Type | Description |
|---|---|
| text | Renders text from runtime data |
| qr | Renders QR code from runtime data |
| image | Reserved for future support |

---

# Text Element Schema

```json
{
  "id": "uuid",
  "type": "text",
  "field": "address",

  "x": 420,
  "y": 860,

  "style": {
    "font": "Montserrat-Bold",
    "size": 42,
    "color": "#FFFFFF",
    "align": "center",
    "textTransform": "upper"
  }
}
```

---

# Text Style Properties

| Field | Type | Required | Description |
|---|---|---|---|
| font | string | yes | Registered font identifier |
| size | integer | yes | Font size in pixels |
| color | string | yes | Hex color value |
| align | string | no | Text alignment |
| textTransform | string | no | Text transform (upper, lower, sentence, title, normal) |

---

# QR Element Schema

```json
{
  "id": "uuid2",

  "type": "qr",

  "field": "registration_link",

  "x": 900,
  "y": 700,

  "size": 180
}
```

---

# QR Properties

| Field | Type | Required | Description |
|---|---|---|---|
| size | integer | yes | Width/height of QR code in pixels |

---

# Runtime Data Injection

Templates do not store event content.

Runtime event data is injected during rendering.

Example runtime payload:

```json
{
  "title": "Product Showcase and Training",
  "location": "Ajax Brewing",
  "date": "May 9, 2026",
  "time": "7:00 PM",
  "address": "123 Main St",
  "registration_link": "https://example.com/register"
}
```

---

# Rendering Rules

## Text Rendering

- Renderer resolves `field`
- Runtime value is rendered as text
- Missing fields render as empty string unless configured otherwise

---

## QR Rendering

- Renderer resolves `field`
- Runtime value becomes QR payload
- QR generation handled exclusively by backend

---

# Asset Rules

## Background Assets

- Stored as relative paths only
- No absolute machine-specific paths
- Assets should reside within managed template asset directories

Example:

```json
{
  "background": "templates/event_flyer/background.png"
}
```

---

# Coordinate Rules

## Canonical Coordinate Space

The canonical coordinate space is the full-resolution render canvas.

Frontend scaling must not alter stored coordinates.

Example:

- Canvas width: 1080
- Frontend preview width: 540

A stored coordinate of:

```json
{
  "x": 540
}
```

always represents the center of the full-resolution canvas.

---

# Reserved Future Expansion Areas

The following areas are intentionally reserved for future support:

- rotation
- opacity
- layer ordering
- grouping
- image elements
- multiline text
- wrapping
- rich text
- gradients
- shadows
- snapping metadata
- animation metadata

---

# Schema Evolution Rules

## Backward Compatibility

New schema versions should preserve compatibility whenever possible.

Breaking changes require:
- schema version increment
- migration strategy
- renderer compatibility review

---

# Validation Rules

Backend validation should reject:

- missing required fields
- unknown element types
- invalid coordinates
- invalid asset references
- malformed style definitions

---

# Recommended Backend Model Strategy

Backend should use typed models (Pydantic) to enforce schema consistency.

Example:

```python
class Element(BaseModel):
    id: str
    type: Literal["text", "qr"]
    field: str
    x: int
    y: int
```

---

# Current Status

This document represents:
- initial schema freeze draft
- baseline implementation target
- API contract foundation

This specification is expected to evolve during frontend and API development.