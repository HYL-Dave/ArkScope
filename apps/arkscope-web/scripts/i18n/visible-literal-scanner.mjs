#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import ts from "typescript";

const VISIBLE_NAMES = new Set([
  "label",
  "title",
  "description",
  "alt",
  "placeholder",
  "aria-label",
  "ariaLabel",
  "caption",
  "helperText",
  "emptyMessage",
  "errorMessage",
  "statusText",
  "tooltip",
]);
const MESSAGE_SETTER = /^set(?:Err|Error|Notice|Warning|Message|BlockedReason)$/;
const PRESENTER_SUFFIX = /(?:Label|Description|Message|Reason|Text|Title)$/;
const CJK = /[\u3400-\u9fff\uf900-\ufaff]/u;
const ALPHABETIC = /[A-Za-z]/;
const ALLOWLIST_CLASSES = new Set([
  "stable_identifier",
  "user_or_source_content",
]);
const DEFAULT_MANIFEST_DIR = path.resolve("scripts/i18n");

function normalizePath(value) {
  return value.split(path.sep).join("/");
}

function normalizeLiteral(value) {
  return value.replace(/\s+/gu, " ").trim();
}

function isVisibleContent(value) {
  return CJK.test(value) || ALPHABETIC.test(value);
}

function isExcludedFile(relativePath) {
  const file = normalizePath(relativePath);
  return (
    /(?:^|\/)src\/test(?:\/|$)/.test(file) ||
    /(?:^|\/)src\/i18n\/resources(?:\/|$)/.test(file) ||
    /\.d\.ts$/i.test(file) ||
    /(?:^|\/)__tests__(?:\/|$)/.test(file) ||
    /\.test\.[cm]?[jt]sx?$/i.test(file) ||
    /\.spec\.[cm]?[jt]sx?$/i.test(file)
  );
}

function propertyNameText(name, sourceFile) {
  if (!name) return null;
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) {
    return name.text;
  }
  return name.getText(sourceFile);
}

function findAncestor(node, predicate) {
  for (let current = node.parent; current; current = current.parent) {
    if (predicate(current)) return current;
  }
  return null;
}

function isDirectJsxExpressionContent(node) {
  const expression = findAncestor(node, ts.isJsxExpression);
  if (
    !expression ||
    (!ts.isJsxElement(expression.parent) && !ts.isJsxFragment(expression.parent))
  ) {
    return false;
  }

  let current = node;
  while (current.parent && current.parent !== expression) {
    const parent = current.parent;
    if (
      ts.isParenthesizedExpression(parent) ||
      ts.isAsExpression(parent) ||
      ts.isTypeAssertionExpression(parent) ||
      ts.isNonNullExpression(parent) ||
      ts.isArrayLiteralExpression(parent)
    ) {
      current = parent;
      continue;
    }
    if (ts.isConditionalExpression(parent)) {
      if (current === parent.condition) return false;
      current = parent;
      continue;
    }
    if (ts.isBinaryExpression(parent)) {
      const operator = parent.operatorToken.kind;
      if (
        operator !== ts.SyntaxKind.PlusToken &&
        operator !== ts.SyntaxKind.QuestionQuestionToken &&
        operator !== ts.SyntaxKind.BarBarToken &&
        operator !== ts.SyntaxKind.AmpersandAmpersandToken
      ) {
        return false;
      }
      current = parent;
      continue;
    }
    return false;
  }
  return current.parent === expression;
}

function isTypeOnlyLiteral(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isExpressionStatement(current) || ts.isVariableStatement(current)) return false;
    if (
      ts.isLiteralTypeNode(current) ||
      ts.isTypeAliasDeclaration(current) ||
      ts.isInterfaceDeclaration(current) ||
      ts.isTypeParameterDeclaration(current) ||
      ts.isImportTypeNode(current)
    ) {
      return true;
    }
    if (ts.isSourceFile(current)) return false;
  }
  return false;
}

function isModuleSpecifier(node) {
  const parent = node.parent;
  return (
    (ts.isImportDeclaration(parent) && parent.moduleSpecifier === node) ||
    (ts.isExportDeclaration(parent) && parent.moduleSpecifier === node)
  );
}

function isPropertyName(node) {
  const parent = node.parent;
  return (
    (ts.isPropertyAssignment(parent) && parent.name === node) ||
    (ts.isPropertySignature(parent) && parent.name === node) ||
    (ts.isMethodDeclaration(parent) && parent.name === node) ||
    (ts.isMethodSignature(parent) && parent.name === node) ||
    (ts.isGetAccessorDeclaration(parent) && parent.name === node) ||
    (ts.isSetAccessorDeclaration(parent) && parent.name === node)
  );
}

