"""Canonical schema, immutable exact observations and continuation receipts."""

from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import sqlite3

import pytest

from src.sec_research.catalog import parse_submissions
from src.sec_research.facts import parse_companyfacts
from src.sec_research.paths import SecResearchPaths


ROOT = Path(__file__).resolve().parents[1]
CIK = "0000320193"
WHEN = "2026-09-11T00:00:00Z"
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
HISTORY = "CIK0000320193-submissions-001.json"


@pytest.fixture
def modules():
    for name in ("schema", "store"):
        assert (ROOT / f"src/sec_research/{name}.py").is_file(), f"SEC {name} missing"
    return (importlib.import_module("src.sec_research.schema"),
            importlib.import_module("src.sec_research.store"))


@pytest.fixture
def store(tmp_path, modules):
    result = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    result.install()
    return result


def facts(value="1234567890.123456789012345678900"):
    raw = ('{"cik":320193,"facts":{"us-gaap":{"Revenue":{"units":{"USD":['
           '{"val":' + value + ',"end":"2026-03-31","form":"10-Q",'
           '"accn":"0000950170-26-000001","filed":"2026-05-01"},'
           '{"val":124,"end":"2026-03-31","form":"10-Q/A",'
           '"accn":"0000950170-26-000002","filed":"2026-06-01"}]}}}}}').encode()
    return raw, parse_companyfacts(raw, cik=CIK)


def catalog(*, historical=False, files=True):
    columns = {"accessionNumber": ["0000950170-26-000001"],
               "filingDate": ["2026-05-01"], "form": ["10-Q"],
               "reportDate": ["2026-03-31"], "primaryDocument": ["actual.htm"]}
    doc = columns if historical else {"cik":320193, "filings":{"recent":columns}}
    if not historical and files:
        doc["filings"]["files"] = [{"name": HISTORY, "filingCount":1}]
    raw = json.dumps(doc).encode()
    return raw, parse_submissions(raw, cik=CIK, historical_name=HISTORY if historical else None)


def register(store, raw, snapshot):
    with store.connect() as conn:
        conn.execute("INSERT INTO sec_research_objects VALUES (?, ?, ?)",
                     (snapshot.sha256, "objects/" + snapshot.sha256, len(raw)))
        conn.commit()


def publish(store, pair, **kwargs):
    raw, snapshot = pair
    register(store, raw, snapshot)
    return store.publish(snapshot, object_sha256=snapshot.sha256,
                         observed_at=WHEN, source_url=URL, **kwargs)


def test_constructor_and_readonly_never_create_files(tmp_path, modules):
    store = modules[1].Store(SecResearchPaths(tmp_path / "absent" / "market.db"))
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(sqlite3.OperationalError):
        with store.connect(readonly=True):
            pass
    assert list(tmp_path.iterdir()) == []


def test_install_preserves_populated_unrelated_tables(tmp_path, modules):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    with store.connect() as conn:
        for table in ("prices", "news", "financial_cache"):
            conn.execute(f"CREATE TABLE {table}(sentinel TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES ('unchanged')")
        conn.commit()
    for _ in range(2):
        store.install()
        with store.connect(readonly=True) as conn:
            modules[0].verify(conn)
            for table in ("prices", "news", "financial_cache"):
                assert conn.execute(f"SELECT sentinel FROM {table}").fetchone()[0] == "unchanged"


@pytest.fixture
def uninstalled_issuer_market(tmp_path, modules):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    with store.connect() as conn:
        for table in ("prices", "news", "financial_cache"):
            conn.execute(f"CREATE TABLE {table}(sentinel TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES ('unchanged')")
    return store


