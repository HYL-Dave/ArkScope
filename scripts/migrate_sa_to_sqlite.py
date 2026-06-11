#!/usr/bin/env python3
"""
One-shot SA capture migration: PostgreSQL → data/sa_capture.db (slice 3d, prep-5).

Modeled on migrate_market_to_sqlite.py: builds into ``<out>.building``, validates
BEFORE os.replace (mismatch discards the tmp, never the existing store), unlinks
stale WAL/SHM sidecars across the swap.

AUTHORITY GUARD: unlike market_data.db this store becomes the WRITE AUTHORITY at
cutover — a post-flip rebuild from PG would DESTROY captures PG never saw. The
build path therefore REFUSES to run while ``use_local_sa`` is enabled, with no
override flag (runbook: "explicitly NO post-cutover rebuild-from-PG affordance").
``--validate-only`` stays allowed (post-flip mismatch is EXPECTED and says so).

Usage:
    python scripts/migrate_sa_to_sqlite.py --dry-run        # PG counts only
    python scripts/migrate_sa_to_sqlite.py --out /tmp/rehearsal_sa.db   # §5g copy
    python scripts/migrate_sa_to_sqlite.py                  # → data/sa_capture.db
    python scripts/migrate_sa_to_sqlite.py --validate-only  # compare existing vs PG
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_data_admin import _pg_conn  # noqa: E402 — the one shared PG connector
from src.sa_capture_store import (  # noqa: E402
    canon_date,
    canon_ts,
    connect,
    resolve_sa_db_path,
)

# (table, id_col, [(col, canonicalizer)], FK-safe copy order)
_TS, _DATE, _JSON, _BOOL = "ts", "date", "json", "bool"
_TABLES = [
    ("sa_alpha_picks", "id", {
        "picked_date": _DATE, "closed_date": _DATE, "is_stale": _BOOL,
        "return_pct": None, "holding_pct": None, "raw_data": _JSON,
        "detail_fetched_at": _TS, "last_seen_snapshot": _TS,
        "fetched_at": _TS, "updated_at": _TS,
    }),
    ("sa_refresh_meta", None, {
        "last_attempt_at": _TS, "last_success_at": _TS, "snapshot_ts": _TS,
        "ok": _BOOL, "updated_at": _TS,
    }),
    ("sa_articles", "id", {
        "published_date": _DATE, "raw_data": _JSON, "detail_fetched_at": _TS,
        "comments_fetched_at": _TS, "fetched_at": _TS, "updated_at": _TS,
    }),
    ("sa_article_comments", "id", {"comment_date": _TS, "fetched_at": _TS}),
    ("sa_market_news", "id", {
        "published_at": _TS, "raw_data": _JSON, "detail_fetched_at": _TS,
        "fetched_at": _TS, "updated_at": _TS,
    }),
    ("sa_comment_signals", "comment_row_id", {
        "keyword_buckets": _JSON, "high_value_score": None,  # NUMERIC → float
        "needs_verification": _BOOL, "extracted_at": _TS,
    }),
]
# PG TEXT[] columns → SQLite junction tables (locked L8)
_ARRAY_COLS = {
    "sa_market_news": [("tickers", "sa_market_news_tickers", "news_row_id", "id")],
    "sa_comment_signals": [
        ("ticker_mentions", "sa_signal_ticker_mentions", "comment_row_id", "comment_row_id"),
        ("candidate_mentions", "sa_signal_candidate_mentions", "comment_row_id", "comment_row_id"),
    ],
}


def _canon(kind, value):
    if value is None:
        return None
    if kind == _TS:
        return canon_ts(value)
    if kind == _DATE:
        return canon_date(value)
    if kind == _JSON:
        return json.dumps(value) if not isinstance(value, str) else value
    if kind == _BOOL:
        return 1 if value else 0
    if kind is None:  # NUMERIC → float
        return float(value)
    return value


def _use_local_sa_enabled() -> bool:
    """Mirror the DAL toggle read (env OR profile_settings) — build-path guard."""
    import sqlite3

    truthy = ("1", "true", "yes", "on")
    if os.environ.get("ARKSCOPE_USE_LOCAL_SA", "").strip().lower() in truthy:
        return True
    root = Path(__file__).resolve().parents[1]
    profile = os.environ.get("ARKSCOPE_PROFILE_DB") or str(root / "data" / "profile_state.db")
    if not Path(profile).exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{profile}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT value FROM profile_settings WHERE key = 'use_local_sa'").fetchone()
        finally:
            conn.close()
        return bool(row) and str(row[0]).strip().lower() in truthy
    except sqlite3.OperationalError:
        return False


def _pg_columns(cur, table) -> list:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position", (table,))
    return [r[0] for r in cur.fetchall()]


def _copy_all(cur, sconn) -> dict:
    """Copy all 6 tables (FK-safe order; ids preserved verbatim) + junctions.
    FTS mirrors populate automatically via the schema triggers."""
    counts = {}
    for table, _id, canon_map in _TABLES:
        pg_cols = _pg_columns(cur, table)
        array_specs = _ARRAY_COLS.get(table, [])
        array_names = {a[0] for a in array_specs}
        scalar_cols = [c for c in pg_cols if c not in array_names]
        sq_cols = ", ".join(scalar_cols)
        placeholders = ", ".join("?" for _ in scalar_cols)
        cur.execute(f"SELECT {', '.join(pg_cols)} FROM {table} ORDER BY 1")
        col_idx = {c: i for i, c in enumerate(pg_cols)}
        n = 0
        junction_rows = {spec[1]: [] for spec in array_specs}
        for row in cur.fetchall():
            values = [
                _canon(canon_map.get(c, ""), row[col_idx[c]]) if c in canon_map
                else row[col_idx[c]]
                for c in scalar_cols
            ]
            sconn.execute(
                f"INSERT INTO {table} ({sq_cols}) VALUES ({placeholders})", values)
            for arr_col, junc, junc_fk, src_key in array_specs:
                parent = row[col_idx[src_key]]
                for ticker in (row[col_idx[arr_col]] or []):
                    junction_rows[junc].append((parent, ticker))
            n += 1
        for junc, rows in junction_rows.items():
            # PG arrays can contain dupes; junction PK can't — INSERT OR IGNORE and
            # validation compares DISTINCT cardinality on both sides.
            sconn.executemany(
                f"INSERT OR IGNORE INTO {junc} VALUES (?, ?)", rows)
            counts[junc] = sconn.execute(f"SELECT COUNT(*) FROM {junc}").fetchone()[0]
        counts[table] = n
        sconn.commit()
    return counts


# --- validation (identical-aggregate-both-sides; NEVER fetched_at-based) ----------

def _fingerprints_pg(cur) -> dict:
    out = {}
    for table, id_col, _ in _TABLES:
        if id_col:
            cur.execute(f"SELECT COUNT(*), COALESCE(SUM({id_col}), 0) FROM {table}")
            out[table] = tuple(cur.fetchone())
        else:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            out[table] = (cur.fetchone()[0], 0)
    for table, specs in _ARRAY_COLS.items():
        for arr_col, junc, _fk, _src in specs:
            cur.execute(
                f"SELECT COUNT(*) FROM (SELECT DISTINCT {('id' if table != 'sa_comment_signals' else 'comment_row_id')} AS pid, "
                f"unnest({arr_col}) FROM {table}) t")
            out[junc] = (cur.fetchone()[0], 0)
    return out


def _fingerprints_sqlite(conn) -> dict:
    out = {}
    for table, id_col, _ in _TABLES:
        if id_col:
            row = conn.execute(
                f"SELECT COUNT(*), COALESCE(SUM({id_col}), 0) FROM {table}").fetchone()
            out[table] = (row[0], row[1])
        else:
            out[table] = (conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
    for specs in _ARRAY_COLS.values():
        for _arr, junc, _fk, _src in specs:
            out[junc] = (conn.execute(f"SELECT COUNT(*) FROM {junc}").fetchone()[0], 0)
    return out


def _content_rows_pg(cur):
    cur.execute(
        "SELECT id, symbol, TO_CHAR(picked_date,'YYYY-MM-DD'), "
        "COALESCE(TO_CHAR(closed_date,'YYYY-MM-DD'),''), portfolio_status, "
        "is_stale::int, COALESCE(return_pct,0)::float FROM sa_alpha_picks ORDER BY id")
    picks = cur.fetchall()
    cur.execute("SELECT scope, row_count, ok::int FROM sa_refresh_meta ORDER BY scope")
    return [tuple(r) for r in picks], [tuple(r) for r in cur.fetchall()]


def _content_rows_sqlite(conn):
    picks = conn.execute(
        "SELECT id, symbol, picked_date, COALESCE(closed_date,''), portfolio_status, "
        "is_stale, COALESCE(return_pct,0) FROM sa_alpha_picks ORDER BY id").fetchall()
    meta = conn.execute(
        "SELECT scope, row_count, ok FROM sa_refresh_meta ORDER BY scope").fetchall()
    return [tuple(r) for r in picks], [tuple(r) for r in meta]


def validate(out_path: str) -> bool:
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        pg_fp = _fingerprints_pg(cur)
        pg_picks, pg_meta = _content_rows_pg(cur)
    finally:
        pg.close()
    conn = connect(out_path, read_only=True)
    try:
        sq_fp = _fingerprints_sqlite(conn)
        sq_picks, sq_meta = _content_rows_sqlite(conn)
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    ok = True
    for key in pg_fp:
        match = pg_fp[key] == sq_fp.get(key)
        ok &= match
        print(f"  {key:32s} pg={pg_fp[key]} sqlite={sq_fp.get(key)} {'✓' if match else '✗'}")
    picks_match, meta_match = pg_picks == sq_picks, pg_meta == sq_meta
    ok &= picks_match and meta_match
    print(f"  {'sa_alpha_picks content':32s} {'✓' if picks_match else '✗ (row-level diff)'}")
    print(f"  {'sa_refresh_meta content':32s} {'✓' if meta_match else '✗'}")
    print(f"  {'foreign_key_check':32s} {'✓ empty' if not fk else f'✗ {len(fk)} violations'}")
    print(f"  {'integrity_check':32s} {'✓' if integ == 'ok' else '✗ ' + str(integ)}")
    return ok and not fk and integ == "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate PG sa_* tables → local sa_capture.db (one-shot)")
    ap.add_argument("--out", default=resolve_sa_db_path())
    ap.add_argument("--dry-run", action="store_true", help="PG counts only; write nothing")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        pg = _pg_conn()
        try:
            for key, fp in _fingerprints_pg(pg.cursor()).items():
                print(f"PG {key:32s} rows={fp[0]:,} sum_id={fp[1]}")
        finally:
            pg.close()
        print("[DRY RUN] no SQLite written.")
        return 0

    if args.validate_only:
        if not Path(args.out).exists():
            print(f"{args.out} does not exist.")
            return 1
        if _use_local_sa_enabled():
            print("NOTE: use_local_sa is ON — the local store is the live authority; "
                  "divergence from the frozen PG is EXPECTED after capture resumes.")
        ok = validate(args.out)
        print("✓ MATCH" if ok else "✗ MISMATCH")
        return 0 if ok else 1

    # --- build (one-shot; refuses post-flip) ---
    if _use_local_sa_enabled():
        print("REFUSED: use_local_sa is enabled — sa_capture.db is the write authority; "
              "rebuilding from PG would DESTROY captures PG never saw. There is no "
              "override (runbook L1/L5). Flip the toggle off only as a deliberate "
              "rollback, then re-run.")
        return 2

    out = args.out
    tmp = out + ".building"
    Path(tmp).unlink(missing_ok=True)
    Path(tmp + "-wal").unlink(missing_ok=True)
    Path(tmp + "-shm").unlink(missing_ok=True)
    print(f"Building {tmp} from PG …")
    pg = _pg_conn()
    try:
        sconn = connect(tmp)  # creates schema (WAL, FKs ON — copy order is FK-safe)
        try:
            counts = _copy_all(pg.cursor(), sconn)
        finally:
            sconn.close()  # clean close checkpoints + truncates the tmp WAL
    finally:
        pg.close()
    for table, n in counts.items():
        print(f"  copied {table:32s} {n:,}")

    print("Validating before swap …")
    if not validate(tmp):
        Path(tmp).unlink(missing_ok=True)
        Path(tmp + "-wal").unlink(missing_ok=True)
        Path(tmp + "-shm").unlink(missing_ok=True)
        print("✗ MISMATCH — build discarded; existing store untouched.")
        return 1
    os.replace(tmp, out)
    # stale sidecars of the OLD inode would replay onto the new file (filename-bound)
    Path(out + "-wal").unlink(missing_ok=True)
    Path(out + "-shm").unlink(missing_ok=True)
    print(f"✓ MATCH — swapped into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
