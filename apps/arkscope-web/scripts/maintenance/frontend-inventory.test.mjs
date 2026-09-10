import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { scanFrontend } from "./frontend-inventory.mjs";

const moduleUrl = new URL("./frontend-inventory.mjs", import.meta.url);
const web = "apps/arkscope-web";
const desktop = "apps/arkscope-desktop";
const json = (value) => JSON.stringify(value, null, 2);
const resource = (locale, namespace = "common") => `${web}/src/i18n/resources/${locale}/${namespace}.ts`;
const key = (report, namespace, name, locale = "en") => report.i18n.keys.find(
  (entry) => entry.locale === locale && entry.namespace === namespace && entry.key === name,
);

test("translator object property escapes retain uncertainty", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { title: "Title" };',
    [`${web}/src/view.ts`]: 'const hook = useTranslation("common"); const alias = hook.t; alias(dynamicKey);',
  });
  assert(report.unresolved.some((row) => row.reason === "escaped-translation-binding"));
  assert.equal(key(report, "common", "title").status, "unresolved");
});

test("loop bindings cannot shadow an enclosing translator after the loop", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { title: "Title" };',
    [`${web}/src/view.ts`]: 'const {t:tr} = useTranslation("common"); for (const tr of callbacks) {} tr("title");',
  });
  assert.equal(key(report, "common", "title").status, "referenced");
});

test("locale and CSS references do not cross workspace ownership", () => {
  const report = scanFrontend({
    [`${web}/package.json`]: '{}', [`${desktop}/package.json`]: '{}',
    [resource("en")]: 'export default { title: "Web" };',
    [`${desktop}/src/i18n/resources/en/common.ts`]: 'export default { title: "Desktop" };',
    [`${web}/src/view.tsx`]: 'const {t} = useTranslation("common"); t("title"); const view = <div className="used" />;',
    [`${web}/src/style.css`]: '.used { color: red; }',
    [`${desktop}/src/style.css`]: '.used { color: red; }',
  });
  assert.equal(report.i18n.keys.find((row) => row.file.startsWith(desktop)).status, "no-static-reference");
  assert.equal(report.css.selectors.find((row) => row.file.startsWith(desktop)).status, "no-static-reference");
  assert.equal(report.i18n.keys.find((row) => row.file.startsWith(web)).status, "referenced");
});

test("missing manifests do not collapse separate workspaces into one authority", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { title: "Web" };',
    [`${desktop}/src/i18n/resources/en/common.ts`]: 'export default { title: "Desktop" };',
    [`${web}/src/view.tsx`]: 'const {t} = useTranslation("common"); t("title"); const view = <div className="used" />;',
    [`${web}/src/style.css`]: '.used { color: red; }',
    [`${desktop}/src/style.css`]: '.used { color: red; }',
  });
  assert.notEqual(report.i18n.keys.find((row) => row.file.startsWith(desktop)).status, "referenced");
  assert.notEqual(report.css.selectors.find((row) => row.file.startsWith(desktop)).status, "referenced");
  assert(report.unresolved.some((row) => row.reason === "workspace-manifest-missing"));
});

test("empty input is a deterministic, explicitly non-exhaustive inventory", () => {
  const report = scanFrontend({});
  assert.equal(report.schemaVersion, 1);
  assert.equal(report.deadCodeProof, false);
  assert.equal(report.coverage.filesAnalyzed, 0);
  assert.deepEqual(report.dependencies.candidates, []);
  assert.deepEqual(report.i18n.keys, []);
  assert.deepEqual(report.http.references, []);
  assert.deepEqual(report.css.selectors, []);
  assert.deepEqual(report.unresolved, []);
});

