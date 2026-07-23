// Shared tag-chip rendering + facet helpers (two-dimensional tag model).
//
// A tag has a facet (semantic axis) and a source (authority/origin). Filtering is
// by facet (Category / Theme / Provenance); colour is by facet, with user tags
// given a distinct accent. Only editable tags (user/legacy) get a remove
// affordance — provenance/provider/system are read-only external facts.

import i18n from "i18next";
import { useTranslation } from "react-i18next";

import { isEditableTag, type TagRef } from "./api";
import type { ExploreT } from "./explore/explorePresentation";

type KnownTagFacet = "category" | "theme" | "provenance" | "industry" | "sector";

// Tasks 5/7 will pass translators from the remaining direct helper callers.
// Until then, their compatibility path still resolves copy from Explore resources.
function activeExploreT(): ExploreT {
  return i18n.getFixedT(null, "explore");
}

// Facet axes used for the filter dropdowns, in display order. Industry/sector
// (provider-sourced) join later (slice 3); unknown facets fall through. Getter-backed
// labels keep Universe resource-owned until its Task 5 translator migration.
export const TAG_FACETS: { facet: KnownTagFacet; readonly label: string }[] = [
  { facet: "category", get label() { return facetLabel("category"); } },
  { facet: "theme", get label() { return facetLabel("theme"); } },
  { facet: "provenance", get label() { return facetLabel("provenance"); } },
  { facet: "industry", get label() { return facetLabel("industry"); } },
  { facet: "sector", get label() { return facetLabel("sector"); } },
];

export function facetLabel(facet: string, t: ExploreT = activeExploreT()): string {
  switch (facet) {
    case "category":
      return t(($) => $.tags.category);
    case "theme":
      return t(($) => $.tags.theme);
    case "provenance":
      return t(($) => $.tags.provenance);
    case "industry":
      return t(($) => $.tags.industry);
    case "sector":
      return t(($) => $.tags.sector);
    default:
      return facet;
  }
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

export function tagTitle(tag: TagRef, t: ExploreT = activeExploreT()): string {
  const readOnly = isEditableTag(tag) ? "" : ` ${t(($) => $.tags.readOnlySuffix)}`;
  return t(($) => $.tags.compositeTitle, {
    facet: facetLabel(tag.facet, t),
    value: tag.value,
    source: tag.source,
    readOnly,
  });
}

export function tagKey(t: TagRef): string {
  return `${t.facet}:${t.value}:${t.source}`;
}

// Read-only chip row for table cells. Caps the count with a "+N" overflow.
export function TagChips({ tags, max = 5 }: { tags?: TagRef[]; max?: number }) {
  const { t: translate } = useTranslation("explore");
  if (!tags || tags.length === 0) return null;
  const shown = tags.slice(0, max);
  const extra = tags.length - shown.length;
  return (
    <span className="chips tagchips">
      {shown.map((t) => (
        <span key={tagKey(t)} className={tagClass(t)} title={tagTitle(t, translate)}>
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
