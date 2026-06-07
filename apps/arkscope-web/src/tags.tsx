// Shared tag-chip rendering + facet helpers (two-dimensional tag model).
//
// A tag has a facet (semantic axis) and a source (authority/origin). Filtering is
// by facet (Category / Theme / Provenance); colour is by facet, with user tags
// given a distinct accent. Only editable tags (user/legacy) get a remove
// affordance — provenance/provider/system are read-only external facts.

import { isEditableTag, type TagRef } from "./api";

// Facet axes used for the filter dropdowns, in display order. Industry/sector
// (provider-sourced) join later (slice 3); unknown facets fall through.
export const TAG_FACETS: { facet: string; label: string }[] = [
  { facet: "category", label: "Category" },
  { facet: "theme", label: "Theme" },
  { facet: "provenance", label: "Provenance" },
  { facet: "industry", label: "Industry" },
  { facet: "sector", label: "Sector" },
];

export function facetLabel(facet: string): string {
  return TAG_FACETS.find((f) => f.facet === facet)?.label ?? facet;
}

// Chip class: user tags pop (editable, "mine"); others are coloured by facet.
export function tagClass(t: TagRef): string {
  if (t.source === "user") return "tagchip tagchip--user";
  switch (t.facet) {
    case "category":
      return "tagchip tagchip--cat";
    case "theme":
      return "tagchip tagchip--theme";
    case "provenance":
      return "tagchip tagchip--prov";
    case "industry":
    case "sector":
      return "tagchip tagchip--ind";
    default:
      return "tagchip";
  }
}

export function tagTitle(t: TagRef): string {
  const ro = isEditableTag(t) ? "" : " · 唯讀";
  return `${facetLabel(t.facet)} · ${t.value} (${t.source})${ro}`;
}

export function tagKey(t: TagRef): string {
  return `${t.facet}:${t.value}:${t.source}`;
}

// Read-only chip row for table cells. Caps the count with a "+N" overflow.
export function TagChips({ tags, max = 5 }: { tags?: TagRef[]; max?: number }) {
  if (!tags || tags.length === 0) return null;
  const shown = tags.slice(0, max);
  const extra = tags.length - shown.length;
  return (
    <span className="chips tagchips">
      {shown.map((t) => (
        <span key={tagKey(t)} className={tagClass(t)} title={tagTitle(t)}>
          {t.value}
        </span>
      ))}
      {extra > 0 && (
        <span className="muted tiny" title={tags.slice(max).map((t) => t.value).join(", ")}>
          +{extra}
        </span>
      )}
    </span>
  );
}