test("module syntax records package roots, locations, type-only imports, and dynamic uncertainty", () => {
  const file = `${web}/src/example.ts`;
  const report = scanFrontend({
    [`${web}/package.json`]: json({ dependencies: { react: "1", "@scope/lib": "1", lazy: "1", cjs: "1" } }),
    [file]: [
      'import React from "react";',
      'export { value } from "@scope/lib/subpath";',
      'const loaded = require("cjs");',
      'const lazy = import("lazy/chunk");',
      'import type { Thing } from "type-only";',
      'import { type Other } from "named-types";',
      'type T = import("import-types").T;',
      'import C = require("import-equals");',
      'import(packageName);',
      'require(`plugin-${name}`);',
      'import "./local";',
      'import "node:fs";',
    ].join("\n"),
  });
  assert.deepEqual(report.dependencies.references.filter((r) => r.file === file).map(
    ({ package: name, line, mode }) => [name, line, mode],
  ), [
    ["react", 1, "runtime"], ["@scope/lib", 2, "runtime"], ["cjs", 3, "runtime"],
    ["lazy", 4, "runtime"], ["type-only", 5, "tooling"], ["named-types", 6, "tooling"],
    ["import-types", 7, "tooling"], ["import-equals", 8, "runtime"],
  ]);
  assert.ok(report.dependencies.candidates.every((entry) => entry.status === "runtime"));
  assert.equal(report.unresolved.filter((entry) => entry.reason === "dynamic-module-specifier").length, 2);
});

test("root and workspace scripts, configs, and ambient types protect tooling dependencies", () => {
  const report = scanFrontend({
    "package.json": json({ devDependencies: { typescript: "1" }, scripts: { check: "tsc --noEmit" } }),
    [`${web}/package.json`]: json({
      dependencies: { react: "1", absent: "1" },
      devDependencies: { vite: "1", jsdom: "1", "@types/react": "1", "@types/node": "1", "@vitejs/plugin-react": "1", unseenTool: "1" },
      scripts: { dev: "vite", check: "node custom-tool.js" },
    }),
    [`${desktop}/package.json`]: json({ devDependencies: { electron: "1" }, scripts: { start: "electron ." } }),
    [`${web}/vite.config.ts`]: 'import react from "@vitejs/plugin-react"; export default { environment: "jsdom" };',
    [`${web}/tsconfig.json`]: '{ // JSONC is allowed here\n "compilerOptions": { "types": ["react", "node", "vite/client"] } }',
    [`${web}/src/view.tsx`]: 'import React from "react"; export const view = <div />;',
    [`${desktop}/main.js`]: 'const { app } = require("electron");',
  });
  const statuses = Object.fromEntries(report.dependencies.candidates.map((entry) => [entry.package, entry.status]));
  assert.deepEqual(statuses, {
    react: "runtime", absent: "unresolved", vite: "tooling", jsdom: "tooling",
    "@types/react": "tooling", "@types/node": "tooling", "@vitejs/plugin-react": "tooling",
    unseenTool: "unresolved", electron: "runtime", typescript: "tooling",
  });
  assert.equal(report.coverage.byKind.manifest, 3);
  for (const candidate of report.dependencies.candidates) {
    assert.ok(candidate.file.endsWith("package.json"));
    assert.ok(candidate.line > 1);
    assert.ok(candidate.status !== "unused");
  }
});

test("dependency evidence belongs to the nearest declaring manifest, not sibling workspaces", () => {
  const report = scanFrontend({
    "package.json": json({ dependencies: { shared: "1" } }),
    [`${web}/package.json`]: json({ dependencies: { shared: "1" } }),
    [`${desktop}/package.json`]: json({ dependencies: { shared: "1" } }),
    [`${web}/src/view.ts`]: 'import "shared/subpath";',
  });
  assert.deepEqual(report.dependencies.candidates.map((entry) => [entry.file, entry.status]), [
    [`${desktop}/package.json`, "unresolved"], [`${web}/package.json`, "runtime"], ["package.json", "unresolved"],
  ]);
});

test("locale leaf keys match scoped selectors, string paths, aliases, and fixed translators", () => {
  const file = `${web}/src/view.tsx`;
  const report = scanFrontend({
    [resource("en")]: 'const common = { actions: { close: "Close", open: "Open", untouched: "Other" } } as const; export default common;',
    [resource("zh-Hant")]: 'export default { actions: { close: "Close", open: "Open", untouched: "Other" } };',
    [resource("en", "shell")]: 'export default { title: "Title", nav: { home: "Home" } };',
    [file]: [
      'import { useTranslation as useT } from "react-i18next";',
      'function Common() { const { t: translate } = useT("common");',
      '  translate(($) => $.actions.close);',
      '  translate("actions.open"); }',
      'function Shell() { const { t } = useT("shell"); t(($) => $["title"]); }',
      'const fixed = i18n.getFixedT(null, "shell", "nav"); fixed("home");',
      'function Typed(t: TFunction<"common">) { t(($) => $.actions.close); }',
      't("common:actions.open");',
    ].join("\n"),
  });
  assert.equal(report.i18n.keys.length, 8);
  assert.equal(report.i18n.references.length, 6);
  assert.equal(key(report, "common", "actions.close").status, "referenced");
  assert.equal(key(report, "common", "actions.close", "zh-Hant").status, "referenced");
  assert.equal(key(report, "common", "actions.untouched").status, "no-static-reference");
  assert.equal(key(report, "shell", "nav.home").status, "referenced");
  assert.equal(report.i18n.references.find((entry) => entry.line === 3).key, "actions.close");
  assert.deepEqual(report.unresolved.filter((entry) => entry.axis === "i18n"), []);
});

