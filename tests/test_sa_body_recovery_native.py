"""Exercise the real native entry, including read-only preview and write bounds."""

import hashlib
import sqlite3
from datetime import datetime, timezone

import pytest

from src import sa_capture_store as store
from src.sa_native_host import handle_message
from src.tools.backends.sa_capture_backend import SACaptureBackend


BAD = "Analyst's Disclosure: no positions.\n\nSeeking Alpha's Disclosure: investing involves risk."
GOOD = "Demand and free cash flow improved following the company's cost reduction program."


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "sa.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(path))
    backend = SACaptureBackend(sa_db=str(path), market_db=str(tmp_path / "market.db"))
    today = datetime.now(timezone.utc).date().isoformat()
    backend.upsert_sa_articles_meta([{
        "article_id": "123", "title": "Portfolio update", "published_date": today,
        "url": "https://seekingalpha.com/alpha-picks/articles/123-update",
    }, {
        "article_id": "456", "title": "Closed pick update", "published_date": "2020-01-01",
        "url": "https://seekingalpha.com/alpha-picks/articles/456-update",
    }])
    with store.connect(str(path)) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?", (BAD,))
    return path


def test_native_preview_is_readonly_and_has_no_network_or_dal_initialization(db, monkeypatch):
    import src.tools.data_access as data_access
    monkeypatch.setattr(data_access, "DataAccessLayer", lambda: pytest.fail("preview instantiated DAL"))
    before = db.read_bytes()
    result = handle_message({"action": "preview_article_body_recovery"})
    assert result["status"] == "ok"
    assert [target["article_id"] for target in result["targets"]] == ["123"]
    assert db.read_bytes() == before


def test_native_preview_missing_store_does_not_create_it(tmp_path, monkeypatch):
    path = tmp_path / "missing" / "sa.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(path))
    result = handle_message({"action": "preview_article_body_recovery"})
    assert result["status"] == "unavailable"
    assert not path.parent.exists()


def test_preview_bounds_native_payload_but_preserves_total_count(db):
    with store.connect(str(db)) as conn:
        date = datetime.now(timezone.utc).date().isoformat()
        conn.executemany("INSERT INTO sa_articles(article_id,url,title,published_date) VALUES (?,?,?,?)", [
            (str(i), f"https://seekingalpha.com/alpha-picks/articles/{i}-update", "Portfolio update", date)
            for i in range(1000, 1020)
        ])
    result = handle_message({"action": "preview_article_body_recovery"})
    assert len(result["targets"]) == 5
    assert result["counts"]["targets"] == 21
    assert "held" not in result
    assert "excluded" not in result


def test_native_repair_revalidates_scope_and_then_skips_already_saved_body(db):
    digest = hashlib.sha256(BAD.encode()).hexdigest()
    base = {"article_id": "123", "body_sha256": digest}
    checked = handle_message({"action": "check_article_body_recovery_target", **base})
    assert checked["status"] == "ok"
    result = handle_message({"action": "save_article_body_recovery", "article_id": "123",
                             "expected_body_sha256": digest, "body_markdown": GOOD})
    assert result["status"] == "ok"
    assert result["body_saved"] is True
    assert handle_message({"action": "check_article_body_recovery_target", **base})["reason"] == "already_present"
    assert handle_message({"action": "preview_article_body_recovery"})["targets"] == []


@pytest.mark.parametrize("article_id,digest,reason", [
    ("456", hashlib.sha256(BAD.encode()).hexdigest(), "out_of_scope"),
    ("123", "0" * 64, "source_changed"),
])
def test_native_save_cannot_expand_frozen_scope_or_overwrite_changed_input(db, article_id, digest, reason):
    before = db.read_bytes()
    result = handle_message({"action": "save_article_body_recovery", "article_id": article_id,
                             "expected_body_sha256": digest, "body_markdown": GOOD})
    assert result["status"] == "skipped"
    assert result["reason"] == reason
    assert not result.get("body_saved")
    assert db.read_bytes() == before


def test_native_save_rejects_bad_capture_and_preserves_raw_evidence(db):
    result = handle_message({"action": "save_article_body_recovery", "article_id": "123",
                             "expected_body_sha256": hashlib.sha256(BAD.encode()).hexdigest(),
                             "body_markdown": BAD})
    assert result["status"] == "error"
    assert result["error_code"] == "sa_article_body_disclosure_only"
    with sqlite3.connect(str(db)) as conn:
        assert conn.execute("SELECT body_markdown FROM sa_articles WHERE article_id='123'").fetchone()[0] == BAD
