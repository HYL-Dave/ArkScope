/** @vitest-environment jsdom */
import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CardDetail,
  CardSummary,
  EvidencePacket,
  GenerateResult,
  InvestorProfileResponse,
  PersonalizationTrace,
  ResultCard,
} from "./api";
import type { NavigationTarget } from "./shell/navigation";

const apiMocks = vi.hoisted(() => ({
  generateCard: vi.fn(),
  getCard: vi.fn(),
  getCards: vi.fn(),
  getInvestorProfile: vi.fn(),
  saveCard: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ...apiMocks };
});

import { AICardTab, CardModal, CardView } from "./AICard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const TICKER = "CARD.SRC";
const RUN_ID = 8801;
const RUN_ID_B = 8802;
const SOURCE_QUESTION = "SOURCE QUESTION / 原文 <keep>";
const SOURCE_CONCLUSION = "SOURCE CONCLUSION / 結論 <keep>";
const SOURCE_REASON = "SOURCE PRIMARY REASON / 原文";
const SOURCE_COUNTER = "SOURCE COUNTER / 原文";
const SOURCE_INVALIDATION = "SOURCE INVALIDATION / 原文";
const SOURCE_TRIGGER = "SOURCE TRIGGER / 原文";
const SOURCE_ASSUMPTION = "SOURCE ASSUMPTION / 原文";
const SOURCE_RISK = "SOURCE RISK / 原文";
const SOURCE_WATCH = "SOURCE WATCH ITEM / 原文";
const SOURCE_NARRATIVE = "SOURCE MARKET NARRATIVE / 原文";
const SOURCE_DIVERGENCE = "SOURCE DIVERGENCE / 原文";
const SOURCE_RATIONALE = "SOURCE CONFIDENCE RATIONALE / 原文";
const SOURCE_CLAIM = "SOURCE CLAIM / 原文 <keep>";
const SOURCE_EVIDENCE_ID = "source-evidence-id/v9";
const SOURCE_PROVIDER = "provider/source-id";
const SOURCE_TYPE = "source_type/runtime-id";
const SOURCE_NOTE = "SOURCE EVIDENCE NOTE / 原文";
const SOURCE_FRESHNESS = "SOURCE freshness/raw";
const SOURCE_COMPLETENESS_NOTE = "SOURCE COMPLETENESS NOTE / 原文";
const SOURCE_CONCLUSION_B = "SOURCE CARD B CONCLUSION / 原文";
const RAW_ERROR = "RAW backend failure token=secret cards";
const RAW_DIAGNOSTIC = "Authorization: Bearer sk-private\nTraceback /srv/private.py:42";

const TRACE: PersonalizationTrace = {
  profile_active: true,
  assistant_stance: "strict_risk_control",
  skill_mode: "suggest_only",
  suggested_skills: ["source_skill_alpha"],
  applied_skills: [],
  context_snapshot: "SOURCE CONTEXT SNAPSHOT",
};

const PROFILE: InvestorProfileResponse = {
  profile: {
    enabled: true,
    primary_preset: "custom",
    risk_appetite: 3,
    risk_capacity: 2,
    risk_mismatch: "appetite_above_capacity",
    holding_horizon: "source-horizon-id",
    drawdown_tolerance_pct: 12,
    concentration_limit_pct: 20,
    preferred_edge: ["source-edge"],
    avoidances: ["source-avoidance"],
    behavioral_flags: ["source-flag"],
    freeform_notes: "SOURCE PROFILE NOTES",
    default_stance: "strict_risk_control",
    skill_mode: "suggest_only",
    last_reviewed_at: "SOURCE_REVIEWED_AT",
    updated_at: "SOURCE_UPDATED_AT",
  },
  effective_stance: "strict_risk_control",
  trace: TRACE,
  context_preview: "SOURCE CONTEXT PREVIEW",
};

