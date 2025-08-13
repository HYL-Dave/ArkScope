#!/usr/bin/env python3
"""
Token Usage Summary — 記憶體友善的 CSV 彙整工具

用途
- 從大型 CSV 彙整任意 token 欄位（如 'completion_tokens', 'prompt_tokens'）。
- 輸出總 token 數、有效筆數、總筆數、有效平均。
- 對缺值（NaN）筆數提供診斷：缺值行的 Article、Lsa_summary 是否為空。
- 支援依欄位分組（如 Date、Stock_symbol），顯示 Top-N，並可輸出分組 CSV。
- 可選擇依每千 tokens 價格換算成本（僅在列印的 Top-N 摘要中顯示）。

參數
- --csv: CSV 路徑（必填）。
- --cols: 要彙總的 token 欄位名（可多個）。若省略，會自動偵測常見欄位。
- --group-by: 分組欄位，可多個，如 Date Stock_symbol。
- --top: 分組輸出顯示 Top-N（預設 20）。
- --save-group-csv: 將完整分組結果寫入 CSV。
  • 若指定為資料夾：輸出為 <dir>/<col>_grouped.csv。
  • 若指定為含副檔名的檔案：輸出為 <parent>/<stem>_<col>_grouped.csv。
  • 若指定為無副檔名的路徑：視為資料夾，輸出為 <path>/<col>_grouped.csv。
- --price-prompt: 每千 prompt tokens 的 USD 單價（只影響印出之分組摘要中的 cost 欄）。
- --price-completion: 每千 completion tokens 的 USD 單價（同上）。
- --chunksize: 讀檔分塊大小（預設 200000）。

基本用法
- 同時彙總 completion 與 prompt：
  python scripts/token_usage_summary.py --csv /path/to/file.csv --cols completion_tokens prompt_tokens

- 自動偵測欄位：
  python scripts/token_usage_summary.py --csv /path/to/file.csv

- 依日期分組並顯示前 10 名，另存 CSV：
  python scripts/token_usage_summary.py \
    --csv /path/to/file.csv \
    --cols completion_tokens \
    --group-by Date --top 10 \
    --save-group-csv outputs/by_date

- 依股票代號分組（同時換算成本），另存 CSV：
  python scripts/token_usage_summary.py \
    --csv /path/to/file.csv \
    --cols prompt_tokens \
    --group-by Stock_symbol --top 10 \
    --save-group-csv outputs/by_symbol \
    --price-prompt 3.00

輸出說明
- 總覽：顯示欄位名稱、總 token、有效筆數/總筆數、有效平均、缺值診斷。
- 分組：顯示 group keys、total_tokens、non_null。若提供單價，會額外顯示 cost_usd（僅印出，不寫入 CSV）。
- 缺值診斷：顯示缺值筆數，以及缺值行中 Article/Lsa_summary 是否為空、是否兩者皆空。

備註
- 日期欄位（名稱中包含 'date'）會嘗試正規化為日期字串（YYYY-MM-DD）。
- 非數值 token 值會視為缺值（以 0 計入總和，不計入有效筆數）。
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


def fmt_int(n: int) -> str:
    return f"{n:,}"


def is_empty_series(s: pd.Series) -> pd.Series:
    # Treat NaN or whitespace-only strings as empty
    if s.dtype == object:
        return s.isna() | (s.astype(str).str.strip() == "")
    return s.isna()


def summarize_column(csv_path: Path, col: str, chunksize: int = 200_000) -> None:
    exists = csv_path.exists()
    print(f"CSV: {csv_path}  (exists: {exists})")
    if not exists:
        return

    # Restrict columns for efficiency; include optional columns for empty checks
    candidate_cols = [col]
    optional_cols = []
    for name in ["Article", "Lsa_summary"]:
        optional_cols.append(name)

    # Probe header to see what exists
    header = pd.read_csv(csv_path, nrows=0)
    header_cols = list(header.columns)
    if col not in header_cols:
        print(f"- Column not found: '{col}'. Available columns: {header_cols}")
        return

    usecols = [c for c in [col, *optional_cols] if c in header_cols]

    total_rows = 0
    nonnull = 0
    total_tokens = 0

    missing_rows = 0
    missing_article_empty = 0
    missing_lsa_empty = 0
    missing_both_empty = 0

    for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=chunksize):
        total_rows += len(chunk)

        # Token column aggregation
        s = pd.to_numeric(chunk[col], errors="coerce")
        nonnull += int(s.notna().sum())
        total_tokens += int(s.fillna(0).sum())

        # Missing-value diagnostics
        m = s.isna()
        if m.any():
            missing_rows += int(m.sum())

            # Check Article emptiness if present
            if "Article" in chunk.columns:
                art_empty = is_empty_series(chunk["Article"]) if "Article" in chunk.columns else None
            else:
                art_empty = None

            # Check Lsa_summary emptiness if present
            if "Lsa_summary" in chunk.columns:
                lsa_empty = is_empty_series(chunk["Lsa_summary"]) if "Lsa_summary" in chunk.columns else None
            else:
                lsa_empty = None

            if art_empty is not None:
                missing_article_empty += int((m & art_empty).sum())
            if lsa_empty is not None:
                missing_lsa_empty += int((m & lsa_empty).sum())
            if art_empty is not None and lsa_empty is not None:
                missing_both_empty += int((m & art_empty & lsa_empty).sum())

    mean_tokens = (total_tokens / nonnull) if nonnull else 0.0

    print(f"- 欄位名稱: '{col}'")
    print(f"- 總 {col}: {fmt_int(total_tokens)}")
    print(f"- 有效筆數: {fmt_int(nonnull)} / 總筆數: {fmt_int(total_rows)}（其餘為缺值）")
    print(f"- 平均每筆 {col}（有效筆）: {mean_tokens:.1f}")

    # Missing diagnostics
    print("- 缺值筆數: " + fmt_int(missing_rows))
    if "Article" in usecols:
        print("  - 缺值中 Article 為空: " + fmt_int(missing_article_empty))
    else:
        print("  - 欄位 'Article' 不存在，無法檢查")
    if "Lsa_summary" in usecols:
        print("  - 缺值中 Lsa_summary 為空: " + fmt_int(missing_lsa_empty))
    else:
        print("  - 欄位 'Lsa_summary' 不存在，無法檢查")
    if "Article" in usecols and "Lsa_summary" in usecols:
        print("  - 缺值中 兩者皆空: " + fmt_int(missing_both_empty))


def _normalize_group_cols(df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    res = df.copy()
    for gc in group_cols:
        if gc not in res.columns:
            # Add a missing column filled with NaN to keep pipeline robust
            res[gc] = pd.NA
        # Try to normalize date-like columns to date-only string
        if "date" in gc.lower():
            res[gc] = pd.to_datetime(res[gc], errors="coerce").dt.date.astype(str)
    return res


def group_summaries(
    csv_path: Path,
    token_col: str,
    group_cols: List[str],
    chunksize: int = 200_000,
) -> pd.DataFrame:
    header = pd.read_csv(csv_path, nrows=0)
    header_cols = list(header.columns)
    if token_col not in header_cols:
        raise ValueError(f"Column not found: {token_col}")
    missing_gcs = [g for g in group_cols if g not in header_cols]

    usecols = [c for c in [token_col, *group_cols] if c in header_cols]

    agg: Dict[Tuple, List[int]] = {}

    for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=chunksize):
        chunk = _normalize_group_cols(chunk, [gc for gc in group_cols if gc in chunk.columns])
        s = pd.to_numeric(chunk[token_col], errors="coerce")
        # Build key tuples
        keys_df = chunk[[gc for gc in group_cols if gc in chunk.columns]].copy()
        if keys_df.empty:
            # No valid group-by columns present; use a single group
            keys = [()] * len(chunk)
        else:
            keys = list(map(tuple, keys_df.itertuples(index=False, name=None)))
        for key, val in zip(keys, s):
            if key not in agg:
                agg[key] = [0, 0]  # [sum_tokens, non_null]
            if pd.notna(val):
                agg[key][0] += int(val)
                agg[key][1] += 1

    # Materialize DataFrame
    if group_cols:
        rows = [list(k) + v for k, v in agg.items()]
        cols = list(group_cols) + ["total_tokens", "non_null"]
    else:
        # Single group
        rows = [["ALL", *v] for v in agg.values()]
        cols = ["group", "total_tokens", "non_null"]
    out = pd.DataFrame(rows, columns=cols)
    out.sort_values("total_tokens", ascending=False, inplace=True)
    return out


def print_group_top(df: pd.DataFrame, group_cols: List[str], token_col: str, top: int, price_per_1k: Optional[float]) -> None:
    show = df.head(top)
    print(f"- 依 {', '.join(group_cols) if group_cols else 'ALL'} 分組的 {token_col} 前 {len(show)} 名:")
    # Add cost column if price provided
    if price_per_1k is not None:
        show = show.copy()
        show["cost_usd"] = show["total_tokens"] / 1000.0 * float(price_per_1k)
    # Print compact
    cols_to_print = list(group_cols) + ["total_tokens", "non_null"]
    if price_per_1k is not None:
        cols_to_print.append("cost_usd")
    print(show[cols_to_print].to_string(index=False))


def autodetect_cols(csv_path: Path) -> List[str]:
    header = pd.read_csv(csv_path, nrows=0)
    cols = list(header.columns)
    preferred = []
    for name in ["completion_tokens", "prompt_tokens"]:
        if name in cols:
            preferred.append(name)
    # Fallback: any column containing both 'token' and 'completion' or 'prompt'
    if not preferred:
        for c in cols:
            lc = c.lower()
            if "token" in lc and ("completion" in lc or "prompt" in lc):
                preferred.append(c)
    return preferred


def main(argv: Optional[Iterable[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Summarize token usage from CSV")
    ap.add_argument("--csv", required=True, help="Path to the CSV file")
    ap.add_argument(
        "--cols",
        nargs="*",
        help="Token columns to summarize (e.g., completion_tokens prompt_tokens)"
    )
    ap.add_argument(
        "--group-by",
        nargs="*",
        default=None,
        help="Group by these column(s), e.g., Date or Stock_symbol (can provide multiple)"
    )
    ap.add_argument(
        "--top",
        type=int,
        default=20,
        help="Show top-N groups (default: 20)"
    )
    ap.add_argument(
        "--save-group-csv",
        default=None,
        help="Optional path to save full grouped results for each token column (appends column name)."
    )
    ap.add_argument(
        "--price-prompt",
        type=float,
        default=None,
        help="USD price per 1K prompt tokens for cost conversion"
    )
    ap.add_argument(
        "--price-completion",
        type=float,
        default=None,
        help="USD price per 1K completion tokens for cost conversion"
    )
    ap.add_argument(
        "--chunksize",
        type=int,
        default=200_000,
        help="Chunk size for reading the CSV (default: 200000)")
    args = ap.parse_args(argv)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return

    cols = args.cols or autodetect_cols(csv_path)
    if not cols:
        print("No token columns detected. Please specify with --cols.")
        return

    for col in cols:
        summarize_column(csv_path, col, chunksize=args.chunksize)

        # Optional grouping
        if args.group_by:
            try:
                df = group_summaries(csv_path, col, args.group_by, chunksize=args.chunksize)
                # Choose price based on column type
                price = None
                if "prompt" in col.lower() and args.price_prompt is not None:
                    price = args.price_prompt
                elif "completion" in col.lower() and args.price_completion is not None:
                    price = args.price_completion

                print_group_top(df, args.group_by, col, args.top, price)
                # Save full grouped CSV if requested
                if args.save_group_csv:
                    out_path = Path(args.save_group_csv)
                    if out_path.is_dir():
                        out_file = out_path / f"{col}_grouped.csv"
                    else:
                        # Treat as prefix; append column name
                        parent = out_path.parent if out_path.suffix else out_path
                        parent.mkdir(parents=True, exist_ok=True)
                        out_file = (parent / f"{out_path.stem}_{col}_grouped.csv") if out_path.suffix else (parent / f"{col}_grouped.csv")
                    df.to_csv(out_file, index=False)
                    print(f"- 已輸出分組結果: {out_file}")
            except Exception as e:
                print(f"[WARN] 分組計算失敗 ({col}): {e}")

        print("")


if __name__ == "__main__":
    main()