test("dynamic translation keys and namespaces retain uncertainty for unreferenced leaves", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { known: "Known", other: "Other" };',
    [resource("en", "shell")]: 'export default { title: "Title" };',
    [`${web}/src/dynamic.tsx`]: [
      'function Known() { const { t } = useTranslation("common");',
      't("known"); t(key); t(($) => $[key]); t(`prefix.${key}`); }',
      'function Unknown() { const { t } = useTranslation(namespace); t("title"); }',
      'const fixed = getFixedT(null, namespace); fixed("title");',
      'resources[locale][namespace][key];',
    ].join("\n"),
  });
  assert.equal(key(report, "common", "known").status, "referenced");
  assert.equal(key(report, "common", "other").status, "unresolved");
  assert.equal(key(report, "shell", "title").status, "unresolved");
  const reasons = report.unresolved.filter((entry) => entry.axis === "i18n").map((entry) => entry.reason);
  assert.ok(reasons.includes("dynamic-translation-key"));
  assert.ok(reasons.includes("dynamic-translation-namespace"));
  assert.ok(reasons.includes("resource-access"));
});

test("translator scopes and dynamic key prefixes cannot manufacture static matches", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { title: "Title", panel: { title: "Panel" } };',
    [resource("en", "shell")]: 'export default { title: "Shell" };',
    [`${web}/src/scopes.tsx`]: [
      'function One() { const { t } = useTranslation("common"); t("title");',
      '  { const { t } = useTranslation("shell"); t("title"); }',
      '  function nested(t) { t("panel.title"); } }',
      'function Two() { const { t } = useTranslation("common", { keyPrefix: prefix }); t("title"); }',
    ].join("\n"),
  });
  assert.deepEqual(report.i18n.references.map((entry) => [entry.namespace, entry.key]), [
    ["common", "title"], ["shell", "title"],
  ]);
  assert.equal(key(report, "common", "panel.title").status, "unresolved");
  assert.ok(report.unresolved.some((entry) => entry.reason === "dynamic-translation-prefix"));
});

test("JSON locale leaves are parsed, while resource spreads and computed keys are unresolved", () => {
  const report = scanFrontend({
    [`${web}/public/locales/en/common.json`]: '{\n "actions": { "close": "Close" }\n}',
    [resource("zh-Hant")]: 'export default { actions: { close: "Close" }, ...extra, [key]: "Value" };',
  });
  assert.equal(report.i18n.keys.length, 2);
  assert.equal(key(report, "common", "actions.close").line, 2);
  assert.ok(report.unresolved.some((entry) => entry.reason === "dynamic-resource-member"));
});

test("unbound translation factories still report dynamic namespace uncertainty", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { possible: "Possible" };',
    [`${web}/src/factories.tsx`]: [
      'function make() { return i18n.getFixedT(null, namespace); }',
      'const hooks = { result: useTranslation(namespaces) };',
    ].join("\n"),
  });
  assert.equal(report.unresolved.filter((entry) => entry.reason === "dynamic-translation-namespace").length, 2);
  assert.equal(key(report, "common", "possible").status, "unresolved");
});

test("translation call options do not silently override prefixes or separator assumptions", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { title: "Title", panel: { title: "Panel" } };',
    [`${web}/src/options.ts`]: [
      'const fixed = getFixedT(null, "common", "panel");',
      'fixed("title", { keyPrefix: "" });',
      'fixed("title", { keyPrefix: prefix });',
      'fixed("panel.title", { keySeparator: false });',
      'fixed("title", { ns: namespace });',
    ].join("\n"),
  });
  assert.deepEqual(report.i18n.references.map((entry) => [entry.namespace, entry.key]), [["common", "title"]]);
  assert.equal(key(report, "common", "panel.title").status, "unresolved");
  assert.ok(report.unresolved.some((entry) => entry.reason === "dynamic-translation-prefix"));
  assert.ok(report.unresolved.some((entry) => entry.reason === "unsupported-translation-options"));
});

