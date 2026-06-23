/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { PendingAssistantBubble } from "./Research";
import type { PendingTurn } from "./researchReducer";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
});

const pending = (over: Partial<PendingTurn> = {}): PendingTurn => ({
  threadId: "t1",
  startedAt: 0,
  provider: "openai",
  model: "gpt-5.5",
  effort: "xhigh",
  interimText: "Streaming answer text",
  trace: [],
  thinkingActive: false,
  turnCount: 1,
  tickers: [],
  ...over,
});

describe("PendingAssistantBubble", () => {
  it("renders streamed answer text as normal assistant content, not muted placeholder text", async () => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);

    await act(async () => {
      root!.render(React.createElement(PendingAssistantBubble, { pending: pending() }));
    });

    const interim = host.querySelector(".research-interim");
    expect(interim?.textContent).toBe("Streaming answer text");
    expect(interim?.classList.contains("muted")).toBe(false);
    expect(interim?.classList.contains("research-bubble-body")).toBe(true);
    expect(host.textContent).toContain("生成中");
  });
});
