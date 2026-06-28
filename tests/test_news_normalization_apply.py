from dataclasses import replace
from contextlib import contextmanager, nullcontext
from pathlib import Path
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.news_identity import canonical_article_hash
from src.news_normalized.migration import build_resolved_plan
from src.news_normalized.migration_apply import (
    MigrationValidationError,
    read_body_evidence_batch,
    validate_applied_plan,
    write_resolved_plan,
)
from src.news_normalized.schema import begin_news_normalized_schema_transaction
from scripts.migration import apply_news_normalization as apply_module


NOW = "2026-06-29T12:00:00Z"


def _legacy_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published = "2026-06-27T10:00:00Z"
    rows = (
        (1, "AAPL", "Polygon shared", "https://example.test/shared", "polygon"),
        (2, "MSFT", "IBKR ambiguous", "", "ibkr"),
    )
    for row_id, ticker, title, url, source in rows:
        conn.execute(
            "INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
            (
                row_id,
                ticker,
                title,
                "",
                url,
                "Wire",
                source,
                published,
                canonical_article_hash(ticker, title, published),
            ),
        )
    conn.commit()
    conn.close()


def _parquet_inputs(root: Path):
    published = "2026-06-27T10:00:00Z"
    polygon = root / "polygon" / "2026" / "input.parquet"
    polygon.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "AAPL",
                    "title": "Polygon shared",
                    "published_at": published,
                    "source_api": "polygon",
                    "content": body,
                    "description": "",
                    "url": "https://example.test/shared",
                    "publisher": "Wire",
                    "related_tickers": '["AAPL"]',
                    "content_fetched_at": fetched_at,
                }
                for provider_id, body, fetched_at in (
                    ("polygon-a", "short body", "2026-06-27T10:01:00Z"),
                    (
                        "polygon-b",
                        "longer canonical body text",
                        "2026-06-27T10:02:00Z",
                    ),
                )
            ]
        ),
        polygon,
        row_group_size=2,
    )
    ibkr = root / "ibkr" / "2026" / "input.parquet"
    ibkr.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "MSFT",
                    "title": "IBKR ambiguous",
                    "published_at": published,
                    "source_api": "ibkr",
                    "content": "",
                    "description": "",
                    "url": "",
                    "publisher": "Wire",
                    "related_tickers": '["MSFT"]',
                }
                for provider_id in ("ibkr-a", "ibkr-b")
            ]
        ),
        ibkr,
    )
    return [polygon, ibkr]


@pytest.fixture
def temp_inputs(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    paths = _parquet_inputs(tmp_path / "raw")
    plan = build_resolved_plan(db, paths)
    assert plan.preview.would_apply
    return db, paths, plan


def _apply(temp_inputs):
    db, _paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    begin_news_normalized_schema_transaction(conn)
    result = write_resolved_plan(conn, plan, "backup.db", NOW)
    validate_applied_plan(conn, plan)
    conn.commit()
    return conn, result


def test_apply_accounts_for_every_legacy_row(temp_inputs):
    conn, result = _apply(temp_inputs)
    mapped = conn.execute("SELECT COUNT(*) FROM news_legacy_migration_map").fetchone()[0]
    legacy = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    assert mapped == legacy == 2
    assert result.resolved_fingerprint == temp_inputs[2].preview.resolved_fingerprint
    conn.close()


def test_apply_keeps_cold_body_out_of_fts(temp_inputs):
    conn, _result = _apply(temp_inputs)
    cold = conn.execute("SELECT raw_body FROM news_article_body_variants").fetchone()[0]
    active = conn.execute(
        "SELECT body_text FROM news_article_bodies WHERE body_status='fetched'"
    ).fetchone()[0]
    fts = " ".join(row[0] for row in conn.execute("SELECT body_text FROM news_search_documents"))
    assert cold == "short body"
    assert active == "longer canonical body text"
    assert cold not in fts
    assert active in fts
    conn.close()


def test_apply_polygon_aliases_have_no_url_key(temp_inputs):
    conn, _result = _apply(temp_inputs)
    provider_keys = conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='provider_id'"
    ).fetchone()[0]
    url_keys = conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='url'"
    ).fetchone()[0]
    assert provider_keys == 2
    assert url_keys == 0
    conn.close()


