/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createInstance, type i18n } from "i18next";
import { createRoot } from "react-dom/client";
import { I18nextProvider } from "react-i18next";
import { afterEach, describe, expect, it } from "vitest";

import type { TagRef } from "./api";
import type { ExploreT } from "./explore/explorePresentation";
import { initializeI18n } from "./i18n/resources";
import {
  TAG_FACETS,
  TagChips,
  facetLabel,
  tagClass,
  tagKey,
  tagTitle,
} from "./tags";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

type Locale = "zh-Hant" | "en";

function instanceFor(locale: Locale): i18n {
  return initializeI18n(createInstance(), locale);
}

function exploreT(locale: Locale): ExploreT {
  return instanceFor(locale).getFixedT(locale, "explore");
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function renderTags(instance: i18n, tags: TagRef[]) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root!.render(
      <I18nextProvider i18n={instance}>
        <TagChips tags={tags} />
      </I18nextProvider>,
    );
  });
  return host;
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

describe("Explore tags", () => {
  it("maps every known tag facet in both locales", () => {
    const expected = {
      "zh-Hant": ["類別", "主題", "來源依據", "Industry", "Sector"],
      en: ["Category", "Theme", "Provenance", "Industry", "Sector"],
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = exploreT(locale);
      expect(TAG_FACETS.map(({ facet }) => facetLabel(facet, t))).toEqual(expected[locale]);
    }
  });

  it("keeps unknown interactive facet IDs distinct and visible", () => {
    const alpha = "planted_facet_alpha";
    const beta = "planted_facet_beta";

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = exploreT(locale);
      const suffix = locale === "en" ? " · read-only" : " · 唯讀";
      expect([facetLabel(alpha, t), facetLabel(beta, t)]).toEqual([alpha, beta]);
      expect(tagTitle({ facet: alpha, value: "A", source: "system" }, t)).toBe(
        `${alpha} · A (system)${suffix}`,
      );
      expect(tagTitle({ facet: beta, value: "B", source: "system" }, t)).toBe(
        `${beta} · B (system)${suffix}`,
      );
    }
  });

  it("preserves tag values and source IDs byte for byte", () => {
    const value = "  Alpha:β / %2F  ";
    const source = "provider:Plant/RAW%2Fv1";
    const tag = { facet: "provenance", value, source };
    const host = renderTags(instanceFor("en"), [tag]);
    const chip = host.querySelector<HTMLElement>(".tagchip");

    expect(chip?.textContent).toBe(value);
    expect(chip?.title).toBe(`Provenance · ${value} (${source}) · read-only`);
    expect(tag.value).toBe(value);
    expect(tag.source).toBe(source);
  });

  it("preserves tag keys editability and CSS classes", () => {
    const editable: TagRef = { facet: "category", value: "Core:Value", source: "user" };
    const readOnly: TagRef = { facet: "theme", value: "Cloud", source: "provider:seed" };

    expect(tagKey(editable)).toBe("category:Core:Value:user");
    expect(tagKey(readOnly)).toBe("theme:Cloud:provider:seed");
    expect(tagClass(editable)).toBe("tagchip tagchip--user");
    expect(tagClass(readOnly)).toBe("tagchip tagchip--theme");
    expect(tagClass({ facet: "provenance", value: "x", source: "system" })).toBe(
      "tagchip tagchip--prov",
    );
    expect(tagClass({ facet: "industry", value: "x", source: "provider" })).toBe(
      "tagchip tagchip--ind",
    );
    expect(tagClass({ facet: "unknown", value: "x", source: "system" })).toBe("tagchip");
    expect(tagTitle(editable, exploreT("zh-Hant"))).toBe("類別 · Core:Value (user)");
    expect(tagTitle(readOnly, exploreT("en"))).toBe(
      "Theme · Cloud (provider:seed) · read-only",
    );
  });

  it("switches tag chrome in place without replacing the value node", async () => {
    const instance = instanceFor("zh-Hant");
    const host = renderTags(instance, [
      { facet: "category", value: "planted-value", source: "system" },
    ]);
    const valueNode = host.querySelector<HTMLElement>(".tagchip");

    expect(valueNode?.title).toBe("類別 · planted-value (system) · 唯讀");
    await act(async () => {
      await instance.changeLanguage("en");
    });

    expect(host.querySelector(".tagchip")).toBe(valueNode);
    expect(valueNode?.textContent).toBe("planted-value");
    expect(valueNode?.title).toBe("Category · planted-value (system) · read-only");
  });
});
