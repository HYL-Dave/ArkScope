"""Read-only recovery selection never turns capture gaps into portfolio facts."""

from datetime import date, datetime, timezone
import hashlib
import json
import sqlite3

import pytest

from src import sa_capture_store


AS_OF = "2026-09-25"
DISCLOSURE = (
    "Analyst's Disclosure: I/we have no stock, option or similar derivative "
    "position in any of the companies mentioned, and no plans to initiate any "
    "such positions within the next 72 hours. I wrote this article myself, "
    "and it expresses my own opinions. I am not receiving compensation for it."
)
NARRATIVE = (
    "The company increased revenue as customers renewed multiyear contracts. "
    "Operating margins improved because the newer product required less support. "
    "Management expects slower expansion next quarter as larger customers delay "
    "purchases. We consider the valuation reasonable, but weaker renewals would "
    "undermine the investment thesis. Free cash flow remains positive after "
    "capital spending, giving the company room to invest without issuing debt."
)


def build(path, **kwargs):
    from src.sa.article_body_recovery import build_recovery_manifest
    from src.sa.article_acquisition_settings import ArticleAcquisitionSettings

    return build_recovery_manifest(path, settings=ArticleAcquisitionSettings(body_lookback_days=365),
        scope_context={"status": "ok", "context_id": "manifest-unit-authority"}, **kwargs)


@pytest.fixture(autouse=True)
def accepted_scope_for_manifest_unit_tests(monkeypatch):
    # This module isolates body quality, URL, age and snapshot assembly. Real
    # cross-store authority, defaults and rejection paths have their own suite.
    from src.sa import article_acquisition_scope
    monkeypatch.setattr(article_acquisition_scope, "decide_article_acquisition", lambda *a, **kw: {
        "allowed": True, "reason_code": None, "effective_membership": "unknown",
        "context_id": "manifest-unit-authority",
    })


@pytest.fixture
def capture(tmp_path):
    path = tmp_path / "capture.db"
    conn = sa_capture_store.connect(str(path))
    yield path, conn
    conn.close()


def pick(conn, lineage, symbol="KEEP", picked="2024-01-10", *,
         status="current", stale=0, canonical=None, company=None):
    conn.execute(
        "INSERT OR IGNORE INTO sa_pick_lineages "
        "(lineage_id, symbol_key, picked_date, created_at) VALUES (?, ?, ?, ?)",
        (lineage, symbol, picked, picked),
    )
    conn.execute(
        "INSERT INTO sa_alpha_picks "
        "(lineage_id, symbol, company, picked_date, portfolio_status, is_stale, "
        "canonical_article_id, closed_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (lineage, symbol, company or symbol + " Corporation", picked, status,
         stale, canonical, "2025-01-01" if status == "closed" else None),
    )


def article(conn, aid, *, published="2026-09-01", ticker=None, listed=None,
            detail=None, title="Portfolio review", body=None, url=None,
            article_type="analysis"):
    conn.execute(
        "INSERT INTO sa_articles "
        "(article_id, url, title, published_date, ticker, list_ticker, "
        "detail_ticker, body_markdown, article_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (aid, url or f"https://seekingalpha.com/alpha-picks/articles/{aid}-review",
         title, published, ticker, listed, detail, body, article_type),
    )


def link(conn, lid, lineage, aid, *, role="entry", revoked=None):
    conn.execute(
        "INSERT INTO sa_pick_article_links "
        "(link_id, lineage_id, article_id, role, event_anchor_date, link_source, "
        "evidence_codes, linked_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (lid, lineage, aid, role, "2024-01-10", "user", '["user_selected"]',
         "2026-09-01", revoked),
    )


def finish(capture):
    path, conn = capture
    conn.commit()
    return build(path, as_of=AS_OF)


def by_id(result, bucket="targets"):
    return {row["article_id"]: row for row in result[bucket]}


