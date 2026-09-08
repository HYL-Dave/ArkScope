/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { withTestUiLocale } from "../test/testUiLocale";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const ACTIVITY_MODULE = "./LifecycleActivityBand";
const decisions = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/ticker_history_decisions_v1.json"), "utf8"));

const APPLIED_ACTIVITY = {
  activity_id: "activity-applied",
  transition_id: "transition-1",
  case_id: "case-1",
  activity_type: "applied",
  source_ticker: "OLD",
  successor_ticker: "NEW",
  effective_date: "2026-08-25",
  user_owned_changes: [
    { change_type: "watchlist_membership_archived", count: 2 },
    { change_type: "watchlist_membership_added", count: 2 },
  ],
  provider_owned_retained: ["sa_alpha_picks_current"],
  state_sha256: "a".repeat(64),
  rule_id: "simple-symbol-continuation",
  rule_version: "1",
  decision_provenance_sha256: "b".repeat(64),
  occurred_at: "2026-08-25T12:00:00Z",
  acknowledged_at: null,
  created_at: "2026-08-25T12:00:00Z",
  reverse_readiness: { reversible: true, block_reasons: [] },
};

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function mountActivity(
  items: Array<Record<string, unknown>>,
  onAcknowledge = vi.fn(),
  onReverse = vi.fn(),
) {
  const { LifecycleActivityBand } = await import(
    /* @vite-ignore */ ACTIVITY_MODULE
  );
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(withTestUiLocale(
      <LifecycleActivityBand
        items={items}
        busyAction={null}
        onAcknowledge={onAcknowledge}
        onReverse={onReverse}
      />,
    ));
    await Promise.resolve();
  });
  return { onAcknowledge, onReverse };
}

async function click(label: string) {
  const button = Array.from(document.body.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(label));
  if (!button) throw new Error(`missing button: ${label}`);
  await act(async () => button.click());
}

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.clearAllMocks();
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

