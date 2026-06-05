import json
import sqlite3
import uuid
from typing import List, Optional

from models.template import TemplateModel

DB_PATH = "templates.db"


# ---------------------------
# DB INIT
# ---------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                schema_version INTEGER NOT NULL DEFAULT 1,
                template_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Revisions table — one row per saved snapshot
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS template_revisions (
                id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                revision_json TEXT NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'interval',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_revisions_template_created
            ON template_revisions (template_id, created_at DESC)
            """
        )

        conn.commit()


# ---------------------------
# SAFE JSON LOADER
# ---------------------------
def _safe_json_load(value, fallback):
    try:
        if value is None:
            return fallback

        if isinstance(value, (dict, list)):
            return value

        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return fallback
            return json.loads(value)

        return fallback

    except Exception as e:
        print("JSON parse error:", e)
        print("Raw value:", value)
        return fallback


# ---------------------------
# NORMALIZE ROW → TEMPLATE (SINGLE SOURCE OF TRUTH)
# ---------------------------
def _row_to_template(row) -> TemplateModel:
    template_data = _safe_json_load(row["template_json"], {})
    canvas = _safe_json_load(template_data.get("canvas"), {"width": 1080, "height": 1350, "dpi": 72})
    elements = _safe_json_load(template_data.get("elements"), [])
    
    template_id = template_data.get("id")
    template_name = template_data.get("name")
    if not template_id or not template_name:
        raise ValueError(
            f"Corrupt template_json — missing 'id' or 'name'. "
            f"Keys found: {list(template_data.keys())}"
        )

    return TemplateModel.model_validate({
        "id": template_id,
        "name": template_name,
        "canvas": canvas,
        "background": template_data.get("background") or "",
        "elements": elements,
    })


# ---------------------------
# GET TEMPLATE
# ---------------------------
def get_template(template_id: str) -> Optional[TemplateModel]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM templates
            WHERE id = ?
            """,
            (template_id,)
        )

        row = cursor.fetchone()

        if not row:
            return None

        return _row_to_template(row)


# ---------------------------
# LIST TEMPLATES
# ---------------------------
def list_templates() -> List[TemplateModel]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM templates")
        rows = cursor.fetchall()

        return [_row_to_template(row) for row in rows]


# ---------------------------
# SAVE TEMPLATE
# ---------------------------
def save_template(template: TemplateModel):
    # Serialize the full template as a single JSON payload
    template_json = json.dumps({
        "id": template.id,
        "name": template.name,
        "canvas": template.canvas.model_dump(),
        "background": template.background,
        "elements": [
            e.model_dump() if hasattr(e, "model_dump") else e 
            for e in template.elements
        ],
    })

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO templates (id, name, schema_version, template_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                schema_version=excluded.schema_version,
                template_json=excluded.template_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                template.id,
                template.name,
                1,  # schema_version
                template_json,
            ),
        )

        conn.commit()


# ---------------------------
# DELETE TEMPLATE
# ---------------------------
def delete_template(template_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        conn.commit()


# ---------------------------
# SAVE REVISION
# Stores a full snapshot of the template at the time of the call.
# Automatically prunes the oldest entries so each template keeps at
# most `max_revisions` rows.
# ---------------------------
def save_revision(
    template_id: str,
    snapshot: dict,
    trigger: str = "interval",
    max_revisions: int = 50,
) -> str:
    revision_id = str(uuid.uuid4())
    revision_json = json.dumps(snapshot)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO template_revisions (id, template_id, revision_json, trigger)
            VALUES (?, ?, ?, ?)
            """,
            (revision_id, template_id, revision_json, trigger),
        )

        # Prune: keep only the N most-recent revisions for this template
        cursor.execute(
            """
            DELETE FROM template_revisions
            WHERE template_id = ?
              AND id NOT IN (
                  SELECT id FROM template_revisions
                  WHERE template_id = ?
                  ORDER BY created_at DESC
                  LIMIT ?
              )
            """,
            (template_id, template_id, max_revisions),
        )

        conn.commit()

    return revision_id


# ---------------------------
# LIST REVISIONS (metadata only — no snapshot body)
# ---------------------------
def list_revisions(template_id: str) -> List[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, template_id, trigger, created_at
            FROM template_revisions
            WHERE template_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (template_id,),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ---------------------------
# GET SINGLE REVISION (includes full snapshot)
# ---------------------------
def get_revision(revision_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, template_id, revision_json, trigger, created_at
            FROM template_revisions
            WHERE id = ?
            """,
            (revision_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "templateId": row["template_id"],
            "trigger": row["trigger"],
            "createdAt": row["created_at"],
            "snapshot": json.loads(row["revision_json"]),
        }