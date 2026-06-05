"""
Tests for the revision system: repository functions and API endpoints.

Covers:
  - Periodic capture (interval trigger)
  - Event-triggered capture (switch / unload triggers)
  - Storage and retrieval from SQLite via the repository layer
  - HTTP API contracts (create, list, get)
  - Pruning (max_revisions enforcement)
  - Hash-free backend behaviour (backend always persists; de-dup is frontend logic)
"""

import json
import sqlite3
import tempfile
import os
import pytest

from fastapi.testclient import TestClient

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    """
    Redirect DB_PATH to a fresh temporary database for each test so repository
    tests never touch the real templates.db.
    """
    import repositories.template_repository as repo

    db_file = str(tmp_path / "test_revisions.db")
    monkeypatch.setattr(repo, "DB_PATH", db_file)
    repo.init_db()
    return db_file


@pytest.fixture()
def api_client(tmp_db):
    """
    FastAPI TestClient wired to the temporary database.
    Importing app *after* monkeypatching ensures the test DB is used.
    """
    from api.app import app
    return TestClient(app)


# Minimal valid TemplateDTO snapshot (matches TemplateModel constraints)
SNAPSHOT = {
    "id": "tpl-abc",
    "name": "Test Template",
    "canvas": {"width": 1080, "height": 1350},
    "background": "",
    "elements": [],
}

TEMPLATE_ID = "tpl-abc"


# ─── Repository layer ─────────────────────────────────────────────────────────


class TestSaveRevision:
    def test_returns_uuid_string(self, tmp_db):
        import repositories.template_repository as repo

        rid = repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="interval")
        assert isinstance(rid, str) and len(rid) == 36  # UUID4 format

    def test_stores_all_trigger_types(self, tmp_db):
        import repositories.template_repository as repo

        for trigger in ("interval", "switch", "unload", "manual"):
            rid = repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger=trigger)
            rev = repo.get_revision(rid)
            assert rev["trigger"] == trigger

    def test_snapshot_roundtrip_is_lossless(self, tmp_db):
        import repositories.template_repository as repo

        snapshot = {**SNAPSHOT, "elements": [{"id": "e1", "type": "text",
                                               "field": "name", "label": "Name",
                                               "x": 10, "y": 20, "style": {}}]}
        rid = repo.save_revision(TEMPLATE_ID, snapshot, trigger="interval")
        rev = repo.get_revision(rid)
        assert rev["snapshot"] == snapshot

    def test_template_id_is_stored(self, tmp_db):
        import repositories.template_repository as repo

        rid = repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="switch")
        rev = repo.get_revision(rid)
        assert rev["templateId"] == TEMPLATE_ID

    def test_created_at_is_populated(self, tmp_db):
        import repositories.template_repository as repo

        rid = repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="interval")
        rev = repo.get_revision(rid)
        assert rev["createdAt"] is not None and rev["createdAt"] != ""

    def test_multiple_triggers_all_persist(self, tmp_db):
        """Each trigger type (interval, switch, unload) independently saves a row."""
        import repositories.template_repository as repo

        for trigger in ("interval", "switch", "unload"):
            repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger=trigger)

        revisions = repo.list_revisions(TEMPLATE_ID)
        assert len(revisions) == 3
        triggers_stored = {r["trigger"] for r in revisions}
        assert triggers_stored == {"interval", "switch", "unload"}


