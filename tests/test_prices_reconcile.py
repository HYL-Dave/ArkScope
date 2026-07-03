import json

from src.prices_reconcile import (
    PriceKey,
    classify_price_differences,
    compare_value_checksums,
    fingerprint_report,
)


def test_alias_projection_explains_pg_only_lc_rows():
    pg_rows = {
        PriceKey("LC", "15min", "2026-01-02T14:30:00+0000"),
    }
    local_rows = {
        PriceKey("HAPN", "15min", "2026-01-02T14:30:00+0000"),
    }
    report = classify_price_differences(
        pg_rows=pg_rows,
        local_rows=local_rows,
        aliases={"LC": "HAPN"},
    )

    assert report.unexplained_pg_only == ()
    assert report.alias_explained_pg_only == (
        {
            "pg_key": ("LC", "15min", "2026-01-02T14:30:00+0000"),
            "canonical_key": ("HAPN", "15min", "2026-01-02T14:30:00+0000"),
            "reason": "pg_alias_matches_local_canonical",
        },
    )


def test_unexplained_pg_only_blocks_no_bulk_copy_gate():
    pg_rows = {PriceKey("MSFT", "15min", "2026-01-02T14:30:00+0000")}
    local_rows = set()
    report = classify_price_differences(pg_rows=pg_rows, local_rows=local_rows, aliases={})

    assert report.unexplained_pg_only == (
        ("MSFT", "15min", "2026-01-02T14:30:00+0000"),
    )
    assert report.bulk_copy_allowed is False


def test_reconcile_fingerprint_is_order_stable():
    first = {
        "pg_only_by_ticker": {"LC": 2, "AAPL": 1},
        "local_only_by_ticker": {"HAPN": 3},
    }
    second = {
        "local_only_by_ticker": {"HAPN": 3},
        "pg_only_by_ticker": {"AAPL": 1, "LC": 2},
    }

    assert fingerprint_report(first) == fingerprint_report(second)


def test_value_checksum_mismatch_is_reported_by_bucket():
    mismatches = compare_value_checksums(
        pg_checksums={("NVDA", "15min"): "pg-hash", ("AAPL", "15min"): "same"},
        local_checksums={("NVDA", "15min"): "local-hash", ("AAPL", "15min"): "same"},
    )

    assert mismatches == (
        {
            "bucket": ("NVDA", "15min"),
            "pg_checksum": "pg-hash",
            "local_checksum": "local-hash",
            "reason": "ohlcv_checksum_mismatch",
        },
    )


def test_reconcile_cli_writes_deterministic_report(tmp_path, monkeypatch, capsys):
    from scripts.migration import p0c_prices_reconcile as cli

    output = tmp_path / "report.json"
    monkeypatch.setattr(
        cli,
        "load_pg_snapshot",
        lambda _url: {
            "summary": {
                "row_count": 1,
                "ticker_count": 1,
                "intervals": {"15min": 1},
                "min_datetime": "2026-01-02T14:30:00+0000",
                "max_datetime": "2026-01-02T14:30:00+0000",
            },
            "keys": [("LC", "15min", "2026-01-02T14:30:00+0000")],
            "value_checksums": {("LC", "15min"): "pg-lc-hash"},
            "samples": [],
        },
    )
    monkeypatch.setattr(
        cli,
        "load_sqlite_snapshot",
        lambda _db: {
            "summary": {
                "row_count": 1,
                "ticker_count": 1,
                "intervals": {"15min": 1},
                "min_datetime": "2026-01-02T14:30:00+0000",
                "max_datetime": "2026-01-02T14:30:00+0000",
            },
            "keys": [("HAPN", "15min", "2026-01-02T14:30:00+0000")],
            "value_checksums": {("HAPN", "15min"): "local-hapn-hash"},
            "aliases": {"LC": "HAPN"},
            "samples": [],
        },
    )

    code = cli.main(
        [
            "preview",
            "--database-url",
            "postgres://secret@example/db",
            "--market-db",
            str(tmp_path / "market_data.db"),
            "--output",
            str(output),
        ]
    )

    stdout = capsys.readouterr().out
    report = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert "secret" not in stdout
    assert report["unexplained_pg_only_count"] == 0
    assert report["alias_explained_pg_only_count"] == 1
    assert len(report["fingerprint"]) == 64
