#!/usr/bin/env python3
"""
修復 o3_summary 遺失的 6 筆 BKR 資料及所有下游評分檔案。

Usage:
    # 0. 強制備份 (修復前必須完成)
    python repair_o3_data.py --stage backup --backup-dir /mnt/md0/finrl/backups/repair_YYYYMMDD

    # 0.1 驗證備份完整性
    python repair_o3_data.py --verify-backup /mnt/md0/finrl/backups/repair_YYYYMMDD

    # 1. 先執行乾跑模式查看影響範圍
    python repair_o3_data.py --dry-run

    # 2. 僅修復 o3_summary (第一階段)
    python repair_o3_data.py --stage summary

    # 3. 修復所有下游評分 (第二階段)
    python repair_o3_data.py --stage scores

    # 4. 修復 o4-mini high 額外遺失 (第三階段)
    python repair_o3_data.py --stage o4mini-extra

    # 5. 完整修復 (全部階段，需先完成備份)
    python repair_o3_data.py --stage all
"""

import os
import sys
import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import pandas as pd
import numpy as np

# 添加專案根目錄到 path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 自動載入 config/.env
ENV_FILE = PROJECT_ROOT / "config" / ".env"
if ENV_FILE.exists():
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)

# ============================================================================
# 常數定義
# ============================================================================

ORIGINAL_CSV = Path("/mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv")
O3_SUMMARY_CSV = Path("/mnt/md0/finrl/o3/summary/o3_news_with_summary.csv")
FINRL_BASE = Path("/mnt/md0/finrl")

# o3_summary 遺失的 6 筆 BKR 資料 (原始 row index)
MISSING_ROWS_O3 = [19334, 19335, 19336, 19337, 19338, 19339]

# o4-mini high 額外遺失的 2 筆 (API 失敗)
# 注意: 原本錯誤地列為 44887 (GILD 2015-11-25)，該行原始 Article 為空，所有模型都是 NaN
# 正確的是 44893 (GILD 2015-11-17)，該行有 o3_summary 但 o4-mini high 評分失敗
MISSING_ROWS_O4MINI_HIGH = [12543, 44893]

# 所有使用 o3_summary 作為輸入的下游評分檔案
DOWNSTREAM_FILES = [
    # (relative_path, model, reasoning, task)
    # o3
    ("o3/sentiment/sentiment_o3_high_by_o3_summary.csv", "o3", "high", "sentiment"),
    ("o3/sentiment/sentiment_o3_medium_by_o3_summary.csv", "o3", "medium", "sentiment"),
    ("o3/sentiment/sentiment_o3_low_by_o3_summary.csv", "o3", "low", "sentiment"),
    ("o3/risk/risk_o3_high_by_o3_summary.csv", "o3", "high", "risk"),
    ("o3/risk/risk_o3_medium_by_o3_summary.csv", "o3", "medium", "risk"),
    ("o3/risk/risk_o3_low_by_o3_summary.csv", "o3", "low", "risk"),
    # o4-mini
    ("o4-mini/sentiment/sentiment_o4_mini_high_by_o3_summary.csv", "o4-mini", "high", "sentiment"),
    ("o4-mini/sentiment/sentiment_o4_mini_medium_by_o3_summary.csv", "o4-mini", "medium", "sentiment"),
    ("o4-mini/sentiment/sentiment_o4_mini_low_by_o3_summary.csv", "o4-mini", "low", "sentiment"),
    ("o4-mini/risk/risk_o4_mini_high_by_o3_summary.csv", "o4-mini", "high", "risk"),
    ("o4-mini/risk/risk_o4_mini_medium_by_o3_summary.csv", "o4-mini", "medium", "risk"),
    ("o4-mini/risk/risk_o4_mini_low_by_o3_summary.csv", "o4-mini", "low", "risk"),
    # gpt-5
    ("gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv", "gpt-5", "high", "sentiment"),
    ("gpt-5/sentiment/sentiment_gpt-5_medium_by_o3_summary.csv", "gpt-5", "medium", "sentiment"),
    ("gpt-5/sentiment/sentiment_gpt-5_low_by_o3_summary.csv", "gpt-5", "low", "sentiment"),
    ("gpt-5/sentiment/sentiment_gpt-5_minimal_by_o3_summary.csv", "gpt-5", "minimal", "sentiment"),
    ("gpt-5/risk/risk_gpt-5_high_by_o3_summary.csv", "gpt-5", "high", "risk"),
    ("gpt-5/risk/risk_gpt-5_medium_by_o3_summary.csv", "gpt-5", "medium", "risk"),
    ("gpt-5/risk/risk_gpt-5_low_by_o3_summary.csv", "gpt-5", "low", "risk"),
    ("gpt-5/risk/risk_gpt-5_minimal_by_o3_summary.csv", "gpt-5", "minimal", "risk"),
    # gpt-4.1 系列
    ("gpt-4.1/sentiment/sentiment_gpt-4.1_by_o3_summary.csv", "gpt-4.1", None, "sentiment"),
    ("gpt-4.1/risk/risk_gpt-4.1_by_o3_summary.csv", "gpt-4.1", None, "risk"),
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_o3_summary.csv", "gpt-4.1-mini", None, "sentiment"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_o3_summary.csv", "gpt-4.1-mini", None, "risk"),
    ("gpt-4.1-nano/sentiment/sentiment_gpt-4.1-nano_by_o3_summary.csv", "gpt-4.1-nano", None, "sentiment"),
    ("gpt-4.1-nano/risk/risk_gpt-4.1-nano_by_o3_summary.csv", "gpt-4.1-nano", None, "risk"),
]

