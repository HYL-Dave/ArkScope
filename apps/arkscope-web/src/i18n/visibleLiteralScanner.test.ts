import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { afterEach, describe, expect, it } from "vitest";

interface Candidate {
  file: string;
  line: number;
  column: number;
  kind: string;
  literal: string;
  signature: string;
}

const projectRoot = resolve(import.meta.dirname, "../..");
const cli = resolve(projectRoot, "scripts/i18n/visible-literal-scanner.mjs");
const temporaryRoots: string[] = [];

afterEach(() => {
  for (const path of temporaryRoots.splice(0)) {
    rmSync(path, { recursive: true, force: true });
  }
});

function run(args: string[], cwd = projectRoot) {
  const result = spawnSync(process.execPath, [cli, ...args], {
    cwd,
    encoding: "utf8",
  });
  if (result.error) throw result.error;
  return result;
}

function scanFixture(name: string): Candidate[] {
  const result = run([
    "scan",
    `scripts/i18n/fixtures/${name}.tsx.txt`,
  ]);
  expect(result.status, result.stderr).toBe(0);
  return JSON.parse(result.stdout) as Candidate[];
}

function createPolicyRoot(source: string) {
  const root = mkdtempSync(resolve(tmpdir(), "arkscope-i18n-scanner-"));
  temporaryRoots.push(root);
  mkdirSync(resolve(root, "src"), { recursive: true });
  writeFileSync(resolve(root, "src/example.tsx"), source);
  const paths = {
    root,
    source: resolve(root, "src/example.tsx"),
    debt: resolve(root, "debt.json"),
    allowlist: resolve(root, "allowlist.json"),
    migrated: resolve(root, "migrated.json"),
  };
  writeFileSync(paths.debt, JSON.stringify({ version: 1, signatures: [] }));
  writeFileSync(paths.allowlist, JSON.stringify({ version: 1, entries: [] }));
  writeFileSync(paths.migrated, JSON.stringify({ version: 1, scopes: [] }));
  return paths;
}

function policyArgs(paths: ReturnType<typeof createPolicyRoot>) {
  return [
    "check",
    "--root",
    paths.root,
    "--debt",
    paths.debt,
    "--allowlist",
    paths.allowlist,
    "--migrated",
    paths.migrated,
  ];
}

