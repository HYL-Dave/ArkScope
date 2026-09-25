"""Retained research is paged evidence, not acquisition or schema initialization."""

import asyncio
from contextlib import closing
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import sa_capture_store
from src.portfolio_state import BrokerPosition, PortfolioStore
from src.tools.backends.sa_capture_backend import SACaptureBackend
from src.tools.data_access import DataAccessLayer
from src.tools.portfolio_holdings_tools import get_portfolio_holdings
from src.tools.sa_tools import get_sa_article_detail, get_sa_comment_focus
# eventkit needs an event loop when first imported, before channel tests run asyncio.run.
from src import portfolio_ibkr


def _write(path, sql, parameters=()):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(sql, parameters)
        conn.commit()


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def captured(tmp_path, monkeypatch):
    path = tmp_path / "sa.db"
    conn = sa_capture_store.connect(str(path))
    body = "First paragraph.\n\n" + "Retained evidence. " * 900
    conn.execute(
        "INSERT INTO sa_articles (article_id, url, title, ticker, body_markdown, "
        "detail_fetched_at, comments_count, comment_recovery_state) "
        "VALUES ('123', 'https://seekingalpha.com/article/123-example', 'Example', "
        "'AMD', ?, '2026-09-20T12:00:00Z', 9, 'pending')", (body,),
    )
    stamp = sa_capture_store.now_ts()
    conn.execute("UPDATE sa_articles SET published_date=?", (stamp[:10],))
    for i in range(5):
        conn.execute(
            "INSERT INTO sa_article_comments (article_id, comment_id, parent_comment_id, "
            "comment_text, comment_date) VALUES ('123', ?, ?, ?, ?)",
            (f"c{i}", None if i == 0 else "c0", "Discussion " * (1000 if i == 1 else 5),
             stamp if i < 4 else None),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr("src.tools.sa_tools._is_sa_enabled", lambda: True)
    dal = DataAccessLayer(backend=SACaptureBackend(
        sa_db=str(path), market_db=str(tmp_path / "market.db")))
    return dal, path, body


def test_article_default_is_bounded_and_does_not_claim_comments_complete(captured):
    dal, _, body = captured
    result = get_sa_article_detail(dal, "123")
    assert result["body_markdown"] == body[:4000]
    assert result["status"] == "ok"
    assert result["pagination"]["next_body_offset"] == 4000
    assert result["coverage"]["comments"]["status"] == "partial"
    assert result["coverage"]["comments"]["complete"] is None
    assert len(result["comments"]) == 2
    assert result["comments"][1]["next_text_offset"] == 500
    assert len(json.dumps(result, ensure_ascii=False)) < 8_000


def test_missing_holdings_read_does_not_create_profile_or_manual_account(tmp_path, monkeypatch):
    path = tmp_path / "missing" / "profile.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(path))
    result = get_portfolio_holdings()
    assert not path.parent.exists()
    assert result["error_code"] == "portfolio_snapshot_missing"


def test_full_body_can_be_reassembled_without_gaps_and_ui_reader_is_unchanged(captured):
    dal, path, body = captured
    before = _digest(path)
    first = get_sa_article_detail(dal, "123", comment_limit=0)
    pages, page = [], first
    while True:
        pages.append(page["body_markdown"])
        offset = page["pagination"]["next_body_offset"]
        if offset is None:
            break
        page = get_sa_article_detail(dal, "123", body_offset=offset, comment_limit=0,
                                     snapshot_id=first["snapshot_id"])
        assert page["snapshot_id"] == first["snapshot_id"]
    assert "".join(pages) == body
    full = dal.get_sa_article_detail("123")
    assert full["body_markdown"] == body and len(full["comments"]) == 5
    assert _digest(path) == before


def test_comment_paging_is_stable_for_equal_or_missing_dates_and_parent_is_addressable(captured):
    dal, _, _ = captured
    first = get_sa_article_detail(dal, "123", body_limit=0)
    ids, page = [], first
    while True:
        ids.extend(row["comment_id"] for row in page["comments"])
        offset = page["pagination"]["next_comment_offset"]
        if offset is None:
            break
        page = get_sa_article_detail(dal, "123", body_limit=0, comment_offset=offset,
                                     snapshot_id=first["snapshot_id"])
    assert ids == [f"c{i}" for i in range(5)]
    parent = get_sa_article_detail(dal, "123", body_limit=0, comment_id="c0", snapshot_id=first["snapshot_id"])
    assert parent["comments"][0]["comment_id"] == "c0"
    assert parent["comments"][0]["parent_comment_id"] is None
    assert first["comments"][1]["parent_in_store"] is True


def test_long_unicode_comment_is_fully_retrievable_not_a_permanent_preview(captured):
    dal, path, _ = captured
    text = "\u4e2d\u6587\n\U0001f4ca\n" * 403
    _write(path, "UPDATE sa_article_comments SET comment_text=?, parent_comment_id='absent' WHERE comment_id='c1'", (text,))
    first = get_sa_article_detail(dal, "123", body_limit=0, comment_id="c1")
    pieces, page = [], first
    while True:
        comment = page["comments"][0]
        pieces.append(comment["comment_text"])
        assert comment["parent_in_store"] is False
        assert comment["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        offset = comment["next_text_offset"]
        if offset is None:
            break
        page = get_sa_article_detail(dal, "123", body_limit=0, comment_id="c1", comment_text_offset=offset,
                                     snapshot_id=first["snapshot_id"])
    assert "".join(pieces) == text


@pytest.mark.parametrize("sql", [
    "UPDATE sa_articles SET body_markdown='Changed' WHERE article_id='123'",
    "UPDATE sa_articles SET title='Changed' WHERE article_id='123'",
    "UPDATE sa_article_comments SET comment_text='Edited' WHERE comment_id='c4'",
    "UPDATE sa_article_comments SET upvotes=20 WHERE comment_id='c0'",
    "DELETE FROM sa_article_comments WHERE comment_id='c4'",
    "UPDATE sa_articles SET comments_fetched_at='2026-09-21T12:00:00Z' WHERE article_id='123'",
])
def test_article_change_between_pages_is_not_silently_joined(captured, sql):
    dal, path, _ = captured
    first = get_sa_article_detail(dal, "123")
    _write(path, sql)
    result = get_sa_article_detail(dal, "123", snapshot_id=first["snapshot_id"])
    assert result["error_code"] == "sa_article_snapshot_changed"
    assert "body_markdown" not in result and "comments" not in result


@pytest.mark.parametrize("query,code", [
    ({"body_offset": -1}, "pagination_invalid"),
    ({"body_limit": True}, "pagination_invalid"),
    ({"comment_offset": "0"}, "pagination_invalid"),
    ({"comment_text_limit": 0}, "pagination_invalid"),
    ({"comment_limit": 2**63}, "pagination_invalid"),
    ({"snapshot_id": "../wrong"}, "snapshot_id_invalid"),
    ({"body_offset": 1}, "snapshot_required"),
    ({"comment_offset": 1}, "snapshot_required"),
    ({"comment_text_offset": 1}, "snapshot_required"),
    ({"comment_id": []}, "comment_id_invalid"),
    ({"body_limit": 0, "comment_limit": 0}, "pagination_invalid"),
    ({"comment_id": "missing"}, "comment_not_found"),
])
def test_article_bad_queries_are_typed_not_coerced(captured, query, code):
    assert get_sa_article_detail(captured[0], "123", **query)["error_code"] == "sa_article_" + code


def test_out_of_range_pages_and_unaddressed_comment_text_are_rejected(captured):
    dal, _, body = captured
    snapshot = get_sa_article_detail(dal, "123")["snapshot_id"]
    for query in ({"body_offset": len(body) + 1}, {"comment_offset": 6}, {"comment_id": "c0", "comment_text_offset": 999}):
        result = get_sa_article_detail(dal, "123", snapshot_id=snapshot, **query)
        assert result["error_code"] == "sa_article_offset_out_of_range"
    result = get_sa_article_detail(dal, "123", comment_text_offset=1, snapshot_id=snapshot)
    assert result["error_code"] == "sa_article_comment_id_required"


@pytest.mark.parametrize("state,count,scan,expected", [
    ("repaired", 0, None, "not_captured"),
    ("repaired", 0, "2026-09-20T12:00:00Z", "observed_empty"),
    ("pending", 9, "2026-09-20T12:00:00Z", "partial"),
    ("unreachable_terminal", 9, "2026-09-20T12:00:00Z", "partial"),
])
def test_comment_capture_missingness_does_not_follow_body_success(captured, state, count, scan, expected):
    dal, path, _ = captured
    _write(path, "DELETE FROM sa_article_comments")
    _write(path, "UPDATE sa_articles SET comment_recovery_state=?, comments_count=?, "
                 "provider_comments_count_at_last_scan=?, comments_fetched_at=?", (state, count, count, scan))
    result = get_sa_article_detail(dal, "123")
    assert result["coverage"]["body"]["status"] == "available"
    assert result["coverage"]["comments"]["status"] == expected
    assert result["coverage"]["comments"]["complete"] is None


def test_comments_can_be_read_when_body_is_absent(captured):
    dal, path, _ = captured
    _write(path, "UPDATE sa_articles SET body_markdown=NULL, detail_fetched_at=NULL")
    result = get_sa_article_detail(dal, "123")
    assert result["coverage"]["body"]["status"] == "not_captured"
    assert result["comments"] and result["body_markdown"] == ""


def test_missing_or_invalid_sa_store_is_not_reported_as_no_discussion(tmp_path, monkeypatch):
    monkeypatch.setattr("src.tools.sa_tools._is_sa_enabled", lambda: True)
    path = tmp_path / "absent" / "sa.db"
    dal = SimpleNamespace(_backend=SimpleNamespace(_sa_db=path))
    assert get_sa_article_detail(dal, "123")["error_code"] == "sa_article_capture_missing"
    assert get_sa_comment_focus(dal)["error_code"] == "sa_comment_focus_store_missing"
    assert not path.parent.exists()
    path.parent.mkdir()
    _write(path, "CREATE TABLE unrelated (x)")
    before = _digest(path)
    assert get_sa_article_detail(dal, "123")["error_code"] == "sa_article_store_unavailable"
    assert get_sa_comment_focus(dal)["error_code"] == "sa_comment_focus_store_unavailable"
    assert _digest(path) == before


def test_sa_read_is_one_snapshot_even_if_writer_commits_during_hash(captured, monkeypatch):
    dal, path, body = captured
    original = sqlite3.connect
    changed = False

    class Reader(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            nonlocal changed
            if sql.startswith("SELECT comment_id") and not changed:
                changed = True
                with closing(original(path)) as writer:
                    writer.execute("UPDATE sa_articles SET body_markdown='new version'")
                    writer.execute("UPDATE sa_article_comments SET comment_text='new comment' WHERE comment_id='c0'")
                    writer.commit()
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=Reader))
    result = get_sa_article_detail(dal, "123")
    assert result["body_markdown"] == body[:4000]
    assert result["comments"][0]["comment_text"] == "Discussion " * 5
    assert get_sa_article_detail(dal, "123", snapshot_id=result["snapshot_id"])["error_code"] == "sa_article_snapshot_changed"


@pytest.fixture
def holdings(tmp_path, monkeypatch):
    path = tmp_path / "profile.db"
    store = PortfolioStore(path)
    account = store.ensure_manual_account()
    for i in range(13):
        store.upsert_manual_position(account_id=account.id, symbol=f"STK{i:02}", quantity=i + 1, currency="USD")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(path))
    return store, account, path


