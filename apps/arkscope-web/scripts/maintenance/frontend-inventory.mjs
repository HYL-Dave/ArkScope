#!/usr/bin/env node

import { isBuiltin } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";

const SOURCE = /\.[cm]?[jt]sx?$/i;
const CONFIG = /(?:^|\/)(?:[^/]*\.config\.[cm]?[jt]s|(?:ts|js)config[^/]*\.json)$/i;
const RESOURCE = /(?:^|\/)(?:resources|locales)\/(en|zh-Hant)\/([^/]+)\.(?:json|[cm]?[jt]s)$/;
const TOOLING = /(?:^|\/)(?:scripts|test|tests|__tests__)(?:\/|$)|\.(?:test|spec)\.[cm]?[jt]sx?$|\.d\.[cm]?ts$/;
const SECTIONS = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"];
const METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE"]);

function walk(node, visit) {
  visit(node);
  ts.forEachChild(node, (child) => walk(child, visit));
}

function unwrap(node) {
  while (node && (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
    || ts.isSatisfiesExpression(node) || ts.isTypeAssertionExpression(node) || ts.isNonNullExpression(node))) {
    node = node.expression;
  }
  return node;
}

function literal(node) {
  node = unwrap(node);
  return node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? node.text : null;
}

function nameOf(node) {
  return node && (ts.isIdentifier(node) || ts.isStringLiteral(node) || ts.isNumericLiteral(node)) ? node.text : null;
}

function memberName(node) {
  if (ts.isPropertyAccessExpression(node)) return node.name.text;
  if (ts.isElementAccessExpression(node)) return literal(node.argumentExpression);
  return nameOf(node);
}

// A later spread/computed property can override an earlier explicit property.
function property(node, name) {
  node = unwrap(node);
  let result = { present: false, unknown: false, value: undefined };
  if (!node) return result;
  if (!ts.isObjectLiteralExpression(node)) return { ...result, unknown: true };
  for (const entry of node.properties) {
    if (ts.isSpreadAssignment(entry) || (entry.name && ts.isComputedPropertyName(entry.name))) {
      result = { present: false, unknown: true, value: undefined };
    } else if (nameOf(entry.name) === name) {
      result = { present: true, unknown: !ts.isPropertyAssignment(entry), value: entry.initializer };
    }
  }
  return result;
}

function location(sf, node = 0) {
  const offset = typeof node === "number" ? node : node.getStart(sf);
  const { line, character } = sf.getLineAndCharacterOfPosition(offset);
  return { file: sf.fileName, line: line + 1, column: character + 1 };
}

function unresolved(report, axis, sf, node, reason, extra = {}) {
  report.unresolved.push({
    axis, reason, ...location(sf, node), ...extra,
    ...(typeof node === "number" ? {} : { expression: node.getText(sf).slice(0, 200) }),
  });
}

