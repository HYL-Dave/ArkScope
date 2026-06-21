/** @vitest-environment jsdom */
import React, { useState } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { SetupDisclosure } from "./Settings";

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

describe("SetupDisclosure", () => {
  it("can be closed after being opened without reading a cleared React event", async () => {
    function Harness() {
      const [openByProvider, setOpenByProvider] = useState<Record<string, boolean>>({ openai: true });
      return React.createElement(
        SetupDisclosure,
        {
          provider: "openai",
          open: openByProvider.openai,
          onOpenChange: (provider: string, open: boolean) =>
            setOpenByProvider((prev) => ({ ...prev, [provider]: open })),
        },
        React.createElement("div", null, "setup body"),
      );
    }

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);

    await act(async () => {
      root!.render(React.createElement(Harness));
    });

    const details = host.querySelector("details")!;
    const summary = host.querySelector("summary")!;
    expect(details.open).toBe(true);

    await act(async () => {
      summary.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(details.open).toBe(false);
  });
});