def test_holdings_pages_are_readonly_and_totals_are_not_page_totals(holdings):
    store, account, path = holdings
    expected = asdict(store.snapshot(included_only=True))
    before = _digest(path)
    first = get_portfolio_holdings(row_limit=4)
    positions, page = [], first
    while True:
        positions.extend(page["positions"])
        assert page["totals"] == expected["totals"]
        assert page["totals_scope"] == "all_open_positions_in_selected_accounts"
        assert page["totals_coverage"]["USD"]["position_count"] == 13
        assert page["totals_coverage"]["USD"]["market_value_count"] == 0
        offset = page["pagination"]["next_row_offset"]
        if offset is None:
            break
        page = get_portfolio_holdings(row_limit=4, row_offset=offset, snapshot_id=first["snapshot_id"])
    assert positions == expected["positions"]
    assert _digest(path) == before
    assert first["valuation_basis"] == "stored_values_not_live"
    assert first["accounts"][0]["id"] == account.id


def test_holdings_changes_and_scope_changes_invalidate_continuations(holdings):
    store, account, _ = holdings
    first = get_portfolio_holdings()
    assert get_portfolio_holdings(include_closed=True, snapshot_id=first["snapshot_id"])["error_code"] == "portfolio_snapshot_changed"
    store.upsert_manual_position(account_id=account.id, symbol="NEW", quantity=1, currency="USD")
    assert get_portfolio_holdings(row_offset=10, snapshot_id=first["snapshot_id"])["error_code"] == "portfolio_snapshot_changed"