test("imported t aliases are observed and escaping or reassigned translators are unresolved", () => {
  const report = scanFrontend({
    [resource("en")]: 'export default { known: "Known", other: "Other" };',
    [`${web}/src/aliases.ts`]: [
      'import { t as translate } from "i18next";',
      'translate("common:known");',
      'const { t } = useTranslation("common"); const alias = t; alias(dynamicKey);',
      'let fixed = getFixedT(null, "common"); fixed = unknown; fixed("other");',
    ].join("\n"),
  });
  assert.deepEqual(report.i18n.references.map((entry) => entry.key), ["known"]);
  assert.equal(key(report, "common", "other").status, "unresolved");
  assert.ok(report.unresolved.some((entry) => entry.reason === "escaped-translation-binding"));
  assert.ok(report.unresolved.some((entry) => entry.reason === "reassigned-translation-binding"));
});

test("HTTP inventory keeps literal and template routes and extractable methods without executing calls", () => {
  const file = `${web}/src/api.ts`;
  const report = scanFrontend({ [file]: [
    'fetch("/healthz");',
    'fetch(`${apiBase}/query/stream`, { method: "POST" });',
    'getJSON<Result>(`/items/${id}`);',
    'sendJSON("/items", "PATCH", body);',
    'fetchWithTimeout("/slow", 3000, { method: "DELETE" });',
    'client.put("/client", body);',
    'axios.request({ url: "/request", method: "post" });',
    'fetch(endpoint, options);',
    'fetch("/unknown-method", { method });',
    'const map = new Map(); map.get("not-a-route");',
    'throw new Error("SCANNER MUST NOT EVALUATE THIS MODULE");',
  ].join("\n") });
  assert.deepEqual(report.http.references.map(({ url, method, kind, line }) => [url, method, kind, line]), [
    ["/healthz", "GET", "literal", 1], ["${apiBase}/query/stream", "POST", "template", 2],
    ["/items/${id}", "GET", "template", 3], ["/items", "PATCH", "literal", 4],
    ["/slow", "DELETE", "literal", 5], ["/client", "PUT", "literal", 6],
    ["/request", "POST", "literal", 7], [null, null, "dynamic", 8],
    ["/unknown-method", null, "literal", 9],
  ]);
  assert.ok(report.unresolved.some((entry) => entry.reason === "dynamic-http-method"));
  assert.ok(report.unresolved.some((entry) => entry.reason === "template-http-url"));
});

test("HTTP option spreads invalidate a preceding method but not a later explicit method", () => {
  const report = scanFrontend({ [`${web}/src/routes.ts`]: [
    'fetch("/first", { method: "POST", ...options });',
    'fetch("/second", { ...options, method: "PUT" });',
    'fetch("/third", { ...options });',
  ].join("\n") });
  assert.deepEqual(report.http.references.map((entry) => entry.method), [null, "PUT", null]);
});

test("HTTP request overloads retain URL arguments and never invent defaults for arbitrary wrappers", () => {
  const report = scanFrontend({ [`${web}/src/overloads.ts`]: [
    'axios("/direct", { method: "PUT" });',
    'axios(`/items/${id}`);',
    'client.request("/request", { method: "DELETE" });',
    'client.request("/unknown");',
  ].join("\n") });
  assert.deepEqual(report.http.references.map((entry) => [entry.url, entry.method]), [
    ["/direct", "PUT"], ["/items/${id}", "GET"], ["/request", "DELETE"], ["/unknown", null],
  ]);
});

test("CSS selector candidates match literal className tokens, not comments or declaration strings", () => {
  const file = `${web}/src/styles.css`;
  const report = scanFrontend({
    [file]: [
      '/* .comment { color: red; } */',
      '.used:hover, .other { color: red; content: ".not-a-selector"; }',
      '@media (min-width: 10px) { .nested > .used { display: flex; } }',
      '.absent { background: url("/image.png"); }',
    ].join("\n"),
    [`${web}/src/view.tsx`]: '<><div className="used other" /><span className={"nested"} /></>',
  });
  assert.deepEqual(report.css.references.map((entry) => entry.className).sort(), ["nested", "other", "used"]);
  assert.deepEqual(report.css.selectors.map(({ selector, status, line }) => [selector, status, line]), [
    [".used:hover", "referenced", 2], [".other", "referenced", 2],
    [".nested > .used", "referenced", 3], [".absent", "no-static-reference", 4],
  ]);
});