def test_issuer_resolution_existing_uninstalled_market_is_unobserved(uninstalled_issuer_market):
    from src.sec_research.issuer_store import IssuerStore

    store = uninstalled_issuer_market
    with store.connect(readonly=True) as conn:
        before = list(conn.execute("SELECT * FROM sqlite_master"))
    try:
        result = IssuerStore(store).resolve("AAPL")
    except ValueError as exc:
        result = {"raised": str(exc)}
    assert result.get("status") == "unavailable", result
    assert result["cik"] is None and result["candidates"] == []
    assert result["observed_at"] is None
    assert result["source"] == {"url": "https://www.sec.gov/files/company_tickers.json", "sha256": None}
    assert result["gaps"] == [{"code": "issuer_map_unobserved"}]
    with store.connect(readonly=True) as conn:
        assert list(conn.execute("SELECT * FROM sqlite_master")) == before
        for table in ("prices", "news", "financial_cache"):
            assert [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")] == [("unchanged",)]
    assert not store.paths.capture_root.exists()


@pytest.mark.parametrize("ddl", [
    "CREATE TABLE sec_research_issuer_maps(value TEXT)",
    "CREATE TABLE sec_research_objects(sha256 TEXT)",
    "CREATE VIEW SEC_RESEARCH_ISSUER_MAPS AS SELECT 1 AS value",
], ids=["wrong-map", "partial", "view"])
def test_issuer_resolution_incompatible_schema_remains_explicit(uninstalled_issuer_market, ddl):
    from src.sec_research.issuer_store import IssuerStore

    store = uninstalled_issuer_market
    with store.connect() as conn:
        conn.execute(ddl)
        before = list(conn.execute("SELECT * FROM sqlite_master"))
    failure = None
    try:
        IssuerStore(store).resolve("AAPL")
    except ValueError as exc:
        failure = str(exc)
    assert failure == "sec_research_schema_mismatch"
    with store.connect(readonly=True) as conn:
        assert list(conn.execute("SELECT * FROM sqlite_master")) == before
        for table in ("prices", "news", "financial_cache"):
            assert [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")] == [("unchanged",)]
    assert not store.paths.capture_root.exists()


@pytest.mark.parametrize("ddl", [
    "CREATE TABLE sec_research_objects(sha256 TEXT PRIMARY KEY, object_key TEXT UNIQUE NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes>0))",
    "CREATE TABLE sec_research_surprise(x)",
    "CREATE VIEW sec_research_objects AS SELECT 1 AS sha256",
])
def test_shape_mismatch_is_rejected_without_installing_anything(tmp_path, modules, ddl):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    with store.connect() as conn:
        conn.execute(ddl)
        before = list(conn.execute("SELECT * FROM sqlite_master"))
        with pytest.raises(ValueError, match="sec_research_schema_mismatch"):
            modules[0].install(conn)
        assert list(conn.execute("SELECT * FROM sqlite_master")) == before


def test_verify_does_not_repair_missing_trigger(store, modules):
    with store.connect() as conn:
        name = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' LIMIT 1").fetchone()[0]
        conn.execute(f'DROP TRIGGER "{name}"')
        before = list(conn.execute("SELECT * FROM sqlite_master"))
        with pytest.raises(ValueError, match="sec_research_schema_mismatch"):
            modules[0].verify(conn)
        with pytest.raises(ValueError, match="sec_research_schema_mismatch"):
            modules[0].install(conn)
        assert list(conn.execute("SELECT * FROM sqlite_master")) == before


def test_install_rolls_back_interrupted_ddl(tmp_path, modules):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    with store.connect() as conn:
        count = 0
        def authorizer(action, *args):
            nonlocal count
            if action == sqlite3.SQLITE_CREATE_TABLE:
                count += 1
                if count == 2:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        conn.set_authorizer(authorizer)
        with pytest.raises(sqlite3.DatabaseError):
            modules[0].install(conn)
        # This interpreter keeps a rejecting callback after set_authorizer(None).
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        assert not list(conn.execute("SELECT name FROM sqlite_master"))
        assert not conn.in_transaction


def test_install_uses_market_lock_and_immediate_transaction(tmp_path, modules, monkeypatch):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    events = []
    @contextmanager
    def lock():
        events.append("lock")
        yield
        events.append("unlock")
    monkeypatch.setattr(modules[1], "market_write_lock", lock)
    original = store.connect
    @contextmanager
    def connect(*args, **kwargs):
        with original(*args, **kwargs) as conn:
            conn.set_trace_callback(events.append)
            yield conn
    monkeypatch.setattr(store, "connect", connect)
    store.install()
    assert events.index("lock") < events.index("BEGIN IMMEDIATE") < events.index("COMMIT") < events.index("unlock")


def test_connections_enable_foreign_keys_readonly_and_close(store):
    with store.connect(readonly=True) as conn:
        assert conn.isolation_level is None
        assert conn.row_factory is sqlite3.Row
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO sec_research_orphans VALUES ('x', 1)")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
    with pytest.raises(RuntimeError):
        with store.connect() as conn:
            raise RuntimeError("interrupt")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_exact_fact_text_and_amendments_reopen(store, modules):
    pair = facts()
    sid = publish(store, pair)
    reopened = modules[1].Store(store.paths)
    result = reopened.facts(CIK)
    assert [r["value"] for r in result] == [f.value for f in pair[1].facts]
    assert [r["form"] for r in result] == ["10-Q", "10-Q/A"]
    for row, fact in zip(result, pair[1].facts):
        assert {key: row[key] for key in asdict(fact)} == asdict(fact)
        assert (row["snapshot_id"], row["source_url"], row["object_sha256"]) == (sid, URL, pair[1].sha256)
    with store.connect(readonly=True) as conn:
        assert {r[0] for r in conn.execute("SELECT typeof(value) FROM sec_research_facts")} == {"text"}


def test_retained_snapshots_and_idempotent_publication(store):
    pair = facts()
    first = publish(store, pair)
    repeated = store.publish(pair[1], object_sha256=pair[1].sha256,
                             observed_at="2026-09-12T00:00:00Z", source_url=URL)
    second = publish(store, facts("999"))
    assert first == repeated and first != second
    saved = store.snapshots(CIK, "facts")
    assert len(saved) == 2
    assert saved[0]["observed_at"] == WHEN
    assert {r["snapshot_id"] for r in store.facts(CIK)} == {first, second}
    assert len(store.facts(CIK)) == 4
    assert store.facts("1") == []


@pytest.mark.parametrize("historical,files", [(False, True), (False, False), (True, False)])
def test_catalog_provenance_and_historical_coverage(store, historical, files):
    pair = catalog(historical=historical, files=files)
    publish(store, pair)
    row, = store.catalog(CIK)
    assert {key:row[key] for key in asdict(pair[1].filings[0])} == asdict(pair[1].filings[0])
    metadata, = store.snapshots(CIK, "catalog")
    assert metadata["historical_files_observed"] is pair[1].historical_files_observed
    assert metadata["historical_name"] == pair[1].historical_name
    assert metadata["historical_files"] == [asdict(f) for f in pair[1].historical_files]


def test_publication_requires_matching_registered_source_hash(store):
    raw, snapshot = facts()
    with pytest.raises(ValueError, match="sec_research_object_missing"):
        store.publish(snapshot, object_sha256=snapshot.sha256, observed_at=WHEN, source_url=URL)
    register(store, raw, snapshot)
    with pytest.raises(ValueError, match="sec_research_object_hash_mismatch"):
        store.publish(snapshot, object_sha256="0" * 64, observed_at=WHEN, source_url=URL)
    forged = replace(snapshot, facts=(replace(snapshot.facts[0], source=replace(snapshot.facts[0].source, sha256="0" * 64)),))
    with pytest.raises(ValueError, match="sec_research_object_hash_mismatch"):
        store.publish(forged, object_sha256=snapshot.sha256, observed_at=WHEN, source_url=URL)
    assert store.snapshots(CIK, "facts") == []


def test_publication_rolls_back_interrupted_rows(store, monkeypatch):
    raw, snapshot = facts()
    register(store, raw, snapshot)
    original = store.connect
    @contextmanager
    def interrupted(*args, **kwargs):
        with original(*args, **kwargs) as conn:
            conn.create_function("interrupt", 0, lambda: 1 / 0)
            conn.execute("CREATE TEMP TRIGGER interrupt_fact BEFORE INSERT ON sec_research_facts BEGIN SELECT interrupt(); END")
            yield conn
    with monkeypatch.context() as patch:
        patch.setattr(store, "connect", interrupted)
        with pytest.raises(sqlite3.DatabaseError):
            store.publish(snapshot, object_sha256=snapshot.sha256, observed_at=WHEN, source_url=URL)
    assert store.snapshots(CIK, "facts") == []
    assert store.facts(CIK) == []


@pytest.mark.parametrize("table", ["sec_research_snapshots", "sec_research_facts", "sec_research_objects", "sec_research_receipts", "sec_research_filings"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_published_rows_are_append_only(store, table, operation):
    publish(store, facts())
    publish(store, catalog())
    store.record_receipt(CIK, status="partial", completed=["submissions"], pending=["companyfacts"], gaps=[], observed_at=WHEN)
    with store.connect() as conn:
        sql = f"DELETE FROM {table}" if operation == "DELETE" else f"UPDATE {table} SET rowid=rowid"
        with pytest.raises(sqlite3.IntegrityError, match="sec_research_immutable"):
            conn.execute(sql)


@pytest.mark.parametrize("table", ["sec_research_snapshots", "sec_research_facts", "sec_research_objects", "sec_research_receipts", "sec_research_filings"])
def test_replace_cannot_overwrite_immutable_rows(store, table):
    publish(store, facts())
    publish(store, catalog())
    store.record_receipt(CIK, status="ok", completed=[], pending=[], gaps=[], observed_at=WHEN)
    with store.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="sec_research_immutable"):
            conn.execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}")


def test_verify_empty_database_and_unexpected_attached_index(tmp_path, modules):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    with store.connect() as conn:
        with pytest.raises(ValueError, match="sec_research_schema_mismatch"):
            modules[0].verify(conn)
        assert list(conn.execute("SELECT name FROM sqlite_master")) == []
        modules[0].install(conn)
        conn.execute("CREATE INDEX foreign_name ON sec_research_objects(size_bytes)")
        with pytest.raises(ValueError, match="sec_research_schema_mismatch"):
            modules[0].verify(conn)


def test_install_refuses_to_commit_callers_active_transaction(store, modules):
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO sec_research_orphans VALUES ('fixture', 1)")
        with pytest.raises(ValueError, match="sec_research_transaction_active"):
            modules[0].install(conn)
        assert conn.in_transaction
        conn.rollback()
        assert list(conn.execute("SELECT * FROM sec_research_orphans")) == []


def test_declared_snapshot_limits_and_actual_row_rejection(store, modules):
    assert modules[1].MAX_SNAPSHOT_ROWS == 100000
    assert modules[1].MAX_SNAPSHOT_BYTES == 64 * 1024 * 1024
    _, snapshot = facts()
    oversized = replace(snapshot, facts=(snapshot.facts[0],) * 100001)
    with pytest.raises(ValueError, match="sec_research_snapshot_rows_exceeded"):
        store.publish(oversized, object_sha256=snapshot.sha256, observed_at=WHEN, source_url=URL)


def test_snapshot_foreign_key_rejects_unregistered_object(store):
    with store.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conn.execute("INSERT INTO sec_research_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         ("missing", CIK, "facts", "0" * 64, WHEN, URL, None, 0, "[]", 0))


def test_receipts_append_and_latest_uses_append_order_not_observation_time(store):
    assert store.latest_receipt(CIK) is None
    first = store.record_receipt(CIK, status="partial", completed=["submissions"], pending=["companyfacts", HISTORY], gaps=[{"code":"fixture_gap"}], observed_at=WHEN)
    latest = store.record_receipt(CIK, status="ok", completed=["submissions", "companyfacts", HISTORY], pending=[], gaps=[], observed_at="2020-01-01T00:00:00Z")
    assert latest == store.latest_receipt("320193")
    assert first["receipt_id"] < latest["receipt_id"]
    assert first["completed"] == ["submissions"]
    with store.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM sec_research_receipts").fetchone()[0] == 2


def test_receipt_ordering_across_zero_fraction_and_equal_timestamps(store, modules, monkeypatch):
    # Timestamp formatting and equal clock samples cannot change append authority.
    times = iter([datetime(2026, 9, 11, tzinfo=timezone.utc),
                  datetime(2026, 9, 11, microsecond=1, tzinfo=timezone.utc),
                  datetime(2026, 9, 11, microsecond=1, tzinfo=timezone.utc)])
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(times)
    monkeypatch.setattr(modules[1], "datetime", Clock)
    for _ in range(3):
        receipt = store.record_receipt(CIK, status="ok", completed=[], pending=[], gaps=[], observed_at=WHEN)
        assert store.latest_receipt(CIK) == receipt


def test_latest_receipt_survives_clock_rollback_and_reopening(store, modules, monkeypatch):
    times = iter([datetime(2026, 9, 11, 1, tzinfo=timezone.utc),
                  datetime(2026, 9, 11, 0, tzinfo=timezone.utc)])
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(times)
    monkeypatch.setattr(modules[1], "datetime", Clock)
    old = store.record_receipt(CIK, status="ok", completed=["submissions", "companyfacts"],
                               pending=[], gaps=[], observed_at=WHEN)
    new = store.record_receipt(CIK, status="unavailable", completed=[],
                               pending=["submissions", "companyfacts"], gaps=[],
                               observed_at="2026-09-11T00:00:01Z")
    assert new["receipt_id"] > old["receipt_id"]
    assert new["recorded_at"] < old["recorded_at"]
    assert new["observed_at"] > old["observed_at"]
    assert store.latest_receipt(CIK) == new
    assert modules[1].Store(store.paths).latest_receipt(CIK) == new
    with store.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM sec_research_receipts").fetchone()[0] == 2


def test_receipt_lookup_index_tracks_durable_append_order(store):
    with store.connect(readonly=True) as conn:
        columns = [(row["name"], row["desc"]) for row in conn.execute(
            "PRAGMA index_xinfo(sec_research_receipts_lookup)") if row["key"]]
    assert columns == [("cik", 0), ("receipt_id", 1)]


@pytest.mark.parametrize("change", [{"status":"empty"}, {"completed":[{}]}, {"pending":"companyfacts"}, {"gaps":["gap"]}, {"completed":["../unsafe"]}])
def test_receipt_shape_is_closed(store, change):
    kwargs = dict(status="partial", completed=[], pending=[], gaps=[], observed_at=WHEN)
    with pytest.raises(ValueError, match="sec_research_receipt_invalid"):
        store.record_receipt(CIK, **(kwargs | change))
    assert store.latest_receipt(CIK) is None


@pytest.mark.parametrize("bound", ["rows", "bytes"])
def test_snapshot_limits_reject_before_writer_lock(store, modules, monkeypatch, bound):
    pair = facts()
    register(store, *pair)
    monkeypatch.setattr(modules[1], "MAX_SNAPSHOT_ROWS" if bound == "rows" else "MAX_SNAPSHOT_BYTES", 1)
    @contextmanager
    def forbidden():
        pytest.fail("oversized snapshot acquired writer lock")
        yield
    monkeypatch.setattr(modules[1], "market_write_lock", forbidden)
    with pytest.raises(ValueError, match="sec_research_snapshot_(rows|bytes)_exceeded"):
        store.publish(pair[1], object_sha256=pair[1].sha256, observed_at=WHEN, source_url=URL)
    assert store.snapshots(CIK, "facts") == []


@pytest.mark.parametrize("bound", ["rows", "bytes"])
def test_receipt_limits_reject_before_writer_lock(store, modules, monkeypatch, bound):
    with monkeypatch.context() as patch:
        patch.setattr(modules[1], "MAX_SNAPSHOT_ROWS" if bound == "rows" else "MAX_SNAPSHOT_BYTES", 1)
        @contextmanager
        def forbidden():
            pytest.fail("oversized receipt acquired writer lock")
            yield
        patch.setattr(modules[1], "market_write_lock", forbidden)
        with pytest.raises(ValueError) as error:
            store.record_receipt(CIK, status="unavailable", completed=[],
                                 pending=["submissions", "companyfacts"], gaps=[], observed_at=WHEN)
        assert error.value.args == (f"sec_research_snapshot_{bound}_exceeded",)
        assert store.latest_receipt(CIK) is None
    receipt = store.record_receipt(CIK, status="ok", completed=["submissions", "companyfacts"],
                                   pending=[], gaps=[], observed_at=WHEN)
    assert store.latest_receipt(CIK) == receipt


def bound_receipt(store, bindings, *, completed=None):
    return store.record_receipt(
        CIK, status="ok", completed=list(bindings) if completed is None else completed,
        pending=[], gaps=[], observed_at=WHEN, source_snapshots=bindings,
    )


def test_receipt_binding_reopens_exact_snapshot_and_capture_time(store, modules):
    sid = publish(store, catalog())
    later = "2026-09-12T00:00:00Z"
    bindings = {"submissions": {"snapshot_id": sid, "observed_at": later}}
    receipt = bound_receipt(store, bindings)
    bindings["submissions"]["observed_at"] = WHEN
    reopened = modules[1].Store(store.paths)
    assert reopened.receipt(CIK, receipt["receipt_id"])["source_snapshots"] == {
        "submissions": {"snapshot_id": sid, "observed_at": later}}
    assert reopened.receipt("1", receipt["receipt_id"]) is None
    assert reopened.snapshot(CIK, sid)["observed_at"] == WHEN
    assert reopened.snapshot("1", sid) is None
    assert reopened.snapshot_observations(CIK, sid)[0]["form"] == "10-Q"
    assert reopened.snapshot_observations("1", sid) == []


@pytest.mark.parametrize("wrong", ["issuer", "kind", "locator", "missing"])
def test_receipt_rejects_cross_source_snapshot_binding(store, wrong):
    pair = facts() if wrong == "kind" else catalog(historical=wrong == "locator")
    if wrong == "issuer":
        raw = pair[0].replace(b"320193", b"789019")
        pair = raw, parse_submissions(raw, cik="789019")
    sid = publish(store, pair)
    if wrong == "missing":
        sid = "secsnapshot_" + "0" * 64
    with pytest.raises(ValueError, match="^sec_research_receipt_binding_invalid$"):
        bound_receipt(store, {"submissions": {"snapshot_id": sid, "observed_at": WHEN}})
    assert store.latest_receipt(CIK) is None


@pytest.mark.parametrize("binding", [None, {}, {"snapshot_id": "x"},
    {"snapshot_id": "secsnapshot_" + "0" * 64, "observed_at": "yesterday"},
    {"snapshot_id": "secsnapshot_" + "0" * 64, "observed_at": WHEN, "extra": 1}])
def test_receipt_binding_shape_is_closed(store, binding):
    with pytest.raises(ValueError, match="^sec_research_receipt_binding_invalid$"):
        bound_receipt(store, {"submissions": binding})


def test_receipt_bindings_cover_completed_exactly_and_unbound_is_explicit(store):
    sid = publish(store, catalog())
    binding = {"submissions": {"snapshot_id": sid, "observed_at": WHEN}}
    for mapping, completed in [(binding, []), ({}, ["submissions"])]:
        with pytest.raises(ValueError, match="^sec_research_receipt_binding_invalid$"):
            bound_receipt(store, mapping, completed=completed)
    unbound = store.record_receipt(CIK, status="ok", completed=["submissions"],
                                   pending=[], gaps=[], observed_at=WHEN)
    assert unbound["source_snapshots"] == {}


def test_receipt_sequence_does_not_reuse_committed_ids(store):
    maximum = 2**63 - 1
    with store.connect() as conn:
        conn.execute("""INSERT INTO sec_research_receipts
            (receipt_id, cik, status, completed, pending, gaps, observed_at, recorded_at)
            VALUES (?, ?, 'ok', '[]', '[]', '[]', ?, ?)""", (maximum, CIK, WHEN, WHEN))
    with pytest.raises(sqlite3.OperationalError, match="full"):
        store.record_receipt(CIK, status="ok", completed=[], pending=[], gaps=[], observed_at=WHEN)
    assert store.latest_receipt(CIK)["receipt_id"] == maximum
    with store.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM sec_research_receipts").fetchone()[0] == 1


def test_sec_schema_leaves_unrelated_autoincrement_sequence_owned_by_sqlite(tmp_path, modules):
    store = modules[1].Store(SecResearchPaths(tmp_path / "market.db"))
    with store.connect() as conn:
        conn.execute("CREATE TABLE unrelated(id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)")
        conn.execute("INSERT INTO unrelated VALUES (42, 'keep')")
        before = tuple(conn.execute("SELECT * FROM sqlite_sequence WHERE name='unrelated'").fetchone())
    store.install()
    store.record_receipt(CIK, status="ok", completed=[], pending=[], gaps=[], observed_at=WHEN)
    store.install()
    with store.connect() as conn:
        modules[0].verify(conn)
        assert tuple(conn.execute("SELECT * FROM sqlite_sequence WHERE name='unrelated'").fetchone()) == before
        conn.execute("INSERT INTO unrelated(value) VALUES ('next')")
        assert conn.execute("SELECT max(id) FROM unrelated").fetchone()[0] == 43


@pytest.mark.parametrize("completed,pending", [(["submissions", "submissions"], []),
    ([], ["submissions", "submissions"]), (["submissions"], ["submissions"])])
def test_receipt_locators_have_one_unambiguous_state(store, completed, pending):
    with pytest.raises(ValueError, match="^sec_research_receipt_invalid$"):
        store.record_receipt(CIK, status="partial", completed=completed, pending=pending,
                             gaps=[], observed_at=WHEN)


def insert_stored_receipt(store, **changes):
    fields = dict(cik=CIK, status="ok", completed="[]", pending="[]", gaps="[]",
                  observed_at=WHEN, recorded_at=WHEN, source_snapshots="{}")
    fields.update(changes)
    with store.connect() as conn:
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        return conn.execute(f"INSERT INTO sec_research_receipts ({columns}) VALUES ({placeholders})",
                            tuple(fields.values())).lastrowid


@pytest.mark.parametrize("field", ["source_snapshots", "completed", "pending", "gaps"])
@pytest.mark.parametrize("value", ["null", "1", "true", '"PRIVATE"', "[]", "{}", "[null]", "[{}]"])
def test_receipt_reads_validate_decoded_field_types(store, field, value):
    receipt_id = insert_stored_receipt(store, **{field: value})
    if (field == "source_snapshots" and value == "{}"
            or field != "source_snapshots" and value == "[]"
            or field == "gaps" and value == "[{}]"):
        assert store.latest_receipt(CIK)[field] == json.loads(value)
        assert store.receipt(CIK, receipt_id)[field] == json.loads(value)
        return
    before = store.paths.market_db_path.read_bytes()
    for read in (lambda: store.latest_receipt(CIK), lambda: store.receipt(CIK, receipt_id)):
        with pytest.raises(ValueError, match="^sec_research_receipt_binding_invalid$"):
            read()
    assert store.paths.market_db_path.read_bytes() == before


@pytest.mark.parametrize("changes", [
    {"completed": '["submissions", "submissions"]'},
    {"pending": '["companyfacts", "companyfacts"]'},
    {"completed": '["submissions"]', "pending": '["submissions"]'},
    {"completed": '["../PRIVATE"]'},
    {"pending": '["CIK0000789019-submissions-001.json"]'},
    {"completed": '["submissions"]', "source_snapshots": '{"companyfacts": {}}'},
    {"source_snapshots": '{"submissions": {}}'},
    {"observed_at": "PRIVATE invalid time"},
    {"recorded_at": "2026-09-11T00:00:00"},
    {"receipt_id": 0},
])
def test_receipt_reads_reject_invalid_canonical_relationships(store, changes):
    insert_stored_receipt(store, **changes)
    with pytest.raises(ValueError, match="^sec_research_receipt_binding_invalid$"):
        store.latest_receipt(CIK)


@pytest.mark.parametrize("binding", [None, 1, [], {}, {"snapshot_id": "PRIVATE"},
    {"snapshot_id": "secsnapshot_" + "0" * 64, "observed_at": None},
    {"snapshot_id": "secsnapshot_" + "0" * 64, "observed_at": WHEN, "extra": 1}])
def test_receipt_reads_validate_inner_snapshot_binding(store, binding):
    receipt_id = insert_stored_receipt(store, completed='["submissions"]',
                                      source_snapshots=json.dumps({"submissions": binding}))
    with pytest.raises(ValueError, match="^sec_research_receipt_binding_invalid$"):
        store.receipt(CIK, receipt_id)


@pytest.mark.parametrize("completed", [[], ["submissions"]])
def test_receipt_reads_preserve_explicit_unbound_mapping(store, completed):
    receipt_id = insert_stored_receipt(store, completed=json.dumps(completed))
    saved = store.latest_receipt(CIK)
    assert saved["source_snapshots"] == {}
    assert saved["completed"] == completed
    assert store.receipt(CIK, receipt_id) == saved