@pytest.mark.parametrize("query,code", [
    ({"account_id": True}, "account_id_invalid"),
    ({"account_id": 999}, "account_not_found"),
    ({"include_closed": "false"}, "query_invalid"),
    ({"row_limit": 0}, "pagination_invalid"),
    ({"row_offset": -1}, "pagination_invalid"),
    ({"row_limit": 2**64}, "pagination_invalid"),
    ({"row_limit": 2.5}, "pagination_invalid"),
    ({"snapshot_id": "wrong"}, "snapshot_id_invalid"),
    ({"row_offset": 1}, "snapshot_required"),
])
def test_holdings_queries_have_explicit_failures(holdings, query, code):
    assert get_portfolio_holdings(**query)["error_code"] == "portfolio_" + code


def test_holdings_existing_uninitialized_profile_is_not_migrated(tmp_path, monkeypatch):
    path = tmp_path / "profile.db"
    _write(path, "CREATE TABLE other (x)")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(path))
    before = _digest(path)
    assert get_portfolio_holdings()["error_code"] == "portfolio_store_unavailable"
    assert _digest(path) == before


def test_empty_holdings_are_not_an_error_or_a_new_manual_account(tmp_path, monkeypatch):
    path = tmp_path / "profile.db"
    store = PortfolioStore(path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(path))
    before = _digest(path)
    result = get_portfolio_holdings()
    assert result["status"] == "ok" and not result["accounts"]
    assert result["empty_reason"] == "no_retained_positions_in_scope"
    assert not store.list_accounts(ensure_manual=False)
    assert _digest(path) == before