# 備份標記檔案名稱
BACKUP_MARKER_FILE = ".backup_complete"


# ============================================================================
# 第零階段：強制備份
# ============================================================================

def get_all_files_to_backup() -> List[Path]:
    """取得所有需要備份的檔案列表"""
    files = [O3_SUMMARY_CSV]
    for rel_path, _, _, _ in DOWNSTREAM_FILES:
        files.append(FINRL_BASE / rel_path)
    return files


def backup_all_files(backup_dir: Path, dry_run: bool = False) -> bool:
    """
    備份所有受影響的檔案到指定目錄

    Args:
        backup_dir: 備份目標目錄
        dry_run: 乾跑模式

    Returns:
        True if successful
    """
    logging.info("=" * 60)
    logging.info("Stage 0: Creating backups (MANDATORY)")
    logging.info("=" * 60)

    files_to_backup = get_all_files_to_backup()
    logging.info(f"Total files to backup: {len(files_to_backup)}")

    if dry_run:
        logging.info("[DRY RUN] Would create backup directory and copy files:")
        for f in files_to_backup:
            if f.exists():
                logging.info(f"  - {f.name}")
            else:
                logging.warning(f"  - {f.name} (NOT FOUND)")
        return True

    # 建立備份目錄
    backup_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Backup directory: {backup_dir}")

    # 建立備份清單檔案
    manifest_path = backup_dir / "backup_manifest.txt"
    manifest_lines = [
        f"# Backup created: {datetime.now().isoformat()}",
        f"# Source: {FINRL_BASE}",
        "",
    ]

    success_count = 0
    failed_files = []

    for file_path in files_to_backup:
        if not file_path.exists():
            logging.warning(f"File not found, skipping: {file_path}")
            failed_files.append(str(file_path))
            continue

        # 保留相對路徑結構
        try:
            rel_path = file_path.relative_to(FINRL_BASE)
        except ValueError:
            rel_path = file_path.name

        dest_path = backup_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(file_path, dest_path)
            file_size = file_path.stat().st_size
            manifest_lines.append(f"{rel_path}|{file_size}|{file_path.stat().st_mtime}")
            logging.info(f"Backed up: {rel_path} ({file_size:,} bytes)")
            success_count += 1
        except Exception as e:
            logging.error(f"Failed to backup {file_path}: {e}")
            failed_files.append(str(file_path))

    # 寫入清單
    with open(manifest_path, "w") as f:
        f.write("\n".join(manifest_lines))

    # 寫入備份完成標記
    if success_count == len(files_to_backup) - len([f for f in files_to_backup if not f.exists()]):
        marker_path = backup_dir / BACKUP_MARKER_FILE
        with open(marker_path, "w") as f:
            f.write(f"Backup completed: {datetime.now().isoformat()}\n")
            f.write(f"Files backed up: {success_count}\n")
            f.write(f"Files not found: {len(failed_files)}\n")
        logging.info(f"Backup marker created: {marker_path}")

    logging.info(f"Backup complete: {success_count} files backed up")
    if failed_files:
        logging.warning(f"Files not found (skipped): {len(failed_files)}")

    return len(failed_files) == 0 or all(not Path(f).exists() for f in failed_files)


