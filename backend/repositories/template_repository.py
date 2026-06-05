import json
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional

from models.template import TemplateModel

DB_PATH = "templates.db"
_BASE_DIR = Path(__file__).resolve().parent.parent


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

        # ---------------------------
        # MULTI-TENANT CATALOG TABLES
        # ---------------------------
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orgs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS catalogs (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                label TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(org_id, name)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog_items (
                id TEXT PRIMARY KEY,
                catalog_id TEXT NOT NULL REFERENCES catalogs(id) ON DELETE CASCADE,
                value TEXT NOT NULL,
                label TEXT NOT NULL,
                image_path TEXT,
                meta TEXT NOT NULL DEFAULT '{}',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(catalog_id, value)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_catalog_items_lookup
            ON catalog_items(catalog_id, sort_order ASC)
            """
        )

        conn.commit()

        _seed_default_org(conn)


def _seed_default_org(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orgs")
    if cursor.fetchone()[0] > 0:
        return

    default_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO orgs (id, name, slug) VALUES (?, ?, ?)",
        (default_id, "Default Organization", "default"),
    )

    partners_file = _BASE_DIR / "partners.txt"
    if not partners_file.exists():
        conn.commit()
        return

    catalog_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO catalogs (id, org_id, name, label) VALUES (?, ?, ?, ?)",
        (catalog_id, default_id, "partners", "Partners"),
    )

    logos_dir = _BASE_DIR / "assets" / "logos"
    with open(partners_file) as f:
        names = [line.strip() for line in f if line.strip()]

    for i, name in enumerate(names):
        normalized = (
            name.lower()
            .replace(" ", "-")
            .replace("_", "-")
            .replace("&", "and")
            .replace("/", "-")
        )
        image_path = None
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = logos_dir / f"{normalized}{ext}"
            if candidate.exists():
                image_path = f"assets/logos/{normalized}{ext}"
                break

        cursor.execute(
            """
            INSERT OR IGNORE INTO catalog_items
                (id, catalog_id, value, label, image_path, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), catalog_id, name, name, image_path, i),
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

    fields = _safe_json_load(template_data.get("fields"), [])

    return TemplateModel.model_validate({
        "id": template_id,
        "name": template_name,
        "canvas": canvas,
        "background": template_data.get("background") or "",
        "elements": elements,
        "fields": fields,
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
        "fields": [f.model_dump() for f in template.fields],
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