def test_body_reader_batches_same_parquet_row_group(temp_inputs, monkeypatch):
    refs = [
        ref
        for article in temp_inputs[2].articles
        for ref in ((article.active_body,) + article.cold_bodies)
        if ref is not None
    ]
    calls = []
    original = pq.ParquetFile.read_row_group

    def recording(self, row_group, *args, **kwargs):
        calls.append((self.reader.metadata.num_rows, row_group))
        return original(self, row_group, *args, **kwargs)

    monkeypatch.setattr(pq.ParquetFile, "read_row_group", recording)
    bodies = read_body_evidence_batch(refs)

    assert set(bodies.values()) == {"short body", "longer canonical body text"}
    assert len(calls) == 1


def test_apply_rolls_back_when_outer_validation_raises(temp_inputs):
    db, _paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    with pytest.raises(MigrationValidationError):
        write_resolved_plan(conn, plan, "backup.db", NOW)
        raise MigrationValidationError("injected")
    conn.rollback()
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 0
    conn.close()


def test_body_locator_digest_mismatch_aborts(temp_inputs):
    db, _paths, plan = temp_inputs
    article_index = next(
        index for index, article in enumerate(plan.articles) if article.active_body
    )
    article = plan.articles[article_index]
    bad_article = replace(
        article,
        active_body=replace(article.active_body, body_sha256="0" * 64),
    )
    bad_plan = replace(
        plan,
        articles=plan.articles[:article_index]
        + (bad_article,)
        + plan.articles[article_index + 1 :],
    )
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    with pytest.raises(MigrationValidationError, match="digest changed"):
        write_resolved_plan(conn, bad_plan, "backup.db", NOW)
    conn.rollback()
    conn.close()


def test_second_apply_of_same_fingerprint_is_zero_change(temp_inputs):
    conn, first = _apply(temp_inputs)
    before = conn.total_changes
    second = write_resolved_plan(conn, temp_inputs[2], "backup.db", NOW)
    assert second.already_applied is True
    assert second.run_id == first.run_id
    assert conn.total_changes == before
    conn.close()


def _approved_arguments(temp_inputs, tmp_path):
    db, paths, plan = temp_inputs
    return {
        "market_db": db,
        "parquet_root": Path(paths[0]).parents[2],
        "expected_input_fingerprint": plan.preview.input_fingerprint,
        "expected_resolved_fingerprint": plan.preview.resolved_fingerprint,
        "expected_rejection_evidence_fingerprint": (
            plan.preview.rejection_evidence.fingerprint
        ),
        "backup_path": tmp_path / "backup.db",
    }


@pytest.mark.parametrize(
    ("argument", "bad_value"),
    [
        ("expected_input_fingerprint", "bad-input"),
        ("expected_resolved_fingerprint", "bad-resolved"),
        ("expected_rejection_evidence_fingerprint", "bad-rejection"),
    ],
)
def test_orchestrator_refuses_each_fingerprint_before_backup(
    tmp_path, monkeypatch, temp_inputs, argument, bad_value
):
    backup_calls = []
    monkeypatch.setattr(
        apply_module, "build_resolved_plan", lambda *args: temp_inputs[2]
    )
    monkeypatch.setattr(
        apply_module,
        "backup_market_db",
        lambda *args, **kwargs: backup_calls.append(args),
    )
    kwargs = _approved_arguments(temp_inputs, tmp_path)
    kwargs[argument] = bad_value

    with pytest.raises(apply_module.MigrationFingerprintMismatch):
        apply_module.apply_news_normalization(**kwargs)

    assert backup_calls == []


class _RecordingConnection:
    def __init__(self, events):
        self.events = events

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.events.append("close")