def verify_backup(backup_dir: Path) -> bool:
    """
    驗證備份完整性

    Args:
        backup_dir: 備份目錄

    Returns:
        True if backup is valid
    """
    logging.info("=" * 60)
    logging.info("Verifying backup integrity")
    logging.info("=" * 60)

    if not backup_dir.exists():
        logging.error(f"Backup directory not found: {backup_dir}")
        return False

    marker_path = backup_dir / BACKUP_MARKER_FILE
    if not marker_path.exists():
        logging.error(f"Backup marker not found: {marker_path}")
        logging.error("Backup may be incomplete!")
        return False

    manifest_path = backup_dir / "backup_manifest.txt"
    if not manifest_path.exists():
        logging.error(f"Backup manifest not found: {manifest_path}")
        return False

    # 讀取清單並驗證
    verified_count = 0
    failed_count = 0

    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) != 3:
                continue

            rel_path, expected_size, _ = parts
            backup_file = backup_dir / rel_path

            if not backup_file.exists():
                logging.error(f"Missing backup file: {rel_path}")
                failed_count += 1
                continue

            actual_size = backup_file.stat().st_size
            if actual_size != int(expected_size):
                logging.error(f"Size mismatch for {rel_path}: expected {expected_size}, got {actual_size}")
                failed_count += 1
                continue

            verified_count += 1

    logging.info(f"Verified: {verified_count} files")
    if failed_count > 0:
        logging.error(f"Failed: {failed_count} files")
        return False

    logging.info("Backup verification: PASSED")
    return True


def check_backup_exists(backup_dir: Optional[Path] = None) -> bool:
    """
    檢查是否已完成備份

    如果沒有提供 backup_dir，會檢查預設位置
    """
    if backup_dir is None:
        # 檢查今天的備份
        today = datetime.now().strftime("%Y%m%d")
        backup_dir = Path(f"/mnt/md0/finrl/backups/repair_{today}")

    if not backup_dir.exists():
        return False

    marker_path = backup_dir / BACKUP_MARKER_FILE
    return marker_path.exists()


# ============================================================================
# 工具函數
# ============================================================================