function card(overrides: Partial<ResultCard> = {}): ResultCard {
  return {
    ticker: TICKER,
    question: SOURCE_QUESTION,
    horizon: "source-horizon-id",
    card_type: "source-card-type",
    analysis_time: "SOURCE_ANALYSIS_TIME",
    conclusion: SOURCE_CONCLUSION,
    primary_reasons: [SOURCE_REASON],
    counter_thesis: [SOURCE_COUNTER],
    key_assumptions: [SOURCE_ASSUMPTION],
    trigger_conditions: [SOURCE_TRIGGER],
    invalidation_conditions: [SOURCE_INVALIDATION],
    risks: [SOURCE_RISK],
    watch_list: [SOURCE_WATCH],
    market_narrative: SOURCE_NARRATIVE,
    divergence: SOURCE_DIVERGENCE,
    confidence_level: "high",
    confidence_rationale: SOURCE_RATIONALE,
    traceability: {
      data_sources: [
        {
          name: SOURCE_PROVIDER,
          as_of: "SOURCE_PROVIDER_AS_OF",
          is_real_time: false,
          detail: "SOURCE PROVIDER DETAIL",
        },
      ],
      is_single_model_inference: true,
      completeness: {
        news: true,
        fundamentals: false,
        technicals: true,
        note: SOURCE_COMPLETENESS_NOTE,
      },
      claims: [{ claim: SOURCE_CLAIM, evidence_ids: [SOURCE_EVIDENCE_ID] }],
    },
    ...overrides,
  };
}

const SOURCE_CARD = card();

const EVIDENCE: EvidencePacket = {
  ticker: TICKER,
  generated_at: "SOURCE_EVIDENCE_GENERATED_AT",
  question: SOURCE_QUESTION,
  horizon: "source-horizon-id",
  excluded_note: "SOURCE EXCLUDED NOTE",
  items: [
    {
      evidence_id: SOURCE_EVIDENCE_ID,
      source: SOURCE_PROVIDER,
      source_type: SOURCE_TYPE,
      as_of: "SOURCE_EVIDENCE_AS_OF",
      is_real_time: true,
      freshness: SOURCE_FRESHNESS,
      derived_from: ["SOURCE_DERIVED_ID"],
      data: {
        SOURCE_DATA_KEY: "SOURCE DATA VALUE / 原值",
        SOURCE_ARRAY: ["A", "B", "C"],
        SOURCE_SINGLE_ARRAY: ["ONLY"],
      },
      note: SOURCE_NOTE,
    },
  ],
};

const GENERATE_RESULT: GenerateResult = {
  run_id: RUN_ID,
  status: "source-completed-state",
  provider: SOURCE_PROVIDER,
  model: "source-model-id",
  effort: "source-effort-id",
  generated_at: "SOURCE_GENERATED_AT",
  card: SOURCE_CARD,
  evidence_packet: EVIDENCE,
  personalization: TRACE,
};

const CARD_DETAIL: CardDetail = {
  ...GENERATE_RESULT,
  ticker: TICKER,
  question: SOURCE_QUESTION,
  horizon: "source-horizon-id",
  card_type: "source-card-type",
  as_of: "SOURCE_CARD_AS_OF",
  saved_report_id: null,
};

const SOURCE_CARD_B = card({ conclusion: SOURCE_CONCLUSION_B });
const CARD_DETAIL_B: CardDetail = {
  ...CARD_DETAIL,
  run_id: RUN_ID_B,
  card: SOURCE_CARD_B,
};

const RECENT: CardSummary[] = [
  {
    run_id: RUN_ID,
    ticker: TICKER,
    question: SOURCE_QUESTION,
    horizon: "source-horizon-id",
    card_type: "source-card-type",
    status: "saved",
    provider: SOURCE_PROVIDER,
    model: "source-model-id",
    generated_at: "SOURCE_GENERATED_AT",
    saved_report_id: 9901,
    conclusion: SOURCE_CONCLUSION,
    confidence_level: "high",
    personalization: TRACE,
  },
];

const RECENT_B: CardSummary[] = [{
  ...RECENT[0]!,
  run_id: RUN_ID_B,
  status: "source-completed-state",
  saved_report_id: null,
  conclusion: SOURCE_CONCLUSION_B,
}];


