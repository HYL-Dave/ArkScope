from __future__ import annotations


def _observation(
    *,
    form: str = "8-K",
    items: tuple[str, ...] = ("2.01",),
) -> dict[str, object]:
    return {
        "ticker": "BLBD",
        "cik": "0001589526",
        "issuer_name": "Blue Bird Corporation",
        "filing_date": "2026-07-15",
        "filing_form": form,
        "filing_items": list(items),
        "evidence_url": "https://www.sec.gov/Archives/example",
    }


def _run(
    run_id: str = "run-current",
    *,
    fingerprint: str = "f" * 64,
    status: str = "blocked",
    blockers: tuple[str, ...] = ("sec_evidence_insufficient",),
    completed: int = 1,
    candidates: int = 1,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "observation_fingerprint_sha256": fingerprint,
        "status": status,
        "blockers": [
            {"blocker_code": blocker, "retryable": True} for blocker in blockers
        ],
        "diagnostics": {
            "sec_candidate_document_count": candidates,
            "sec_completed_document_count": completed,
        },
    }


def _fact(
    fact_type: str,
    value: object,
    *,
    run_id: str = "run-current",
    evidence_id: str = "evidence-current",
) -> dict[str, object]:
    return {
        "automation_run_id": run_id,
        "evidence_id": evidence_id,
        "source_family": "regulator",
        "fact_type": fact_type,
        "normalized_value": value,
    }


def _classify(
    *,
    observation: dict[str, object] | None = None,
    runs: tuple[dict[str, object], ...] = (),
    facts: tuple[dict[str, object], ...] = (),
):
    from src.security_lifecycle_sec_admission import classify_sec_admission

    return classify_sec_admission(
        observation=observation or _observation(),
        observation_fingerprint_sha256="f" * 64,
        automation_runs=runs,
        automation_facts=facts,
    )


def test_direct_listing_item_is_admitted_without_waiting_for_extraction():
    decision = _classify(observation=_observation(items=("3.01",)))

    assert (decision.state, decision.reason) == (
        "admitted",
        "direct_listing_item",
    )


def test_identity_form_requires_an_exact_current_ticker_binding():
    missing = _classify(
        observation=_observation(form="25-NSE", items=()),
        runs=(_run(),),
    )
    bound = _classify(
        observation=_observation(form="25-NSE", items=()),
        runs=(_run(),),
        facts=(
            _fact("source_ticker", "BLBD"),
            _fact("tracked_security_effect", "terminal_delisting"),
        ),
    )

    assert (missing.state, missing.reason) == (
        "needs_review",
        "identity_binding_missing",
    )
    assert (bound.state, bound.reason) == (
        "admitted",
        "direct_identity_filing",
    )


def test_blbd_and_ccl_material_effects_promote_conditional_candidates():
    for effect in (
        "asset_acquisition_no_registrant_change",
        "no_identity_change",
    ):
        decision = _classify(
            runs=(_run(status="succeeded", blockers=()),),
            facts=(
                _fact("source_ticker", "BLBD"),
                _fact("tracked_security_effect", effect),
            ),
        )
        assert (decision.state, decision.reason) == (
            "admitted",
            "material_tracked_security_fact",
        )


def test_completed_conditional_candidate_without_material_fact_is_screened_out():
    decision = _classify(
        runs=(_run(),),
        facts=(
            _fact("issuer_cik", "0001589526"),
            _fact("source_ticker", "BLBD"),
        ),
    )

    assert (decision.state, decision.reason) == (
        "screened_out",
        "no_material_tracked_security_fact",
    )


def test_incomplete_or_failed_regulator_acquisition_never_screens_on_zero_facts():
    incomplete = _classify(runs=(_run(completed=0),))
    failed = _classify(
        runs=(
            _run(
                status="failed",
                blockers=(),
                completed=0,
            ),
        )
    )

    assert (incomplete.state, incomplete.reason) == (
        "needs_review",
        "regulator_screening_incomplete",
    )
    assert (failed.state, failed.reason) == (
        "needs_review",
        "regulator_screening_incomplete",
    )


def test_unknown_candidate_form_is_visible_instead_of_silently_screened():
    decision = _classify(observation=_observation(form="S-4", items=()))

    assert (decision.state, decision.reason) == ("needs_review", "unknown_form")


def test_only_latest_matching_run_and_its_regulator_facts_can_admit():
    stale_material = (
        _fact(
            "tracked_security_effect",
            "no_identity_change",
            run_id="run-stale",
        ),
    )
    decision = _classify(
        runs=(
            _run("run-new-observation", fingerprint="a" * 64, status="succeeded", blockers=()),
            _run("run-current"),
            _run("run-stale", status="succeeded", blockers=()),
        ),
        facts=stale_material,
    )

    assert (decision.state, decision.reason) == (
        "screened_out",
        "no_material_tracked_security_fact",
    )


def test_effective_date_is_material_only_when_same_evidence_binds_current_ticker():
    unrelated = _classify(
        runs=(_run(status="succeeded", blockers=()),),
        facts=(
            _fact("source_ticker", "BLBD", evidence_id="identity"),
            _fact("effective_date", "2026-07-20", evidence_id="other"),
        ),
    )
    bound = _classify(
        runs=(_run(status="succeeded", blockers=()),),
        facts=(
            _fact("source_ticker", "BLBD"),
            _fact("effective_date", "2026-07-20"),
        ),
    )

    assert unrelated.state == "screened_out"
    assert (bound.state, bound.reason) == (
        "admitted",
        "material_tracked_security_fact",
    )


def test_candidate_projection_is_closed_and_contains_no_run_or_fact_storage_fields():
    from src.security_lifecycle_sec_admission import project_sec_candidate

    projected = project_sec_candidate(
        case_id="slc_case",
        observation=_observation(),
        decision=_classify(),
    )

    assert projected == {
        "case_id": "slc_case",
        "ticker": "BLBD",
        "issuer_name": "Blue Bird Corporation",
        "filing_form": "8-K",
        "filing_items": ["2.01"],
        "filing_date": "2026-07-15",
        "evidence_url": "https://www.sec.gov/Archives/example",
        "admission_state": "pending",
        "admission_reason": "awaiting_regulator_screening",
    }
