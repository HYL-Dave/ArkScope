import { expect, it } from "vitest";
import { parseWebRun } from "./webContract";
import { webRunFixture, webUsageFixture } from "./webFixtures";

function run(report = structuredClone(webUsageFixture)) {
  return { ...webRunFixture, usage_report: report, usage: report.totals };
}

it("roundtrips phase counters without losing provenance or cache counts", () => {
  const parsed = parseWebRun(run());
  expect((parsed as any)?.usage_report).toEqual(webUsageFixture);
  expect(parseWebRun(parsed)).toEqual(parsed);
});

it("keeps old usage scope unknown rather than inventing a zero or complete report", () => {
  const legacy = { ...webRunFixture } as any; delete legacy.usage_report;
  expect((parseWebRun(legacy) as any)?.usage_report).toBeNull();
  expect((parseWebRun(webRunFixture) as any)?.usage_report).toBeNull();
  expect(parseWebRun(legacy)?.usage).toEqual(webRunFixture.usage);
});

it("keeps completed search accounting separate from failed investigation status", () => {
  const report = { ...webUsageFixture, recorded_submissions: 1, phases: webUsageFixture.phases.slice(0, 1),
    totals: { input_tokens: 29706, output_tokens: 3228 }, known_subtotal: { input_tokens: 29706, output_tokens: 3228 } };
  const result = parseWebRun({ ...run(report), status: "failed", failure_code: "source_read_incomplete", finding: null, model_submissions: 1 });
  expect(result?.status).toBe("failed");
  expect((result as any)?.usage_report.coverage).toBe("complete");
});

it("retains a known subtotal while a submitted analysis has no returned counters", () => {
  const report = { ...webUsageFixture, coverage: "partial", recorded_submissions: 1, phases: webUsageFixture.phases.slice(0, 1),
    totals: { input_tokens: null, output_tokens: null }, known_subtotal: { input_tokens: 29706, output_tokens: 3228 } };
  const result = parseWebRun({ ...webRunFixture, usage_report: report, usage: report.totals,
    status: "remote_outcome_unknown", failure_code: "web_execution_interrupted", finding: null });
  expect((result as any)?.usage_report).toEqual(report);
  expect(result?.usage).toEqual({ input_tokens: null, output_tokens: null });
});

it.each([
  ["string counter", (r: any) => { r.phases[0].input_tokens = "29706"; }],
  ["negative counter", (r: any) => { r.phases[0].output_tokens = -1; }],
  ["unsafe integer", (r: any) => { r.phases[0].input_tokens = 2 ** 53; }],
  ["duplicate phase", (r: any) => { r.phases[1] = r.phases[0]; }],
  ["missing counter", (r: any) => { delete r.phases[0].input_tokens; }],
  ["internal id", (r: any) => { r.phases[0].remote_id = "private"; }],
  ["invented cost", (r: any) => { r.total_cost_usd = 0.1; }],
  ["wrong subtotal", (r: any) => { r.known_subtotal.input_tokens = 4; }],
  ["wrong total", (r: any) => { r.totals.input_tokens = 4; }],
  ["fake coverage", (r: any) => { r.coverage = "partial"; }],
  ["fake submissions", (r: any) => { r.recorded_submissions = 1; }],
  ["unknown basis", (r: any) => { r.phases[0].basis = "invoice"; }],
  ["phase array absent", (r: any) => { delete r.phases; }],
  ["phase array malformed", (r: any) => { r.phases = {}; }],
])("rejects %s instead of hiding present malformed usage", (_, mutate) => {
  const report = structuredClone(webUsageFixture); (mutate as (r: any) => void)(report);
  expect(() => parseWebRun(run(report))).toThrow("lifecycle_web_payload_invalid");
});

it("rejects disagreement with the parent usage pair", () => {
  expect(() => parseWebRun({ ...run(), usage: { input_tokens: 4, output_tokens: 1036 } })).toThrow("lifecycle_web_payload_invalid");
});

it("keeps actual zero counters distinguishable from unreported counters", () => {
  const report = structuredClone(webUsageFixture);
  for (const phase of report.phases) Object.assign(phase, { input_tokens: 0, output_tokens: 0, cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0, web_search_requests: 0 });
  report.totals = report.known_subtotal = { input_tokens: 0, output_tokens: 0 };
  expect((parseWebRun(run(report)) as any)?.usage_report.coverage).toBe("complete");
  expect((parseWebRun(run(report)) as any)?.usage_report.totals.input_tokens).toBe(0);
});