function packageName(value) {
  if (!value || /^(?:[./#]|[a-zA-Z][\w+.-]*:)/.test(value) || isBuiltin(value)) return null;
  return value.startsWith("@") ? value.split("/").slice(0, 2).join("/") : value.split("/")[0];
}

function dependencyRef(report, sf, node, specifier, kind, mode = "runtime") {
  const name = packageName(specifier);
  if (name) report.dependencies.references.push({
    ...location(sf, node), package: name, specifier, kind, mode,
  });
}

function manifest(report, sf) {
  const root = sf.statements[0]?.expression;
  for (const section of SECTIONS) {
    const object = property(root, section).value;
    if (!object || !ts.isObjectLiteralExpression(object)) continue;
    for (const entry of object.properties) {
      const name = nameOf(entry.name);
      if (name) report.dependencies.candidates.push({
        ...location(sf, entry.name), package: name, section, status: "unresolved", evidence: [],
      });
    }
  }
}

function manifestScripts(report, sf) {
  const scripts = property(sf.statements[0]?.expression, "scripts").value;
  if (!scripts || !ts.isObjectLiteralExpression(scripts)) return;
  const packages = new Set(report.dependencies.candidates.map((entry) => entry.package));
  for (const script of scripts.properties) {
    const command = literal(script.initializer);
    if (command === null) continue;
    const tokens = new Set(command.match(/[\w@./-]+/g) ?? []);
    for (const name of packages) {
      const bins = name === "typescript" ? ["tsc", "tsserver"] : [name, name.split("/").at(-1)];
      if (bins.some((bin) => tokens.has(bin) || tokens.has(`node_modules/.bin/${bin}`))) {
        dependencyRef(report, sf, script, name, "script-token", "tooling");
      }
    }
    unresolved(report, "dependencies", sf, script, "shell-script-not-evaluated");
  }
}

function scanDependencies(report, sf, kind) {
  const tooling = kind === "config" || TOOLING.test(sf.fileName);
  const mode = tooling ? "tooling" : "runtime";
  const declared = new Set(report.dependencies.candidates.map((entry) => entry.package));
  for (const directive of sf.typeReferenceDirectives ?? []) {
    const name = directive.fileName;
    const types = `@types/${name.replace("/", "__")}`;
    dependencyRef(report, sf, directive.pos, declared.has(types) ? types : name, "type-directive", "tooling");
  }
  walk(sf, (node) => {
    let specifier;
    let referenceKind;
    let typeOnly = false;
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      specifier = node.moduleSpecifier;
      referenceKind = ts.isImportDeclaration(node) ? "import" : "export-from";
      const bindings = node.importClause?.namedBindings ?? node.exportClause;
      typeOnly = Boolean(node.isTypeOnly || node.importClause?.isTypeOnly
        || (!node.importClause?.name && bindings?.elements?.length && bindings.elements.every((entry) => entry.isTypeOnly)));
    } else if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
      specifier = node.moduleReference.expression;
      referenceKind = "import-equals";
      typeOnly = node.isTypeOnly;
    } else if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) {
      specifier = node.argument.literal;
      referenceKind = "import-type";
      typeOnly = true;
    } else if (ts.isCallExpression(node)
      && (node.expression.kind === ts.SyntaxKind.ImportKeyword || nameOf(node.expression) === "require")) {
      specifier = node.arguments[0];
      referenceKind = node.expression.kind === ts.SyntaxKind.ImportKeyword ? "dynamic-import" : "require";
      if (literal(specifier) === null) {
        unresolved(report, "dependencies", sf, node, "dynamic-module-specifier");
      }
    }
    if (specifier && literal(specifier) !== null) {
      dependencyRef(report, sf, specifier, literal(specifier), referenceKind, typeOnly ? "tooling" : mode);
    }
    if (kind === "config" && literal(node) !== null) {
      const name = packageName(literal(node));
      const types = `@types/${literal(node).replace("/", "__")}`;
      if (declared.has(name)) dependencyRef(report, sf, node, name, "config-literal", "tooling");
      if (declared.has(types)) dependencyRef(report, sf, node, types, "config-type", "tooling");
    }
  });
}

function resourceKeys(report, sf, locale, namespace) {
  const constants = new Map();
  const exported = [];
  for (const statement of sf.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name)) {
        constants.set(declaration.name.text, declaration.initializer);
        if (statement.modifiers?.some((mod) => mod.kind === ts.SyntaxKind.ExportKeyword)) exported.push(declaration.initializer);
      }
    }
  }
  let root = sf.fileName.endsWith(".json") ? sf.statements[0]?.expression
    : sf.statements.find(ts.isExportAssignment)?.expression ?? (exported.length === 1 ? exported[0] : undefined);
  const seen = new Set();
  root = unwrap(root);
  while (root && ts.isIdentifier(root) && constants.has(root.text) && !seen.has(root.text)) {
    seen.add(root.text);
    root = unwrap(constants.get(root.text));
  }
  if (!root || !ts.isObjectLiteralExpression(root)) {
    unresolved(report, "i18n", sf, root ?? 0, "unsupported-resource-root", { namespaces: [namespace] });
    return;
  }
  function leaves(node, path, evidence) {
    node = unwrap(node);
    if (ts.isObjectLiteralExpression(node)) {
      for (const entry of node.properties) {
        const name = nameOf(entry.name);
        if (!ts.isPropertyAssignment(entry) || name === null) {
          unresolved(report, "i18n", sf, entry, "dynamic-resource-member", { namespaces: [namespace] });
        } else leaves(entry.initializer, [...path, name], entry.name);
      }
    } else if (ts.isArrayLiteralExpression(node)) {
      node.elements.forEach((entry, index) => leaves(entry, [...path, String(index)], entry));
    } else if (literal(node) !== null || ts.isNumericLiteral(node)
      || [ts.SyntaxKind.TrueKeyword, ts.SyntaxKind.FalseKeyword, ts.SyntaxKind.NullKeyword].includes(node.kind)) {
      report.i18n.keys.push({ ...location(sf, evidence), locale, namespace, key: path.join("."), status: "no-static-reference" });
    } else {
      unresolved(report, "i18n", sf, node, "dynamic-resource-value", { namespaces: [namespace] });
    }
  }
  leaves(root, [], root);
}

