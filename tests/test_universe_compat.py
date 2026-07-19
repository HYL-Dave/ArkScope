"""Contracts for the reviewed legacy-universe compatibility bridge."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src import sa_capture_store
from src.active_universe import ActiveUniverseSnapshot, build_active_universe_snapshot
from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore, UniverseSourceAnnotation


FIXTURE = Path(__file__).parent / "fixtures" / "universe" / "tickers_core_legacy.json"
NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-07-19T12:00:00+00:00"
LEGACY_SOURCE = "legacy_config_seed"
SA_SOURCE = "sa_alpha_picks_current"


def _compat():
    return importlib.import_module("src.universe_compat")


def _fixture_document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _snapshot(
    tickers: tuple[str, ...],
    *,
    sources: dict[str, tuple[str, ...]] | None = None,
    generated_at: str = NOW_TEXT,
) -> ActiveUniverseSnapshot:
    source_map = sources or {ticker: ("manual_lists",) for ticker in tickers}
    return ActiveUniverseSnapshot(
        tickers=tickers,
        sources_by_ticker=source_map,
        source_status={},
        unavailable_sources=(),
        generated_at=generated_at,
    )


def _annotation(ticker: str, key: str, value: str) -> UniverseSourceAnnotation:
    return UniverseSourceAnnotation(
        source_key=LEGACY_SOURCE,
        ticker=ticker,
        annotation_key=key,
        annotation_value=value,
    )


def _review_preview():
    compat = _compat()
    snapshot = _snapshot(
        ("AAPL", "BTSG", "HAPN"),
        sources={
            "AAPL": ("manual_lists",),
            "BTSG": (SA_SOURCE,),
            "HAPN": ("portfolio_open",),
        },
    )
    return compat.build_legacy_preview(
        compat.parse_active_json(_fixture_document()),
        snapshot=snapshot,
        hidden_tickers={"ATGE"},
    )


def test_parse_active_json_preserves_paired_paths_and_ignores_reference_settings():
    compat = _compat()
    document = _fixture_document()
    document["tier1_core"]["core_platforms"]["tickers"].extend([" aapl ", ""])
    document["tier1_core"]["_ignored_group"] = {"tickers": ["IGNORED"]}
    document["tier1_core"]["malformed"] = {"tickers": "NOT-A-LIST"}
    document["unknown_tier"] = {"ignored": {"tickers": ["UNKNOWN"]}}

    entries = compat.parse_active_json(document)

    assert set(document["settings"]) == {
        "default_tier",
        "include_tier2",
        "include_tier3",
        "include_etf_benchmarks",
        "auto_expand_on_capacity",
        "max_tickers_per_request",
        "news_lookback_days",
    }
    assert entries == tuple(
        sorted(entries, key=lambda row: (row.ticker, row.tier, row.category_path))
    )
    assert [(row.ticker, row.tier, row.category_path) for row in entries] == [
        ("AAPL", "tier1_core", "tier1_core/core_platforms"),
        ("ATGE", "tier1_core", "tier1_core/review_candidates"),
        (
            "BTSG",
            "tier3_user_watchlist",
            "tier3_user_watchlist/sa_alpha_picks_auto",
        ),
        (
            "BTSG",
            "tier3_user_watchlist",
            "tier3_user_watchlist/seeking_picks_tech",
        ),
        ("LC", "tier1_core", "tier1_core/core_platforms"),
        ("OKTA", "tier2_expanded", "tier2_expanded/identity_access"),
        (
            "OKTA",
            "tier3_user_watchlist",
            "tier3_user_watchlist/sa_alpha_picks_auto",
        ),
    ]


def test_preview_classifies_hidden_overlap_json_only_and_db_only():
    compat = _compat()
    snapshot = _snapshot(
        ("AAPL", "HAPN", "MSFT", "OKTA"),
        sources={
            "AAPL": ("portfolio_open", "manual_lists", "portfolio_open"),
            "HAPN": ("portfolio_open",),
            "MSFT": ("manual_lists",),
            "OKTA": (LEGACY_SOURCE,),
        },
    )

    rows = compat.build_legacy_preview(
        compat.parse_active_json(_fixture_document()),
        snapshot=snapshot,
        hidden_tickers={" atge "},
    )

    assert [(row.ticker, row.classification) for row in rows] == [
        ("AAPL", "overlap"),
        ("ATGE", "hidden"),
        ("BTSG", "json_only"),
        ("HAPN", "db_only"),
        ("LC", "superseded_by_rename"),
        ("MSFT", "db_only"),
        ("OKTA", "overlap"),
    ]
    by_ticker = {row.ticker: row for row in rows}
    assert by_ticker["AAPL"].sources == ("manual_lists", "portfolio_open")
    assert by_ticker["ATGE"].default_action == "annotate_only"
    assert by_ticker["BTSG"].default_action == "requires_approval"
    assert by_ticker["BTSG"].category_paths == (
        "tier3_user_watchlist/sa_alpha_picks_auto",
        "tier3_user_watchlist/seeking_picks_tech",
    )
    assert by_ticker["HAPN"].category_paths == ()


def test_preview_classifies_lc_as_superseded_by_hapn_default_no_import():
    compat = _compat()
    for active_tickers in (("HAPN",), ()):
        rows = compat.build_legacy_preview(
            compat.parse_active_json(_fixture_document()),
            snapshot=_snapshot(active_tickers),
            hidden_tickers=(),
        )

        lc = next(row for row in rows if row.ticker == "LC")

        assert lc.classification == "superseded_by_rename"
        assert lc.superseded_by == "HAPN"
        assert lc.default_action == "do_not_import"
        with pytest.raises(ValueError, match="visible json_only"):
            compat.build_reviewed_import(rows, ("LC",))


def test_preview_treats_dirty_btsg_as_alpha_overlap_not_seed_membership():
    compat = _compat()
    rows = compat.build_legacy_preview(
        compat.parse_active_json(_fixture_document()),
        snapshot=_snapshot(("BTSG",), sources={"BTSG": (SA_SOURCE,)}),
        hidden_tickers=(),
    )

    btsg = next(row for row in rows if row.ticker == "BTSG")

    assert btsg.classification == "overlap"
    assert btsg.default_action == "annotate_only"
    assert btsg.sources == (SA_SOURCE,)
    assert LEGACY_SOURCE not in btsg.sources


def test_import_requires_explicit_visible_json_only_approval():
    compat = _compat()
    preview = _review_preview()

    assert compat.build_reviewed_import(preview, ()).approved_memberships == ()
    reviewed = compat.build_reviewed_import(preview, (" okta ", "OKTA"))
    assert reviewed.approved_memberships == ("OKTA",)

    for rejected in ("AAPL", "ATGE", "BTSG", "HAPN", "LC", "MISSING"):
        with pytest.raises(ValueError, match="visible json_only"):
            compat.build_reviewed_import(preview, (rejected,))


def test_import_writes_all_annotations_but_membership_only_for_approved_rows():
    compat = _compat()
    reviewed = compat.build_reviewed_import(_review_preview(), ("OKTA",))
    expected = {
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation("AAPL", "legacy_category", "tier1_core/core_platforms"),
        _annotation("ATGE", "legacy_tier", "tier1_core"),
        _annotation("ATGE", "legacy_category", "tier1_core/review_candidates"),
        _annotation("BTSG", "legacy_tier", "tier3_user_watchlist"),
        _annotation(
            "BTSG",
            "legacy_category",
            "tier3_user_watchlist/sa_alpha_picks_auto",
        ),
        _annotation(
            "BTSG",
            "legacy_category",
            "tier3_user_watchlist/seeking_picks_tech",
        ),
        _annotation("LC", "legacy_tier", "tier1_core"),
        _annotation("LC", "legacy_category", "tier1_core/core_platforms"),
        _annotation("OKTA", "legacy_tier", "tier2_expanded"),
        _annotation("OKTA", "legacy_tier", "tier3_user_watchlist"),
        _annotation("OKTA", "legacy_category", "tier2_expanded/identity_access"),
        _annotation(
            "OKTA",
            "legacy_category",
            "tier3_user_watchlist/sa_alpha_picks_auto",
        ),
    }

    assert reviewed.approved_memberships == ("OKTA",)
    assert set(reviewed.annotations) == expected
    assert reviewed.annotations == tuple(
        sorted(
            expected,
            key=lambda row: (
                row.source_key,
                row.ticker,
                row.annotation_key,
                row.annotation_value,
            ),
        )
    )


def test_export_preserves_category_paths_without_cartesian_pairs():
    compat = _compat()
    annotations = (
        _annotation("AAPL", "legacy_tier", "tier3_user_watchlist"),
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation(
            "AAPL", "legacy_category", "tier3_user_watchlist/seeking_picks_tech"
        ),
        _annotation("AAPL", "legacy_category", "tier1_core/core_platforms"),
    )

    document = compat.build_compat_export(_snapshot(("AAPL",)), annotations)

    assert document["tier1_core"] == {"core_platforms": {"tickers": ["AAPL"]}}
    assert document["tier2_expanded"] == {}
    assert document["tier3_user_watchlist"] == {
        "seeking_picks_tech": {"tickers": ["AAPL"]}
    }
    assert compat.flatten_generated_active_tickers(document) == {"AAPL"}


def test_export_places_unannotated_db_symbols_in_generated_group():
    compat = _compat()
    annotations = (
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation("AAPL", "legacy_category", "tier1_core/core_platforms"),
    )

    document = compat.build_compat_export(
        _snapshot(("AAPL", "MSFT", "NVDA")), annotations
    )

    assert document["tier1_core"] == {"core_platforms": {"tickers": ["AAPL"]}}
    assert document["tier3_user_watchlist"] == {
        "db_derived_active": {"tickers": ["MSFT", "NVDA"]}
    }
    assert compat.flatten_generated_active_tickers(document) == {
        "AAPL",
        "MSFT",
        "NVDA",
    }


def test_export_filters_hidden_reference_and_retired_settings():
    compat = _compat()
    annotations = (
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation("AAPL", "legacy_category", "tier1_core/core_platforms"),
        _annotation("ATGE", "legacy_tier", "tier1_core"),
        _annotation("ATGE", "legacy_category", "tier1_core/review_candidates"),
        _annotation("WBA", "legacy_tier", "tier2_expanded"),
        _annotation("WBA", "legacy_category", "tier2_expanded/legacy_reference"),
    )

    document = compat.build_compat_export(_snapshot(("AAPL",)), annotations)

    assert tuple(document) == (
        "_generated",
        "tier1_core",
        "tier2_expanded",
        "tier3_user_watchlist",
    )
    assert document["_generated"] == {
        "authority": "profile_state.db + sa_capture.db via active_universe",
        "warning": "Generated compatibility snapshot; manual edits have no runtime effect",
        "generated_at": NOW_TEXT,
    }
    assert compat.flatten_generated_active_tickers(document) == {"AAPL"}
    assert "settings" not in document
    assert "legacy_reference" not in document


def test_export_is_generated_deterministic_exact_and_manual_edits_are_inert(
    tmp_path,
):
    compat = _compat()
    profile_db = tmp_path / "profile_state.db"
    sa_db = tmp_path / "sa_capture.db"
    profile = ProfileStateStore(profile_db)
    PortfolioStore(profile_db)
    sa_capture_store.connect(str(sa_db)).close()
    profile.import_lists([{"name": "Synthetic", "tickers": ["AAPL"]}])

    snapshot = build_active_universe_snapshot(
        profile_db=profile_db, sa_db=sa_db, now=NOW
    )
    document = compat.build_compat_export(snapshot, ())
    target = tmp_path / "tickers_core.generated.json"
    compat.write_compat_export(target, document)
    original = target.read_bytes()

    assert original.decode("utf-8") == (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    assert target.stat().st_mode & 0o777 == 0o600

    manual = b'{"tier1_core":{"manual":{"tickers":["MANUAL"]}}}\n'
    target.write_bytes(manual)
    rebuilt_snapshot = build_active_universe_snapshot(
        profile_db=profile_db, sa_db=sa_db, now=NOW
    )
    rebuilt_document = compat.build_compat_export(rebuilt_snapshot, ())

    assert rebuilt_snapshot == snapshot
    assert rebuilt_document == document
    assert target.read_bytes() == manual

    compat.write_compat_export(target, rebuilt_document)
    assert target.read_bytes() == original
    assert compat.flatten_generated_active_tickers(rebuilt_document) == set(
        rebuilt_snapshot.tickers
    )


def test_export_rejects_annotation_snapshot_mismatch_instead_of_relaxed_parity():
    compat = _compat()
    mismatched = (
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation("AAPL", "legacy_category", "tier2_expanded/identity_access"),
    )

    with pytest.raises(ValueError, match="annotation snapshot mismatch.*AAPL"):
        compat.build_compat_export(_snapshot(("AAPL",)), mismatched)


def test_atomic_export_failure_preserves_the_existing_target(tmp_path, monkeypatch):
    compat = _compat()
    target = tmp_path / "tickers_core.generated.json"
    original = b"existing target\n"
    target.write_bytes(original)
    original_mode = target.stat().st_mode
    document = compat.build_compat_export(_snapshot(("AAPL",)), ())

    def fail_replace(source, destination):
        assert Path(source).parent == target.parent
        assert Path(destination) == target
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(compat.os, "replace", fail_replace)

    with pytest.raises(OSError, match="synthetic replace failure"):
        compat.write_compat_export(target, document)

    assert target.read_bytes() == original
    assert target.stat().st_mode == original_mode
    assert list(tmp_path.iterdir()) == [target]