function templateLiteralText(node, sourceFile) {
  if (ts.isNoSubstitutionTemplateLiteral(node)) return normalizeLiteral(node.text);
  let value = node.head.text;
  for (const span of node.templateSpans) {
    value += `\${${normalizeLiteral(span.expression.getText(sourceFile))}}`;
    value += span.literal.text;
  }
  return normalizeLiteral(value);
}

function literalText(node, sourceFile) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    return normalizeLiteral(node.text);
  }
  if (ts.isTemplateExpression(node)) return templateLiteralText(node, sourceFile);
  return null;
}

function enclosingFunctionName(node, sourceFile) {
  const fn = findAncestor(node, (candidate) =>
    ts.isFunctionDeclaration(candidate) ||
    ts.isFunctionExpression(candidate) ||
    ts.isArrowFunction(candidate) ||
    ts.isMethodDeclaration(candidate),
  );
  if (!fn) return null;
  if ((ts.isFunctionDeclaration(fn) || ts.isFunctionExpression(fn) || ts.isMethodDeclaration(fn)) && fn.name) {
    return propertyNameText(fn.name, sourceFile);
  }
  if (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) {
    const declaration = ts.isVariableDeclaration(fn.parent) ? fn.parent : null;
    if (declaration && ts.isIdentifier(declaration.name)) return declaration.name.text;
  }
  return null;
}

function callName(call) {
  if (ts.isIdentifier(call.expression)) return call.expression.text;
  if (ts.isPropertyAccessExpression(call.expression)) return call.expression.name.text;
  return null;
}

function literalKind(node, value, sourceFile) {
  if (isModuleSpecifier(node) || isPropertyName(node) || isTypeOnlyLiteral(node)) return null;

  const jsxAttribute = findAncestor(node, ts.isJsxAttribute);
  if (jsxAttribute) {
    const name = propertyNameText(jsxAttribute.name, sourceFile);
    if (name && VISIBLE_NAMES.has(name)) return "jsx_attribute";
  }

  if (isDirectJsxExpressionContent(node)) return "jsx_expression";

  const property = findAncestor(node, ts.isPropertyAssignment);
  if (property) {
    const name = propertyNameText(property.name, sourceFile);
    if (name && VISIBLE_NAMES.has(name)) return "object_property";
  }

  const call = findAncestor(node, ts.isCallExpression);
  if (call && call.arguments.some((argument) => argument === node || argument.pos <= node.pos && argument.end >= node.end)) {
    const name = callName(call);
    if (name && MESSAGE_SETTER.test(name)) return "message_setter";
  }

  const returned = findAncestor(node, ts.isReturnStatement);
  if (returned) {
    const name = enclosingFunctionName(returned, sourceFile);
    if (name && PRESENTER_SUFFIX.test(name)) return "presenter_return";
  }

  return CJK.test(value) ? "runtime_cjk" : null;
}

function selectorIsStatic(node) {
  if (!ts.isArrowFunction(node) || node.parameters.length !== 1) return false;
  const parameter = node.parameters[0].name;
  if (!ts.isIdentifier(parameter)) return false;
  let expression = node.body;
  if (ts.isParenthesizedExpression(expression)) expression = expression.expression;
  if (!ts.isPropertyAccessExpression(expression)) return false;
  while (ts.isPropertyAccessExpression(expression)) expression = expression.expression;
  return ts.isIdentifier(expression) && expression.text === parameter.text;
}

