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
  translateCard: vi.fn(),
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
const TRANSLATED_CONCLUSION = "TRANSLATED CONCLUSION / 翻譯結果";
const SOURCE_CONCLUSION_B = "SOURCE CARD B CONCLUSION / 原文";
const RAW_ERROR = "RAW postgres://admin:secret@10.0.0.8/cards";
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
const TRANSLATED_CARD = card({
  question: "TRANSLATED QUESTION",
  conclusion: TRANSLATED_CONCLUSION,
  primary_reasons: ["TRANSLATED PRIMARY REASON"],
  counter_thesis: ["TRANSLATED COUNTER"],
  confidence_rationale: "TRANSLATED RATIONALE",
});

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

const TRANSLATION_RESULT = {
  run_id: RUN_ID,
  lang: "zh-Hant" as const,
  card: TRANSLATED_CARD,
  cached: false,
};

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
  developerMode = false,
}: {
  cardValue?: ResultCard;
  developerMode?: boolean;
} = {}) {
  await mount(
    <CardView
      card={cardValue}
      runId={RUN_ID}
      evidencePacket={EVIDENCE}
      saved={false}
      onSave={vi.fn()}
      developerMode={developerMode}
      onNavigateTarget={vi.fn()}
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

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  document.documentElement.lang = "zh-Hant";
  apiMocks.getCards.mockReset().mockResolvedValue({ cards: RECENT });
  apiMocks.getInvestorProfile.mockReset().mockResolvedValue(PROFILE);
  apiMocks.generateCard.mockReset().mockResolvedValue(GENERATE_RESULT);
  apiMocks.getCard.mockReset().mockResolvedValue(CARD_DETAIL);
  apiMocks.saveCard.mockReset().mockResolvedValue({
    run_id: RUN_ID,
    status: "saved",
    saved_report_id: 9901,
  });
  apiMocks.translateCard.mockReset().mockResolvedValue(TRANSLATION_RESULT);
});

afterEach(() => {
  unmountCard();
});