test("dynamic classes, escaped selectors, and non-class selectors remain unresolved", () => {
  const report = scanFrontend({
    [`${web}/src/styles.css`]: '.maybe {}\n.escaped\\:name {}\nbutton {}',
    [`${web}/src/view.tsx`]: '<div className={`maybe-${tone} ${className}`} />',
  });
  assert.ok(report.css.selectors.every((entry) => entry.status === "unresolved"));
  assert.ok(report.unresolved.some((entry) => entry.reason === "dynamic-class-name"));
  assert.ok(report.unresolved.some((entry) => entry.reason === "unsupported-css-selector"));
});

test("large CSS and non-BMP text preserve offsets without variadic array limits", () => {
  const report = scanFrontend({
    [`${web}/src/large.css`]: `/* ${"x".repeat(180000)} */\n/* \u{1f680} */ .after { content: "/* not a comment */"; }`,
  });
  assert.equal(report.css.selectors.length, 1);
  assert.equal(report.css.selectors[0].selector, ".after");
  assert.equal(report.css.selectors[0].line, 2);
  assert.equal(report.css.selectors[0].column, 10);
  assert.deepEqual(report.coverage.parseErrors, []);
});

test("className shorthands and computed access retain uncertainty", () => {
  const report = scanFrontend({
    [`${web}/src/style.css`]: ".possible {}",
    [`${web}/src/classes.ts`]: 'React.createElement("div", { className }); element["className"] = generated;',
  });
  assert.equal(report.unresolved.filter((entry) => entry.reason === "dynamic-class-name").length, 2);
  assert.equal(report.css.selectors[0].status, "unresolved");
});

test("coverage reports supplied files, unsupported files, parse failures, and all evidence locations", () => {
  const report = scanFrontend({
    [`${web}/src/broken.tsx`]: 'const value = <div',
    [`${web}/package.json`]: '{ "dependencies": ',
    [`${web}/src/broken.css`]: '.missing { color: red;',
    [resource("en")]: 'export default { unseen: "Unseen" };',
    "README.md": "This is not source code.",
  });
  assert.equal(report.coverage.filesSupplied, 5);
  assert.equal(report.coverage.filesAnalyzed, 4);
  assert.deepEqual(report.coverage.skippedFiles, [{ file: "README.md", reason: "unsupported-file-kind" }]);
  assert.equal(new Set(report.coverage.parseErrors.map((entry) => entry.file)).size, 3);
  assert.equal(key(report, "common", "unseen").status, "unresolved");
  assert.equal(report.coverage.unresolvedCount, report.unresolved.length);
  for (const entry of [...report.unresolved, ...report.coverage.parseErrors]) {
    assert.equal(typeof entry.file, "string");
    assert.ok(Number.isInteger(entry.line) && entry.line > 0);
  }
});

test("CLI reads only supplied JSON, is deterministic across input order and cwd, and rejects invalid input", () => {
  const files = {
    [`${web}/src/view.tsx`]: 'import "not-installed-anywhere"; fetch("/synthetic"); throw new Error("do not evaluate");',
    [`${web}/package.json`]: json({ dependencies: { "not-installed-anywhere": "1" } }),
  };
  const run = (input) => spawnSync(process.execPath, [fileURLToPath(moduleUrl)], {
    cwd: "/tmp", input, encoding: "utf8", timeout: 10000,
  });
  const first = run(JSON.stringify(files));
  const second = run(JSON.stringify(Object.fromEntries(Object.entries(files).reverse())));
  assert.equal(first.status, 0, first.stderr);
  assert.equal(first.stderr, "");
  assert.equal(first.stdout, second.stdout);
  assert.deepEqual(JSON.parse(first.stdout), scanFrontend(files));
  assert.equal(JSON.parse(first.stdout).coverage.filesSupplied, 2);
  const invalid = run("{");
  assert.notEqual(invalid.status, 0);
  assert.equal(invalid.stdout, "");
  for (const value of [null, [], { "x.ts": 1 }, { "/absolute.ts": "" }, { "../outside.ts": "" }]) {
    assert.throws(() => scanFrontend(value), /mapping|relative|source/i);
  }
});