@pytest.mark.parametrize("currencies,base_expected", [(('USD', 'EUR'), None), (('USD', None), None), (('USD', 'USD'), 'USD')])
def test_holdings_never_sum_unverified_broker_base_currencies(tmp_path, monkeypatch, currencies, base_expected):
    path = tmp_path / "profile.db"
    store = PortfolioStore(path)
    for i, currency in enumerate(currencies):
        account = store.upsert_broker_account("ibkr", f"private-account-{i}", f"Account {i}")
        store.update_account(account.id, base_currency=currency)
        store.apply_broker_positions(account_id=account.id, positions=[BrokerPosition(
            broker="ibkr", broker_account_id=f"private-account-{i}", broker_con_id=str(i),
            symbol=f"STK{i}", asset_class="STK", quantity=1, market_value=100,
            market_value_base=100, unrealized_pnl_base=None,
        )], source="ibkr")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(path))
    result = get_portfolio_holdings()
    assert result["broker_base_currency"] == base_expected
    if base_expected is None:
        assert result["totals"]["broker_base"] is None
        assert result["totals_gaps"] == ["broker_base_currency_unverified"]
    else:
        assert result["totals"]["broker_base"] == {"market_value": 200.0, "unrealized_pnl": None}
        assert result["totals_gaps"] == ["broker_base_unrealized_pnl_incomplete"]
    assert "private-account-" not in json.dumps(result)


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_channels_can_read_article_then_complete_comment(captured, channel):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    dal, path, _ = captured
    before = _digest(path)
    feed = unwrap(asyncio.run(invoke(channel, "get_sa_feed", {"ticker": "AMD", "item_type": "article", "limit": 1}, dal)))
    article_id = feed["items"][0]["id"]
    first = unwrap(asyncio.run(invoke(channel, "get_sa_article_detail", {"article_id": article_id}, dal)))
    assert first["url"] == feed["items"][0]["url"]
    assert first["pagination"]["next_body_offset"] == 4000
    args = {"article_id": "123", "body_limit": 0, "comment_id": "c1", "comment_text_offset": 500,
            "snapshot_id": first["snapshot_id"]}
    next_page = unwrap(asyncio.run(invoke(channel, "get_sa_article_detail", args, dal)))
    assert next_page["comments"][0]["text_offset"] == 500
    assert next_page["source_ref"] == first["source_ref"]
    assert _digest(path) == before


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_channels_can_read_holdings_without_initialization_or_sync(holdings, channel, monkeypatch):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    monkeypatch.setattr(PortfolioStore, "_ensure_schema", Mock(side_effect=AssertionError("schema write")))
    monkeypatch.setattr(portfolio_ibkr, "read_ibkr_portfolio_snapshot", Mock(side_effect=AssertionError("broker access")))
    before = _digest(holdings[2])
    first = unwrap(asyncio.run(invoke(channel, "get_portfolio_holdings", {"row_limit": 2}, object())))
    assert len(first["positions"]) == 2 and first["pagination"]["total_rows"] == 13
    next_page = unwrap(asyncio.run(invoke(channel, "get_portfolio_holdings", {
        "row_limit": 2, "row_offset": 2, "snapshot_id": first["snapshot_id"]}, object())))
    assert next_page["positions"][0]["symbol"] == "STK02"
    assert _digest(holdings[2]) == before


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_channels_report_unscored_comment_backlog_without_starting_extraction(captured, channel, monkeypatch):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    monkeypatch.setattr("src.sa.comment_signal_backfill.run_backfill", Mock(side_effect=AssertionError("extraction")))
    result = unwrap(asyncio.run(invoke(channel, "get_sa_comment_focus", {"window_days": 90}, captured[0])))
    assert result["retrieval"] == "stored"
    assert result["empty_reason"] == "extraction_backlog_pending"
    assert result["required_action"] == "run_extract_sa_comment_signals_explicitly"


