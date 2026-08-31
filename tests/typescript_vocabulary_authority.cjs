"use strict";

const fs = require("node:fs");
const ts = require("typescript");

function fail(message) {
  throw new Error(message);
}

function hasModifier(node, kind) {
  return (node.modifiers || []).some((modifier) => modifier.kind === kind);
}

function exportedStringUnion(sourceFile, name) {
  const declarations = sourceFile.statements.filter(
    (statement) =>
      ts.isTypeAliasDeclaration(statement) && statement.name.text === name,
  );
  if (declarations.length !== 1) {
    fail(
      `expected exactly one exported type alias named ${name}; found ${declarations.length}`,
    );
  }

  const declaration = declarations[0];
  if (!hasModifier(declaration, ts.SyntaxKind.ExportKeyword)) {
    fail(`expected exactly one exported type alias named ${name}; found 0`);
  }

  const members = ts.isUnionTypeNode(declaration.type)
    ? declaration.type.types
    : [declaration.type];
  if (
    members.length === 0
    || members.some(
      (member) =>
        !ts.isLiteralTypeNode(member) || !ts.isStringLiteral(member.literal),
    )
  ) {
    fail(`type alias ${name} must be a closed string-literal union`);
  }
  return members.map((member) => member.literal.text);
}

function constStringArray(sourceFile, name) {
  const declarations = [];
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.name.text === name) {
        declarations.push({ declaration, statement });
      }
    }
  }
  if (declarations.length !== 1) {
    fail(
      `expected exactly one const array declaration named ${name}; found ${declarations.length}`,
    );
  }

  const { declaration, statement } = declarations[0];
  if (!(statement.declarationList.flags & ts.NodeFlags.Const)) {
    fail(`expected exactly one const array declaration named ${name}; found 0`);
  }
  if (
    !declaration.initializer
    || !ts.isArrayLiteralExpression(declaration.initializer)
  ) {
    fail(`const ${name} must be a closed string-literal array`);
  }

  const members = declaration.initializer.elements;
  if (
    members.length === 0
    || members.some((member) => !ts.isStringLiteral(member))
  ) {
    fail(`const ${name} must be a closed string-literal array`);
  }
  return members.map((member) => member.text);
}

function main() {
  const [sourcePath, requestsJson] = process.argv.slice(2);
  if (!sourcePath || !requestsJson) {
    fail("usage: typescript_vocabulary_authority.cjs SOURCE_PATH REQUESTS_JSON");
  }

  const source = fs.readFileSync(sourcePath, "utf8");
  const sourceFile = ts.createSourceFile(
    sourcePath,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  if (sourceFile.parseDiagnostics.length) {
    const details = sourceFile.parseDiagnostics
      .map((diagnostic) =>
        ts.flattenDiagnosticMessageText(diagnostic.messageText, " "),
      )
      .join("; ");
    fail(`TypeScript parse failed: ${details}`);
  }

  const requests = JSON.parse(requestsJson);
  if (!requests || typeof requests !== "object" || Array.isArray(requests)) {
    fail("authority requests must be a JSON object");
  }

  const result = {};
  for (const [key, request] of Object.entries(requests)) {
    if (
      !request
      || typeof request !== "object"
      || typeof request.name !== "string"
      || !request.name
    ) {
      fail(`invalid authority request: ${key}`);
    }
    if (request.kind === "type") {
      result[key] = exportedStringUnion(sourceFile, request.name);
    } else if (request.kind === "array") {
      result[key] = constStringArray(sourceFile, request.name);
    } else {
      fail(`invalid authority kind for ${key}: ${request.kind}`);
    }
  }

  process.stdout.write(JSON.stringify(result));
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}