def test_orchestrator_orders_lock_backup_begin_and_postcheck(
    tmp_path, monkeypatch, temp_inputs
):
    events = []

    @contextmanager
    def recording_lock(*args, **kwargs):
        events.append("lock-enter")
        try:
            yield
        finally:
            events.append("lock-exit")

    monkeypatch.setattr(apply_module, "market_write_lock", recording_lock)
    monkeypatch.setattr(
        apply_module, "build_resolved_plan", lambda *args: temp_inputs[2]
    )
    monkeypatch.setattr(
        apply_module,
        "backup_market_db",
        lambda *args, **kwargs: events.append("backup") or str(args[1]),
    )
    monkeypatch.setattr(
        apply_module,
        "open_apply_connection",
        lambda *args: _RecordingConnection(events),
    )
    monkeypatch.setattr(
        apply_module,
        "begin_news_normalized_schema_transaction",
        lambda conn: events.append("begin"),
    )
    monkeypatch.setattr(
        apply_module,
        "write_resolved_plan",
        lambda *args: events.append("write") or "result",
    )
    monkeypatch.setattr(
        apply_module,
        "validate_applied_plan",
        lambda *args: events.append("validate"),
    )
    monkeypatch.setattr(
        apply_module,
        "validate_reopened_read_only",
        lambda *args: events.append("postcheck"),
    )
    monkeypatch.setattr(
        apply_module,
        "require_idempotent_replan",
        lambda *args: events.append("idempotent"),
    )

    result = apply_module.apply_news_normalization(
        **_approved_arguments(temp_inputs, tmp_path)
    )

    assert result == "result"
    assert events == [
        "lock-enter",
        "backup",
        "begin",
        "write",
        "validate",
        "commit",
        "close",
        "postcheck",
        "idempotent",
        "lock-exit",
    ]


def test_orchestrator_rolls_back_on_validation_failure(
    tmp_path, monkeypatch, temp_inputs
):
    events = []
    connection = _RecordingConnection(events)
    monkeypatch.setattr(
        apply_module, "build_resolved_plan", lambda *args: temp_inputs[2]
    )
    monkeypatch.setattr(
        apply_module, "backup_market_db", lambda *args, **kwargs: str(args[1])
    )
    monkeypatch.setattr(
        apply_module, "open_apply_connection", lambda *args: connection
    )
    monkeypatch.setattr(
        apply_module, "begin_news_normalized_schema_transaction", lambda conn: None
    )
    monkeypatch.setattr(
        apply_module, "write_resolved_plan", lambda *args: "result"
    )
    monkeypatch.setattr(
        apply_module,
        "validate_applied_plan",
        lambda *args: (_ for _ in ()).throw(MigrationValidationError("injected")),
    )

    with pytest.raises(MigrationValidationError):
        apply_module.apply_news_normalization(
            **_approved_arguments(temp_inputs, tmp_path)
        )

    assert "rollback" in events
    assert "commit" not in events


def test_orchestrator_integrates_backup_apply_reopen_and_replan(
    tmp_path, monkeypatch, temp_inputs
):
    monkeypatch.setattr(
        apply_module, "market_write_lock", lambda *args, **kwargs: nullcontext()
    )
    kwargs = _approved_arguments(temp_inputs, tmp_path)

    result = apply_module.apply_news_normalization(**kwargs)

    assert result.already_applied is False
    assert kwargs["backup_path"].is_file()
    backup = sqlite3.connect(
        f"file:{kwargs['backup_path']}?mode=ro", uri=True
    )
    assert backup.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 0
    backup.close()
    live = sqlite3.connect(f"file:{kwargs['market_db']}?mode=ro", uri=True)
    assert live.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 3
    live.close()


def test_apply_cli_requires_scheduler_paused_confirmation(temp_inputs, tmp_path):
    kwargs = _approved_arguments(temp_inputs, tmp_path)
    arguments = [
        "--market-db",
        str(kwargs["market_db"]),
        "--parquet-root",
        str(kwargs["parquet_root"]),
        "--expected-input-fingerprint",
        kwargs["expected_input_fingerprint"],
        "--expected-resolved-fingerprint",
        kwargs["expected_resolved_fingerprint"],
        "--expected-rejection-evidence-fingerprint",
        kwargs["expected_rejection_evidence_fingerprint"],
        "--backup-path",
        str(kwargs["backup_path"]),
    ]

    with pytest.raises(SystemExit):
        apply_module.build_parser().parse_args(arguments)
    parsed = apply_module.build_parser().parse_args(
        arguments + ["--confirm-scheduler-paused"]
    )
    assert parsed.confirm_scheduler_paused is True
