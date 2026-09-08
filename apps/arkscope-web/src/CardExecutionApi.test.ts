/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from "vitest";
import { ApiError, generateCard, getCard, getCards, translateCard, type RuntimeConfig } from "./api";

const receipt = { provider: "openai", model: "gpt-5.6-sol", effort: "low", auth_mode: "api_key" };
function respond(body: unknown) {
  const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const endpoints = [
  { name: "generate", load: () => generateCard("AAPL"), envelope: (value: object) => value, row: (value: any) => value },
  { name: "detail", load: () => getCard(1), envelope: (value: object) => value, row: (value: any) => value },
  { name: "list", load: () => getCards(), envelope: (value: object) => ({ cards: [value] }), row: (value: any) => value.cards[0] },
  { name: "translate", load: () => translateCard(1), envelope: (value: object) => value, row: (value: any) => value },
];

it.each(endpoints)("preserves the closed receipt on $name", async ({ load, envelope, row }) => {
  respond(envelope({ execution_receipt: receipt }));
  expect(row(await load()).execution_receipt).toEqual(receipt);
});

it.each(endpoints)("preserves custom model IDs verbatim without inventing a length limit on $name", async ({ load, envelope, row }) => {
  const custom = { ...receipt, model: "custom-model-" + "x".repeat(200) };
  respond(envelope({ execution_receipt: custom }));
  expect(row(await load()).execution_receipt).toEqual(custom);
});

it.each(endpoints)("uses only historical top-level provider/model for an older missing receipt on $name", async ({ load, envelope, row }) => {
  respond(envelope({ provider: "openai", model: "gpt-5.4-mini", effort: "untrusted-legacy-effort" }));
  expect(row(await load()).execution_receipt).toEqual({ provider: "openai", model: "gpt-5.4-mini", effort: null, auth_mode: null });
});

it.each(endpoints)("rejects malformed present receipts as safe API errors on $name", async ({ load, envelope }) => {
  for (const execution_receipt of [null, [], "invalid", {}, { ...receipt, effort: 1 }, { ...receipt, model: {} },
    { ...receipt, auth_mode: "api_key_pool" }, { ...receipt, auth_mode: ["api_key"] }, { ...receipt, credential_id: "private-fixture" }, { ...receipt, model: "" }]) {
    respond(envelope({ execution_receipt }));
    const error = await load().catch(error => error);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "card_payload_invalid", diagnostic: null });
    expect(error.message).not.toContain("private-fixture");
  }
});

it("accepts nullable legacy fields and explicit partial-card no-op separately", async () => {
  respond({ execution_receipt: { ...receipt, effort: null, auth_mode: null } });
  expect((await getCard(1)).execution_receipt).toEqual({ ...receipt, effort: null, auth_mode: null });
  const noop = { run_id: 1, lang: "zh-Hant", card: { ticker: "AAPL" }, cached: false, no_op: true, execution_receipt: null };
  respond(noop);
  expect(await translateCard(1)).toEqual(noop);
  respond({ ...noop, execution_receipt: receipt });
  await expect(translateCard(1)).rejects.toMatchObject({ code: "card_payload_invalid" });
});

it("omits normal refresh and sends explicit refresh without losing the runtime timeout", async () => {
  const fetch = respond({ execution_receipt: receipt });
  const timer = vi.spyOn(window, "setTimeout");
  const runtime = { fixed_task_runtime: { card_translation: { model_timeout_s: 600 } } } as RuntimeConfig;
  await translateCard(1, "zh-Hant", runtime);
  await translateCard(1, "zh-Hant", runtime, { refresh: true });
  expect(fetch.mock.calls.map(call => JSON.parse(String((call as unknown as [string, RequestInit])[1].body))))
    .toEqual([{ lang: "zh-Hant" }, { lang: "zh-Hant", refresh: true }]);
  expect(timer.mock.calls.map(call => call[1])).toEqual([660_000, 660_000]);
});
