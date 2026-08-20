"""Schema authority for security-lifecycle observations and investigations."""

from __future__ import annotations

from pathlib import Path
import re
import sqlite3


OBSERVATION_KINDS = frozenset(
    {
        "merger_agreement",
        "merger_proxy",
        "acquisition_completed",
        "listing_status_review",
        "listing_removal_notice",
    }
)
CASE_WORKFLOW_STATES = frozenset(
    {"unresolved", "investigating", "evidence_ready", "reviewed_inconclusive", "resolved"}
)
SOURCE_PRESENCE_STATES = frozenset({"present", "source_missing"})
RUN_TRIGGERS = frozenset({"attended_user"})
RUN_ADAPTERS = frozenset({"manual", "tavily"})
RUN_STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
RUN_FAILURE_CODES = frozenset(
    {
        "adapter_unavailable",
        "credential_missing",
        "permission_denied",
        "rate_limited",
        "network_error",
        "extract_failed",
        "unsupported_content",
    }
)
EVIDENCE_KINDS = frozenset(
    {
        "web_search_result",
        "web_page_excerpt",
        "manual_url",
        "manual_text",
        "document_reference",
    }
)
DOCUMENT_STATUSES = frozenset({"not_inspected", "extraction_needed"})
ASSESSMENT_STATUSES = frozenset({"draft", "accepted", "superseded"})
ASSESSMENT_RELEVANCE = frozenset(
    {"undetermined", "direct_tracked_security", "issuer_related", "unrelated"}
)
ASSESSMENT_CONFIDENCE = frozenset({"unknown", "low", "medium", "high"})
ASSESSMENT_OUTCOMES = frozenset(
    {
        "undetermined",
        "listing_ended",
        "venue_transfer",
        "symbol_changed",
        "symbol_or_venue_changed",
        "acquisition_cash",
        "acquisition_stock",
        "acquisition_mixed",
        "acquisition_terms_unknown",
        "issuer_security_change",
        "no_tracked_security_change",
        "other",
        "not_applicable",
    }
)
ASSESSMENT_AUTHORS = frozenset({"human", "legacy_review"})
ACKNOWLEDGEMENT_REASONS = frozenset({"evidence_insufficient"})
PROPOSAL_ACTIONS = frozenset(
    {
        "notify",
        "keep_tracking",
        "archive_manual_memberships",
        "hide_from_active_universe",
        "review_portfolio_position",
        "remap_symbol",
        "no_action",
    }
)
PROPOSAL_STATUSES = frozenset({"proposed", "dismissed"})
PROPOSAL_BLOCK_REASONS = frozenset(
    {
        "portfolio_position_open",
        "successor_evidence_missing",
        "source_context_unavailable",
        "stale_assessment",
        "action_executor_not_available",
    }
)
MIGRATION_PHASES = frozenset({"profile_written", "market_written", "complete"})


class LifecycleSchemaUnavailable(RuntimeError):
    """The requested SQLite database is absent or cannot be opened read-only."""


class LifecycleSchemaMismatch(RuntimeError):
    """A lifecycle schema is partial, extended, or differs from this authority."""


class LifecycleWritesUnavailable(RuntimeError):
    """Lifecycle writes are blocked while a two-store migration is incomplete."""


def _quoted(values: frozenset[str]) -> str:
    return ", ".join(f"'{value}'" for value in sorted(values))


MARKET_TABLE_SQL = {
    "security_lifecycle_observations": """
        CREATE TABLE security_lifecycle_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL CHECK (length(ticker) BETWEEN 1 AND 20),
            cik TEXT CHECK (cik IS NULL OR (length(cik) = 10 AND cik NOT GLOB '*[^0-9]*')),
            issuer_name TEXT NOT NULL CHECK (length(issuer_name) BETWEEN 1 AND 240),
            filing_date TEXT NOT NULL CHECK (length(filing_date) = 10),
            source TEXT NOT NULL CHECK (length(source) BETWEEN 1 AND 64),
            source_ref TEXT NOT NULL CHECK (length(source_ref) BETWEEN 1 AND 160 AND instr(source_ref, char(0)) = 0),
            filing_form TEXT NOT NULL CHECK (length(filing_form) BETWEEN 1 AND 30),
            filing_items_json TEXT NOT NULL,
            evidence_url TEXT NOT NULL CHECK (length(evidence_url) BETWEEN 1 AND 1000),
            description TEXT NOT NULL CHECK (length(description) <= 1000),
            first_observed_at TEXT NOT NULL,
            last_observed_at TEXT NOT NULL,
            UNIQUE(source, source_ref, ticker)
        )
    """,
    "security_lifecycle_observation_kinds": f"""
        CREATE TABLE security_lifecycle_observation_kinds (
            observation_id INTEGER NOT NULL REFERENCES security_lifecycle_observations(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL CHECK (event_type IN ({_quoted(OBSERVATION_KINDS)})),
            effective_date TEXT CHECK (effective_date IS NULL OR length(effective_date) = 10),
            PRIMARY KEY(observation_id, event_type)
        )
    """,
}