function collectTranslationBindings(sourceFile) {
  const i18nObjects = new Set();
  const directFunctions = new Set();
  const useTranslationNames = new Set(["useTranslation"]);

  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
    const moduleName = statement.moduleSpecifier.text;
    const clause = statement.importClause;
    if (!clause) continue;
    if (moduleName === "i18next") {
      if (clause.name) i18nObjects.add(clause.name.text);
      const bindings = clause.namedBindings;
      if (bindings && ts.isNamespaceImport(bindings)) i18nObjects.add(bindings.name.text);
      if (bindings && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          const imported = element.propertyName?.text ?? element.name.text;
          if (imported === "t") directFunctions.add(element.name.text);
        }
      }
    }
    if (moduleName === "react-i18next" && clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const element of clause.namedBindings.elements) {
        const imported = element.propertyName?.text ?? element.name.text;
        if (imported === "useTranslation") useTranslationNames.add(element.name.text);
      }
    }
  }

  function visit(node) {
    if (
      ts.isVariableDeclaration(node) &&
      ts.isObjectBindingPattern(node.name) &&
      node.initializer &&
      ts.isCallExpression(node.initializer) &&
      ts.isIdentifier(node.initializer.expression) &&
      useTranslationNames.has(node.initializer.expression.text)
    ) {
      for (const element of node.name.elements) {
        const imported = element.propertyName && ts.isIdentifier(element.propertyName)
          ? element.propertyName.text
          : ts.isIdentifier(element.name)
            ? element.name.text
            : null;
        if (imported === "t" && ts.isIdentifier(element.name)) directFunctions.add(element.name.text);
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return { i18nObjects, directFunctions };
}

function isTranslationCall(call, bindings) {
  if (ts.isIdentifier(call.expression)) {
    return bindings.directFunctions.has(call.expression.text);
  }
  return (
    ts.isPropertyAccessExpression(call.expression) &&
    call.expression.name.text === "t" &&
    ts.isIdentifier(call.expression.expression) &&
    bindings.i18nObjects.has(call.expression.expression.text)
  );
}

function translationKeyIsStatic(node) {
  return ts.isStringLiteral(node) || selectorIsStatic(node);
}

function sourceCandidate(file, sourceFile, node, kind, literal) {
  const start = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  const normalizedFile = normalizePath(file);
  return {
    file: normalizedFile,
    line: start.line + 1,
    column: start.character + 1,
    kind,
    literal,
    signature: JSON.stringify([normalizedFile, kind, literal]),
  };
}

function scanSource(file, source) {
  const sourceFile = ts.createSourceFile(
    file,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const bindings = collectTranslationBindings(sourceFile);
  const candidates = [];

  function add(node, kind, literal) {
    const normalized = normalizeLiteral(literal);
    if (!normalized || !isVisibleContent(normalized)) return;
    candidates.push(sourceCandidate(file, sourceFile, node, kind, normalized));
  }

  function visit(node) {
    if (ts.isJsxText(node)) {
      add(node, "jsx_text", node.getText(sourceFile));
    }

    if (ts.isCallExpression(node) && isTranslationCall(node, bindings)) {
      const key = node.arguments[0];
      if (!key || !translationKeyIsStatic(key)) {
        add(node, "dynamic_translation_key", key ? key.getText(sourceFile) : "<missing>");
      }
    }

    if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateExpression(node)
    ) {
      const value = literalText(node, sourceFile);
      if (value !== null) {
        const kind = literalKind(node, value, sourceFile);
        if (kind) add(node, kind, value);
      }
      if (ts.isTemplateExpression(node)) {
        for (const span of node.templateSpans) visit(span.expression);
        return;
      }
    }

    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return candidates;
}

function compareCandidates(left, right) {
  return (
    left.file.localeCompare(right.file) ||
    left.line - right.line ||
    left.column - right.column ||
    left.kind.localeCompare(right.kind) ||
    left.literal.localeCompare(right.literal)
  );
}

function collectFiles(inputPath, root, explicit = false) {
  const absolute = path.resolve(root, inputPath);
  if (!fs.existsSync(absolute)) throw new Error(`scan path does not exist: ${inputPath}`);
  const stat = fs.statSync(absolute);
  if (stat.isDirectory()) {
    return fs.readdirSync(absolute, { withFileTypes: true }).flatMap((entry) =>
      collectFiles(path.join(inputPath, entry.name), root, explicit),
    );
  }
  const relative = normalizePath(path.relative(root, absolute));
  if (isExcludedFile(relative)) return [];
  if (!explicit && !/\.[cm]?[jt]sx?$/i.test(relative)) return [];
  return [{ absolute, relative }];
}

function scanPaths(inputPaths, root, explicit = true) {
  const files = inputPaths.flatMap((inputPath) => collectFiles(inputPath, root, explicit));
  return files
    .flatMap(({ absolute, relative }) => scanSource(relative, fs.readFileSync(absolute, "utf8")))
    .sort(compareCandidates);
}

function parseArguments(argv) {
  const positional = [];
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith("--")) {
      positional.push(value);
      continue;
    }
    const key = value.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) throw new Error(`missing value for --${key}`);
    options[key] = next;
    index += 1;
  }
  return { positional, options };
}