describe("visible literal scanner", () => {
  it("detects and normalizes JSX text through the TypeScript AST", () => {
    const candidates = scanFixture("jsx-text");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "jsx_text", literal: "Visible copy!" },
      { kind: "jsx_text", literal: "Secondary label" },
    ]);
  });

  it("detects label title description and alt props", () => {
    const candidates = scanFixture("visible-props");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "object_property", literal: "Provider status" },
      { kind: "object_property", literal: "Current connection health" },
      { kind: "jsx_attribute", literal: "Account value" },
      { kind: "jsx_attribute", literal: "Value history chart" },
    ]);
  });

  it("detects aria-label and ariaLabel props", () => {
    const candidates = scanFixture("aria-labels");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "object_property", literal: "Open activity" },
      { kind: "jsx_attribute", literal: "Close panel" },
    ]);
  });

  it("detects placeholder props", () => {
    const candidates = scanFixture("placeholder");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "object_property", literal: "Filter settings" },
      { kind: "jsx_attribute", literal: "Search all settings" },
    ]);
  });

  it("detects visible expression and template copy", () => {
    const candidates = scanFixture("expression-template");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "jsx_expression", literal: "Visible expression" },
      { kind: "jsx_expression", literal: "Running ${count} items" },
    ]);
  });

  it("detects visible objects message sinks presenter returns and conservative CJK runtime literals", () => {
    const candidates = scanFixture("message-sinks");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "message_setter", literal: "Could not load settings" },
      { kind: "object_property", literal: "No records available" },
      { kind: "presenter_return", literal: "Ready" },
      { kind: "runtime_cjk", literal: "同步作業失敗" },
    ]);
  });

  it("ignores comments import paths tests resources and declarations", () => {
    expect(scanFixture("ignored-contexts")).toEqual([]);

    const paths = createPolicyRoot("export const view = <p>應被路徑排除</p>;");
    const excluded = [
      "src/example.test.tsx",
      "src/i18n/resources/zh-Hant/common.ts",
      "src/example.d.ts",
      "src/test/helper.ts",
    ];
    for (const relativePath of excluded) {
      const path = resolve(paths.root, relativePath);
      mkdirSync(resolve(path, ".."), { recursive: true });
      writeFileSync(path, readFileSync(paths.source));
    }
    writeFileSync(paths.source, "export const machine = 'provider_status';");
    const result = run(["scan", ...excluded], paths.root);
    expect(result.status, result.stderr).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual([]);
  });

  it("rejects dynamic keys while accepting the one reviewed typed key style", () => {
    const candidates = scanFixture("dynamic-keys");
    expect(candidates.map(({ kind, literal }) => ({ kind, literal }))).toEqual([
      { kind: "dynamic_translation_key", literal: "`settings.${section}`" },
      { kind: "dynamic_translation_key", literal: "keyName" },
    ]);

    const paths = createPolicyRoot(readFileSync(
      resolve(projectRoot, "scripts/i18n/fixtures/dynamic-keys.tsx.txt"),
      "utf8",
    ));
    const result = run(policyArgs(paths), paths.root);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("dynamic translation key");
  });

  it("requires exact current allowlist entries and rejects stale entries", () => {
    const paths = createPolicyRoot("export const view = <p>FRED</p>;");
    const scanned = run(["scan", "src/example.tsx"], paths.root);
    expect(scanned.status, scanned.stderr).toBe(0);
    const [candidate] = JSON.parse(scanned.stdout) as Candidate[];
    writeFileSync(paths.allowlist, JSON.stringify({
      version: 1,
      entries: [{
        file: candidate.file,
        kind: candidate.kind,
        literal: candidate.literal,
        count: 1,
        classification: "stable_identifier",
        reason: "FRED is a stable provider identifier.",
      }],
    }));

    expect(run(policyArgs(paths), paths.root).status).toBe(0);
    writeFileSync(paths.source, "export const view = <p />;");
    const stale = run(policyArgs(paths), paths.root);
    expect(stale.status).not.toBe(0);
    expect(stale.stderr).toContain("stale allowlist");
  });

  it("allows legacy debt only to shrink and requires zero in migrated scopes", () => {
    const paths = createPolicyRoot("export const view = <p>Legacy label</p>;");
    const scanned = run(["scan", "src/example.tsx"], paths.root);
    expect(scanned.status, scanned.stderr).toBe(0);
    const [candidate] = JSON.parse(scanned.stdout) as Candidate[];
    writeFileSync(paths.debt, JSON.stringify({
      version: 1,
      signatures: [{ signature: candidate.signature, count: 1 }],
    }));
    expect(run(policyArgs(paths), paths.root).status).toBe(0);

    writeFileSync(paths.source, "export const view = <p />;");
    expect(run(policyArgs(paths), paths.root).status).toBe(0);

    writeFileSync(
      paths.source,
      "export const view = <><p>Legacy label</p><p>Legacy label</p></>;",
    );
    const increased = run(policyArgs(paths), paths.root);
    expect(increased.status).not.toBe(0);
    expect(increased.stderr).toContain("legacy debt increased");

    writeFileSync(paths.source, "export const view = <p>Legacy label</p>;");
    writeFileSync(paths.migrated, JSON.stringify({ version: 1, scopes: ["src/**"] }));
    const migrated = run(policyArgs(paths), paths.root);
    expect(migrated.status).not.toBe(0);
    expect(migrated.stderr).toContain("migrated scope");
  });
});