function namespaceList(node) {
  node = unwrap(node);
  if (literal(node) !== null) return [literal(node)];
  if (node && ts.isArrayLiteralExpression(node) && node.elements.length && node.elements.every((entry) => literal(entry) !== null)) {
    return node.elements.map(literal);
  }
  if (node && ts.isLiteralTypeNode(node)) return namespaceList(node.literal);
  return null;
}

function translationBindings(report, sf) {
  const factories = new Map([["useTranslation", "useTranslation"], ["getFixedT", "getFixedT"]]);
  const typeNames = new Set(["TFunction"]);
  const imports = [];
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !["i18next", "react-i18next"].includes(literal(statement.moduleSpecifier))) continue;
    for (const entry of statement.importClause?.namedBindings?.elements ?? []) {
      const imported = nameOf(entry.propertyName ?? entry.name);
      if (factories.has(imported)) factories.set(entry.name.text, imported);
      if (imported === "TFunction") typeNames.add(entry.name.text);
      if (imported === "t") imports.push(entry);
    }
  }
  const scopes = new Map();
  function scope(node) {
    for (let parent = node.parent; parent; parent = parent.parent) {
      if (ts.isBlock(parent) || ts.isSourceFile(parent) || ts.isFunctionLike(parent)
        || ts.isForStatement(parent) || ts.isForOfStatement(parent) || ts.isForInStatement(parent)) return parent;
    }
    return sf;
  }
  function bind(node, name, value) {
    const owner = scope(node);
    if (!scopes.has(owner)) scopes.set(owner, new Map());
    scopes.get(owner).set(name, value);
  }
  for (const entry of imports) bind(entry, entry.name.text, { namespaces: null, prefix: "", object: false });
  const factoryValues = new Map();
  function factory(call) {
    if (!call || !ts.isCallExpression(call)) return null;
    if (factoryValues.has(call)) return factoryValues.get(call);
    const name = factories.get(memberName(call.expression));
    if (!name) return null;
    const ns = namespaceList(call.arguments[name === "getFixedT" ? 1 : 0]);
    const prefix = name === "getFixedT" ? { value: call.arguments[2] } : property(call.arguments[1], "keyPrefix");
    const dynamicPrefix = Boolean(prefix.unknown || (prefix.value && literal(prefix.value) === null));
    if (!ns || ns.length !== 1) unresolved(report, "i18n", sf, call, "dynamic-translation-namespace", { namespaces: ns });
    if (dynamicPrefix) unresolved(report, "i18n", sf, call, "dynamic-translation-prefix", { namespaces: ns });
    const value = { namespaces: ns, prefix: literal(prefix.value) ?? "", dynamicPrefix, object: name === "useTranslation" };
    factoryValues.set(call, value);
    return value;
  }
  walk(sf, (node) => {
    if (ts.isCallExpression(node)) factory(node);
    if (ts.isFunctionDeclaration(node) && node.name) bind(node, node.name.text, null);
    if (!ts.isVariableDeclaration(node) && !ts.isParameter(node)) return;
    let value = factory(unwrap(node.initializer));
    if (node.type && ts.isTypeReferenceNode(node.type) && typeNames.has(nameOf(node.type.typeName))) {
      value = { namespaces: namespaceList(node.type.typeArguments?.[0]), prefix: "", dynamicPrefix: false, object: false };
    }
    if (ts.isIdentifier(node.name)) bind(node, node.name.text, value);
    else if (ts.isObjectBindingPattern(node.name) || ts.isArrayBindingPattern(node.name)) {
      node.name.elements.forEach((entry, index) => {
        if (!ts.isBindingElement(entry) || !ts.isIdentifier(entry.name)) return;
        const translator = ts.isArrayBindingPattern(node.name) ? index === 0 : nameOf(entry.propertyName ?? entry.name) === "t";
        bind(node, entry.name.text, translator && value ? { ...value, object: false } : null);
      });
    }
  });
  function resolve(expression, call) {
    let name = nameOf(expression);
    const object = ts.isPropertyAccessExpression(expression) && expression.name.text === "t";
    if (object) name = nameOf(expression.expression);
    for (let node = call; node; node = node.parent) {
      if (!scopes.get(node)?.has(name)) continue;
      const value = scopes.get(node).get(name);
      return value && value.object === object ? value : name === "t" ? { namespaces: null, prefix: "" } : null;
    }
    if (name === "t" || object) return { namespaces: null, prefix: "" };
    return factory(expression);
  }
  walk(sf, (node) => {
    if (!ts.isBinaryExpression(node) || node.operatorToken.kind !== ts.SyntaxKind.EqualsToken) return;
    const value = resolve(node.left, node);
    if (!value) return;
    value.namespaces = null;
    value.reassigned = true;
    unresolved(report, "i18n", sf, node, "reassigned-translation-binding", { namespaces: null });
  });
  return resolve;
}

