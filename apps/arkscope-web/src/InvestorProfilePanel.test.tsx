/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InvestorProfilePanel } from "./InvestorProfilePanel";
import type { InvestorProfileResponse } from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.unstubAllGlobals();
});

const disabledResponse = (): InvestorProfileResponse => ({
  profile: {
    enabled: false,
    primary_preset: "growth",
    risk_appetite: null,
    risk_capacity: null,
    risk_mismatch: "unclear",
    holding_horizon: "mixed",
    drawdown_tolerance_pct: null,
    concentration_limit_pct: null,
    preferred_edge: [],
    avoidances: [],
    behavioral_flags: [],
    freeform_notes: "",
    default_stance: "complementary",
    skill_mode: "off",
    last_reviewed_at: null,
    updated_at: null,
  },
  effective_stance: "off",
  trace: {
    profile_active: false,
    assistant_stance: "off",
    skill_mode: "off",
    suggested_skills: [],
    applied_skills: [],
  },
  context_preview: "",
});

function stubFetch(handler: (url: string, init?: RequestInit) => InvestorProfileResponse) {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: unknown, init?: RequestInit) => {
      const u = String(url);
      calls.push({
        url: u,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      return new Response(JSON.stringify(handler(u, init)), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}

async function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<InvestorProfilePanel />);
  });
}

describe("InvestorProfilePanel", () => {
  it("loads_default_disabled_profile", async () => {
    const calls = stubFetch(() => disabledResponse());
    await mount();
    expect(calls[0].url).toContain("/profile/investor");
    expect(calls[0].method).toBe("GET");
    const checkbox = host!.querySelector<HTMLInputElement>("input[type=checkbox]");
    expect(checkbox?.checked).toBe(false);
    expect(host!.textContent).toContain("投資人設定");
  });

  it("disabled_profile_shows_effective_off", async () => {
    stubFetch(() => disabledResponse());
    await mount();
    expect(host!.textContent).toContain("關閉"); // effective stance off label
  });

  it("draft_button_posts_profile_without_saving", async () => {
    const calls = stubFetch((url) => {
      const resp = disabledResponse();
      if (url.endsWith("/draft")) {
        resp.profile.enabled = true;
        resp.profile.risk_appetite = 8;
        resp.profile.risk_capacity = 4;
        resp.profile.risk_mismatch = "appetite_above_capacity";
      }
      return resp;
    });
    await mount();
    const draftBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("產生設定草稿"),
    )!;
    await act(async () => {
      draftBtn.click();
    });
    const draftCall = calls.find((c) => c.url.endsWith("/profile/investor/draft"));
    expect(draftCall?.method).toBe("POST");
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
    expect(host!.textContent).toContain("風險胃納高於承受能力");
  });

  it("save_button_puts_profile", async () => {
    const calls = stubFetch((url, init) => {
      const resp = disabledResponse();
      if (init?.method === "PUT") {
        resp.profile.enabled = true;
        resp.effective_stance = "complementary";
        resp.trace.profile_active = true;
        resp.trace.assistant_stance = "complementary";
      }
      return resp;
    });
    await mount();
    const saveBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("儲存設定"),
    )!;
    await act(async () => {
      saveBtn.click();
    });
    const putCall = calls.find((c) => c.method === "PUT");
    expect(putCall?.url).toContain("/profile/investor");
    expect(host!.textContent).toContain("互補投資人");
  });
});
