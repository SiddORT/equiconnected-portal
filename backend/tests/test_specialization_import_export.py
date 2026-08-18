"""
Specialization CSV import/export tests (spec section 21).
"""
import io

import pytest
from fastapi.testclient import TestClient

from tests.test_specializations import _auth, _create_spec, admin_token, non_admin_token  # noqa: F401

BASE = "/api/v1/admin/specializations"


def _csv_file(content: str, filename: str = "import.csv"):
    return {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")}


def _preview(client, token, content: str, filename: str = "import.csv"):
    return client.post(
        f"{BASE}/import/preview", files=_csv_file(content, filename), headers=_auth(token)
    )


def _confirm(client, token, rows):
    return client.post(f"{BASE}/import", json={"rows": rows}, headers=_auth(token))


# ── Export ────────────────────────────────────────────────────────────────────

class TestExport:
    def test_export_all(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Cardiology", "Heart")
        _create_spec(client, admin_token, "Neurology")
        resp = client.get(f"{BASE}/export", headers=_auth(admin_token))
        assert resp.status_code == 200
        lines = resp.text.strip().splitlines()
        assert len(lines) == 3  # header + 2 rows
        assert "Cardiology" in resp.text and "Neurology" in resp.text

    def test_export_headers(self, client: TestClient, admin_token: str):
        resp = client.get(f"{BASE}/export", headers=_auth(admin_token))
        assert resp.text.splitlines()[0].strip() == "ID,Name,Description,Status,Created At,Updated At"

    def test_export_content_type_and_filename(self, client: TestClient, admin_token: str):
        resp = client.get(f"{BASE}/export", headers=_auth(admin_token))
        assert resp.headers["content-type"].startswith("text/csv")
        assert "charset=utf-8" in resp.headers["content-type"]
        cd = resp.headers["content-disposition"]
        assert "equiconnected-specializations-" in cd and cd.endswith('.csv"')

    def test_export_filtered_by_active(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "ActiveOne")
        inactive = _create_spec(client, admin_token, "InactiveOne")
        client.patch(f"{BASE}/{inactive['id']}/status", json={"is_active": False}, headers=_auth(admin_token))
        resp = client.get(f"{BASE}/export", params={"is_active": "true"}, headers=_auth(admin_token))
        assert "ActiveOne" in resp.text
        assert "InactiveOne" not in resp.text

    def test_export_filtered_by_search(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Gastroenterology")
        _create_spec(client, admin_token, "Dermatology")
        resp = client.get(f"{BASE}/export", params={"search": "gastro"}, headers=_auth(admin_token))
        assert "Gastroenterology" in resp.text
        assert "Dermatology" not in resp.text

    def test_export_human_readable_status(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "StatusCheck")
        resp = client.get(f"{BASE}/export", headers=_auth(admin_token))
        assert ",Active," in resp.text

    def test_export_utf8(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Kardiológia", "Descripción médica")
        resp = client.get(f"{BASE}/export", headers=_auth(admin_token))
        assert "Kardiológia" in resp.text
        assert "Descripción médica" in resp.text

    def test_export_formula_injection_sanitized(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "=SUM(A1)")
        resp = client.get(f"{BASE}/export", headers=_auth(admin_token))
        assert "\t=SUM(A1)" in resp.text


# ── Template ──────────────────────────────────────────────────────────────────

class TestTemplate:
    def test_template_headers_and_filename(self, client: TestClient, admin_token: str):
        resp = client.get(f"{BASE}/import/template", headers=_auth(admin_token))
        assert resp.status_code == 200
        assert resp.text.splitlines()[0].strip() == "Name,Description,Status"
        assert "equiconnected-specializations-template.csv" in resp.headers["content-disposition"]

    def test_template_contains_guidance_row_only(self, client: TestClient, admin_token: str):
        resp = client.get(f"{BASE}/import/template", headers=_auth(admin_token))
        lines = [line for line in resp.text.strip().splitlines() if line]
        assert len(lines) == 2
        assert "Example" in lines[1]


# ── Preview (validation) ──────────────────────────────────────────────────────

class TestPreview:
    def test_valid_file(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\nCardiology,Heart,ACTIVE\n")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1 and data["valid"] == 1
        assert data["rows"][0]["state"] == "valid"

    def test_missing_header(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description\nCardiology,Heart\n")
        assert resp.status_code == 400
        assert "Status" in resp.json()["detail"]["message"]

    def test_missing_name(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\n,NoName,ACTIVE\n")
        data = resp.json()
        assert data["invalid"] == 1
        assert "Name is required" in data["rows"][0]["reason"]

    def test_invalid_status(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\nCardiology,Heart,MAYBE\n")
        data = resp.json()
        assert data["invalid"] == 1
        assert "Status" in data["rows"][0]["reason"]

    def test_status_case_insensitive(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\nCardiology,,active\nNeuro,,Inactive\n")
        assert resp.json()["valid"] == 2

    def test_duplicate_against_db(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Cardiology")
        resp = _preview(client, admin_token, "Name,Description,Status\ncardiology,Dup,ACTIVE\n")
        data = resp.json()
        assert data["duplicate"] == 1
        assert data["rows"][0]["state"] == "duplicate"

    def test_duplicate_within_file(self, client: TestClient, admin_token: str):
        resp = _preview(
            client, admin_token,
            "Name,Description,Status\nOrtho,,ACTIVE\nOrtho,,ACTIVE\n",
        )
        data = resp.json()
        assert data["valid"] == 1 and data["duplicate"] == 1

    def test_whitespace_normalisation(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\n  Cardio   Vascular  ,,ACTIVE\n")
        assert resp.json()["rows"][0]["name"] == "Cardio Vascular"

    def test_empty_description_ok(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\nCardiology,,ACTIVE\n")
        data = resp.json()
        assert data["valid"] == 1
        assert data["rows"][0]["description"] is None

    def test_empty_file(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "")
        assert resp.status_code == 400

    def test_header_only_file(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\n")
        assert resp.status_code == 400

    def test_non_utf8_rejected(self, client: TestClient, admin_token: str):
        files = {"file": ("import.csv", io.BytesIO("Name,Description,Status\nCafé,,ACTIVE\n".encode("latin-1")), "text/csv")}
        resp = client.post(f"{BASE}/import/preview", files=files, headers=_auth(admin_token))
        assert resp.status_code == 400
        assert "UTF-8" in resp.json()["detail"]["message"]

    def test_non_csv_extension_rejected(self, client: TestClient, admin_token: str):
        resp = _preview(client, admin_token, "Name,Description,Status\nX,,ACTIVE\n", filename="data.xlsx")
        assert resp.status_code == 400

    def test_oversized_file_rejected(self, client: TestClient, admin_token: str):
        big = "Name,Description,Status\n" + ("X" * (5 * 1024 * 1024 + 10))
        resp = _preview(client, admin_token, big)
        assert resp.status_code == 400
        assert "5 MB" in resp.json()["detail"]["message"]

    def test_preview_does_not_modify_db(self, client: TestClient, admin_token: str):
        _preview(client, admin_token, "Name,Description,Status\nPreviewOnly,,ACTIVE\n")
        resp = client.get(BASE, headers=_auth(admin_token))
        assert resp.json()["meta"]["total"] == 0


# ── Confirm import ────────────────────────────────────────────────────────────

class TestConfirmImport:
    def test_confirmed_import_modifies_db(self, client: TestClient, admin_token: str):
        preview = _preview(client, admin_token, "Name,Description,Status\nCardiology,Heart,ACTIVE\nNeurology,,INACTIVE\n").json()
        resp = _confirm(client, admin_token, preview["rows"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2 and data["skipped"] == 0 and data["errors"] == 0

        listing = client.get(BASE, headers=_auth(admin_token)).json()
        assert listing["meta"]["total"] == 2
        by_name = {s["name"]: s for s in listing["data"]}
        assert by_name["Cardiology"]["is_active"] is True
        assert by_name["Neurology"]["is_active"] is False

    def test_partial_import_skips_bad_rows(self, client: TestClient, admin_token: str):
        _create_spec(client, admin_token, "Existing")
        preview = _preview(
            client, admin_token,
            "Name,Description,Status\nGood,,ACTIVE\nExisting,,ACTIVE\n,,ACTIVE\n",
        ).json()
        assert preview["valid"] == 1 and preview["duplicate"] == 1 and preview["invalid"] == 1
        data = _confirm(client, admin_token, preview["rows"]).json()
        assert data["imported"] == 1 and data["skipped"] == 2 and data["errors"] == 1

    def test_commit_recheck_catches_race_duplicate(self, client: TestClient, admin_token: str):
        preview = _preview(client, admin_token, "Name,Description,Status\nRaceSpec,,ACTIVE\n").json()
        # Row created between preview and confirm
        _create_spec(client, admin_token, "RaceSpec")
        data = _confirm(client, admin_token, preview["rows"]).json()
        assert data["imported"] == 0 and data["skipped"] == 1

    def test_tampered_state_revalidated(self, client: TestClient, admin_token: str):
        rows = [{"row_num": 2, "name": "", "description": None, "status": "ACTIVE", "state": "valid", "reason": None}]
        data = _confirm(client, admin_token, rows).json()
        assert data["imported"] == 0 and data["errors"] == 1

    def test_tampered_whitespace_name_rejected(self, client: TestClient, admin_token: str):
        rows = [{"row_num": 2, "name": "   ", "description": None, "status": "ACTIVE", "state": "valid", "reason": None}]
        data = _confirm(client, admin_token, rows).json()
        assert data["imported"] == 0 and data["errors"] == 1
        listing = client.get(BASE, headers=_auth(admin_token)).json()
        assert listing["meta"]["total"] == 0

    def test_tampered_untrimmed_name_normalised(self, client: TestClient, admin_token: str):
        rows = [{"row_num": 2, "name": "  Trim   Me  ", "description": None, "status": "active", "state": "valid", "reason": None}]
        data = _confirm(client, admin_token, rows).json()
        assert data["imported"] == 1
        listing = client.get(BASE, headers=_auth(admin_token)).json()
        assert listing["data"][0]["name"] == "Trim Me"

    def test_tampered_overlong_description_rejected(self, client: TestClient, admin_token: str):
        rows = [{"row_num": 2, "name": "LongDesc", "description": "x" * 2001, "status": "ACTIVE", "state": "valid", "reason": None}]
        data = _confirm(client, admin_token, rows).json()
        assert data["imported"] == 0 and data["errors"] == 1
        listing = client.get(BASE, headers=_auth(admin_token)).json()
        assert listing["meta"]["total"] == 0

    def test_tampered_invalid_status_rejected(self, client: TestClient, admin_token: str):
        rows = [{"row_num": 2, "name": "BadStatus", "description": None, "status": "MAYBE", "state": "valid", "reason": None}]
        data = _confirm(client, admin_token, rows).json()
        assert data["imported"] == 0 and data["errors"] == 1

    def test_transaction_rollback_on_db_error(self, client: TestClient, admin_token: str, db, monkeypatch):
        from app.services import specialization_import_export_service as svc

        original_commit = type(db).commit

        def boom(self):
            raise RuntimeError("simulated failure")

        preview = _preview(client, admin_token, "Name,Description,Status\nRollbackSpec,,ACTIVE\n").json()
        monkeypatch.setattr("sqlalchemy.orm.Session.commit", boom)
        try:
            resp = _confirm(client, admin_token, preview["rows"])
            assert resp.status_code == 500
        except RuntimeError:
            pass  # TestClient re-raises server exceptions
        finally:
            monkeypatch.setattr("sqlalchemy.orm.Session.commit", original_commit)
        listing = client.get(BASE, headers=_auth(admin_token)).json()
        assert all(s["name"] != "RollbackSpec" for s in listing["data"])


# ── Authorization ─────────────────────────────────────────────────────────────

class TestAuthz:
    def test_export_requires_auth(self, client: TestClient):
        assert client.get(f"{BASE}/export").status_code == 401

    def test_template_requires_auth(self, client: TestClient):
        assert client.get(f"{BASE}/import/template").status_code == 401

    def test_preview_requires_auth(self, client: TestClient):
        resp = client.post(f"{BASE}/import/preview", files=_csv_file("Name,Description,Status\n"))
        assert resp.status_code == 401

    def test_import_requires_auth(self, client: TestClient):
        assert client.post(f"{BASE}/import", json={"rows": []}).status_code == 401

    def test_export_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.get(f"{BASE}/export", headers=_auth(non_admin_token)).status_code == 403

    def test_template_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        assert client.get(f"{BASE}/import/template", headers=_auth(non_admin_token)).status_code == 403

    def test_preview_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        resp = client.post(
            f"{BASE}/import/preview",
            files=_csv_file("Name,Description,Status\nX,,ACTIVE\n"),
            headers=_auth(non_admin_token),
        )
        assert resp.status_code == 403

    def test_import_forbidden_for_non_admin(self, client: TestClient, non_admin_token: str):
        rows = [{"row_num": 2, "name": "X", "description": None, "status": "ACTIVE", "state": "valid", "reason": None}]
        resp = client.post(f"{BASE}/import", json={"rows": rows}, headers=_auth(non_admin_token))
        assert resp.status_code == 403
