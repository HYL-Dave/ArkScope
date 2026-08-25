/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { withTestUiLocale } from "../test/testUiLocale";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const ACTIVITY_MODULE = "./LifecycleActivityBand";

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

beforeEach(() => vi.clearAllMocks());

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

describe("Lifecycle transition activity", () => {
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
    expect(articles[0]?.textContent).toContain("Seeking Alpha picks retained");
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