function selectorKey(node) {
  node = unwrap(node);
  if (!node || (!ts.isArrowFunction(node) && !ts.isFunctionExpression(node))) return null;
  const parameter = node.parameters[0];
  if (!parameter || !ts.isIdentifier(parameter.name) || node.parameters.length !== 1) return null;
  let body = unwrap(node.body);
  if (ts.isBlock(body)) body = body.statements.length === 1 && ts.isReturnStatement(body.statements[0]) ? unwrap(body.statements[0].expression) : null;
  const segments = [];
  while (body && (ts.isPropertyAccessExpression(body) || ts.isElementAccessExpression(body))) {
    const name = memberName(body);
    if (name === null) return null;
    segments.unshift(name);
    body = unwrap(body.expression);
  }
  return body && ts.isIdentifier(body) && body.text === parameter.name.text && segments.length ? segments.join(".") : null;
}

function scanTranslations(report, sf, resolve) {
  walk(sf, (node) => {
    if (ts.isPropertyAccessExpression(node) && node.name.text === "t"
      && !(ts.isCallExpression(node.parent) && node.parent.expression === node)) {
      const value = resolve(node, node);
      if (value) unresolved(report, "i18n", sf, node, "escaped-translation-binding", { namespaces: value.namespaces });
    }
    if (ts.isIdentifier(node)) {
      const parent = node.parent;
      const declaration = (ts.isVariableDeclaration(parent) || ts.isParameter(parent) || ts.isFunctionDeclaration(parent)
        || ts.isPropertyAssignment(parent) || ts.isPropertySignature(parent) || ts.isPropertyAccessExpression(parent)) && parent.name === node;
      if (!declaration && !ts.isBindingElement(parent) && !ts.isImportSpecifier(parent)
        && !(ts.isCallExpression(parent) && parent.expression === node)) {
        const value = resolve(node, node);
        if (value) unresolved(report, "i18n", sf, node, "escaped-translation-binding", { namespaces: value.namespaces });
      }
    }
    if ((ts.isElementAccessExpression(node) || ts.isPropertyAccessExpression(node))
      && nameOf(node.expression) === "resources") {
      unresolved(report, "i18n", sf, node, "resource-access", { namespaces: null });
    }
    if (!ts.isCallExpression(node)) return;
    const binding = resolve(unwrap(node.expression), node);
    if (!binding) return;
    if (binding.reassigned) return;
    let namespaces = binding.namespaces;
    const options = property(node.arguments[1], "ns");
    if (options.present || options.unknown) namespaces = options.unknown ? null : namespaceList(options.value);
    const prefixOption = property(node.arguments[1], "keyPrefix");
    const prefix = prefixOption.present ? literal(prefixOption.value) : binding.prefix;
    const dynamicPrefix = prefixOption.unknown || (prefixOption.present ? prefix === null : binding.dynamicPrefix);
    if (["keySeparator", "nsSeparator", "context", "count", "returnObjects"].some((name) => property(node.arguments[1], name).present)) {
      unresolved(report, "i18n", sf, node, "unsupported-translation-options", { namespaces });
      return;
    }
    let key = literal(node.arguments[0]) ?? selectorKey(node.arguments[0]);
    const style = literal(node.arguments[0]) !== null ? "string" : "selector";
    if (style === "string" && key.includes(":")) {
      const split = key.indexOf(":");
      namespaces = [key.slice(0, split)];
      key = key.slice(split + 1);
    }
    if (key === null) {
      unresolved(report, "i18n", sf, node, "dynamic-translation-key", { namespaces });
    } else if (!namespaces || namespaces.length !== 1) {
      unresolved(report, "i18n", sf, node, "dynamic-translation-namespace", { namespaces, key });
    } else if (dynamicPrefix) {
      unresolved(report, "i18n", sf, node, "dynamic-translation-prefix", { namespaces, key });
    } else {
      report.i18n.references.push({
        ...location(sf, node), namespace: namespaces[0], key: [prefix, key].filter(Boolean).join("."), kind: style,
      });
    }
  });
}