class TestListRevisions:
    def test_empty_for_unknown_template(self, tmp_db):
        import repositories.template_repository as repo

        result = repo.list_revisions("nonexistent-id")
        assert result == []

    def test_returns_metadata_without_snapshot(self, tmp_db):
        import repositories.template_repository as repo

        repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="interval")
        revisions = repo.list_revisions(TEMPLATE_ID)

        assert len(revisions) == 1
        row = revisions[0]
        # Metadata keys present
        assert "id" in row
        assert "template_id" in row
        assert "trigger" in row
        assert "created_at" in row
        # Snapshot body must NOT be in list results
        assert "revision_json" not in row
        assert "snapshot" not in row

    def test_ordered_most_recent_first(self, tmp_db):
        """Insert rows with explicit timestamps to avoid 1-second SQLite precision issues."""
        import sqlite3

        conn = sqlite3.connect(tmp_db)
        try:
            older_id = "rev-older"
            newer_id = "rev-newer"
            conn.execute(
                "INSERT INTO template_revisions (id, template_id, revision_json, trigger, created_at) VALUES (?, ?, ?, ?, ?)",
                (older_id, TEMPLATE_ID, "{}", "interval", "2024-01-01 10:00:00"),
            )
            conn.execute(
                "INSERT INTO template_revisions (id, template_id, revision_json, trigger, created_at) VALUES (?, ?, ?, ?, ?)",
                (newer_id, TEMPLATE_ID, "{}", "interval", "2024-01-01 10:01:00"),
            )
            conn.commit()
        finally:
            conn.close()

        import repositories.template_repository as repo
        revisions = repo.list_revisions(TEMPLATE_ID)
        assert revisions[0]["id"] == newer_id
        assert revisions[1]["id"] == older_id

    def test_scoped_to_template(self, tmp_db):
        import repositories.template_repository as repo

        repo.save_revision("tpl-1", {**SNAPSHOT, "id": "tpl-1"}, trigger="interval")
        repo.save_revision("tpl-2", {**SNAPSHOT, "id": "tpl-2"}, trigger="interval")

        assert len(repo.list_revisions("tpl-1")) == 1
        assert len(repo.list_revisions("tpl-2")) == 1


class TestGetRevision:
    def test_returns_full_snapshot(self, tmp_db):
        import repositories.template_repository as repo

        rid = repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="switch")
        rev = repo.get_revision(rid)

        assert rev is not None
        assert rev["id"] == rid
        assert rev["templateId"] == TEMPLATE_ID
        assert rev["trigger"] == "switch"
        assert isinstance(rev["snapshot"], dict)
        assert rev["snapshot"]["name"] == SNAPSHOT["name"]

    def test_returns_none_for_missing_id(self, tmp_db):
        import repositories.template_repository as repo

        result = repo.get_revision("00000000-0000-0000-0000-000000000000")
        assert result is None


class TestPruning:
    def test_prunes_oldest_beyond_max(self, tmp_db):
        """Pruning enforces the row cap; which specific rows survive is an ordering
        concern tested separately — here we only verify the count is enforced."""
        import repositories.template_repository as repo

        max_rev = 5
        for _ in range(max_rev + 2):
            repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="interval",
                               max_revisions=max_rev)

        revisions = repo.list_revisions(TEMPLATE_ID)
        assert len(revisions) == max_rev

    def test_prunes_oldest_rows_when_timestamps_differ(self, tmp_db):
        """With distinct timestamps we can verify the oldest rows are dropped."""
        import sqlite3

        conn = sqlite3.connect(tmp_db)
        try:
            for i in range(5):
                conn.execute(
                    "INSERT INTO template_revisions (id, template_id, revision_json, trigger, created_at) VALUES (?, ?, ?, ?, ?)",
                    (f"rev-{i}", TEMPLATE_ID, "{}", "interval", f"2024-01-01 10:0{i}:00"),
                )
            conn.commit()
        finally:
            conn.close()

        import repositories.template_repository as repo
        # Save one more with max_revisions=5 — rev-0 (oldest) should be pruned
        repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="interval", max_revisions=5)

        revisions = repo.list_revisions(TEMPLATE_ID)
        assert len(revisions) == 5
        kept_ids = {r["id"] for r in revisions}
        assert "rev-0" not in kept_ids

    def test_default_max_is_50(self, tmp_db):
        import repositories.template_repository as repo

        for _ in range(52):
            repo.save_revision(TEMPLATE_ID, SNAPSHOT, trigger="interval")

        revisions = repo.list_revisions(TEMPLATE_ID)
        assert len(revisions) == 50


# ─── API layer ────────────────────────────────────────────────────────────────


