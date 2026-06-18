// MarkdownView — safe Markdown rendering for AI 研究 answers (gpt-5.5 spec).
// Rendered to a static HTML string (no jsdom needed) to assert the safe-render
// contract: GFM elements render, raw HTML is NOT injected, links open external,
// images are restricted to https.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MarkdownView } from "./MarkdownView";

const html = (source: string) => renderToStaticMarkup(createElement(MarkdownView, { source }));

describe("MarkdownView", () => {
  it("renders bold/emphasis", () => {
    expect(html("**bold** and *em*")).toContain("<strong>bold</strong>");
  });

  it("renders GFM tables", () => {
    const out = html("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(out).toContain("<table>");
    expect(out).toContain("<td>1</td>");
  });

  it("renders lists and blockquotes", () => {
    expect(html("- one\n- two")).toContain("<li>one</li>");
    expect(html("> quote")).toContain("<blockquote>");
  });

  it("renders code blocks (selectable text, not executed)", () => {
    const out = html("```\nconst x = 1\n```");
    expect(out).toContain("<code");
    expect(out).toContain("const x = 1");
  });

  it("opens links in a new tab with noopener", () => {
    const out = html("[ark](https://example.com)");
    expect(out).toContain('href="https://example.com"');
    expect(out).toContain('target="_blank"');
    expect(out).toContain("noopener");
  });

  it("does NOT inject raw HTML (no rehype-raw)", () => {
    const out = html('hi <script>alert(1)</script> <b>x</b>');
    expect(out).not.toContain("<script>");      // not rendered as a real script tag
    expect(out).not.toContain("<b>x</b>");        // raw inline HTML not injected
    expect(out).toContain("alert(1)");            // shown as TEXT (escaped), not executed
  });

  it("renders https images", () => {
    expect(html("![alt](https://example.com/a.png)")).toContain('src="https://example.com/a.png"');
  });

  it("blocks non-https image sources (file:// etc.) — shows alt, no img src", () => {
    const out = html("![danger](file:///etc/passwd)");
    expect(out).not.toContain("file:///etc/passwd");  // never emit a file:// src
    expect(out).toContain("danger");                    // fall back to alt text
  });
});
