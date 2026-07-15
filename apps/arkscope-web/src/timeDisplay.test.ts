import { describe, expect, it } from "vitest";

import { formatMarketTimestamp, formatSystemTimestamp } from "./timeDisplay";

describe("formatSystemTimestamp", () => {
  it("shows local time plus US market time for UTC ISO timestamps", () => {
    expect(formatSystemTimestamp("2026-06-21T12:31:00+00:00", { localTimeZone: "Asia/Taipei" })).toBe(
      "06-21 20:31 Asia/Taipei · 06-21 08:31 ET",
    );
  });

  it("normalizes compact UTC offsets from local market DB mirrors", () => {
    expect(formatSystemTimestamp("2026-01-15T03:05:00+0000", { localTimeZone: "Asia/Taipei" })).toBe(
      "01-15 11:05 Asia/Taipei · 01-14 22:05 ET",
    );
  });

  it("preserves empty and malformed values defensively", () => {
    expect(formatSystemTimestamp(null, { localTimeZone: "Asia/Taipei" })).toBe("—");
    expect(formatSystemTimestamp(undefined, { localTimeZone: "Asia/Taipei" })).toBe("—");
    expect(formatSystemTimestamp("not-a-date", { localTimeZone: "Asia/Taipei" })).toBe("not-a-date");
  });

  it("formats market activity in ET before local time", () => {
    expect(formatMarketTimestamp(
      "2026-07-15T14:31:00+00:00",
      { localTimeZone: "Asia/Taipei" },
    )).toBe("07-15 10:31 ET · 07-15 22:31 Asia/Taipei");
  });
});