@pytest.mark.parametrize("tool,code", [("get_sa_article_detail", "sa_article"),
                                      ("get_sa_comment_focus", "sa_comment_focus"),
                                      ("get_portfolio_holdings", "portfolio")])
@pytest.mark.parametrize("wrapped", [False, True])
def test_compressor_does_not_slice_pages_even_if_overflow_storage_fails(tool, code, wrapped):
    from src.agents.shared.compressor.layers import apply_layer_0

    payload = json.dumps({"status": "ok", "snapshot_id": "f" * 64, "body": "x" * 5000})
    if wrapped:
        payload = f'<tool_output tool="{tool}">\n{payload}\n</tool_output>'
    result, _ = apply_layer_0(tool_name=tool, args={}, payload=payload, budget_chars=900,
                             overflow_store=SimpleNamespace(write=Mock(side_effect=OSError())))
    if wrapped:
        result = result.split("\n", 1)[1].rsplit("\n", 1)[0]
    value = json.loads(result)
    assert value["error_code"] == code + "_page_too_large"
    assert value["snapshot_id"] == "f" * 64 and "body" not in value


def test_raw_output_byte_limit_has_an_actionable_smaller_page(captured, monkeypatch):
    from src.tools import retained_read_results
    monkeypatch.setattr(retained_read_results, "MAX_OUTPUT_BYTES", 4000)
    first = get_sa_article_detail(captured[0], "123")
    assert first["error_code"] == "sa_article_page_too_large"
    smaller = get_sa_article_detail(captured[0], "123", body_limit=1, comment_limit=0,
                                    snapshot_id=first["snapshot_id"])
    assert smaller["status"] == "ok"


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
@pytest.mark.parametrize("value", [True, "2"])
def test_channel_does_not_coerce_bad_page_parameters_into_a_store_read(channel, value, monkeypatch):
    from tests.test_freshness_tool_channels import invoke

    read = Mock(side_effect=AssertionError("invalid input reached storage"))
    monkeypatch.setattr(PortfolioStore, "read_snapshot", read)
    assert asyncio.run(invoke(channel, "get_portfolio_holdings", {"row_limit": value}, object()))
    read.assert_not_called()