MARKET_INDEX_SQL = {
    "idx_security_lifecycle_ticker_date": """
        CREATE INDEX idx_security_lifecycle_ticker_date
        ON security_lifecycle_observations(ticker, filing_date DESC)
    """,
    "idx_security_lifecycle_source_identity": """
        CREATE INDEX idx_security_lifecycle_source_identity
        ON security_lifecycle_observations(source, source_ref, ticker)
    """,
}

PROFILE_TABLE_SQL = {
    "security_lifecycle_cases": """
        CREATE TABLE security_lifecycle_cases (
            case_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_ref TEXT NOT NULL CHECK (instr(source_ref, char(0)) = 0),
            ticker TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source, source_ref, ticker)
        )
    """,
    "security_lifecycle_investigation_runs": f"""
        CREATE TABLE security_lifecycle_investigation_runs (
            run_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            trigger TEXT NOT NULL CHECK (trigger IN ({_quoted(RUN_TRIGGERS)})),
            adapter TEXT NOT NULL CHECK (adapter IN ({_quoted(RUN_ADAPTERS)})),
            status TEXT NOT NULL CHECK (status IN ({_quoted(RUN_STATUSES)})),
            query_plan_json TEXT NOT NULL CHECK (length(query_plan_json) <= 6000),
            query_count INTEGER NOT NULL CHECK (query_count BETWEEN 0 AND 3),
            result_count INTEGER CHECK (result_count IS NULL OR result_count >= 0),
            fetch_count INTEGER NOT NULL CHECK (fetch_count BETWEEN 0 AND 5),
            usage_json TEXT NOT NULL CHECK (length(usage_json) <= 4096),
            failure_code TEXT CHECK (failure_code IS NULL OR failure_code IN ({_quoted(RUN_FAILURE_CODES)})),
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL,
            CHECK ((status = 'failed' AND failure_code IS NOT NULL) OR (status <> 'failed' AND failure_code IS NULL)),
            CHECK ((status = 'succeeded' AND result_count IS NOT NULL) OR status <> 'succeeded')
        )
    """,
    "security_lifecycle_evidence": f"""
        CREATE TABLE security_lifecycle_evidence (
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            run_id TEXT REFERENCES security_lifecycle_investigation_runs(run_id),
            kind TEXT NOT NULL CHECK (kind IN ({_quoted(EVIDENCE_KINDS)})),
            source_url TEXT CHECK (source_url IS NULL OR length(source_url) <= 1000),
            title TEXT CHECK (title IS NULL OR length(title) <= 500),
            publisher TEXT CHECK (publisher IS NULL OR length(publisher) <= 240),
            domain TEXT CHECK (domain IS NULL OR length(domain) <= 253),
            source_published_at TEXT,
            retrieved_at TEXT,
            adapter TEXT NOT NULL CHECK (adapter IN ({_quoted(RUN_ADAPTERS)})),
            excerpt TEXT NOT NULL CHECK (length(excerpt) <= 16000),
            content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
            mime_type TEXT CHECK (mime_type IS NULL OR length(mime_type) <= 127),
            document_status TEXT CHECK (document_status IS NULL OR document_status IN ({_quoted(DOCUMENT_STATUSES)})),
            created_at TEXT NOT NULL,
            CHECK ((kind = 'document_reference' AND document_status IS NOT NULL) OR (kind <> 'document_reference' AND document_status IS NULL))
        )
    """,
    "security_lifecycle_assessments": f"""
        CREATE TABLE security_lifecycle_assessments (
            assessment_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            status TEXT NOT NULL CHECK (status IN ({_quoted(ASSESSMENT_STATUSES)})),
            relevance TEXT NOT NULL CHECK (relevance IN ({_quoted(ASSESSMENT_RELEVANCE)})),
            confidence TEXT NOT NULL CHECK (confidence IN ({_quoted(ASSESSMENT_CONFIDENCE)})),
            author TEXT NOT NULL CHECK (author IN ({_quoted(ASSESSMENT_AUTHORS)})),
            conclusion TEXT NOT NULL CHECK (length(conclusion) BETWEEN 1 AND 4000),
            impact_summary TEXT NOT NULL CHECK (length(impact_summary) BETWEEN 1 AND 4000),
            counterparty_name TEXT CHECK (counterparty_name IS NULL OR length(counterparty_name) <= 240),
            counterparty_ticker TEXT CHECK (counterparty_ticker IS NULL OR length(counterparty_ticker) <= 20),
            counterparty_cik TEXT CHECK (counterparty_cik IS NULL OR (length(counterparty_cik) = 10 AND counterparty_cik NOT GLOB '*[^0-9]*')),
            successor_ticker TEXT CHECK (successor_ticker IS NULL OR length(successor_ticker) <= 20),
            destination_venue TEXT CHECK (destination_venue IS NULL OR length(destination_venue) <= 120),
            effective_date TEXT CHECK (effective_date IS NULL OR length(effective_date) = 10),
            consideration_currency TEXT CHECK (consideration_currency IS NULL OR (length(consideration_currency) = 3 AND consideration_currency NOT GLOB '*[^A-Z]*')),
            cash_per_security_decimal TEXT,
            exchange_ratio_decimal TEXT,
            observation_fingerprint_sha256 TEXT NOT NULL CHECK (length(observation_fingerprint_sha256) = 64),
            evidence_set_sha256 TEXT NOT NULL CHECK (length(evidence_set_sha256) = 64),
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            superseded_at TEXT,
            UNIQUE(case_id, revision)
        )
    """,
    "security_lifecycle_assessment_outcomes": f"""
        CREATE TABLE security_lifecycle_assessment_outcomes (
            assessment_id TEXT NOT NULL REFERENCES security_lifecycle_assessments(assessment_id) ON DELETE CASCADE,
            outcome TEXT NOT NULL CHECK (outcome IN ({_quoted(ASSESSMENT_OUTCOMES)})),
            PRIMARY KEY(assessment_id, outcome)
        )
    """,
    "security_lifecycle_assessment_evidence": """
        CREATE TABLE security_lifecycle_assessment_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id TEXT NOT NULL REFERENCES security_lifecycle_assessments(assessment_id) ON DELETE CASCADE,
            reference_kind TEXT NOT NULL CHECK (reference_kind IN ('observation', 'evidence')),
            evidence_id TEXT REFERENCES security_lifecycle_evidence(evidence_id),
            cited_content_sha256 TEXT NOT NULL CHECK (length(cited_content_sha256) = 64),
            CHECK ((reference_kind = 'observation' AND evidence_id IS NULL) OR (reference_kind = 'evidence' AND evidence_id IS NOT NULL))
        )
    """,
    "security_lifecycle_case_acknowledgements": f"""
        CREATE TABLE security_lifecycle_case_acknowledgements (
            acknowledgement_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            reason TEXT NOT NULL CHECK (reason IN ({_quoted(ACKNOWLEDGEMENT_REASONS)})),
            note TEXT CHECK (note IS NULL OR length(note) <= 2000),
            author TEXT NOT NULL CHECK (author = 'human'),
            observation_fingerprint_sha256 TEXT NOT NULL CHECK (length(observation_fingerprint_sha256) = 64),
            evidence_set_sha256 TEXT NOT NULL CHECK (length(evidence_set_sha256) = 64),
            acknowledged_at TEXT NOT NULL,
            reopened_at TEXT
        )
    """,
    "security_lifecycle_action_proposals": f"""
        CREATE TABLE security_lifecycle_action_proposals (
            proposal_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            assessment_id TEXT NOT NULL REFERENCES security_lifecycle_assessments(assessment_id) ON DELETE CASCADE,
            action_type TEXT NOT NULL CHECK (action_type IN ({_quoted(PROPOSAL_ACTIONS)})),
            status TEXT NOT NULL CHECK (status IN ({_quoted(PROPOSAL_STATUSES)})),
            source_ticker TEXT NOT NULL,
            replacement_ticker TEXT,
            source_snapshot_json TEXT NOT NULL,
            reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 2000),
            block_reason TEXT CHECK (block_reason IS NULL OR block_reason IN ({_quoted(PROPOSAL_BLOCK_REASONS)})),
            assessment_fingerprint_sha256 TEXT NOT NULL CHECK (length(assessment_fingerprint_sha256) = 64),
            proposal_dedupe_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            dismissed_at TEXT
        )
    """,
    "security_lifecycle_migration_receipts": f"""
        CREATE TABLE security_lifecycle_migration_receipts (
            migration_key TEXT PRIMARY KEY,
            market_snapshot_sha256 TEXT NOT NULL CHECK (length(market_snapshot_sha256) = 64),
            legacy_mapping_sha256 TEXT NOT NULL CHECK (length(legacy_mapping_sha256) = 64),
            phase TEXT NOT NULL CHECK (phase IN ({_quoted(MIGRATION_PHASES)})),
            expected_legacy_rows INTEGER NOT NULL,
            expected_observations INTEGER NOT NULL,
            expected_kinds INTEGER NOT NULL,
            expected_legacy_assessments INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        )
    """,
}

