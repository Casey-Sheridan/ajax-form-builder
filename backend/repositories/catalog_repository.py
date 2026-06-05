import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional

DB_PATH = "templates.db"
_BASE_DIR = Path(__file__).resolve().parent.parent
_CATALOG_ASSETS_DIR = _BASE_DIR / "static" / "catalog-assets"


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------
# ORGS
# ---------------------------

def list_orgs() -> List[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, name, slug, created_at FROM orgs ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def get_default_org_id() -> Optional[str]:
    with _db() as conn:
        row = conn.execute(
            "SELECT id FROM orgs ORDER BY created_at LIMIT 1"
        ).fetchone()
        return row["id"] if row else None


def get_org_by_id(org_id: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, name, slug FROM orgs WHERE id = ?", (org_id,)
        ).fetchone()
        return dict(row) if row else None


# ---------------------------
# CATALOGS
# ---------------------------

def list_catalogs(org_id: str) -> List[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, name, label, created_at FROM catalogs WHERE org_id = ? ORDER BY label",
            (org_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def ensure_catalog(org_id: str, name: str, label: str) -> str:
    """Return the catalog id, creating it if it doesn't exist."""
    with _db() as conn:
        row = conn.execute(
            "SELECT id FROM catalogs WHERE org_id = ? AND name = ?",
            (org_id, name),
        ).fetchone()
        if row:
            return row["id"]
        catalog_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO catalogs (id, org_id, name, label) VALUES (?, ?, ?, ?)",
            (catalog_id, org_id, name, label),
        )
        conn.commit()
        return catalog_id


# ---------------------------
# CATALOG ITEMS
# ---------------------------

def list_catalog_items(org_id: str, catalog_name: str) -> List[dict]:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT ci.id, ci.value, ci.label, ci.image_path, ci.meta, ci.sort_order
            FROM catalog_items ci
            JOIN catalogs c ON c.id = ci.catalog_id
            WHERE c.org_id = ? AND c.name = ?
            ORDER BY ci.sort_order ASC, ci.label ASC
            """,
            (org_id, catalog_name),
        ).fetchall()
        return [_item_to_dict(r) for r in rows]


def create_catalog_item(
    org_id: str,
    catalog_name: str,
    value: str,
    label: str,
    image_path: Optional[str] = None,
    meta: Optional[dict] = None,
    sort_order: int = 0,
) -> dict:
    label_for_catalog = catalog_name.replace("-", " ").replace("_", " ").title()
    catalog_id = ensure_catalog(org_id, catalog_name, label_for_catalog)
    item_id = str(uuid.uuid4())
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO catalog_items
                (id, catalog_id, value, label, image_path, meta, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(catalog_id, value) DO UPDATE SET
                label      = excluded.label,
                image_path = COALESCE(excluded.image_path, catalog_items.image_path),
                meta       = excluded.meta,
                sort_order = excluded.sort_order
            """,
            (
                item_id,
                catalog_id,
                value,
                label,
                image_path,
                json.dumps(meta or {}),
                sort_order,
            ),
        )
        conn.commit()
        # Re-fetch to get actual id (upsert may have kept the old one)
        row = conn.execute(
            "SELECT id FROM catalog_items WHERE catalog_id = ? AND value = ?",
            (catalog_id, value),
        ).fetchone()
        return {"id": row["id"], "value": value, "label": label}


def get_catalog_item(item_id: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, value, label, image_path, meta, sort_order FROM catalog_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        return _item_to_dict(row) if row else None


def update_catalog_item_image(item_id: str, image_path: str) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "UPDATE catalog_items SET image_path = ? WHERE id = ?",
            (image_path, item_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_catalog_item(org_id: str, item_id: str) -> bool:
    """Delete an item only if it belongs to this org (ownership check via JOIN)."""
    with _db() as conn:
        cur = conn.execute(
            """
            DELETE FROM catalog_items
            WHERE id = ?
              AND catalog_id IN (SELECT id FROM catalogs WHERE org_id = ?)
            """,
            (item_id, org_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------
# ASSET UPLOAD
# ---------------------------

def save_item_asset(org_id: str, catalog_name: str, item_id: str, data: bytes, suffix: str) -> str:
    """
    Write image bytes to disk, update the item row, and return the web-visible path.
    Returns the path relative to backend/ (e.g. 'static/catalog-assets/org/name/uuid.png').
    """
    dest_dir = _CATALOG_ASSETS_DIR / org_id / catalog_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_suffix = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
    filename = f"{uuid.uuid4().hex}{safe_suffix}"
    (dest_dir / filename).write_bytes(data)

    rel_path = f"static/catalog-assets/{org_id}/{catalog_name}/{filename}"
    update_catalog_item_image(item_id, rel_path)
    return rel_path


# ---------------------------
# HELPERS
# ---------------------------

def _item_to_dict(row) -> dict:
    image_path = row["image_path"]
    image_url = f"/{image_path}" if image_path else None
    return {
        "id": row["id"],
        "value": row["value"],
        "label": row["label"],
        "image_url": image_url,
        "meta": json.loads(row["meta"]) if row["meta"] else {},
        "sort_order": row["sort_order"],
    }
