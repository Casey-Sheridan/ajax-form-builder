from pydantic import BaseModel, Field, field_validator, Discriminator
from typing import List, Union, Dict, Any, Literal, Annotated, Optional

FieldType = Literal["text", "date", "time", "timeRange", "address", "url", "select", "image"]
DateFormat = Literal["long", "long_no_year", "medium", "short", "numeric", "iso"]
DerivationStrategy = Literal["asset-lookup", "fuzzy-catalog", "format"]


class FieldDerivationModel(BaseModel):
    strategy: DerivationStrategy
    source_field: str = Field(alias="sourceField")
    asset_type: Optional[str] = Field(default=None, alias="assetType")
    catalog: Optional[str] = None
    format_string: Optional[str] = Field(default=None, alias="format")

    model_config = {"populate_by_name": True}


class FieldDescriptor(BaseModel):
    key: str
    type: FieldType = "text"
    label: str
    required: bool = True
    date_format: Optional[DateFormat] = None
    placeholder: Optional[str] = None
    derivation: Optional[FieldDerivationModel] = None
    catalog: Optional[str] = None       # for type="select": names the catalog (org-scoped)
    allow_custom: bool = False           # adds a free-text "Custom" option to the dropdown

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_legacy_type(cls, v):
        # "partner" was the old name for a catalog-backed select field
        if v == "partner":
            return "select"
        return v


# ---------------------------
# ELEMENT MODELS
# ---------------------------

class BaseElement(BaseModel):
    id: str
    type: str
    x: int
    y: int

    @field_validator("x", "y", mode="before")
    @classmethod
    def coerce_int(cls, v):
        # prevents float values from canvas (Konva returns floats)
        return int(round(v)) if v is not None else 0


class TextElement(BaseElement):
    type: Literal["text"]
    field: str
    label: str
    style: Dict[str, Any] = Field(default_factory=dict)
    bounding_box: Optional[Dict[str, int]] = Field(
        default=None,
        alias="boundingBox",
        description="Optional bounding box {width, height} for text at render time"
    )
    overflow: str = Field(
        default="shrink-to-fit",
        description="Text overflow behavior: shrink-to-fit, wrap, or truncate"
    )

    @field_validator("style", mode="before")
    @classmethod
    def validate_style(cls, v):
        return v or {"size": 12, "color": "#000000"}

    @field_validator("overflow", mode="before")
    @classmethod
    def validate_overflow(cls, v):
        allowed = {"shrink-to-fit", "wrap", "truncate"}
        if v not in allowed:
            return "shrink-to-fit"
        return v

    @field_validator("bounding_box", mode="before")
    @classmethod
    def validate_bounding_box(cls, v):
        if v is None:
            return None
        if not isinstance(v, dict):
            return None
        width = v.get("width")
        height = v.get("height")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            return None
        return {"width": int(width), "height": int(height)}

    model_config = {"populate_by_name": True}


class QRElement(BaseElement):
    type: Literal["qr"]
    field: str
    label: str
    size: int


class ImageElement(BaseElement):
    type: Literal["image"]
    field: str
    label: str
    bounding_box: Dict[str, int] = Field(
        default_factory=lambda: {"width": 200, "height": 200},
        alias="boundingBox",
        description="Bounding box {width, height} that constrains the image"
    )
    maintain_aspect_ratio: bool = Field(
        default=True,
        alias="maintainAspectRatio",
        description="If true, image will scale to fit within bounding box while maintaining aspect ratio"
    )
    source_field: Optional[str] = Field(
        default=None,
        alias="sourceField",
        description="Map this field to a different data source field (e.g., 'partner_logo' field uses 'partner' data)"
    )
    asset_type: Optional[str] = Field(
        default=None,
        alias="assetType",
        description="Asset category for automatic path resolution (e.g., 'logos', 'photos')"
    )

    @field_validator("bounding_box", mode="before")
    @classmethod
    def validate_bounding_box(cls, v):
        if v is None:
            return {"width": 200, "height": 200}
        if not isinstance(v, dict):
            return {"width": 200, "height": 200}
        width = v.get("width", 200)
        height = v.get("height", 200)
        return {"width": int(width), "height": int(height)}

    model_config = {"populate_by_name": True}


# Discriminated union for element types
def get_element_type(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("type", "")
    return getattr(v, "type", "") if hasattr(v, "type") else ""

ElementModel = Annotated[
    Union[TextElement, QRElement, ImageElement],
    Field(discriminator="type")
]


# ---------------------------
# CANVAS MODEL
# ---------------------------

class CanvasModel(BaseModel):
    width: int
    height: int
    dpi: int = 72

    @field_validator("width", "height", mode="before")
    @classmethod
    def coerce_int(cls, v):
        # prevents "1080" string issues from DB/frontend
        return int(v) if v is not None else 0

    @field_validator("dpi", mode="before")
    @classmethod
    def coerce_dpi(cls, v):
        return int(v) if v is not None else 72


# ---------------------------
# TEMPLATE ROOT MODEL
# ---------------------------

class TemplateModel(BaseModel):
    id: str
    name: str
    canvas: CanvasModel
    background: str = ""
    elements: List[ElementModel] = Field(default_factory=list)
    fields: List[FieldDescriptor] = Field(default_factory=list)

    # ---------------------------
    # ELEMENT NORMALIZATION HOOK
    # ---------------------------
    @field_validator("elements", mode="before")
    @classmethod
    def normalize_elements(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("elements must be a list")
        return v

    # ---------------------------
    # CANVAS NORMALIZATION HOOK
    # ---------------------------
    @field_validator("canvas", mode="before")
    @classmethod
    def normalize_canvas(cls, v):
        if v is None:
            raise ValueError("canvas is required")
        return v