function httpMethod(value) {
  const method = literal(value)?.toUpperCase();
  return METHODS.has(method) ? method : null;
}

function optionsMethod(options, defaultMethod = "GET") {
  const method = property(options, "method");
  return method.unknown ? null : method.present ? httpMethod(method.value) : defaultMethod;
}

function scanHttp(report, sf, node) {
  if (!ts.isCallExpression(node)) return;
  const callee = unwrap(node.expression);
  const name = memberName(callee);
  let url = node.arguments[0];
  let method;
  if (name === "getJSON" && ts.isIdentifier(callee)) method = "GET";
  else if (name === "sendJSON" && ts.isIdentifier(callee)) method = httpMethod(node.arguments[1]);
  else if (name === "fetchWithTimeout" && ts.isIdentifier(callee)) method = optionsMethod(node.arguments[2]);
  else if (name === "fetch" && (ts.isIdentifier(callee) || ["window", "globalThis"].includes(nameOf(callee.expression)))) {
    method = optionsMethod(node.arguments[1]);
  } else {
    const receiver = callee.expression?.getText(sf) ?? name;
    if (!/^(?:axios|api|client|http|[A-Za-z_$][\w$]*Client)$/.test(receiver ?? "")) return;
    if (METHODS.has(name?.toUpperCase())) method = name.toUpperCase();
    else if (name === "request" || name === "axios") {
      const first = unwrap(node.arguments[0]);
      const urlArgument = literal(first) !== null || (first && ts.isTemplateExpression(first)) || node.arguments.length > 1;
      const options = urlArgument ? node.arguments[1] : first;
      method = optionsMethod(options, receiver === "axios" ? "GET" : null);
      url = urlArgument ? first : property(options, "url").value;
    } else return;
  }
  url = unwrap(url);
  let value = literal(url);
  let kind = value === null ? "dynamic" : "literal";
  if (url && ts.isTemplateExpression(url)) {
    kind = "template";
    value = url.head.text + url.templateSpans.map((span) => `\${${span.expression.getText(sf)}}${span.literal.text}`).join("");
  }
  report.http.references.push({ ...location(sf, node), client: callee.getText(sf), method, url: value, kind });
  if (kind !== "literal") unresolved(report, "http", sf, node, `${kind}-http-url`);
  if (method === null) unresolved(report, "http", sf, node, "dynamic-http-method");
}

function scanClasses(report, sf, node) {
  let value;
  if (ts.isJsxAttribute(node) && nameOf(node.name) === "className") {
    value = node.initializer && ts.isJsxExpression(node.initializer) ? node.initializer.expression : node.initializer;
  } else if ((ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) && nameOf(node.name) === "className") value = node.initializer;
  else if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && memberName(node.left) === "className") value = node.right;
  else if (ts.isJsxSpreadAttribute(node)) {
    unresolved(report, "css", sf, node, "dynamic-class-name");
    return;
  } else return;
  const classes = literal(value);
  if (classes === null) unresolved(report, "css", sf, node, "dynamic-class-name");
  else for (const className of new Set(classes.split(/\s+/).filter(Boolean))) {
    report.css.references.push({ ...location(sf, node), className });
  }
}

