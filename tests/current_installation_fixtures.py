"""Direct populated V4 fixtures with retained lifecycle, identity and unowned SQL."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3


_AT = "2026-08-28T00:00:00Z"
_HEX_A = "a" * 64
_HEX_B = "b" * 64
_HEX_C = "c" * 64
_HEX_D = "d" * 64
_AUTOMATION_BLOCKER_CODES = frozenset(
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


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def seeded_current_profile(tmp_path: Path, name: str = "profile.db") -> Path:
    from src.portfolio_state import PortfolioStore
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_schema import create_profile_schema
    from src.ticker_identity_schema import create_ticker_identity_schema

    path = tmp_path / name
    ProfileStateStore(path)
    PortfolioStore(path)
    conn = sqlite3.connect(path)
    try:
        create_profile_schema(conn)
        create_ticker_identity_schema(conn)
        conn.executescript(
            """
            CREATE TABLE job_runs (job_name TEXT PRIMARY KEY, tick INTEGER NOT NULL);
            CREATE INDEX idx_job_runs_tick ON job_runs(tick);
            CREATE VIEW job_run_projection AS SELECT job_name,tick FROM job_runs;
            CREATE TABLE job_audit (job_name TEXT NOT NULL, old_tick INTEGER NOT NULL);
            CREATE TRIGGER trg_job_runs_update AFTER UPDATE ON job_runs
            BEGIN
                INSERT INTO job_audit VALUES (OLD.job_name, OLD.tick);
            END;
            INSERT INTO job_runs VALUES ('scheduler', 1);
            CREATE VIEW retained_lifecycle_view AS
                SELECT evidence_id,excerpt FROM security_lifecycle_evidence;
            CREATE INDEX retained_evidence_case ON security_lifecycle_evidence(case_id);
            CREATE TRIGGER retained_evidence_audit AFTER UPDATE ON security_lifecycle_evidence
            BEGIN
                INSERT INTO job_audit VALUES ('evidence', OLD.rowid);
            END;
            """
        )
        conn.execute(
            "INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)",
            ("slc_1", "sec_edgar", "filing-1", "OLD", _AT, _AT),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_investigation_runs "
            "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
            "result_count,fetch_count,usage_json,failure_code,started_at,finished_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slr_1",
                "slc_1",
                "attended_user",
                "manual",
                "succeeded",
                "[]",
                0,
                0,
                0,
                "{}",
                None,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_runs "
            "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
            "run_key,status,decision_tier,action_readiness,query_context_json,"
            "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slar_success",
                "slc_1",
                "historical",
                _HEX_A,
                "policy-v3",
                "run:success",
                "succeeded",
                "verified_automatic",
                "not_applicable",
                "{}",
                "{}",
                None,
                None,
                _AT,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_runs "
            "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
            "run_key,status,decision_tier,action_readiness,query_context_json,"
            "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slar_blocked",
                "slc_1",
                "live",
                _HEX_B,
                "policy-v3",
                "run:blocked",
                "blocked",
                None,
                None,
                "{}",
                "{}",
                _AT,
                None,
                _AT,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.executemany(
            "INSERT INTO security_lifecycle_automation_run_blockers VALUES (?,?,?,?,?)",
            [
                ("slar_blocked", code, 1, "{}", _AT)
                for code in sorted(_AUTOMATION_BLOCKER_CODES)
            ],
        )
        excerpt = "Publisher evidence retained verbatim."
        content_sha = _sha(excerpt)
        conn.execute(
            "INSERT INTO security_lifecycle_evidence "
            "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
            "source_url,title,publisher,domain,source_published_at,retrieved_at,adapter,"
            "excerpt,content_sha256,source_document_sha256,source_locator_json,"
            "evidence_dedupe_key,mime_type,document_status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sle_publisher",
                "slc_1",
                None,
                "slar_success",
                "publisher",
                "publisher_excerpt",
                "https://example.com/article",
                "Legacy article",
                "Example",
                "example.com",
                "2026-08-27",
                _AT,
                "internal_news",
                excerpt,
                content_sha,
                None,
                None,
                "evidence:publisher",
                "text/plain",
                None,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_evidence_translations VALUES (?,?,?,?,?,?,?,?)",
            (
                "sle_publisher",
                content_sha,
                "zh-TW",
                "Translated publisher evidence.",
                "openai",
                "model-1",
                "harness-1",
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slf_1",
                "slar_success",
                "slc_1",
                "sle_publisher",
                "source_ticker",
                '"OLD"',
                0,
                9,
                _HEX_C,
                "publisher-rule",
                "1",
                "fact:source-ticker",
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_assessments "
            "(assessment_id,case_id,revision,status,relevance,confidence,author,"
            "conclusion,impact_summary,counterparty_name,counterparty_ticker,"
            "counterparty_cik,successor_ticker,destination_venue,effective_date,"
            "consideration_currency,cash_per_security_decimal,exchange_ratio_decimal,"
            "observation_fingerprint_sha256,evidence_set_sha256,created_at,accepted_at,"
            "superseded_at,automation_method,acceptance_authority,automation_run_id,"
            "rule_id,rule_version,decision_provenance_sha256) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sla_1",
                "slc_1",
                1,
                "accepted",
                "direct_tracked_security",
                "high",
                "automation",
                "Legacy conclusion",
                "Legacy impact",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                _HEX_A,
                _HEX_D,
                _AT,
                _AT,
                None,
                "deterministic_rule",
                "automation_policy",
                "slar_success",
                "policy-rule",
                "3",
                _HEX_D,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_assessment_outcomes VALUES (?,?)",
            ("sla_1", "no_tracked_security_change"),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_assessment_evidence "
            "(id,assessment_id,reference_kind,evidence_id,cited_content_sha256) "
            "VALUES (?,?,?,?,?)",
            (17, "sla_1", "evidence", "sle_publisher", content_sha),
        )
        conn.execute(
            "UPDATE sqlite_sequence SET seq=41 "
            "WHERE name='security_lifecycle_assessment_evidence'"
        )
        conn.execute(
            "INSERT INTO security_lifecycle_case_acknowledgements VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "slk_1",
                "slc_1",
                "evidence_insufficient",
                "Legacy acknowledgement",
                "human",
                _HEX_A,
                _HEX_D,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_action_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slp_1",
                "slc_1",
                "sla_1",
                "notify",
                "proposed",
                "OLD",
                None,
                "[]",
                "Legacy proposal",
                None,
                _HEX_D,
                "proposal:1",
                _AT,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_migration_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-v1",
                _HEX_A,
                _HEX_B,
                "complete",
                1,
                1,
                1,
                1,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transitions VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tit_1",
                "slc_1",
                "sla_1",
                '["slp_1"]',
                "transition:1",
                "symbol_continuation",
                "approved",
                "OLD",
                "NEW",
                "2026-08-28",
                None,
                0,
                _HEX_A,
                _HEX_D,
                _HEX_C,
                '{"eligible":true}',
                None,
                None,
                _AT,
                _AT,
                None,
                None,
                None,
                "attended_user",
                None,
                None,
                None,
                _HEX_D,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transition_attempts VALUES (?,?,?,?,?,?,?)",
            ("tia_1", "tit_1", "attended_user", "blocked", "[]", _HEX_C, _AT),
        )
        conn.execute(
            "INSERT INTO ticker_identity_links VALUES (?,?,?,?,?,?,?,?)",
            ("til_1", "tit_1", "OLD", "NEW", "symbol_continuation", "2026-08-28", _AT, None),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transition_activity VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tiact_1",
                "tit_1",
                "applied",
                "OLD",
                "NEW",
                "2026-08-28",
                "[]",
                "[]",
                _HEX_A,
                None,
                None,
                _HEX_D,
                _AT,
                None,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_provider_checks VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("provider-1", "OLD", _AT, "{}", "[]", "{}", "[]", "active", _HEX_A, _AT),
        )
        conn.commit()
    finally:
        conn.close()
    return path