def test_missing_database_is_typed_and_creates_nothing(tmp_path):
    root = tmp_path / "does-not-exist"
    result = build(root / "capture.db", as_of=AS_OF)
    assert result["status"] == "unavailable"
    assert result["error_code"] == "sa_article_body_recovery_capture_missing"
    assert result["targets"] == []
    assert not root.exists()


def test_readonly_transaction_and_no_schema_install(capture, monkeypatch):
    path, conn = capture
    article(conn, "1001")
    conn.commit()
    before = list(conn.iterdump())
    observed = []
    real_connect = sqlite3.connect

    def inspect(database, *args, **kwargs):
        assert database == path.resolve().as_uri() + "?mode=ro"
        assert kwargs.get("uri") is True
        reader = real_connect(database, *args, **kwargs)
        reader.set_trace_callback(observed.append)
        return reader

    def no_install(*args, **kwargs):
        pytest.fail("preview attempted to open the schema-installing capture store")

    monkeypatch.setattr(sqlite3, "connect", inspect)
    monkeypatch.setattr(sa_capture_store, "connect", no_install)
    result = build(path, as_of=AS_OF)
    assert result["status"] == "ok"
    assert observed[0:2] == ["PRAGMA query_only=ON", "BEGIN"]
    assert all(sql.lstrip().split()[0].upper() in {"PRAGMA", "BEGIN", "SELECT", "WITH"}
               for sql in observed)
    assert list(conn.iterdump()) == before