function loadManifest(file, expectedKey) {
  let value;
  try {
    value = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    throw new Error(`malformed manifest ${file}: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!value || value.version !== 1 || !Array.isArray(value[expectedKey])) {
    throw new Error(`malformed manifest ${file}: expected version 1 and ${expectedKey} array`);
  }
  return value[expectedKey];
}

function aggregate(candidates) {
  const grouped = new Map();
  for (const candidate of candidates) {
    const existing = grouped.get(candidate.signature);
    if (existing) existing.count += 1;
    else grouped.set(candidate.signature, { ...candidate, count: 1 });
  }
  return [...grouped.values()].sort((left, right) => left.signature.localeCompare(right.signature));
}

function inMigratedScope(file, scopes) {
  return scopes.some((scope) => {
    const normalized = normalizePath(scope);
    if (normalized.endsWith("/**")) {
      const prefix = normalized.slice(0, -3);
      return file === prefix || file.startsWith(`${prefix}/`);
    }
    return file === normalized;
  });
}

function validateDebt(entries) {
  const result = new Map();
  for (const entry of entries) {
    if (
      !entry ||
      typeof entry.signature !== "string" ||
      !Number.isInteger(entry.count) ||
      entry.count <= 0 ||
      result.has(entry.signature)
    ) {
      throw new Error("malformed or duplicate legacy debt entry");
    }
    result.set(entry.signature, entry.count);
  }
  return result;
}

function validateAllowlist(entries) {
  const result = new Map();
  for (const entry of entries) {
    if (
      !entry ||
      typeof entry.file !== "string" ||
      typeof entry.kind !== "string" ||
      typeof entry.literal !== "string" ||
      !Number.isInteger(entry.count) ||
      entry.count <= 0 ||
      !ALLOWLIST_CLASSES.has(entry.classification) ||
      typeof entry.reason !== "string" ||
      !entry.reason.trim()
    ) {
      throw new Error("malformed allowlist entry");
    }
    const signature = JSON.stringify([normalizePath(entry.file), entry.kind, entry.literal]);
    if (result.has(signature)) throw new Error("duplicate allowlist entry");
    result.set(signature, { ...entry, signature });
  }
  return result;
}

function checkPolicy({ root, debtPath, allowlistPath, migratedPath }) {
  const candidates = scanPaths(["src"], root, false);
  const grouped = aggregate(candidates);
  const current = new Map(grouped.map((entry) => [entry.signature, entry]));
  const debt = validateDebt(loadManifest(debtPath, "signatures"));
  const allowlist = validateAllowlist(loadManifest(allowlistPath, "entries"));
  const scopes = loadManifest(migratedPath, "scopes");
  if (scopes.some((scope) => typeof scope !== "string" || !scope.trim())) {
    throw new Error("malformed migrated scope entry");
  }
  if (new Set(scopes).size !== scopes.length) throw new Error("duplicate migrated scope");

  for (const entry of grouped) {
    if (entry.kind === "dynamic_translation_key") {
      throw new Error(`dynamic translation key: ${entry.file}:${entry.line} ${entry.literal}`);
    }
  }

  for (const [signature, allowed] of allowlist) {
    const entry = current.get(signature);
    if (!entry || entry.count !== allowed.count) {
      throw new Error(`stale allowlist entry: ${signature}`);
    }
  }

  for (const entry of grouped) {
    if (allowlist.has(entry.signature)) continue;
    if (inMigratedScope(entry.file, scopes)) {
      throw new Error(`visible literal in migrated scope: ${entry.signature}`);
    }
    const ceiling = debt.get(entry.signature);
    if (ceiling === undefined) throw new Error(`new visible literal debt: ${entry.signature}`);
    if (entry.count > ceiling) {
      throw new Error(`legacy debt increased: ${entry.signature} ${ceiling} -> ${entry.count}`);
    }
  }

  return {
    candidateCount: candidates.length,
    signatureCount: grouped.length,
    debtSignatureCount: debt.size,
    allowlistCount: allowlist.size,
    migratedScopes: [...scopes].sort(),
  };
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

function main() {
  const [command, ...rest] = process.argv.slice(2);
  const { positional, options } = parseArguments(rest);
  const root = path.resolve(options.root ?? process.cwd());
  const debtPath = path.resolve(options.debt ?? path.join(DEFAULT_MANIFEST_DIR, "visible-literal-debt.json"));
  const allowlistPath = path.resolve(options.allowlist ?? path.join(DEFAULT_MANIFEST_DIR, "visible-literal-allowlist.json"));
  const migratedPath = path.resolve(options.migrated ?? path.join(DEFAULT_MANIFEST_DIR, "migrated-scopes.json"));

  if (command === "scan") {
    if (positional.length === 0) throw new Error("scan requires at least one path");
    process.stdout.write(`${JSON.stringify(scanPaths(positional, root), null, 2)}\n`);
    return;
  }
  if (command === "snapshot") {
    const candidates = scanPaths(["src"], root, false);
    const signatures = aggregate(candidates)
      .filter((entry) => entry.kind !== "dynamic_translation_key")
      .map(({ signature, count }) => ({ signature, count }));
    const manifest = { version: 1, signatures };
    writeJson(debtPath, manifest);
    process.stdout.write(`${JSON.stringify({ candidateCount: candidates.length, signatureCount: signatures.length })}\n`);
    return;
  }
  if (command === "check") {
    process.stdout.write(`${JSON.stringify(checkPolicy({
      root,
      debtPath,
      allowlistPath,
      migratedPath,
    }))}\n`);
    return;
  }
  throw new Error("usage: visible-literal-scanner.mjs <scan|snapshot|check> [paths/options]");
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