describe("Lifecycle transition activity", () => {
  it.each(["en", "zh-Hant"])("shows legacy reason, evidence and approval without inventing LLM use or non-use (%s)", async (locale) => {
    await i18n.changeLanguage(locale);
    const commands = await mountActivity([{ ...APPLIED_ACTIVITY, rule_id: null, rule_version: null,
      successor_ticker: null, decision: decisions.provider }]);
    const article = document.querySelector("article")!;
    expect(article.textContent).toContain(decisions.provider.summary);
    const overview = article.querySelector(".lifecycle-decision-overview")!;
    expect(overview?.textContent).toContain("Massive / EODHD / Nasdaq");
    expect(overview?.textContent).not.toContain(locale === "en" ? "No LLM used" : "未使用 LLM");
    expect(overview?.textContent).toContain(locale === "en" ? "Approved by user" : "由使用者核准");
    expect(overview?.textContent).toContain(decisions.provider.limitations[0]);
    expect(overview?.textContent).toContain(locale === "en" ? "Legacy assessment details were not sealed" : "舊版評估資訊未另行封存");
    const details = article.querySelector("details")!;
    expect(details).not.toBeNull();
    expect(details.open).toBe(false);
    await act(async () => details.querySelector("summary")!.click());
    expect(details.open).toBe(true);
    expect(details.querySelectorAll('a[href="https://example.com/status"]')).toHaveLength(6);
    expect(details.textContent).toContain(locale === "en" ? "Not in this directory" : "未列於此名錄");
    expect(commands.onAcknowledge).not.toHaveBeenCalled();
    expect(commands.onReverse).not.toHaveBeenCalled();
    expect(article.textContent).not.toContain("a".repeat(64));
  });

  it("can identify a sealed provider-only review as using no LLM", async () => {
    await mountActivity([{ ...APPLIED_ACTIVITY, rule_id: null, rule_version: null, successor_ticker: null,
      decision: { ...decisions.provider, gaps: [] } }]);
    expect(document.querySelector(".lifecycle-decision-overview")?.textContent).toContain("No LLM used");
  });

  it.each(["en", "zh-Hant"])("distinguishes the LLM from its news source and the human approver (%s)", async (locale) => {
    await i18n.changeLanguage(locale);
    await mountActivity([{ ...APPLIED_ACTIVITY, rule_id: null, rule_version: null, successor_ticker: null, decision: decisions.llm }]);
    const overview = document.querySelector(".lifecycle-decision-overview")!;
    expect(overview?.textContent).toContain("The common stock no longer trades.");
    expect(overview?.textContent).toContain("Anthropic");
    expect(overview?.textContent).toContain("claude-sonnet-5");
    expect(overview?.textContent).toContain(locale === "en" ? "Claude subscription" : "Claude 訂閱");
    expect(overview?.textContent).toContain("Issuer");
    expect(overview?.textContent).toContain(locale === "en" ? "Approved by user" : "由使用者核准");
    expect(overview?.textContent).not.toContain(locale === "en" ? "No LLM used" : "未使用 LLM");
    expect(document.querySelector("details")?.textContent).toContain(locale === "en" ? "Collected news" : "已收集新聞");
  });

  it("does not label an execution date as the unknown event date", async () => {
    await mountActivity([{ ...APPLIED_ACTIVITY, decision: { ...decisions.llm, event_date: null,
      limitations: ["The exact event date was not established."], source_gaps: [{ url: "https://other.example/notice", reason: "source_http_error" }] } }]);
    expect(document.body.textContent).toContain("Event date not recorded");
    expect(document.body.textContent).toContain("Scheduled action date: 2026-08-25");
    expect(document.body.textContent).not.toContain("Effective date: 2026-08-25");
    expect(document.body.textContent).toContain("The exact event date was not established.");
    expect(document.querySelector('a[href="https://other.example/notice"]')).not.toBeNull();
  });

  it("keeps old history usable while explicitly showing absent provenance", async () => {
    await mountActivity([APPLIED_ACTIVITY]);
    expect(document.body.textContent).toContain("Decision details were not recorded");
    expect(document.body.textContent).not.toContain("No LLM used");
    expect(document.body.textContent).toContain("Reverse tracking change");
  });

  it("does not misreport an unrecorded LLM identity as no LLM use", async () => {
    await mountActivity([{ ...APPLIED_ACTIVITY, decision: { ...decisions.llm, model: null, gaps: ["model_missing"] } }]);
    const overview = document.querySelector(".lifecycle-decision-overview")!;
    expect(overview.textContent).toContain("LLM investigation");
    expect(overview.textContent).not.toContain("No LLM used");
    expect(overview.textContent).not.toContain("claude-sonnet-5");
    expect(overview.textContent).toContain("model");
  });

  it("separates automatic approval from the evidence providers", async () => {
    await mountActivity([{ ...APPLIED_ACTIVITY, decision: { ...decisions.provider, method: "rule_engine", approval_authority: "automation_policy" } }]);
    const overview = document.querySelector(".lifecycle-decision-overview")!;
    expect(overview.textContent).toContain("Massive / EODHD / Nasdaq");
    expect(overview.textContent).toContain("Approved by automation policy");
    expect(overview.textContent).not.toContain("Approved by user");
  });

  it("renders unacknowledged automatic activity before history without implicit acknowledgement", async () => {
    const onAcknowledge = vi.fn();
    await mountActivity([
      {
        ...APPLIED_ACTIVITY,
        activity_id: "activity-acknowledged",
        acknowledged_at: "2026-08-25T13:00:00Z",
      },
      APPLIED_ACTIVITY,
    ], onAcknowledge);

    const articles = Array.from(document.body.querySelectorAll("article"));
    expect(articles[0]?.textContent).toContain("OLD -> NEW");
    expect(articles[0]?.textContent).toContain("Automatic tracking change");
    expect(articles[0]?.textContent).toContain("2 watchlist memberships archived");
    expect(articles[0]?.textContent).toContain("Current Alpha Picks retained");
    expect(articles[0]?.textContent).toContain("simple-symbol-continuation · v1");
    expect(onAcknowledge).not.toHaveBeenCalled();

    await click("Acknowledge");
    expect(onAcknowledge).toHaveBeenCalledWith("activity-applied");
  });

  it("keeps acknowledged activity in history and reverse available", async () => {
    const onReverse = vi.fn();
    await mountActivity([{
      ...APPLIED_ACTIVITY,
      activity_id: "activity-seen",
      acknowledged_at: "2026-08-25T13:00:00Z",
    }], vi.fn(), onReverse);

    expect(document.body.textContent).toContain("Recent tracking-change history");
    expect(document.body.textContent).toContain("Acknowledged");
    await click("Reverse tracking change");
    expect(onReverse).toHaveBeenCalledWith("transition-1");
  });

  it("shows the exact reverse blocker instead of an unsafe command", async () => {
    await mountActivity([{
      ...APPLIED_ACTIVITY,
      reverse_readiness: {
        reversible: false,
        block_reasons: ["successor_has_later_transition"],
      },
    }]);

    expect(document.body.textContent).toContain(
      "A later ticker transition exists; this transition cannot be reversed",
    );
    expect(document.body.textContent).not.toContain("Reverse tracking change");
  });
});