def test_incomplete_schema_is_unavailable_and_unchanged(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sa_articles(article_id TEXT)")
    before = path.read_bytes()
    result = build(path, as_of=AS_OF)
    assert result["status"] == "unavailable"
    assert result["error_code"] == "sa_article_body_recovery_schema_unavailable"
    assert path.read_bytes() == before


def test_priorities_include_old_current_entries_and_all_recent_invalid(capture):
    _, conn = capture
    pick(conn, 1, canonical="1001")
    article(conn, "1001", published="2020-01-01")
    article(conn, "1002", ticker="KEEP")
    article(conn, "1003", title="Our market outlook", article_type="analysis")
    article(conn, "1004", title="Team changes", article_type=None, body=DISCLOSURE)
    article(conn, "1005", published="2023-01-01", ticker="KEEP")
    article(conn, "1006", published="2025-09-25", article_type="unexpected_type")
    article(conn, "1007", published="2025-09-24")
    result = finish(capture)
    assert [(r["article_id"], r["priority"]) for r in result["targets"]] == [
        ("1001", 1), ("1002", 2), ("1003", 3), ("1004", 3), ("1006", 3),
    ]
    assert set(by_id(result, "held")) == {"1005", "1007"}
    assert all(row["disposition"] == "hold" for row in result["held"])
    assert result["as_of"] == AS_OF
    assert result["cutoff"] == "2025-09-25"
    assert result["scope"]["recent_days"] == 365
    assert result["scope"]["entry_candidate_days"] == 3
    assert result["counts"]["articles"] == 7
    assert result["counts"]["targets"] == 5
    assert result["counts"]["held"] == 2
    assert result["counts"]["by_priority"] == {"1": 1, "2": 1, "3": 3}


def test_accepted_links_keep_multiple_cohorts_and_override_canonical_guess(capture):
    _, conn = capture
    pick(conn, 1, picked="2023-01-10", canonical="1002")
    pick(conn, 2, picked="2024-01-10")
    pick(conn, 3, "OTHER", picked="2022-07-10")
    article(conn, "1001", published="2019-01-01", listed="PROVIDER")
    article(conn, "1002", published="2023-01-10", ticker="KEEP")
    link(conn, 1, 1, "1001")
    link(conn, 2, 2, "1001")
    link(conn, 3, 3, "1001", role="update")
    result = finish(capture)
    item = by_id(result)["1001"]
    assert item["priority"] == 1
    accepted = [m for m in item["cohort_memberships"] if m["basis"] == "accepted_link"]
    assert [(m["symbol"], m["picked_date"], m["role"], m["link_id"])
            for m in accepted] == [
        ("KEEP", "2023-01-10", "entry", 1),
        ("KEEP", "2024-01-10", "entry", 2),
        ("OTHER", "2022-07-10", "update", 3),
    ]
    assert all(m["evidence_codes"] == ["user_selected"] for m in accepted)
    assert "1002" in by_id(result, "held")


def test_stale_membership_is_unknown_and_closed_requires_observation(capture):
    _, conn = capture
    pick(conn, 1, "STALE", stale=1, canonical="1001")
    pick(conn, 2, "CLOSED", status="closed", canonical="1002")
    pick(conn, 3, "BOTH", canonical="1003")
    pick(conn, 3, "BOTH", status="closed")
    article(conn, "1001", published="2024-01-10", ticker="STALE")
    article(conn, "1002", published="2024-01-10", ticker="CLOSED")
    article(conn, "1003", published="2020-01-01")
    article(conn, "1004", ticker="STALE")
    article(conn, "1005", ticker="NEVER")
    result = finish(capture)
    assert set(by_id(result)) == {"1003", "1004", "1005"}
    assert by_id(result)["1004"]["priority"] == 3
    assert by_id(result)["1005"]["cohort_memberships"] == []
    states = {m["symbol"]: m["membership_status"] for m in result["cohorts"]}
    assert states == {"BOTH": "current", "CLOSED": "closed", "STALE": "unknown"}
    assert by_id(result, "held")["1001"]["cohort_memberships"][0]["membership_status"] == "unknown"


@pytest.mark.parametrize("body", [NARRATIVE, NARRATIVE + "\n\n" + DISCLOSURE],
                         ids=["narrative", "narrative-with-disclosure"])
@pytest.mark.parametrize("published", ["2020-01-01", "2026-09-01"])
def test_narrative_bodies_are_preserved_regardless_of_age(capture, body, published):
    _, conn = capture
    pick(conn, 1, canonical="1001")
    article(conn, "1001", body=body, published=published)
    result = finish(capture)
    assert result["targets"] == result["held"] == []
    item = by_id(result, "excluded")["1001"]
    assert "body_available" in item["reasons"]
    assert item["body_assessment"]["status"] == "available"
    assert item["body_assessment"]["completeness"] == "not_verified"
    assert item["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()


@pytest.mark.parametrize("fields, matched", [
    ({"ticker": "keep"}, True),
    ({"listed": "KEEP", "detail": "KEEP"}, True),
    ({"detail": "KEEP"}, True),
    ({"title": "KEEP: A company review"}, True),
    ({"title": "Keep Corporation expands capacity"}, True),
    ({"title": "A stock buy without an identity"}, False),
    ({"title": "KEEPER: A company review"}, False),
    ({"title": "Keep Corporations expands capacity"}, False),
    ({"title": "KEEP.A: A company review"}, False),
    ({"title": "KEEP-B: A company review"}, False),
    ({"title": "We keep our investments"}, False),
    ({"listed": "KEEP", "detail": "OTHER", "title": "KEEP: New buy"}, False),
    ({"listed": "OTHER", "ticker": "KEEP", "title": "KEEP: New buy"}, False),
])
def test_old_entry_fallback_requires_conservative_identity_near_pick_date(capture, fields, matched):
    _, conn = capture
    pick(conn, 1, company="Keep Corporation")
    article(conn, "1001", published="2024-01-13", **fields)
    result = finish(capture)
    assert bool(result["targets"]) is matched
    if matched:
        item = result["targets"][0]
        assert item["priority"] == 1
        assert "current_cohort_entry_candidate" in item["reasons"]
        candidate = next(m for m in item["cohort_memberships"] if m["basis"] == "entry_candidate")
        assert candidate["role"] is None
        assert candidate["date_distance_days"] == 3
    else:
        assert [r["article_id"] for r in result["held"]] == ["1001"]


@pytest.mark.parametrize("title, matched", [
    ("A market review", False), ("A: Market review", True),
    ("A (NYSE:A) investment", True), ("We discuss $A today", True),
    ("Market review for a", False), ("New BAC position", False),
])
def test_short_ticker_requires_explicit_title_not_ordinary_word(capture, title, matched):
    _, conn = capture
    pick(conn, 1, "A", company="Agilent Technologies")
    article(conn, "1001", title=title, published="2024-01-10")
    assert bool(finish(capture)["targets"]) is matched


def test_no_ever_pick_expansion_revoked_roles_or_title_role_acceptance(capture):
    _, conn = capture
    pick(conn, 1)
    article(conn, "1001", published="2024-01-14", ticker="KEEP", title="KEEP: Stock Buy")
    article(conn, "1002", published="2020-01-01", ticker="KEEP", title="KEEP: Stock Buy")
    article(conn, "1003", published=None, ticker="KEEP", title="KEEP: Stock Buy")
    article(conn, "1004", published="2024-01-10", ticker="KEEP", title="KEEP: Earnings")
    article(conn, "1005", published="2020-01-01")
    link(conn, 1, 1, "1005", revoked="2026-09-02")
    result = finish(capture)
    assert set(by_id(result)) == {"1004"}
    assert all(m["role"] is None for m in by_id(result)["1004"]["cohort_memberships"])
    assert set(by_id(result, "held")) == {"1001", "1002", "1003", "1005"}


@pytest.mark.parametrize("url", [
    "https://example.com/alpha-picks/articles/1001-review",
    "https://seekingalpha.com.evil.test/article/1001",
    "https://seekingalpha.com@evil.test/article/1001",
    "https://user@seekingalpha.com/article/1001",
    "http://seekingalpha.com/article/1001",
    "https://seekingalpha.com:444/article/1001",
    "https://seekingalpha.com/article/1002-review",
    "https://seekingalpha.com/article/1001-review/extra",
    "https://seekingalpha.com/article/1001-..%2F..%2Fsettings",
    "https://seekingalpha.com/article/1001-review?next=https://evil.test",
    "https://seekingalpha.com/article/1001#comments",
    "https://seekingalpha.com/news/1001",
    "https://seekingalpha.com/article/1001\\evil",
    "https://seekingalpha.com/article/1001\n",
    "\x00https://seekingalpha.com/article/1001",
    "https://seekingalpha.com/article/1001?",
    "/alpha-picks/articles/1001-review",
    "javascript:alert(1)",
])
def test_unsafe_or_mismatched_url_is_typed_exclusion(capture, url):
    _, conn = capture
    article(conn, "1001", url=url)
    result = finish(capture)
    assert result["targets"] == []
    item = by_id(result, "excluded")["1001"]
    assert item["reason_code"] == "sa_article_body_recovery_url_invalid"
    assert item["url"] is None


@pytest.mark.parametrize("url", [
    "https://seekingalpha.com/article/1001",
    "https://seekingalpha.com/article/1001-review",
    "https://seekingalpha.com/alpha-picks/articles/1001-review",
])
def test_safe_article_routes_matching_id_are_retained(capture, url):
    _, conn = capture
    article(conn, "1001", url=url)
    assert finish(capture)["targets"][0]["url"] == url


def test_manifest_has_no_body_or_disclosure_prose_and_hashes_snapshot(capture):
    _, conn = capture
    article(conn, "1002", body=DISCLOSURE)
    article(conn, "1001", body="   ")
    first = finish(capture)
    assert [r["article_id"] for r in first["targets"]] == ["1001", "1002"]
    encoded = json.dumps(first)
    assert DISCLOSURE not in encoded
    assert "Analyst's Disclosure" not in encoded
    assert "body_markdown" not in encoded
    item = by_id(first)["1002"]
    assert item["body_sha256"] == hashlib.sha256(DISCLOSURE.encode()).hexdigest()
    assert item["body_assessment"]["assessment_version"] == 2
    assert len(first["manifest_id"]) == 64
    assert finish(capture) == first
    conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='1002'", (DISCLOSURE + "\n",))
    second = finish(capture)
    assert first["manifest_id"] != second["manifest_id"]
    assert first["counts"] == second["counts"]


def test_default_as_of_is_date_only_and_same_day_builds_are_stable(capture, monkeypatch):
    from src.sa import article_body_recovery as recovery

    _, conn = capture
    article(conn, "1001")
    conn.commit()

    class Clock(datetime):
        hour = 1

        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 25, cls.hour, tzinfo=timezone.utc)

    monkeypatch.setattr(recovery, "datetime", Clock)
    first = build(capture[0])
    Clock.hour = 23
    assert build(capture[0]) == first
    assert first["as_of"] == AS_OF
    assert build(capture[0], as_of=date(2026, 9, 25)) == first


def test_dates_outside_snapshot_are_not_misrepresented_as_recent(capture):
    _, conn = capture
    article(conn, "1001", published="2026-09-26")
    article(conn, "1002", published="not-a-date")
    article(conn, "1003", published="2026-09-25T23:59:00Z")
    result = finish(capture)
    assert set(by_id(result)) == {"1003"}
    assert "published_after_as_of" in by_id(result, "held")["1001"]["reasons"]
    assert "published_date_unknown" in by_id(result, "held")["1002"]["reasons"]


@pytest.mark.parametrize("as_of", ["not-a-date", "2026-02-30", 123, True])
def test_invalid_as_of_is_typed_without_creating_database(tmp_path, as_of):
    path = tmp_path / "absent.db"
    result = build(path, as_of=as_of)
    assert result["error_code"] == "sa_article_body_recovery_as_of_invalid"
    assert not path.exists()


def test_article_body_membership_and_links_share_one_read_snapshot(capture, monkeypatch):
    path, conn = capture
    pick(conn, 1)
    article(conn, "1001", published="2020-01-01", body=DISCLOSURE)
    link(conn, 1, 1, "1001")
    conn.commit()
    real_connect = sqlite3.connect
    changed = False

    def change_after_article_read(sql):
        nonlocal changed
        if "FROM sa_pick_lineages ORDER BY" not in sql or changed:
            return
        changed = True
        with real_connect(str(path)) as writer:
            writer.execute("UPDATE sa_alpha_picks SET is_stale=1")
            writer.execute("UPDATE sa_pick_article_links SET revoked_at='2026-09-25'")
            writer.execute("UPDATE sa_articles SET body_markdown=?", (NARRATIVE,))

    def observe(database, *args, **kwargs):
        reader = real_connect(database, *args, **kwargs)
        reader.set_trace_callback(change_after_article_read)
        return reader

    monkeypatch.setattr(sqlite3, "connect", observe)
    first = build(path, as_of=AS_OF)
    assert changed
    assert [r["article_id"] for r in first["targets"]] == ["1001"]
    assert first["targets"][0]["body_sha256"] == hashlib.sha256(DISCLOSURE.encode()).hexdigest()
    second = build(path, as_of=AS_OF)
    assert second["targets"] == []
    assert second["cohorts"][0]["membership_status"] == "unknown"


@pytest.mark.parametrize("basis", ["canonical", "accepted", "candidate"])
def test_future_entry_is_held_even_when_cohort_is_current(capture, basis):
    _, conn = capture
    pick(conn, 1, picked="2026-09-25", canonical="1001" if basis == "canonical" else None)
    article(conn, "1001", published="2026-09-26", ticker="KEEP")
    if basis == "accepted":
        link(conn, 1, 1, "1001")
    result = finish(capture)
    assert result["targets"] == []
    assert "published_after_as_of" in result["held"][0]["reasons"]


def test_recent_article_before_pick_is_not_a_followup(capture):
    _, conn = capture
    pick(conn, 1, picked="2026-09-15")
    article(conn, "1001", published="2026-09-01", ticker="KEEP")
    item = finish(capture)["targets"][0]
    assert item["priority"] == 3
    assert "recent_current_pick_followup" not in item["reasons"]


def test_valid_body_with_invalid_url_is_preserved_and_url_exclusion_is_typed(capture):
    _, conn = capture
    article(conn, "1001", body=NARRATIVE, url="https://evil.test/article/1001")
    result = finish(capture)
    assert result["targets"] == result["held"] == []
    item = result["excluded"][0]
    assert item["reason_code"] == "sa_article_body_recovery_url_invalid"
    assert "body_available" in item["reasons"]


@pytest.mark.parametrize("evidence", [
    "null", "42", '{"prose": "private source text"}', "{broken",
    pytest.param("[" * 2000 + "]" * 2000, id="deeply-nested"),
])
def test_nonlist_evidence_json_never_leaks_prose_or_crashes(capture, evidence):
    _, conn = capture
    pick(conn, 1)
    article(conn, "1001", published="2020-01-01")
    link(conn, 1, 1, "1001")
    conn.execute("PRAGMA ignore_check_constraints=ON")
    conn.execute("UPDATE sa_pick_article_links SET evidence_codes=?", (evidence,))
    result = finish(capture)
    assert result["status"] == "ok"
    accepted = result["targets"][0]["cohort_memberships"][0]
    assert accepted["link_id"] == 1
    assert accepted["evidence_codes"] == []
    assert accepted["evidence_status"] == "unknown"
    assert "private source text" not in json.dumps(result)


def test_newest_first_within_priorities_with_accepted_entries_before_candidates(capture):
    _, conn = capture
    pick(conn, 1)
    pick(conn, 2, "CANDIDATE", picked="2024-01-10")
    article(conn, "1009", published="2020-01-01")
    link(conn, 1, 1, "1009")
    article(conn, "1001", published="2024-01-10", ticker="CANDIDATE")
    article(conn, "1002", published="2026-08-01", ticker="KEEP")
    article(conn, "1003", published="2026-09-21", ticker="KEEP")
    article(conn, "1004", published="2026-09-24")
    article(conn, "1005", published="2026-09-24")
    article(conn, "1006", published="2026-09-20")
    assert [i["article_id"] for i in finish(capture)["targets"]] == [
        "1009", "1001", "1003", "1002", "1004", "1005", "1006",
    ]


def test_latest_snapshot_is_retained_evidence_not_a_freshness_certification(capture):
    _, conn = capture
    pick(conn, 1)
    pick(conn, 1, status="closed")
    conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot='2026-09-20T23:00:00-04:00' "
                 "WHERE portfolio_status='current'")
    conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot='2026-09-21T01:00:00Z' "
                 "WHERE portfolio_status='closed'")
    article(conn, "1001", ticker="KEEP")
    result = finish(capture)
    cohort = result["cohorts"][0]
    assert cohort["latest_snapshot_at"] == "2026-09-21T03:00:00+00:00"
    assert cohort["observations"][0]["last_seen_snapshot"] == "2026-09-20T23:00:00-04:00"
    assert result["targets"][0]["cohort_memberships"][0]["latest_snapshot_at"] == cohort["latest_snapshot_at"]
    assert result["scope"]["membership_basis"] == "retained_snapshot_not_historical_reconstruction"


def test_missing_optional_snapshot_column_does_not_require_migration(capture):
    _, conn = capture
    pick(conn, 1)
    article(conn, "1001", ticker="KEEP")
    conn.execute("DROP INDEX idx_sa_picks_snapshot")
    conn.execute("ALTER TABLE sa_alpha_picks DROP COLUMN last_seen_snapshot")
    result = finish(capture)
    assert result["status"] == "ok"
    assert result["cohorts"][0]["latest_snapshot_at"] is None