def backup_file(file_path: Path) -> Path:
    """備份檔案，返回備份路徑"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".backup_{timestamp}.csv")
    shutil.copy2(file_path, backup_path)
    logging.info(f"Backed up: {file_path} -> {backup_path}")
    return backup_path


def verify_alignment(df1: pd.DataFrame, df2: pd.DataFrame,
                     key_cols: List[str], sample_size: int = 100) -> Tuple[bool, str]:
    """
    驗證兩個 DataFrame 的對齊正確性

    Returns:
        (is_aligned, message)
    """
    if len(df1) != len(df2):
        return False, f"Row count mismatch: {len(df1)} vs {len(df2)}"

    # 隨機抽樣比對
    sample_idx = np.random.choice(len(df1), min(sample_size, len(df1)), replace=False)
    for idx in sample_idx:
        for col in key_cols:
            if col in df1.columns and col in df2.columns:
                if df1.iloc[idx][col] != df2.iloc[idx][col]:
                    return False, f"Mismatch at row {idx}, column {col}"

    return True, f"Verified {len(sample_idx)} samples, all aligned"


# ============================================================================
# 第一階段：修復 o3_summary
# ============================================================================

def get_missing_articles(original_csv: Path, missing_rows: List[int]) -> pd.DataFrame:
    """從原始 CSV 提取遺失行的資料"""
    df = pd.read_csv(original_csv, on_bad_lines='warn')
    missing_df = df.iloc[missing_rows].copy()
    logging.info(f"Extracted {len(missing_df)} missing rows from original data")
    return missing_df


def get_api_keys() -> List[str]:
    """從環境變數取得 API keys，支援單一或多 key"""
    # 優先使用 OPENAI_API_KEYS (多 key，逗號分隔)
    keys_str = os.getenv("OPENAI_API_KEYS", "")
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if keys:
            logging.info(f"Using {len(keys)} API keys from OPENAI_API_KEYS")
            return keys

    # 回退到 OPENAI_API_KEY (單一 key)
    single_key = os.getenv("OPENAI_API_KEY", "")
    if single_key:
        logging.info("Using single API key from OPENAI_API_KEY")
        return [single_key]

    raise ValueError("No API keys found. Set OPENAI_API_KEYS or OPENAI_API_KEY in config/.env")


def generate_summaries(articles_df: pd.DataFrame, model: str = "o3",
                       reasoning_effort: str = "high") -> pd.DataFrame:
    """呼叫 API 生成 summary"""
    try:
        from openai_summary import summarize_article, set_api_keys

        keys = get_api_keys()
        set_api_keys(keys, None)

        summaries = []
        for idx, row in articles_df.iterrows():
            article = row.get("Article", "")
            symbol = row.get("Stock_symbol", "UNKNOWN")

            if pd.isna(article) or not str(article).strip():
                logging.warning(f"Empty article for {symbol}, skipping")
                summaries.append(None)
                continue

            summary, p_tokens, c_tokens = summarize_article(
                article, symbol, model, reasoning_effort
            )
            summaries.append(summary)
            logging.info(f"Generated summary for {symbol}: {len(summary) if summary else 0} chars")

        articles_df["o3_summary"] = summaries
        return articles_df

    except ImportError:
        logging.error("Cannot import openai_summary module")
        raise


def repair_o3_summary(dry_run: bool = False) -> bool:
    """修復 o3_summary 的遺失資料"""
    logging.info("=" * 60)
    logging.info("Stage 1: Repairing o3_summary")
    logging.info("=" * 60)

    # 驗證檔案存在
    if not ORIGINAL_CSV.exists():
        logging.error(f"Original CSV not found: {ORIGINAL_CSV}")
        return False
    if not O3_SUMMARY_CSV.exists():
        logging.error(f"o3_summary CSV not found: {O3_SUMMARY_CSV}")
        return False

    # 載入資料
    original_df = pd.read_csv(ORIGINAL_CSV, on_bad_lines='warn')
    o3_summary_df = pd.read_csv(O3_SUMMARY_CSV, on_bad_lines='warn')

    logging.info(f"Original rows: {len(original_df)}")
    logging.info(f"o3_summary rows: {len(o3_summary_df)}")
    logging.info(f"Missing rows to repair: {MISSING_ROWS_O3}")

    if dry_run:
        logging.info("[DRY RUN] Would extract and generate summaries for 6 rows")
        return True

    # 提取遺失資料
    missing_df = get_missing_articles(ORIGINAL_CSV, MISSING_ROWS_O3)

    # 生成 summary
    logging.info("Generating summaries for missing rows...")
    missing_with_summary = generate_summaries(missing_df, "o3", "high")

    # 備份原始檔案
    backup_file(O3_SUMMARY_CSV)

    # 插入到正確位置
    # o3_summary[0:19333] 對應原始 [0:19333]
    # 需要在 o3_summary 的 row 19334 處插入 6 行
    insert_position = MISSING_ROWS_O3[0]  # 19334

    # 分割並重組
    before = o3_summary_df.iloc[:insert_position]
    after = o3_summary_df.iloc[insert_position:]

    repaired_df = pd.concat([before, missing_with_summary, after], ignore_index=True)

    # 儲存修復後的檔案
    repaired_path = O3_SUMMARY_CSV.with_suffix(".repaired.csv")
    repaired_df.to_csv(repaired_path, index=False)
    logging.info(f"Saved repaired o3_summary to: {repaired_path}")
    logging.info(f"Repaired rows: {len(repaired_df)}")

    # 驗證對齊
    is_aligned, msg = verify_alignment(
        repaired_df, original_df,
        ["Stock_symbol", "Date", "Article_title"]
    )
    if is_aligned:
        logging.info(f"Alignment verification: PASSED - {msg}")
    else:
        logging.error(f"Alignment verification: FAILED - {msg}")
        return False

    return True


# ============================================================================
# 第二階段：修復下游評分檔案
# ============================================================================

def score_articles(articles_df: pd.DataFrame, model: str, reasoning: Optional[str],
                   task: str, text_column: str = "o3_summary") -> pd.DataFrame:
    """呼叫 API 生成評分"""
    try:
        if task == "sentiment":
            from score_sentiment_openai import score_headline as score_func, set_api_keys
        else:
            from score_risk_openai import score_headline as score_func, set_api_keys

        # 使用 get_api_keys() 取得多 key 支援
        keys = get_api_keys()
        set_api_keys(keys, None)  # None = 無每日限額

        scores = []
        for idx, row in articles_df.iterrows():
            text = row.get(text_column, "")
            symbol = row.get("Stock_symbol", "UNKNOWN")

            if pd.isna(text) or not str(text).strip():
                logging.warning(f"Empty text for {symbol}, skipping")
                scores.append(None)
                continue

            # 呼叫評分函數 (reasoning_effort 使用預設 "high" 如果為 None)
            reasoning_effort = reasoning if reasoning else "high"
            score = score_func(text, symbol, model, reasoning_effort)
            scores.append(score)
            logging.info(f"Generated {task} score for {symbol}: {score}")

        score_column = f"{task}_{model.replace('-', '_')}"
        articles_df[score_column] = scores
        return articles_df

    except ImportError as e:
        logging.error(f"Cannot import scoring module: {e}")
        raise


def repair_downstream_file(file_info: Tuple, repaired_summary_df: pd.DataFrame,
                           missing_rows: List[int], dry_run: bool = False) -> bool:
    """修復單一下游評分檔案"""
    rel_path, model, reasoning, task = file_info
    file_path = FINRL_BASE / rel_path

    if not file_path.exists():
        logging.warning(f"File not found, skipping: {file_path}")
        return False

    logging.info(f"Processing: {rel_path}")
    logging.info(f"  Model: {model}, Reasoning: {reasoning}, Task: {task}")

    if dry_run:
        logging.info(f"  [DRY RUN] Would repair {len(missing_rows)} rows")
        return True

    # 載入現有評分檔案
    score_df = pd.read_csv(file_path, on_bad_lines='warn')
    logging.info(f"  Current rows: {len(score_df)}")

    # 提取需要評分的 summary
    rows_to_score = repaired_summary_df.iloc[missing_rows].copy()

    # 生成評分
    scored_rows = score_articles(rows_to_score, model, reasoning, task)

    # 備份原始檔案
    backup_file(file_path)

    # 插入到正確位置
    insert_position = missing_rows[0]
    before = score_df.iloc[:insert_position]
    after = score_df.iloc[insert_position:]

    repaired_df = pd.concat([before, scored_rows, after], ignore_index=True)

    # 儲存
    repaired_path = file_path.with_suffix(".repaired.csv")
    repaired_df.to_csv(repaired_path, index=False)
    logging.info(f"  Saved repaired file to: {repaired_path}")
    logging.info(f"  Repaired rows: {len(repaired_df)}")

    return True


def repair_all_downstream(dry_run: bool = False) -> bool:
    """修復所有下游評分檔案"""
    logging.info("=" * 60)
    logging.info("Stage 2: Repairing downstream scoring files")
    logging.info("=" * 60)

    # 載入修復後的 o3_summary
    repaired_summary_path = O3_SUMMARY_CSV.with_suffix(".repaired.csv")
    if not repaired_summary_path.exists():
        logging.error(f"Repaired o3_summary not found: {repaired_summary_path}")
        logging.error("Please run stage 1 (summary) first")
        return False

    repaired_summary_df = pd.read_csv(repaired_summary_path, on_bad_lines='warn')
    logging.info(f"Loaded repaired o3_summary: {len(repaired_summary_df)} rows")

    success_count = 0
    for file_info in DOWNSTREAM_FILES:
        if repair_downstream_file(file_info, repaired_summary_df, MISSING_ROWS_O3, dry_run):
            success_count += 1

    logging.info(f"Repaired {success_count}/{len(DOWNSTREAM_FILES)} files")
    return success_count == len(DOWNSTREAM_FILES)


# ============================================================================
# 第三階段：修復 o4-mini high 額外遺失
# ============================================================================

def generate_single_score(text: str, symbol: str, model: str, reasoning: str, task: str) -> Optional[int]:
    """為單一文本生成評分"""
    try:
        if task == "sentiment":
            from score_sentiment_openai import score_headline as score_func, set_api_keys
        else:
            from score_risk_openai import score_headline as score_func, set_api_keys

        keys = get_api_keys()
        set_api_keys(keys, None)

        if pd.isna(text) or not str(text).strip():
            logging.warning(f"Empty text for {symbol}, returning None")
            return None

        score = score_func(text, symbol, model, reasoning)
        logging.info(f"{task.capitalize()} token usage: see above")
        logging.info(f"Generated {task} score for {symbol}: {score}")
        return score

    except Exception as e:
        logging.error(f"Error generating {task} score for {symbol}: {e}")
        return None


def repair_o4mini_high_extra(dry_run: bool = False) -> bool:
    """修復 o4-mini high 額外遺失的 2 筆 (API 失敗導致的遺失)"""
    logging.info("=" * 60)
    logging.info("Stage 3: Repairing o4-mini high extra missing rows")
    logging.info("=" * 60)

    # o4-mini high 特有的額外遺失 (這些行有 o3_summary 但 o4-mini high 評分失敗)
    extra_missing = MISSING_ROWS_O4MINI_HIGH

    files_to_repair = [
        ("o4-mini/sentiment/sentiment_o4_mini_high_by_o3_summary.csv", "o4-mini", "high", "sentiment"),
        ("o4-mini/risk/risk_o4_mini_high_by_o3_summary.csv", "o4-mini", "high", "risk"),
    ]

    logging.info(f"Extra missing rows to repair: {extra_missing}")

    if dry_run:
        logging.info(f"[DRY RUN] Would repair 2 files with {len(extra_missing)} extra rows each")
        return True

    # 載入 o3_summary 取得這些行的 summary
    repaired_summary_path = O3_SUMMARY_CSV.with_suffix(".repaired.csv")
    if not repaired_summary_path.exists():
        logging.error("Repaired o3_summary not found")
        return False

    repaired_summary_df = pd.read_csv(repaired_summary_path, on_bad_lines='warn')
    logging.info(f"Loaded repaired o3_summary: {len(repaired_summary_df)} rows")

    all_success = True

    for file_info in files_to_repair:
        rel_path, model, reasoning, task = file_info
        file_path = FINRL_BASE / rel_path

        # 優先使用已修復的版本（來自第二階段）
        repaired_path = file_path.with_suffix(".repaired.csv")
        if repaired_path.exists():
            source_path = repaired_path
            logging.info(f"Using existing repaired file: {repaired_path.name}")
        elif file_path.exists():
            source_path = file_path
            logging.info(f"Using original file: {file_path.name}")
        else:
            logging.error(f"File not found: {file_path}")
            all_success = False
            continue

        # 載入評分檔案
        score_df = pd.read_csv(source_path, on_bad_lines='warn')
        logging.info(f"Processing: {rel_path}")
        logging.info(f"  Current rows: {len(score_df)}")

        # 確定分數欄位名稱 (這些檔案使用 sentiment_deepseek 或 risk_deepseek)
        score_column = "sentiment_deepseek" if task == "sentiment" else "risk_deepseek"

        # 對每個額外遺失的行生成評分
        repairs_made = 0
        for row_idx in extra_missing:
            # 檢查該行目前是否為 NaN
            current_score = score_df.iloc[row_idx][score_column]
            if pd.notna(current_score):
                logging.info(f"  Row {row_idx} already has score ({current_score}), skipping")
                continue

            # 取得該行的 o3_summary
            summary_text = repaired_summary_df.iloc[row_idx].get("o3_summary", "")
            symbol = repaired_summary_df.iloc[row_idx].get("Stock_symbol", "UNKNOWN")

            if pd.isna(summary_text) or not str(summary_text).strip():
                logging.warning(f"  Row {row_idx} ({symbol}): o3_summary is empty, cannot score")
                continue

            # 生成評分
            score = generate_single_score(summary_text, symbol, model, reasoning, task)

            if score is not None:
                # 更新 DataFrame 中的分數
                score_df.iloc[row_idx, score_df.columns.get_loc(score_column)] = score
                repairs_made += 1
                logging.info(f"  Row {row_idx} ({symbol}): {task} score = {score}")
            else:
                logging.error(f"  Row {row_idx} ({symbol}): Failed to generate {task} score")
                all_success = False

        # 備份原始 repaired 檔案（如果存在）
        if repaired_path.exists():
            backup_file(repaired_path)

        # 儲存更新後的檔案（覆蓋 .repaired.csv）
        score_df.to_csv(repaired_path, index=False)
        logging.info(f"  Saved updated file to: {repaired_path}")
        logging.info(f"  Repairs made: {repairs_made}/{len(extra_missing)}")

        # 驗證修復結果
        verify_df = pd.read_csv(repaired_path, on_bad_lines='warn')
        for row_idx in extra_missing:
            final_score = verify_df.iloc[row_idx][score_column]
            status = "✓" if pd.notna(final_score) else "✗"
            logging.info(f"  Verification row {row_idx}: {score_column}={final_score} {status}")

    return all_success


# ============================================================================
# 主程式
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="修復 o3_summary 遺失資料及下游評分檔案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
執行順序:
  1. 先執行備份:     --stage backup --backup-dir /path/to/backup
  2. 驗證備份:       --verify-backup /path/to/backup
  3. 執行修復:       --stage all

重要: 修復操作前必須先完成備份，否則會被拒絕執行。
      使用 --skip-backup-check 可跳過此檢查（不建議）。
        """
    )
    parser.add_argument(
        "--stage",
        choices=["backup", "summary", "scores", "o4mini-extra", "all"],
        default="all",
        help="要執行的修復階段 (backup=強制備份)"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="備份目標目錄 (用於 --stage backup)"
    )
    parser.add_argument(
        "--verify-backup",
        type=Path,
        metavar="BACKUP_DIR",
        help="驗證指定目錄的備份完整性"
    )
    parser.add_argument(
        "--skip-backup-check",
        action="store_true",
        help="跳過備份檢查（危險，不建議使用）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="乾跑模式，不實際執行修復"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細輸出"
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # 處理 --verify-backup 選項
    if args.verify_backup:
        success = verify_backup(args.verify_backup)
        sys.exit(0 if success else 1)

    if args.dry_run:
        logging.info("=" * 60)
        logging.info("DRY RUN MODE - No changes will be made")
        logging.info("=" * 60)

    success = True

    # Stage 0: 備份
    if args.stage == "backup":
        if not args.backup_dir:
            # 使用預設備份目錄
            today = datetime.now().strftime("%Y%m%d")
            args.backup_dir = Path(f"/mnt/md0/finrl/backups/repair_{today}")
            logging.info(f"Using default backup directory: {args.backup_dir}")

        success = backup_all_files(args.backup_dir, args.dry_run)
        if success and not args.dry_run:
            logging.info("")
            logging.info("下一步：驗證備份完整性")
            logging.info(f"  python {sys.argv[0]} --verify-backup {args.backup_dir}")
        sys.exit(0 if success else 1)

    # 檢查是否已完成備份 (除非跳過或是乾跑模式)
    if args.stage in ["summary", "scores", "o4mini-extra", "all"]:
        if not args.dry_run and not args.skip_backup_check:
            if not check_backup_exists():
                logging.error("=" * 60)
                logging.error("錯誤：尚未完成備份！")
                logging.error("=" * 60)
                logging.error("")
                logging.error("修復操作前必須先完成備份以確保資料安全。")
                logging.error("請先執行：")
                logging.error("")
                today = datetime.now().strftime("%Y%m%d")
                backup_dir = f"/mnt/md0/finrl/backups/repair_{today}"
                logging.error(f"  python {sys.argv[0]} --stage backup --backup-dir {backup_dir}")
                logging.error("")
                logging.error("備份完成後再執行修復操作。")
                logging.error("")
                logging.error("如果您確定要跳過備份檢查（不建議），可使用 --skip-backup-check")
                logging.error("=" * 60)
                sys.exit(1)

            logging.info("備份檢查: PASSED - 發現有效備份")

        if args.skip_backup_check and not args.dry_run:
            logging.warning("=" * 60)
            logging.warning("警告：已跳過備份檢查！")
            logging.warning("如果修復過程出錯，可能無法恢復資料。")
            logging.warning("=" * 60)

    # Stage 1-3: 修復操作
    if args.stage in ["summary", "all"]:
        success = repair_o3_summary(args.dry_run) and success

    if args.stage in ["scores", "all"]:
        success = repair_all_downstream(args.dry_run) and success

    if args.stage in ["o4mini-extra", "all"]:
        success = repair_o4mini_high_extra(args.dry_run) and success

    if success:
        logging.info("=" * 60)
        logging.info("All repairs completed successfully!")
        logging.info("=" * 60)
    else:
        logging.error("=" * 60)
        logging.error("Some repairs failed. Check logs for details.")
        logging.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()