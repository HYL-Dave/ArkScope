import type { FinancialCoveragePage, FundamentalsResult } from "./api";

export function financialFixture(): FundamentalsResult {
  const observation = "a".repeat(64);
  const statement = {
    report_period: null, end_month: "2025-12", fiscal_period: null, period_type: "annual",
    period_precision: "month" as const, provider: "seeking_alpha", currency: "USD", observation_id: observation,
    column_index: 2, unit_note: "USD millions", raw_reference: null,
    data: { revenue: "12345678901234567890.12" },
    value_metadata: { revenue: { status: "value", raw: "12345678901234.56789012", normalized_value: "12345678901234567890.12",
      currency: "USD", unit: "USD", precision: "provider_display_rounded" } },
  };
  const gap = { provider: "seeking_alpha", code: "mapping_not_reviewed", metric: "total_debt", required_inputs: ["interest_bearing_debt"] };
  const coverage = { ticker: "AAPL", status: "partial" as const, selected_source: "seeking_alpha" as const,
    period: "annual" as const, requested_currency: "USD", currency: "USD", read_id: "b".repeat(64),
    statements: { income_statement: [{ ...statement, fetched_at: "2026-09-20T12:00:00Z", value_precision: ["provider_display_rounded"] }] },
    missing_statements: ["balance_sheet", "cash_flow_statement"], supported_metrics: ["gross_margin"],
    metric_gaps: { total_debt: "mapping_not_reviewed" }, gaps: [gap] };
  return {
    ticker: "AAPL", status: "partial", snapshot_date: null, data_source: "seeking_alpha", read_id: coverage.read_id,
    market_cap: null, pe_ratio: null, forward_pe: null, ps_ratio: null, pb_ratio: null, roe: null, roa: null,
    debt_to_equity: null, current_ratio: null, revenue_growth: null, earnings_growth: null, dividend_yield: null,
    beta: null, gross_margin: 0.2431, operating_margin: null, net_margin: null, free_cash_flow: null,
    cash_and_equivalents: null, total_debt: null, snapshot: null,
    income_statements: [statement], balance_sheet: [], cash_flow_statements: [],
    coverage, read_gaps: [gap], metric_gaps: coverage.metric_gaps,
    metric_basis: { gross_margin: { provider: "seeking_alpha", observation_id: observation,
      end_month: "2025-12", precision: "provider_display_rounded", currency: "USD" } },
    source_observations: [{ provider: "seeking_alpha", dataset: "income_statement", observation_id: observation,
      fetched_at: "2026-09-20T12:00:00Z", source_url: "https://seekingalpha.com/symbol/AAPL/income-statement",
      freshness_mode: "stored", retrieval: "stored", persisted: true }],
    source_routes: [{ configured_sources: ["seeking_alpha", "financial_datasets"], selected_source: "seeking_alpha" }],
    update_choices: [{ provider: "seeking_alpha", action: "browser_capture",
      capture_urls: ["https://seekingalpha.com/symbol/AAPL/income-statement"] },
      { provider: "financial_datasets", action: "explicit_refresh", requires_paid_admission: true }],
    pagination: { offset: 0, limit: 4, total_periods: 6, has_more: true },
  };
}

export function coverageFixture(): FinancialCoveragePage {
  return { status: "partial", scope: "configured_local_candidates", candidate_count: 40,
    items: [financialFixture().coverage!], offset: 0, next_offset: 25, gaps: [] };
}