// Only rule boundaries and simple class tokens are inventoried, not CSS semantics.
function scanCss(report, file, source) {
  const lines = [0];
  for (let i = 0; i < source.length; i++) if (source[i] === "\n") lines.push(i + 1);
  const loc = (offset) => {
    let low = 0;
    let high = lines.length;
    while (low + 1 < high) {
      const mid = (low + high) >> 1;
      if (lines[mid] <= offset) low = mid;
      else high = mid;
    }
    return { file, line: low + 1, column: offset - lines[low] + 1 };
  };
  const error = (offset, message) => report.coverage.parseErrors.push({ ...loc(offset), message });
  // UTF-16 offsets must agree with TypeScript and JavaScript string indexing.
  const clean = source.split("");
  const masked = source.split("");
  for (let i = 0; i < source.length; i++) {
    const comment = source.startsWith("/*", i);
    const quote = source[i] === '"' || source[i] === "'" ? source[i] : null;
    if (!comment && !quote) continue;
    const start = i;
    let end;
    if (comment) {
      const close = source.indexOf("*/", i + 2);
      if (close < 0) error(start, "Unterminated CSS comment");
      end = close < 0 ? source.length : close + 2;
    } else {
      i++;
      while (i < source.length && source[i] !== quote) {
        if (source[i] === "\\") i++;
        i++;
      }
      if (i === source.length) error(start, "Unterminated CSS string");
      end = Math.min(i + 1, source.length);
    }
    for (let j = start; j < end; j++) {
      if (source[j] !== "\n") masked[j] = " ";
      if (comment) clean[j] = masked[j];
    }
    i = end - 1;
  }
  const text = clean.join("");
  const mask = masked.join("");
  const stack = [];
  let start = 0;
  let parentheses = 0;
  function selector(from, to) {
    const raw = text.slice(from, to);
    const offset = from + raw.length - raw.trimStart().length;
    const value = raw.trim();
    if (!value) return;
    const tokens = mask.slice(from, to);
    const classes = [...new Set([...tokens.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map((match) => match[1]))];
    const unsupported = !classes.length || /[\\&[\]()]/.test(value) || /[^\x00-\x7f]/.test(value);
    report.css.selectors.push({ ...loc(offset), selector: value, classes, status: unsupported ? "unresolved" : "no-static-reference" });
    if (unsupported) report.unresolved.push({ axis: "css", reason: "unsupported-css-selector", ...loc(offset), expression: value.slice(0, 200) });
  }
  for (let i = 0; i < mask.length; i++) {
    const char = mask[i];
    if (char === "(" || char === "[") parentheses++;
    if (char === ")" || char === "]") parentheses--;
    if (parentheses) continue;
    if (char === "{") {
      const header = mask.slice(start, i).trim();
      if (header && !header.startsWith("@") && !stack.some((entry) => entry.keyframes)) {
        let segment = start;
        let depth = 0;
        for (let j = start; j < i; j++) {
          if (mask[j] === "(" || mask[j] === "[") depth++;
          if (mask[j] === ")" || mask[j] === "]") depth--;
          if (mask[j] === "," && !depth) { selector(segment, j); segment = j + 1; }
        }
        selector(segment, i);
      }
      stack.push({ offset: i, keyframes: /^@(?:-\w+-)?keyframes\b/.test(header) });
      start = i + 1;
    } else if (char === "}") {
      if (!stack.length) error(i, "Unexpected CSS closing brace");
      else stack.pop();
      start = i + 1;
    } else if (char === ";") start = i + 1;
  }
  if (stack.length) error(stack[0].offset, "Unclosed CSS block");
  if (parentheses) error(source.length, "Unbalanced CSS parentheses or brackets");
}

function finish(report) {
  const candidates = report.dependencies.candidates;
  const directory = (file) => file.slice(0, -"package.json".length);
  const workspaceRoots = report.coverage.analyzedFiles.filter((file) => file.endsWith("package.json")).map(directory);
  const declaredWorkspace = (file) => workspaceRoots.filter((root) => file.startsWith(root)).sort((a, b) => b.length - a.length)[0];
  const inferredWorkspace = (file) => file.match(/^((?:apps|packages|extensions)\/[^/]+)\//)?.[1]
    ?? file.match(/^(.*?)\/(?:src|resources|locales)\//)?.[1] ?? "<unscoped>";
  const workspace = (file) => declaredWorkspace(file) ?? `inferred:${inferredWorkspace(file)}`;
  const missingRoots = new Set(report.coverage.analyzedFiles.filter((file) => declaredWorkspace(file) === undefined).map(inferredWorkspace));
  if (missingRoots.size > 1) {
    for (const [axis, entries] of [["i18n", report.i18n.keys], ["css", report.css.selectors]]) {
      const seen = new Set();
      for (const entry of entries) {
        if (declaredWorkspace(entry.file) !== undefined || seen.has(workspace(entry.file))) continue;
        seen.add(workspace(entry.file));
        report.unresolved.push({ axis, reason: "workspace-manifest-missing", file: entry.file,
          line: entry.line, column: entry.column, namespaces: null });
      }
    }
  }
  for (const reference of report.dependencies.references) {
    const owners = candidates.filter((entry) => entry.package === reference.package && reference.file.startsWith(directory(entry.file)));
    const nearest = Math.max(-1, ...owners.map((entry) => directory(entry.file).length));
    for (const entry of owners) if (directory(entry.file).length === nearest) entry.evidence.push(reference);
  }
  for (const entry of candidates) {
    entry.status = entry.evidence.some((ref) => ref.mode === "runtime") ? "runtime" : entry.evidence.length ? "tooling" : "unresolved";
    if (entry.status === "unresolved") report.unresolved.push({
      axis: "dependencies", reason: "no-static-dependency-reference", file: entry.file, line: entry.line, column: entry.column, package: entry.package,
    });
  }
  const parseFailure = report.coverage.parseErrors.length > 0;
  const keyRefs = new Set(report.i18n.references.map((entry) => JSON.stringify([workspace(entry.file), entry.namespace, entry.key])));
  const i18nUnknown = report.unresolved.filter((entry) => entry.axis === "i18n");
  for (const entry of report.i18n.keys) {
    entry.workspace = workspace(entry.file);
    entry.status = keyRefs.has(JSON.stringify([entry.workspace, entry.namespace, entry.key])) ? "referenced"
      : parseFailure || i18nUnknown.some((issue) => !issue.namespaces || issue.namespaces.includes(entry.namespace)) ? "unresolved" : "no-static-reference";
  }
  const classes = new Set(report.css.references.map((entry) => JSON.stringify([workspace(entry.file), entry.className])));
  const dynamicClasses = report.unresolved.some((entry) => entry.axis === "css" && entry.reason === "dynamic-class-name");
  for (const entry of report.css.selectors) {
    entry.workspace = workspace(entry.file);
    if (entry.status === "unresolved") continue;
    entry.status = entry.classes.every((name) => classes.has(JSON.stringify([entry.workspace, name]))) ? "referenced"
      : parseFailure || dynamicClasses ? "unresolved" : "no-static-reference";
  }
  report.unresolved = [...new Map(report.unresolved.map((entry) => [JSON.stringify(entry), entry])).values()];
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  const byLocation = (a, b) => compare(a.file, b.file) || a.line - b.line || a.column - b.column;
  for (const entries of [candidates, report.dependencies.references, report.i18n.keys, report.i18n.references,
    report.http.references, report.css.selectors, report.css.references, report.unresolved, report.coverage.parseErrors]) entries.sort(byLocation);
  report.coverage.unresolvedCount = report.unresolved.length;
  report.coverage.counts = {
    dependencyCandidates: candidates.length, dependencyReferences: report.dependencies.references.length,
    i18nKeys: report.i18n.keys.length, i18nReferences: report.i18n.references.length,
    httpReferences: report.http.references.length, cssSelectors: report.css.selectors.length, cssReferences: report.css.references.length,
    parseErrors: report.coverage.parseErrors.length,
  };
  return report;
}

/** Scan supplied source strings only. No traversal, module resolution, or evaluation. */
export function scanFrontend(files) {
  if (!files || typeof files !== "object" || Array.isArray(files)) throw new TypeError("Expected a path-to-source mapping");
  const entries = Object.entries(files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
  for (const [file, source] of entries) {
    if (!file || /^(?:\/|[A-Za-z]:)/.test(file) || file.includes("\\") || file.includes("\0") || file.split("/").some((part) => !part || part === "." || part === "..")) {
      throw new TypeError("Expected normalized repo-relative paths");
    }
    if (typeof source !== "string") throw new TypeError("Expected source strings in the file mapping");
  }
  const report = {
    schemaVersion: 1, deadCodeProof: false,
    limitations: [
      "Only supplied files are analyzed; missing inputs and generated code are outside coverage.",
      "References are syntactic evidence, not proof of runtime reachability or safe deletion.",
      "No application evaluation, filesystem traversal, module resolution, or cross-file dataflow.",
      "Scripts use package-name and known binary tokens; arbitrary shell commands and implicit tooling remain unresolved.",
      "Translations support literal resource objects and locally bound selectors/string keys; unknown namespaces, aliases, and dynamic access are not inferred.",
      "HTTP clients are recognized by fetch, getJSON, sendJSON, fetchWithTimeout and common client naming conventions; templates are not concrete routes.",
      "CSS is a rule-boundary/class-token inventory, not a complete CSS parser or selector reachability analysis.",
    ],
    coverage: {
      filesSupplied: entries.length, filesAnalyzed: 0, analyzedFiles: [], skippedFiles: [],
      byKind: { source: 0, manifest: 0, config: 0, resource: 0, css: 0 }, parseErrors: [],
    },
    dependencies: { candidates: [], references: [] }, i18n: { keys: [], references: [] },
    http: { references: [] }, css: { selectors: [], references: [] }, unresolved: [],
  };
  const parsed = [];
  for (const [file, source] of entries) {
    const resource = file.match(RESOURCE);
    const kind = /(?:^|\/)package\.json$/.test(file) ? "manifest" : resource ? "resource"
      : CONFIG.test(file) ? "config" : SOURCE.test(file) ? "source" : file.endsWith(".css") ? "css" : null;
    if (!kind) {
      report.coverage.skippedFiles.push({ file, reason: "unsupported-file-kind" });
      continue;
    }
    report.coverage.filesAnalyzed++;
    report.coverage.analyzedFiles.push(file);
    report.coverage.byKind[kind]++;
    if (kind === "css") { scanCss(report, file, source); continue; }
    const sf = file.endsWith(".json") ? ts.parseJsonText(file, source)
      : ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
    for (const diagnostic of sf.parseDiagnostics) {
      report.coverage.parseErrors.push({ ...location(sf, diagnostic.start ?? 0), message: ts.flattenDiagnosticMessageText(diagnostic.messageText, " ") });
    }
    if (file.endsWith(".json") && kind !== "config") {
      try { JSON.parse(source); }
      catch {
        if (!sf.parseDiagnostics.length) report.coverage.parseErrors.push({ ...location(sf), message: "Invalid JSON" });
      }
    }
    if (kind === "manifest") manifest(report, sf);
    parsed.push({ sf, kind, resource });
  }
  for (const { sf, kind, resource } of parsed) {
    if (kind === "manifest") { manifestScripts(report, sf); continue; }
    scanDependencies(report, sf, kind);
    if (kind === "resource") resourceKeys(report, sf, resource[1], resource[2]);
    else if (!sf.fileName.endsWith(".json")) {
      scanTranslations(report, sf, translationBindings(report, sf));
      walk(sf, (node) => { scanHttp(report, sf, node); scanClasses(report, sf, node); });
    }
  }
  return finish(report);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    let input = "";
    process.stdin.setEncoding("utf8");
    for await (const chunk of process.stdin) input += chunk;
    process.stdout.write(`${JSON.stringify(scanFrontend(JSON.parse(input)))}\n`);
  } catch (error) {
    process.stderr.write(`frontend-inventory: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
