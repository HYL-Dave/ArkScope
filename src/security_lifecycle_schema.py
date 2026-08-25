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
        "usage_limit_reached",
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


# V1 is the exact post-investigation/pre-automation authority. Keep these
# literal objects available for migration and rollback verification.
V1_PROFILE_TABLE_SQL = dict(PROFILE_TABLE_SQL)
V1_PROFILE_INDEX_SQL = dict(PROFILE_INDEX_SQL)

RUN_ADAPTERS = frozenset({"manual"})
RUN_FAILURE_CODES = frozenset(
    {
        "adapter_unavailable",
        "extract_failed",
        "unsupported_content",
    }
)
EVIDENCE_SOURCE_FAMILIES = frozenset(
    {"regulator", "market_infrastructure", "publisher", "general_web", "manual"}
)
EVIDENCE_ADAPTERS = frozenset(
    {"sec_edgar", "internal_news", "ibkr_contract", "manual", "hosted_search"}
)
EVIDENCE_KINDS = frozenset(
    {
        "regulator_excerpt",
        "market_infrastructure_snapshot",
        "publisher_excerpt",
        "hosted_search_citation",
        "manual_url",
        "manual_text",
        "document_reference",
    }
)
AUTOMATION_MODES = frozenset({"live", "historical"})
AUTOMATION_RUN_STATUSES = frozenset(
    {"queued", "running", "succeeded", "blocked", "failed", "cancelled"}
)
AUTOMATION_BLOCKER_CODES = frozenset(
    {
        "sec_identity_unconfigured",
        "sec_governor_unavailable",
        "sec_request_budget_exhausted",
        "sec_rate_limited",
        "sec_access_denied",
        "sec_transport_unavailable",
        "sec_document_unavailable",
        "sec_evidence_insufficient",
        "internal_news_unavailable",
        "internal_news_schema_mismatch",
        "ibkr_gateway_unavailable",
        "ibkr_contract_missing",
        "ibkr_contract_ambiguous",
        "ibkr_entitlement_denied",
        "market_confirmation_missing",
        "source_conflict",
        "impact_context_requested",
        "transition_approval_changed",
        "transition_approval_unavailable",
    }
)
AUTOMATION_FAILURE_CODES = frozenset(
    {
        "source_payload_invalid",
        "extractor_failed",
        "profile_schema_mismatch",
        "persistence_failed",
        "internal_error",
    }
)
DECISION_TIERS = frozenset({"verified_automatic", "review_suggested"})
ACTION_READINESS = frozenset(
    {
        "not_applicable",
        "waiting_effective_date",
        "waiting_market_confirmation",
        "waiting_transition_revalidation",
        "transition_eligible",
        "action_blocked",
    }
)
FACT_TYPES = frozenset(
    {
        "source_ticker",
        "successor_ticker",
        "source_venue",
        "destination_venue",
        "effective_date",
        "security_class",
        "issuer_cik",
        "transaction_structure",
        "tracked_security_effect",
    }
)
FACT_SCALAR_TYPES = FACT_TYPES - {"transaction_structure"}
TRANSACTION_TERMS_STATUSES = frozenset({"not_extracted", "partial", "complete"})
TRANSACTION_STRUCTURE_KINDS = frozenset(
    {
        "asset_acquisition",
        "cash",
        "corporate_unification",
        "mixed",
        "security_class_change",
        "spin_off",
        "stock",
        "unknown",
    }
)
ASSESSMENT_AUTHORS = frozenset({"human", "legacy_review", "automation"})
AUTOMATION_METHODS = frozenset({"deterministic_rule", "model_assisted"})
ACCEPTANCE_AUTHORITIES = frozenset(
    {"human", "automation_policy", "legacy_migration"}
)


