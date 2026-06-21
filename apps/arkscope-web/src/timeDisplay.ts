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

export function formatSystemTimestamp(
  iso: string | null | undefined,
  opts: { localTimeZone?: string; marketTimeZone?: string } = {},
): string {
  if (!iso) return "—";
  const date = new Date(normalizeIsoOffset(iso));
  if (Number.isNaN(date.getTime())) return iso;

  const localTimeZone = opts.localTimeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "local";
  const marketTimeZone = opts.marketTimeZone ?? MARKET_TIME_ZONE;
  return `${dateParts(date, localTimeZone)} ${localTimeZone} · ${dateParts(date, marketTimeZone)} ET`;
}