class TestCreateRevisionEndpoint:
    def test_returns_id_and_template_id(self, api_client):
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "interval"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["templateId"] == TEMPLATE_ID

    def test_all_valid_triggers_accepted(self, api_client):
        for trigger in ("interval", "switch", "unload", "manual"):
            resp = api_client.post(
                f"/templates/{TEMPLATE_ID}/revisions",
                json={"snapshot": SNAPSHOT, "trigger": trigger},
            )
            assert resp.status_code == 200, f"trigger={trigger} failed: {resp.text}"

    def test_invalid_trigger_coerced_to_interval(self, api_client):
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "bogus"},
        )
        assert resp.status_code == 200
        # Verify the stored revision has trigger="interval"
        rev_id = resp.json()["id"]
        get_resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions/{rev_id}")
        assert get_resp.json()["trigger"] == "interval"

    def test_missing_snapshot_returns_400(self, api_client):
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"trigger": "interval"},
        )
        assert resp.status_code == 400

    def test_invalid_snapshot_returns_400(self, api_client):
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": {"not": "a template"}, "trigger": "interval"},
        )
        assert resp.status_code == 400

    def test_snapshot_id_overridden_by_path_param(self, api_client):
        """Backend ignores snapshot.id in favour of the URL path param."""
        snapshot_with_wrong_id = {**SNAPSHOT, "id": "wrong-id"}
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": snapshot_with_wrong_id, "trigger": "switch"},
        )
        assert resp.status_code == 200
        assert resp.json()["templateId"] == TEMPLATE_ID

    def test_interval_trigger_persists_on_repeated_calls(self, api_client):
        """The backend always stores; de-dup is the frontend's responsibility."""
        for _ in range(3):
            resp = api_client.post(
                f"/templates/{TEMPLATE_ID}/revisions",
                json={"snapshot": SNAPSHOT, "trigger": "interval"},
            )
            assert resp.status_code == 200

        list_resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions")
        assert len(list_resp.json()) == 3

    def test_switch_trigger_persists(self, api_client):
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "switch"},
        )
        assert resp.status_code == 200
        rev_id = resp.json()["id"]
        get_resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions/{rev_id}")
        assert get_resp.json()["trigger"] == "switch"

    def test_unload_trigger_persists(self, api_client):
        resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "unload"},
        )
        assert resp.status_code == 200
        rev_id = resp.json()["id"]
        get_resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions/{rev_id}")
        assert get_resp.json()["trigger"] == "unload"


class TestListRevisionsEndpoint:
    def test_returns_empty_list_for_no_revisions(self, api_client):
        resp = api_client.get("/templates/unknown-tpl/revisions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_metadata_list(self, api_client):
        api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "interval"},
        )
        resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        item = items[0]
        assert "id" in item
        assert "trigger" in item
        assert "created_at" in item or "createdAt" in item

    def test_snapshot_not_in_list_response(self, api_client):
        api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "interval"},
        )
        resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions")
        for item in resp.json():
            assert "snapshot" not in item
            assert "revision_json" not in item

    def test_returns_all_saved_revisions(self, api_client):
        """All created revisions appear in the list (ordering is a DB concern)."""
        ids = set()
        for _ in range(3):
            r = api_client.post(
                f"/templates/{TEMPLATE_ID}/revisions",
                json={"snapshot": SNAPSHOT, "trigger": "interval"},
            )
            ids.add(r.json()["id"])

        resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions")
        returned_ids = {item["id"] for item in resp.json()}
        assert ids == returned_ids


class TestGetRevisionEndpoint:
    def test_returns_full_revision_with_snapshot(self, api_client):
        create_resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "switch"},
        )
        rev_id = create_resp.json()["id"]

        resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions/{rev_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == rev_id
        assert "snapshot" in body
        assert isinstance(body["snapshot"], dict)

    def test_snapshot_content_matches_original(self, api_client):
        create_resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "interval"},
        )
        rev_id = create_resp.json()["id"]

        resp = api_client.get(f"/templates/{TEMPLATE_ID}/revisions/{rev_id}")
        assert resp.json()["snapshot"]["name"] == SNAPSHOT["name"]
        assert resp.json()["snapshot"]["canvas"] == SNAPSHOT["canvas"]

    def test_not_found_returns_404(self, api_client):
        resp = api_client.get(
            f"/templates/{TEMPLATE_ID}/revisions/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_wrong_template_returns_404(self, api_client):
        """A revision that exists but belongs to a different template returns 404."""
        create_resp = api_client.post(
            f"/templates/{TEMPLATE_ID}/revisions",
            json={"snapshot": SNAPSHOT, "trigger": "interval"},
        )
        rev_id = create_resp.json()["id"]

        resp = api_client.get(f"/templates/different-template/revisions/{rev_id}")
        assert resp.status_code == 404