PROFILE_INDEX_SQL = {
    "idx_security_lifecycle_cases_identity": """
        CREATE INDEX idx_security_lifecycle_cases_identity
        ON security_lifecycle_cases(source, source_ref, ticker)
    """,
    "idx_security_lifecycle_runs_case_created": """
        CREATE INDEX idx_security_lifecycle_runs_case_created
        ON security_lifecycle_investigation_runs(case_id, created_at)
    """,
    "idx_security_lifecycle_evidence_case_created": """
        CREATE INDEX idx_security_lifecycle_evidence_case_created
        ON security_lifecycle_evidence(case_id, created_at)
    """,
    "idx_security_lifecycle_assessments_case_revision": """
        CREATE INDEX idx_security_lifecycle_assessments_case_revision
        ON security_lifecycle_assessments(case_id, revision DESC)
    """,
    "idx_security_lifecycle_one_current_ack": """
        CREATE UNIQUE INDEX idx_security_lifecycle_one_current_ack
        ON security_lifecycle_case_acknowledgements(case_id)
        WHERE reopened_at IS NULL
    """,
}


def _execute_schema(conn: sqlite3.Connection, tables: dict[str, str], indexes: dict[str, str]) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        for statement in tables.values():
            conn.execute(statement)
        for statement in indexes.values():
            conn.execute(statement)