describe("AI Card localization", () => {
  it("renders reviewed zh-Hant Card chrome and generated content byte for byte", async () => {
    await mountTab();
    expect(host!.querySelector(".saved-star")?.getAttribute("title")).toBe("已存為報告");

    const question = host!.querySelector<HTMLInputElement>(".aicard-q")!;
    await setValue(question, SOURCE_QUESTION);
    await click(buttonByText("產生卡片"));
    await waitForText(SOURCE_CONCLUSION);

    const text = host!.textContent ?? "";
    for (const expected of [
      "主要理由",
      "反方理由",
      "失效條件",
      "觸發條件",
      "關鍵假設",
      "風險",
      "觀察清單",
      "市場敘事",
      "與共識分歧",
      "可信度說明：",
      "資料來源 · 可追溯性",
      "高",
      SOURCE_QUESTION,
      SOURCE_CONCLUSION,
      SOURCE_REASON,
      SOURCE_COUNTER,
      SOURCE_INVALIDATION,
      SOURCE_TRIGGER,
      SOURCE_ASSUMPTION,
      SOURCE_RISK,
      SOURCE_WATCH,
      SOURCE_NARRATIVE,
      SOURCE_DIVERGENCE,
      SOURCE_RATIONALE,
    ]) {
      expect(text).toContain(expected);
    }
    const confidence = Array.from(host!.querySelectorAll<HTMLElement>(".cardview p"))
      .find((node) => node.textContent?.startsWith("可信度說明："));
    const trace = host!.querySelector<HTMLDetailsElement>(".cardview-trace")!;
    const completeness = Array.from(trace.querySelectorAll<HTMLElement>("div.muted.tiny"))
      .find((node) => node.textContent?.startsWith("完整度 — 新聞"));
    expect(confidence?.textContent).toBe(`可信度說明：${SOURCE_RATIONALE}`);
    expect(trace.querySelector("summary")?.textContent)
      .toBe("資料來源 · 可追溯性（1 源 · 1 引用）");
    expect(completeness?.textContent).toBe(
      `完整度 — 新聞 ✓ · 基本面 — · 技術面 ✓ · ${SOURCE_COMPLETENESS_NOTE}`,
    );
    expect(apiMocks.generateCard).toHaveBeenCalledWith(TICKER, {
      question: SOURCE_QUESTION,
      provider: "anthropic",
      news_days: 21,
      max_news: 12,
      assistant_stance: "strict_risk_control",
    }, undefined);
  });

  it("renders English Card chrome without translating generated content", async () => {
    await switchLocale("en");
    await mountTab();
    expect(host!.textContent).toContain("Recent Cards");
    expect(host!.textContent).toContain(SOURCE_CONCLUSION);
    expect(host!.querySelector(".saved-star")?.getAttribute("title")).toBe("saved as report");

    await click(buttonByText("Generate Card"));
    await waitForText(SOURCE_REASON);
    const text = host!.textContent ?? "";
    for (const expected of [
      "Primary reasons",
      "Counterarguments",
      "Invalidation conditions",
      "Triggers",
      "Key assumptions",
      "Risks",
      "Watch list",
      "Market narrative",
      "Divergence from consensus",
      "Confidence explanation:",
      "Data sources · Traceability",
      "High",
      SOURCE_QUESTION,
      SOURCE_CONCLUSION,
      SOURCE_REASON,
      SOURCE_RATIONALE,
    ]) {
      expect(text).toContain(expected);
    }
    expect(apiMocks.translateCard).not.toHaveBeenCalled();
  });

  it("maps recent Card and Investor Profile load failures separately", async () => {
    apiMocks.getCards.mockRejectedValueOnce(
      structuredError("recent_cards_failed", "/analysis/cards?limit=10"),
    );
    apiMocks.getInvestorProfile.mockRejectedValueOnce(
      structuredError("investor_profile_failed", "/profile/investor"),
    );
    await mountTab();

    const titles = Array.from(host!.querySelectorAll('[role="alert"] .ui-status-badge'))
      .map((node) => node.textContent);
    expect(titles).toEqual([
      "無法載入最近卡片。",
      "無法載入投資人設定。",
    ]);
    expect(host!.textContent).not.toContain(RAW_ERROR);
    expect(apiMocks.getCards).toHaveBeenCalledWith(TICKER, 10);
    expect(apiMocks.getInvestorProfile).toHaveBeenCalledTimes(1);
  });

  it("maps generation failure without changing question or advanced controls", async () => {
    apiMocks.generateCard.mockRejectedValueOnce(
      structuredError("card_generation_failed", `/analysis/card/${TICKER}`),
    );
    await mountTab();
    await click(buttonByText("進階"));

    const question = host!.querySelector<HTMLInputElement>(".aicard-q")!;
    const numbers = host!.querySelectorAll<HTMLInputElement>('input[type="number"]');
    const stance = host!.querySelector<HTMLSelectElement>(".aicard-adv select")!;
    await setValue(question, "SOURCE GENERATION QUESTION");
    await setValue(numbers[0]!, "33");
    await setValue(numbers[1]!, "23");
    await setValue(stance, "valuation_rationalist");
    await click(buttonByText("產生卡片"));
    await waitForCalls(apiMocks.generateCard, 1);

    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法產生 AI 卡片。");
    expect(question.value).toBe("SOURCE GENERATION QUESTION");
    expect(numbers[0]!.value).toBe("33");
    expect(numbers[1]!.value).toBe("23");
    expect(stance.value).toBe("valuation_rationalist");
    expect(host!.querySelector(".aicard-adv")).not.toBeNull();
    expect(host!.textContent).not.toContain(RAW_ERROR);
  });

  it("maps save failure without changing Card identity", async () => {
    async function openCardBWhileSavePending(pendingSave: ReturnType<typeof deferred>) {
      apiMocks.saveCard.mockReset().mockReturnValueOnce(pendingSave.promise);
      await mountTab();
      await click(buttonByText("產生卡片"));
      await waitForText(SOURCE_CONCLUSION);
      await waitForCalls(apiMocks.getCards, 2);
      await click(buttonByText("存成報告"));
      await waitForCalls(apiMocks.saveCard, 1);

      apiMocks.getCards.mockResolvedValue({ cards: RECENT_B });
      await click(buttonByText("卡片列表"));
      await waitForCalls(apiMocks.getCards, 3);
      await waitForText(SOURCE_CONCLUSION_B);
      apiMocks.getCard.mockResolvedValueOnce(CARD_DETAIL_B);
      await click(host!.querySelector<HTMLLIElement>(".aicard-recent li")!);
      await waitForCalls(apiMocks.getCard, 1);
      await waitForText(SOURCE_CONCLUSION_B);
      return {
        cardNode: host!.querySelector<HTMLElement>(".cardview")!,
        conclusionNode: host!.querySelector<HTMLElement>(".cardview-concl")!,
        saveButton: Array.from(
          host!.querySelectorAll<HTMLButtonElement>(".cardview-head > button"),
        ).at(-1)!,
      };
    }

    const pendingSuccess = deferred<Awaited<ReturnType<typeof apiMocks.saveCard>>>();
    const successCardB = await openCardBWhileSavePending(pendingSuccess);
    const recentCallsBeforeSuccess = apiMocks.getCards.mock.calls.length;
    await act(async () => {
      pendingSuccess.resolve({ run_id: RUN_ID, status: "saved", saved_report_id: 9901 });
      await pendingSuccess.promise;
    });
    await flush();

    expect(host!.querySelector(".cardview")).toBe(successCardB.cardNode);
    expect(host!.querySelector(".cardview-concl")).toBe(successCardB.conclusionNode);
    expect(successCardB.conclusionNode.textContent).toBe(SOURCE_CONCLUSION_B);
    expect(successCardB.saveButton.textContent).toBe("存成報告");
    expect(successCardB.saveButton.disabled).toBe(false);
    expect(apiMocks.getCards).toHaveBeenCalledTimes(recentCallsBeforeSuccess);

    unmountCard();
    apiMocks.getCards.mockReset().mockResolvedValue({ cards: RECENT });
    apiMocks.getInvestorProfile.mockReset().mockResolvedValue(PROFILE);
    apiMocks.generateCard.mockReset().mockResolvedValue(GENERATE_RESULT);
    apiMocks.getCard.mockReset().mockResolvedValue(CARD_DETAIL);

    const pendingFailure = deferred<Awaited<ReturnType<typeof apiMocks.saveCard>>>();
    const failureCardB = await openCardBWhileSavePending(pendingFailure);
    await act(async () => {
      pendingFailure.reject(structuredError("stale_card_a_save", `/analysis/cards/${RUN_ID}/save`));
      await pendingFailure.promise.catch(() => undefined);
    });
    await flush();

    expect(host!.querySelector('[role="alert"]')).toBeNull();
    expect(host!.querySelector(".cardview")).toBe(failureCardB.cardNode);
    expect(failureCardB.conclusionNode.textContent).toBe(SOURCE_CONCLUSION_B);
    expect(failureCardB.saveButton.disabled).toBe(false);

    apiMocks.saveCard.mockRejectedValueOnce(
      structuredError("card_b_save_failed", `/analysis/cards/${RUN_ID_B}/save`),
    );
    await click(failureCardB.saveButton);
    await waitForCalls(apiMocks.saveCard, 2);
    const alert = host!.querySelector<HTMLElement>('[role="alert"]')!;
    expect(alert.querySelector(".ui-status-badge")?.textContent)
      .toBe("無法將卡片存成報告。");
    expect(host!.querySelector(".cardview")).toBe(failureCardB.cardNode);
    expect(failureCardB.conclusionNode.textContent).toBe(SOURCE_CONCLUSION_B);
    expect(host!.textContent).not.toContain(RAW_ERROR);

    apiMocks.saveCard.mockResolvedValueOnce({
      run_id: RUN_ID_B,
      status: "saved",
      saved_report_id: 9902,
    });
    await click(buttonByText("重試", alert));
    await waitForCalls(apiMocks.saveCard, 3);
    expect(apiMocks.saveCard.mock.calls).toEqual([
      [RUN_ID],
      [RUN_ID_B],
      [RUN_ID_B],
    ]);
  });

  it("maps open-Card failure and preserves modal focus recovery", async () => {
    apiMocks.getCard.mockRejectedValueOnce(
      structuredError("card_open_failed", `/analysis/cards/${RUN_ID}`),
    );

    function ModalHarness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>OPEN SOURCE CARD</button>
          {open ? (
            <CardModal
              runId={RUN_ID}
              developerMode={false}
              onNavigateTarget={vi.fn()}
              onClose={() => setOpen(false)}
            />
          ) : null}
        </>
      );
    }

    await mount(<ModalHarness />);
    const opener = buttonByText("OPEN SOURCE CARD");
    opener.focus();
    await click(opener);
    await waitForCalls(apiMocks.getCard, 1);

    const dialog = host!.querySelector<HTMLElement>('[role="dialog"]')!;
    const close = buttonByText("關閉", dialog);
    expect(document.activeElement).toBe(close);
    expect(dialog.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法開啟 AI 卡片。");
    expect(dialog.textContent).not.toContain(RAW_ERROR);

    await click(close);
    expect(host!.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("keeps explicit translation user-triggered with the existing request payload", async () => {
    await mountCardView();
    expect(apiMocks.translateCard).not.toHaveBeenCalled();

    await switchLocale("en");
    expect(host!.textContent).toContain("Save as report");
    expect(apiMocks.translateCard).not.toHaveBeenCalled();

    await click(buttonByText("繁中"));
    await waitForText(TRANSLATED_CONCLUSION);
    expect(apiMocks.translateCard).toHaveBeenCalledTimes(1);
    expect(apiMocks.translateCard).toHaveBeenCalledWith(RUN_ID, "zh-Hant", undefined);
    expect(host!.querySelector(".cardview-concl")?.textContent).toBe(TRANSLATED_CONCLUSION);
  });

  it("maps explicit translation failure without raw detail", async () => {
    apiMocks.translateCard.mockRejectedValueOnce(
      structuredError("card_translation_failed", `/analysis/cards/${RUN_ID}/translate`),
    );
    await mountCardView({ developerMode: false });
    const questionNode = host!.querySelector(".cardview-q");
    await click(buttonByText("繁中"));
    await waitForCalls(apiMocks.translateCard, 1);

    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法翻譯卡片。");
    expect(host!.querySelector(".cardview-q")).toBe(questionNode);
    expect(questionNode?.textContent).toContain(SOURCE_QUESTION);
    expect(host!.textContent).not.toContain(RAW_ERROR);
    expect(host!.textContent).not.toContain("sk-private");
  });

  it("preserves a translated Card node and sends no second request on locale switch", async () => {
    const pending = deferred<typeof TRANSLATION_RESULT>();
    apiMocks.translateCard.mockReturnValueOnce(pending.promise);
    await mountCardView();
    const cardNode = host!.querySelector<HTMLElement>(".cardview")!;
    const conclusionNode = host!.querySelector<HTMLElement>(".cardview-concl")!;
    const zhButton = buttonByText("繁中");
    zhButton.focus();
    await click(zhButton);
    await waitForCalls(apiMocks.translateCard, 1);
    expect(zhButton.textContent).toBe("翻譯中…");
    expect(conclusionNode.textContent).toBe(SOURCE_CONCLUSION);

    await switchLocale("en");

    expect(host!.querySelector(".cardview")).toBe(cardNode);
    expect(host!.querySelector(".cardview-concl")).toBe(conclusionNode);
    expect(conclusionNode.textContent).toBe(SOURCE_CONCLUSION);
    expect(zhButton.textContent).toBe("Translating…");
    expect(zhButton.disabled).toBe(true);
    expect(document.activeElement).toBe(zhButton);
    expect(apiMocks.translateCard).toHaveBeenCalledTimes(1);

    await act(async () => {
      pending.resolve(TRANSLATION_RESULT);
      await pending.promise;
    });
    await waitForText(TRANSLATED_CONCLUSION);

    expect(host!.querySelector(".cardview")).toBe(cardNode);
    expect(host!.querySelector(".cardview-concl")).toBe(conclusionNode);
    expect(conclusionNode.textContent).toBe(TRANSLATED_CONCLUSION);
    expect(zhButton.textContent).toBe("繁中");
    expect(zhButton.classList.contains("on")).toBe(true);
    expect(document.activeElement).toBe(zhButton);
    expect(host!.textContent).toContain("Save as report");
    expect(apiMocks.translateCard).toHaveBeenCalledTimes(1);
  });

  it("reactively localizes shared stance and trace chrome without changing IDs", async () => {
    await mountTab();
    await click(buttonByText("進階"));
    const stance = host!.querySelector<HTMLSelectElement>(".aicard-adv select")!;
    expect(stance.value).toBe("strict_risk_control");
    expect(Array.from(stance.options).map((option) => [option.value, option.textContent])).toContainEqual([
      "strict_risk_control",
      "嚴格風控",
    ]);

    await click(buttonByText("產生卡片"));
    await waitForText("立場：嚴格風控");
    const traceNode = Array.from(host!.querySelectorAll<HTMLParagraphElement>("p"))
      .find((node) => node.textContent?.includes("立場：嚴格風控"))!;

    await switchLocale("en");

    expect(host!.querySelector(".aicard-adv select")).toBe(stance);
    expect(stance.value).toBe("strict_risk_control");
    expect(Array.from(stance.options).map((option) => [option.value, option.textContent])).toContainEqual([
      "strict_risk_control",
      "Strict risk control",
    ]);
    expect(stance.closest("label")?.childNodes[0]?.textContent).toBe("Stance");
    expect(traceNode.textContent).toBe("Stance: Strict risk control　Suggested skills: source_skill_alpha");
    expect(host!.textContent).toContain("Stance");
    expect(apiMocks.generateCard).toHaveBeenCalledTimes(1);
  });

  it("preserves evidence claims rationale and source values byte for byte", async () => {
    await switchLocale("en");
    await mountCardView();

    const text = host!.textContent ?? "";
    for (const expected of [
      "Citations for each claim (claim → evidence_id)",
      "Evidence citation summary",
      "as-of SOURCE_EVIDENCE_AS_OF",
      "· realtime",
      "[3 items]",
      SOURCE_CLAIM,
      SOURCE_EVIDENCE_ID,
      SOURCE_PROVIDER,
      SOURCE_TYPE,
      SOURCE_NOTE,
      SOURCE_FRESHNESS,
      SOURCE_RATIONALE,
      "SOURCE_DATA_KEY: SOURCE DATA VALUE / 原值",
      SOURCE_COMPLETENESS_NOTE,
    ]) {
      expect(text).toContain(expected);
    }
    expect(text).not.toContain("TRANSLATED SOURCE CLAIM");
    expect(apiMocks.translateCard).not.toHaveBeenCalled();
  });

  it("preserves question advanced controls modal and in-flight work across locale switch", async () => {
    const pending = deferred<GenerateResult>();
    apiMocks.generateCard.mockReturnValueOnce(pending.promise);

    await mount(
      <>
        <AICardTab ticker={TICKER} developerMode={true} onNavigateTarget={vi.fn()} />
        <CardModal
          runId={RUN_ID}
          developerMode={true}
          onNavigateTarget={vi.fn()}
          onClose={vi.fn()}
        />
      </>,
    );
    await waitForText(SOURCE_CONCLUSION);
    const tab = host!.querySelector<HTMLElement>(".aicard")!;
    const dialog = host!.querySelector<HTMLElement>('[role="dialog"]')!;
    const modalCard = dialog.querySelector<HTMLElement>(".cardview")!;
    await click(buttonByText("進階", tab));

    const question = tab.querySelector<HTMLInputElement>(".aicard-q")!;
    const numbers = tab.querySelectorAll<HTMLInputElement>('input[type="number"]');
    const stance = tab.querySelector<HTMLSelectElement>("select")!;
    await setValue(question, "SOURCE IN-FLIGHT QUESTION");
    await setValue(numbers[0]!, "44");
    await setValue(numbers[1]!, "24");
    await setValue(stance, "growth_opportunity");
    const generateButton = buttonByText("產生卡片", tab);
    await click(generateButton);
    await waitForCalls(apiMocks.generateCard, 1);
    const before = requestCounts();

    await switchLocale("en");

    expect(host!.querySelector(".aicard")).toBe(tab);
    expect(host!.querySelector('[role="dialog"]')).toBe(dialog);
    expect(dialog.querySelector(".cardview")).toBe(modalCard);
    expect(tab.querySelector(".aicard-q")).toBe(question);
    expect(question.value).toBe("SOURCE IN-FLIGHT QUESTION");
    expect(numbers[0]!.value).toBe("44");
    expect(numbers[1]!.value).toBe("24");
    expect(stance.value).toBe("growth_opportunity");
    expect(tab.querySelector(".aicard-adv")).not.toBeNull();
    expect(generateButton.textContent).toBe("Generating…");
    expect(generateButton.disabled).toBe(true);
    expect(requestCounts()).toEqual(before);

    await act(async () => {
      pending.resolve({
        ...GENERATE_RESULT,
        card: card({ conclusion: "SOURCE IN-FLIGHT COMPLETION" }),
      });
      await pending.promise;
    });
    await waitForText("SOURCE IN-FLIGHT COMPLETION");
    expect(host!.querySelector('[role="dialog"]')).toBe(dialog);
    expect(apiMocks.generateCard).toHaveBeenCalledWith(TICKER, {
      question: "SOURCE IN-FLIGHT QUESTION",
      provider: "anthropic",
      news_days: 44,
      max_news: 24,
      assistant_stance: "growth_opportunity",
    }, undefined);
  });
});