@pytest.mark.parametrize("tool", ["get_sa_article_detail", "get_sa_comment_focus", "get_portfolio_holdings"])
def test_summary_transcript_preserves_whole_read_or_typed_failure(tool):
    from src.agents.shared.compressor.transcript import format_messages_as_transcript
    value = {"status": "ok", "snapshot_id": "e" * 64, "text": "x" * 100_000}
    text = format_messages_as_transcript([{"role": "tool_result", "tool_name": tool, "content": json.dumps(value)}])
    result = json.loads(text.split("]: ", 1)[1])
    assert result["error_code"].endswith("_page_too_large") and result["snapshot_id"] == "e" * 64


def test_default_long_comment_page_fits_native_insertion_budget(captured):
    from src.agents.shared.compressor.layers import apply_layer_0
    from src.agents.config import AgentConfig

    dal, path, _ = captured
    _write(path, "UPDATE sa_article_comments SET comment_text=?", ("x" * 5000,))
    value = get_sa_article_detail(dal, "123")
    payload = '<tool_output tool="get_sa_article_detail">\n' + json.dumps(value) + '\n</tool_output>'
    result, record = apply_layer_0(tool_name="get_sa_article_detail", args={}, payload=payload,
                                  budget_chars=AgentConfig().compaction_layer_0_budget_chars,
                                  overflow_store=SimpleNamespace(write=Mock(side_effect=AssertionError())))
    assert result == payload and record is None


def test_sa_local_uri_special_characters_do_not_select_another_file(captured, tmp_path):
    import shutil
    dal, path, _ = captured
    renamed = tmp_path / "retained?# sa.db"
    shutil.copyfile(path, renamed)
    dal._backend._sa_db = str(renamed)
    assert get_sa_article_detail(dal, "123")["status"] == "ok"
    assert get_sa_comment_focus(dal)["status"] == "ok"


def test_holdings_read_is_one_snapshot_if_writer_changes_quantity(holdings, monkeypatch):
    _, _, path = holdings
    original = sqlite3.connect
    changed = False

    class Reader(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            nonlocal changed
            if sql.startswith("SELECT p.*") and not changed:
                changed = True
                with closing(original(path)) as writer:
                    writer.execute("UPDATE portfolio_positions SET quantity=999 WHERE symbol='STK00'")
                    writer.commit()
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=Reader))
    first = get_portfolio_holdings()
    assert first["positions"][0]["quantity"] == 1
    assert get_portfolio_holdings(snapshot_id=first["snapshot_id"])["error_code"] == "portfolio_snapshot_changed"


def test_all_exporters_admit_only_the_intended_new_tools_and_publish_paging():
    from src.auth_drivers.chatgpt_oauth_driver import _RESEARCH_READONLY_TOOLS as chatgpt
    from src.auth_drivers.claude_code_sdk_driver import _RESEARCH_READONLY_TOOLS as claude
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.openai_agent.tools import create_openai_tools
    from src.agents.shared.subagent import SUBAGENT_REGISTRY
    from src.tools.registry import create_default_registry

    required = {"get_sa_article_detail", "get_sa_comment_focus", "get_portfolio_holdings"}
    assert chatgpt == claude and len(chatgpt) == 27 and required <= chatgpt
    assert not {"save_report", "save_memory", "web_browse", "get_detailed_financials"} & chatgpt
    for name in ("deep_researcher", "data_summarizer"):
        assert required | {"get_sa_feed"} <= set(SUBAGENT_REGISTRY[name].tool_names)
    registry = create_default_registry()
    native_anthropic = {t["name"]: t["input_schema"]["properties"] for t in get_anthropic_tools()}
    native_openai = {t.name.removeprefix("tool_"): t.params_json_schema["properties"] for t in create_openai_tools(object())}
    for name in required:
        expected = {parameter.name for parameter in registry.get(name).parameters}
        assert expected == set(native_anthropic[name]) == set(native_openai[name])