def create_market_schema(conn: sqlite3.Connection) -> None:
    _execute_schema(conn, MARKET_TABLE_SQL, MARKET_INDEX_SQL)


def create_profile_schema(conn: sqlite3.Connection) -> None:
    _execute_schema(conn, PROFILE_TABLE_SQL, PROFILE_INDEX_SQL)


def _normalize_sql(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    normalized = normalized.replace("create table if not exists", "create table")
    normalized = normalized.replace("create index if not exists", "create index")
    normalized = normalized.replace("create unique index if not exists", "create unique index")
    return normalized


def _verify_connection(
    conn: sqlite3.Connection,
    tables: dict[str, str],
    indexes: dict[str, str],
) -> None:
    expected_tables = set(tables)
    expected_indexes = set(indexes)
    actual_tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'security_lifecycle_%'"
        )
    }
    if actual_tables != expected_tables:
        raise LifecycleSchemaMismatch("lifecycle table set mismatch")
    actual_indexes = {
        str(row[0]): str(row[1])
        for row in conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_security_lifecycle_%' AND sql IS NOT NULL"
        )
    }
    if set(actual_indexes) != expected_indexes:
        raise LifecycleSchemaMismatch("lifecycle index set mismatch")
    for name, expected in tables.items():
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        if row is None or _normalize_sql(row[0]) != _normalize_sql(expected):
            raise LifecycleSchemaMismatch(f"lifecycle table mismatch: {name}")
    for name, expected in indexes.items():
        if _normalize_sql(actual_indexes[name]) != _normalize_sql(expected):
            raise LifecycleSchemaMismatch(f"lifecycle index mismatch: {name}")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise LifecycleSchemaMismatch("lifecycle foreign key mismatch")


def verify_market_connection(conn: sqlite3.Connection) -> None:
    _verify_connection(conn, MARKET_TABLE_SQL, MARKET_INDEX_SQL)


def verify_profile_connection(conn: sqlite3.Connection) -> None:
    _verify_connection(conn, PROFILE_TABLE_SQL, PROFILE_INDEX_SQL)


def _verify_path(path: str | Path, verifier) -> None:
    candidate = Path(path)
    if not candidate.is_file():
        raise LifecycleSchemaUnavailable("lifecycle database is absent")
    try:
        conn = sqlite3.connect(f"file:{candidate.resolve()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise LifecycleSchemaUnavailable("lifecycle database is unavailable") from exc
    try:
        verifier(conn)
    except sqlite3.Error as exc:
        raise LifecycleSchemaMismatch("lifecycle schema query failed") from exc
    finally:
        conn.close()


def verify_market_schema(path: str | Path) -> None:
    _verify_path(path, verify_market_connection)


def verify_profile_schema(path: str | Path) -> None:
    _verify_path(path, verify_profile_connection)


def assert_lifecycle_writes_available(profile_conn: sqlite3.Connection | None) -> None:
    if profile_conn is None:
        return
    receipt_table = profile_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='security_lifecycle_migration_receipts'"
    ).fetchone()
    if receipt_table is None:
        return
    row = profile_conn.execute(
        "SELECT phase FROM security_lifecycle_migration_receipts "
        "WHERE phase <> 'complete' LIMIT 1"
    ).fetchone()
    if row is not None:
        raise LifecycleWritesUnavailable("security_lifecycle_migration_incomplete")