PROFILE_TABLE_SQL = {
    **V1_PROFILE_TABLE_SQL,
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
    "security_lifecycle_automation_runs": f"""
        CREATE TABLE security_lifecycle_automation_runs (
            run_id TEXT PRIMARY KEY CHECK (length(run_id) BETWEEN 1 AND 120),
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            mode TEXT NOT NULL CHECK (mode IN ({_quoted(AUTOMATION_MODES)})),
            observation_fingerprint_sha256 TEXT NOT NULL CHECK (length(observation_fingerprint_sha256) = 64 AND observation_fingerprint_sha256 NOT GLOB '*[^0-9a-f]*'),
            policy_version TEXT NOT NULL CHECK (length(policy_version) BETWEEN 1 AND 120 AND instr(policy_version, char(0)) = 0),
            run_key TEXT NOT NULL UNIQUE CHECK (length(run_key) BETWEEN 1 AND 500 AND instr(run_key, char(0)) = 0),
            status TEXT NOT NULL CHECK (status IN ({_quoted(AUTOMATION_RUN_STATUSES)})),
            decision_tier TEXT CHECK (decision_tier IS NULL OR decision_tier IN ({_quoted(DECISION_TIERS)})),
            action_readiness TEXT CHECK (action_readiness IS NULL OR action_readiness IN ({_quoted(ACTION_READINESS)})),
            query_context_json TEXT NOT NULL CHECK (length(query_context_json) BETWEEN 2 AND 16384),
            diagnostics_json TEXT NOT NULL CHECK (length(diagnostics_json) BETWEEN 2 AND 8192),
            retry_at TEXT,
            failure_code TEXT CHECK (failure_code IS NULL OR failure_code IN ({_quoted(AUTOMATION_FAILURE_CODES)})),
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (retry_at IS NULL OR status = 'blocked'),
            CHECK (
                (status = 'queued' AND decision_tier IS NULL AND action_readiness IS NULL AND failure_code IS NULL AND started_at IS NULL AND finished_at IS NULL)
                OR (status = 'running' AND decision_tier IS NULL AND action_readiness IS NULL AND failure_code IS NULL AND started_at IS NOT NULL AND finished_at IS NULL)
                OR (status = 'succeeded' AND decision_tier IS NOT NULL AND action_readiness IS NOT NULL AND failure_code IS NULL AND started_at IS NOT NULL AND finished_at IS NOT NULL)
                OR (status = 'blocked' AND failure_code IS NULL AND started_at IS NOT NULL AND finished_at IS NOT NULL)
                OR (status = 'failed' AND failure_code IS NOT NULL AND started_at IS NOT NULL AND finished_at IS NOT NULL)
                OR (status = 'cancelled' AND failure_code IS NULL AND finished_at IS NOT NULL)
            )
        )
    """,
    "security_lifecycle_automation_run_blockers": f"""
        CREATE TABLE security_lifecycle_automation_run_blockers (
            automation_run_id TEXT NOT NULL REFERENCES security_lifecycle_automation_runs(run_id) ON DELETE CASCADE,
            blocker_code TEXT NOT NULL CHECK (blocker_code IN ({_quoted(AUTOMATION_BLOCKER_CODES)})),
            retryable INTEGER NOT NULL CHECK (retryable IN (0, 1)),
            context_json TEXT NOT NULL CHECK (length(context_json) BETWEEN 2 AND 4096),
            created_at TEXT NOT NULL,
            PRIMARY KEY(automation_run_id, blocker_code)
        )
    """,
    "security_lifecycle_evidence": f"""
        CREATE TABLE security_lifecycle_evidence (
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            run_id TEXT REFERENCES security_lifecycle_investigation_runs(run_id),
            automation_run_id TEXT REFERENCES security_lifecycle_automation_runs(run_id),
            source_family TEXT NOT NULL CHECK (source_family IN ({_quoted(EVIDENCE_SOURCE_FAMILIES)})),
            kind TEXT NOT NULL CHECK (kind IN ({_quoted(EVIDENCE_KINDS)})),
            source_url TEXT CHECK (source_url IS NULL OR length(source_url) <= 1000),
            title TEXT CHECK (title IS NULL OR length(title) <= 500),
            publisher TEXT CHECK (publisher IS NULL OR length(publisher) <= 240),
            domain TEXT CHECK (domain IS NULL OR length(domain) <= 253),
            source_published_at TEXT,
            retrieved_at TEXT,
            adapter TEXT NOT NULL CHECK (adapter IN ({_quoted(EVIDENCE_ADAPTERS)})),
            excerpt TEXT NOT NULL CHECK (length(excerpt) <= 16000),
            content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'),
            source_document_sha256 TEXT CHECK (source_document_sha256 IS NULL OR (length(source_document_sha256) = 64 AND source_document_sha256 NOT GLOB '*[^0-9a-f]*')),
            source_locator_json TEXT CHECK (source_locator_json IS NULL OR length(source_locator_json) BETWEEN 2 AND 4096),
            evidence_dedupe_key TEXT NOT NULL UNIQUE CHECK (length(evidence_dedupe_key) BETWEEN 1 AND 500 AND instr(evidence_dedupe_key, char(0)) = 0),
            mime_type TEXT CHECK (mime_type IS NULL OR length(mime_type) <= 127),
            document_status TEXT CHECK (document_status IS NULL OR document_status IN ({_quoted(DOCUMENT_STATUSES)})),
            created_at TEXT NOT NULL,
            UNIQUE(evidence_id, content_sha256),
            CHECK (run_id IS NULL OR automation_run_id IS NULL),
            CHECK ((kind = 'document_reference' AND document_status IS NOT NULL) OR (kind <> 'document_reference' AND document_status IS NULL)),
            CHECK (
                (adapter = 'manual' AND source_family = 'manual' AND kind IN ('manual_url', 'manual_text', 'document_reference') AND automation_run_id IS NULL)
                OR (adapter = 'sec_edgar' AND source_family = 'regulator' AND kind = 'regulator_excerpt' AND run_id IS NULL AND automation_run_id IS NOT NULL AND source_document_sha256 IS NOT NULL AND source_locator_json IS NOT NULL)
                OR (adapter = 'internal_news' AND source_family = 'publisher' AND kind = 'publisher_excerpt' AND run_id IS NULL AND automation_run_id IS NOT NULL)
                OR (adapter = 'ibkr_contract' AND source_family = 'market_infrastructure' AND kind = 'market_infrastructure_snapshot' AND run_id IS NULL AND automation_run_id IS NOT NULL)
                OR (adapter = 'hosted_search' AND source_family = 'general_web' AND kind = 'hosted_search_citation' AND run_id IS NULL AND automation_run_id IS NOT NULL)
            )
        )
    """,
    "security_lifecycle_automation_facts": f"""
        CREATE TABLE security_lifecycle_automation_facts (
            fact_id TEXT PRIMARY KEY CHECK (length(fact_id) BETWEEN 1 AND 120),
            automation_run_id TEXT NOT NULL REFERENCES security_lifecycle_automation_runs(run_id) ON DELETE CASCADE,
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            evidence_id TEXT NOT NULL REFERENCES security_lifecycle_evidence(evidence_id) ON DELETE RESTRICT,
            fact_type TEXT NOT NULL CHECK (fact_type IN ({_quoted(FACT_TYPES)})),
            normalized_value_json TEXT NOT NULL CHECK (length(normalized_value_json) BETWEEN 1 AND 4096),
            source_span_start INTEGER NOT NULL CHECK (source_span_start >= 0),
            source_span_end INTEGER NOT NULL CHECK (source_span_end > source_span_start),
            cited_text_sha256 TEXT NOT NULL CHECK (length(cited_text_sha256) = 64 AND cited_text_sha256 NOT GLOB '*[^0-9a-f]*'),
            extractor_rule_id TEXT NOT NULL CHECK (length(extractor_rule_id) BETWEEN 1 AND 160 AND instr(extractor_rule_id, char(0)) = 0),
            extractor_rule_version TEXT NOT NULL CHECK (length(extractor_rule_version) BETWEEN 1 AND 120 AND instr(extractor_rule_version, char(0)) = 0),
            fact_dedupe_key TEXT NOT NULL UNIQUE CHECK (length(fact_dedupe_key) BETWEEN 1 AND 500 AND instr(fact_dedupe_key, char(0)) = 0),
            created_at TEXT NOT NULL
        )
    """,
    "security_lifecycle_evidence_translations": """
        CREATE TABLE security_lifecycle_evidence_translations (
            evidence_id TEXT NOT NULL,
            evidence_content_sha256 TEXT NOT NULL CHECK (length(evidence_content_sha256) = 64 AND evidence_content_sha256 NOT GLOB '*[^0-9a-f]*'),
            locale TEXT NOT NULL CHECK (length(locale) BETWEEN 2 AND 32 AND instr(locale, char(0)) = 0),
            translated_text TEXT NOT NULL CHECK (length(translated_text) BETWEEN 1 AND 16000),
            provider TEXT NOT NULL CHECK (length(provider) BETWEEN 1 AND 64 AND instr(provider, char(0)) = 0),
            model TEXT NOT NULL CHECK (length(model) BETWEEN 1 AND 160 AND instr(model, char(0)) = 0),
            harness TEXT NOT NULL CHECK (length(harness) BETWEEN 1 AND 160 AND instr(harness, char(0)) = 0),
            translated_at TEXT NOT NULL,
            PRIMARY KEY(evidence_id, evidence_content_sha256, locale),
            FOREIGN KEY(evidence_id, evidence_content_sha256)
                REFERENCES security_lifecycle_evidence(evidence_id, content_sha256)
                ON DELETE CASCADE
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
            observation_fingerprint_sha256 TEXT NOT NULL CHECK (length(observation_fingerprint_sha256) = 64 AND observation_fingerprint_sha256 NOT GLOB '*[^0-9a-f]*'),
            evidence_set_sha256 TEXT NOT NULL CHECK (length(evidence_set_sha256) = 64 AND evidence_set_sha256 NOT GLOB '*[^0-9a-f]*'),
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            superseded_at TEXT,
            automation_method TEXT CHECK (automation_method IS NULL OR automation_method IN ({_quoted(AUTOMATION_METHODS)})),
            acceptance_authority TEXT CHECK (acceptance_authority IS NULL OR acceptance_authority IN ({_quoted(ACCEPTANCE_AUTHORITIES)})),
            automation_run_id TEXT REFERENCES security_lifecycle_automation_runs(run_id) ON DELETE RESTRICT,
            rule_id TEXT CHECK (rule_id IS NULL OR (length(rule_id) BETWEEN 1 AND 160 AND instr(rule_id, char(0)) = 0)),
            rule_version TEXT CHECK (rule_version IS NULL OR (length(rule_version) BETWEEN 1 AND 120 AND instr(rule_version, char(0)) = 0)),
            decision_provenance_sha256 TEXT CHECK (decision_provenance_sha256 IS NULL OR (length(decision_provenance_sha256) = 64 AND decision_provenance_sha256 NOT GLOB '*[^0-9a-f]*')),
            UNIQUE(case_id, revision),
            CHECK (
                (status = 'draft' AND acceptance_authority IS NULL AND accepted_at IS NULL AND superseded_at IS NULL)
                OR (status = 'accepted' AND acceptance_authority IS NOT NULL AND accepted_at IS NOT NULL AND superseded_at IS NULL)
                OR (status = 'superseded' AND acceptance_authority IS NOT NULL AND accepted_at IS NOT NULL AND superseded_at IS NOT NULL)
            ),
            CHECK (
                (author = 'human' AND automation_method IS NULL AND automation_run_id IS NULL AND rule_id IS NULL AND rule_version IS NULL AND decision_provenance_sha256 IS NULL AND (acceptance_authority IS NULL OR acceptance_authority = 'human'))
                OR (author = 'legacy_review' AND automation_method IS NULL AND automation_run_id IS NULL AND rule_id IS NULL AND rule_version IS NULL AND decision_provenance_sha256 IS NULL AND (acceptance_authority IS NULL OR acceptance_authority = 'legacy_migration'))
                OR (author = 'automation' AND automation_method IS NOT NULL AND automation_run_id IS NOT NULL AND rule_id IS NOT NULL AND rule_version IS NOT NULL AND decision_provenance_sha256 IS NOT NULL AND (acceptance_authority IS NULL OR acceptance_authority IN ('human', 'automation_policy')))
            ),
            CHECK (acceptance_authority <> 'automation_policy' OR automation_method = 'deterministic_rule')
        )
    """,
}


