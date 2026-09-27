import { ChevronDown } from "lucide-react";
import { formatSystemTimestamp, systemTimestampParts } from "../timeDisplay";

export function RecordedTimestamp({ value }: { value: string | null | undefined }) {
  const parts = systemTimestampParts(value);
  if (!parts) return <span>{formatSystemTimestamp(value)}</span>;
  return <details className="settings-timestamp">
    <summary>
      <span>
        <time dateTime={parts.iso} title={parts.iso}>{parts.local}</time>
        <span className="muted tiny settings-timestamp-zone">{parts.localTimeZone}</span>
      </span>
      <ChevronDown size={12} aria-hidden="true" />
    </summary>
    <span className="muted tiny settings-timestamp-market">{parts.market}</span>
  </details>;
}
