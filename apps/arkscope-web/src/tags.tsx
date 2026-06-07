// Shared tag-chip rendering + source helpers (slice 2b).
//
// Tags are classification metadata decoupled from list membership. The source
// determines the chip's colour and facet. config:* tags are owned by
// import-universe (read-only in the UI); only source="user" tags are editable.

import { type TagRef } from "./api";

// Stable facet ordering — config families first, then user.
export const TAG_FACETS: { source: string; label: string }[] = [
  { source: "config:tier", label: "Tier" },
  { source: "config:category", label: "Category" },
  { source: "config:theme", label: "Theme" },
  { source: "user", label: "User" },
];

export function sourceClass(source: string): string {
  switch (source) {
    case "config:tier":
      return "tagchip tagchip--tier";
    case "config:category":
      return "tagchip tagchip--cat";
    case "config:theme":
      return "tagchip tagchip--theme";
    case "user":
      return "tagchip tagchip--user";
    default:
      return "tagchip"; // provider:* etc. (slice 3) fall back to the base style
  }
}

export function sourceLabel(source: string): string {
  const f = TAG_FACETS.find((x) => x.source === source);
  if (f) return f.label;
  if (source.startsWith("provider:")) return "Industry";
  return source;
}

export function isUserTag(t: TagRef): boolean {
  return t.source === "user";
}

// Read-only chip row for table cells. Caps the count with a "+N" overflow.
export function TagChips({ tags, max = 5 }: { tags?: TagRef[]; max?: number }) {
  if (!tags || tags.length === 0) return null;
  const shown = tags.slice(0, max);
  const extra = tags.length - shown.length;
  return (
    <span className="chips tagchips">
      {shown.map((t) => (
        <span
          key={`${t.source}:${t.tag}`}
          className={sourceClass(t.source)}
          title={`${sourceLabel(t.source)} · ${t.tag}`}
        >
          {t.tag}
        </span>
      ))}
      {extra > 0 && <span className="muted tiny" title={tags.slice(max).map((t) => t.tag).join(", ")}>+{extra}</span>}
    </span>
  );
}