PROFILE_INDEX_SQL = {
    **V1_PROFILE_INDEX_SQL,
    "idx_security_lifecycle_automation_runs_case_created": """
        CREATE INDEX idx_security_lifecycle_automation_runs_case_created
        ON security_lifecycle_automation_runs(case_id, created_at)
    """,
    "idx_security_lifecycle_automation_blockers_run": """
        CREATE INDEX idx_security_lifecycle_automation_blockers_run
        ON security_lifecycle_automation_run_blockers(automation_run_id, blocker_code)
    """,
    "idx_security_lifecycle_evidence_automation_run": """
        CREATE INDEX idx_security_lifecycle_evidence_automation_run
        ON security_lifecycle_evidence(automation_run_id, created_at)
    """,
    "idx_security_lifecycle_facts_run_type": """
        CREATE INDEX idx_security_lifecycle_facts_run_type
        ON security_lifecycle_automation_facts(automation_run_id, fact_type)
    """,
    "idx_security_lifecycle_translations_evidence_locale": """
        CREATE INDEX idx_security_lifecycle_translations_evidence_locale
        ON security_lifecycle_evidence_translations(evidence_id, locale)
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


def create_v1_profile_schema(conn: sqlite3.Connection) -> None:
    _execute_schema(conn, V1_PROFILE_TABLE_SQL, V1_PROFILE_INDEX_SQL)


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


def verify_v1_profile_connection(conn: sqlite3.Connection) -> None:
    _verify_connection(conn, V1_PROFILE_TABLE_SQL, V1_PROFILE_INDEX_SQL)


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
