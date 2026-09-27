const MARKET_TIME_ZONE = "America/New_York";

function normalizeIsoOffset(iso: string): string {
  return iso.replace(/([+-]\d{2})(\d{2})$/, "$1:$2");
}

function dateParts(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    hourCycle: "h23",
  }).formatToParts(date);
  const byType = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${byType.month}-${byType.day} ${byType.hour}:${byType.minute}`;
}

export function systemTimestampParts(
  iso: string | null | undefined,
  opts: { localTimeZone?: string; marketTimeZone?: string } = {},
): { iso: string; local: string; localTimeZone: string; market: string } | null {
  if (!iso) return null;
  const date = new Date(normalizeIsoOffset(iso));
  if (Number.isNaN(date.getTime())) return null;

  const localTimeZone = opts.localTimeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "local";
  const marketTimeZone = opts.marketTimeZone ?? MARKET_TIME_ZONE;
  return {
    iso: date.toISOString(), local: dateParts(date, localTimeZone), localTimeZone,
    market: `${dateParts(date, marketTimeZone)} ET`,
  };
}

export function formatSystemTimestamp(
  iso: string | null | undefined,
  opts: { localTimeZone?: string; marketTimeZone?: string } = {},
): string {
  const parts = systemTimestampParts(iso, opts);
  return parts ? `${parts.local} ${parts.localTimeZone} · ${parts.market}` : iso || "—";
}

export function formatMarketTimestamp(
  iso: string | null | undefined,
  opts: { localTimeZone?: string; marketTimeZone?: string } = {},
): string {
  if (!iso) return "—";
  const date = new Date(normalizeIsoOffset(iso));
  if (Number.isNaN(date.getTime())) return iso;

  const localTimeZone = opts.localTimeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "local";
  const marketTimeZone = opts.marketTimeZone ?? MARKET_TIME_ZONE;
  return `${dateParts(date, marketTimeZone)} ET · ${dateParts(date, localTimeZone)} ${localTimeZone}`;
}
