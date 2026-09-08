"""Whole-focus ownership for instrument binding and bounded OAuth exploration."""

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-07-lifecycle-web-usage-canary"))
from verify_json_analysis import verifier


mutation = verifier.mutation
FINDING = "src/security_lifecycle_web_finding.py"
PIPELINE = "src/security_lifecycle_web_pipeline.py"
CONTRACT = "src/security_lifecycle_web_contract.py"
CLAUDE = "src/auth_drivers/lifecycle_web_claude.py"
verifier.MUTATIONS["backend"] += (
    mutation("event_class_binding_removed", "test_other_instrument_delisting_never_combines_with_stock_identity", FINDING,
        "if _contains(citation.quote, finding.security_class)", "if True"),
    mutation("event_identity_anchor_removed", "test_unbound_same_class_event_from_another_issuer_does_not_supply_stock_change", FINDING,
        "and (citation.source_id in identity_sources\n             or (_contains(citation.quote, request.issuer_name)\n                 and _contains(citation.quote, request.ticker, symbol=True)))",
        "and True"),
    mutation("date_borrows_unrelated_security", "test_other_instrument_date_cannot_complete_a_stock_listing_event", FINDING,
        'or not any("effective_date" in item.supports and finding.effective_date_text in item.quote for item in event_citations)',
        'or not any("effective_date" in item.supports and finding.effective_date_text in item.quote for item in admitted)'),
    mutation("listing_labels_are_pooled", "test_other_instrument_delisting_never_combines_with_stock_identity", FINDING,
        'if "listing_ended" not in target_support:', 'if "listing_ended" not in support:'),
    mutation("unrelated_otc_security_vetoes_stock", "test_only_target_instrument_active_otc_evidence_vetoes_stock_removal", FINDING,
        'if target_support & {"active_listing", "active_otc"}:', 'if support & {"active_listing", "active_otc"}:'),
    mutation("oauth_budget_remains_four_searches", "test_only_claude_oauth_gets_the_larger_preflight_and_execution_budget", PIPELINE,
        "max_search_uses=12 if expanded else 4,", "max_search_uses=4,"),
    mutation("other_transports_expanded_without_admission", "test_only_claude_oauth_gets_the_larger_preflight_and_execution_budget", PIPELINE,
        'expanded = auth_mode == "claude_code_oauth"', 'expanded = True'),
    mutation("expanded_search_has_no_upper_bound", "test_expanded_claude_search_allows_twelve_and_denies_the_thirteenth_before_execution", CLAUDE,
        "elif len(self._search) >= self.call.max_search_uses:", "elif False:"),
    mutation("search_does_not_receive_its_budget", "test_actual_model_prompts_separate_instruments_and_explain_available_search_budget", PIPELINE,
        '+ f"Your search budget is at most {options.max_search_uses} WebSearch calls; "', '+ "Search for this public question; "'),
    mutation("search_does_not_receive_instrument_scope", "test_actual_model_prompts_separate_instruments_and_explain_available_search_budget", CONTRACT,
        '"Exclude notices that concern only other instruments of the same issuer: common shares, preferred shares, "',
        '"Common shares, preferred shares, "'),
)


if __name__ == "__main__":
    verifier.main()