type RequestName = keyof typeof apiMocks;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function structuredError(
  code = "card_fixture_failed",
  path = "/analysis/cards?token=private#fragment",
  diagnostic = RAW_DIAGNOSTIC,
) {
  return Object.assign(new Error(RAW_ERROR), {
    status: 503,
    code,
    path,
    diagnostic,
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flush(delay = 0) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, delay));
  });
}

async function waitForCalls(mock: ReturnType<typeof vi.fn>, count: number) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (mock.mock.calls.length >= count) {
      await flush();
      return;
    }
    await flush();
  }
  throw new Error(`expected ${count} calls, received ${mock.mock.calls.length}`);
}

async function waitForText(text: string) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (host?.textContent?.includes(text)) return;
    await flush();
  }
  throw new Error(`text not found: ${text}; rendered=${host?.textContent ?? ""}`);
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
  await flush();
}

async function setValue(
  control: HTMLInputElement | HTMLSelectElement,
  value: string,
) {
  const prototype = control instanceof HTMLSelectElement
    ? HTMLSelectElement.prototype
    : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(control, value);
    control.dispatchEvent(new Event(control instanceof HTMLSelectElement ? "change" : "input", {
      bubbles: true,
    }));
  });
  await flush();
}

function buttonByText(text: string, scope: ParentNode = host!): HTMLButtonElement {
  const match = Array.from(scope.querySelectorAll<HTMLButtonElement>("button"))
    .find((button) => button.textContent?.includes(text));
  if (!match) throw new Error(`button not found: ${text}; rendered=${scope.textContent ?? ""}`);
  return match;
}

function unmountCard() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

async function mount(element: React.ReactNode) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(element);
    await Promise.resolve();
  });
  await flush();
}

async function mountTab({
  developerMode = false,
  onNavigateTarget = vi.fn(),
}: {
  developerMode?: boolean;
  onNavigateTarget?: (target: NavigationTarget) => void;
} = {}) {
  await mount(
    <AICardTab
      ticker={TICKER}
      developerMode={developerMode}
      onNavigateTarget={onNavigateTarget}
    />,
  );
  await waitForCalls(apiMocks.getCards, 1);
  await waitForCalls(apiMocks.getInvestorProfile, 1);
  return { onNavigateTarget };
}

async function mountCardView({
  cardValue = SOURCE_CARD,
}: {
  cardValue?: ResultCard;
} = {}) {
  await mount(
    <CardView
      card={cardValue}
      evidencePacket={EVIDENCE}
      saved={false}
      onSave={vi.fn()}
    />,
  );
}

async function switchLocale(locale: "zh-Hant" | "en") {
  await act(async () => {
    await i18n.changeLanguage(locale);
  });
  await flush();
}

function requestCounts(): Record<RequestName, number> {
  return Object.fromEntries(
    Object.entries(apiMocks).map(([name, mock]) => [name, mock.mock.calls.length]),
  ) as Record<RequestName, number>;
}


afterEach(() => {
  unmountCard();
});

it.each(["en", "zh-Hant"] as const)("keeps original card receipts without translation controls in %s", async (locale) => {
  await switchLocale(locale);
  const receipt = { provider: "openai", model: "gpt-6-astra", effort: "high", auth_mode: "api_key" as const };
  await mount(<CardView card={SOURCE_CARD} executionReceipt={receipt} saved={false} onSave={vi.fn()} />);
  expect(host!.querySelector(".cardview-concl")?.textContent).toBe(SOURCE_CONCLUSION);
  expect(host!.querySelector('[data-execution-source="original"]')?.textContent).toContain("gpt-6-astra");
  expect(host!.querySelector(".lang-toggle")).toBeNull();
  expect(host!.querySelector('[data-execution-source="translation"]')).toBeNull();
  const requests = requestCounts();
  await switchLocale(locale === "en" ? "zh-Hant" : "en");
  expect(host!.querySelector(".cardview-concl")?.textContent).toBe(SOURCE_CONCLUSION);
  expect(requestCounts()).toEqual(requests);
});
