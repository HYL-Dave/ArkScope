import { expect, it } from "vitest";
import { CURRENT_ACTION_STATES, CURRENT_REVIEW_REASONS } from "./currentReviewContract";
import { currentReviewCopy } from "./currentReviewPresentation";

it.each(["en", "zh-Hant"] as const)("has exactly the current review and action vocabulary in %s", (locale) => {
  const copy = currentReviewCopy(locale);
  expect(Object.keys(copy.reasons).sort()).toEqual([...CURRENT_REVIEW_REASONS].sort());
  expect(Object.keys(copy.states).sort()).toEqual([...CURRENT_ACTION_STATES].sort());
  for (const value of [...Object.values(copy.reasons), ...Object.values(copy.states)]) expect(value.trim()).not.toBe("");
});
