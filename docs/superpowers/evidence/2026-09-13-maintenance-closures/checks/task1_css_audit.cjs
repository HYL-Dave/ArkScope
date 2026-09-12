const assert = require('node:assert/strict');
const { execFileSync, spawnSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const { readFileSync, writeFileSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');

const work = __dirname;
const root = path.resolve(work, '../../..');
const requireWeb = createRequire(path.join(root, 'apps/arkscope-web/package.json'));
const postcss = requireWeb('postcss');
const ts = requireWeb('typescript');
const base = '5526bc40dc8d62efa6dd819cf1ffc99d8acff7ce';
const cssPath = 'apps/arkscope-web/src/styles.css';
const phase = process.argv[2];
assert.ok(['before', 'after', 'final'].includes(phase));
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' });
const sha = (text) => createHash('sha256').update(text).digest('hex');
const read = (file) => readFileSync(path.join(root, file), 'utf8');
const head = git('rev-parse', 'HEAD').trim();
git('merge-base', '--is-ancestor', base, head);
assert.equal(git('branch', '--show-current').trim(), 'codex/sec-research-integration');

const before = postcss.parse(git('show', `${base}:${cssPath}`));
const currentText = read(cssPath);
const current = postcss.parse(currentText);
const retired = /\.page-head(?:-actions)?(?![\w-])/;
function inventory(tree) {
  const rules = [];
  tree.walkRules((rule) => {
    const context = [];
    for (let p = rule.parent; p && p.type !== 'root'; p = p.parent) {
      context.unshift(`@${p.name} ${p.params}`);
    }
    rules.push({ selector: rule.selector, context, line: rule.source.start.line,
      declarations: rule.nodes.filter((n) => n.type === 'decl')
        .map((n) => ({ property: n.prop, value: n.value, important: Boolean(n.important) })) });
  });
  return rules;
}
const baseRules = inventory(before);
const removed = baseRules.filter((rule) => retired.test(rule.selector));
assert.deepEqual(removed.map((r) => [r.selector, r.context]), [
  ['.page-head', []], ['.page-head h1', []], ['.page-head-actions', []],
  ['.page-head', ['@media (max-width: 760px)']],
  ['.page-head-actions', ['@media (max-width: 760px)']],
]);
const expected = before.clone();
expected.walkRules((rule) => { if (retired.test(rule.selector)) rule.remove(); });
const semantic = (tree) => inventory(tree).map(({ line, ...rule }) => rule);
if (phase === 'before') assert.equal(currentText, before.toString());
else {
  assert.equal(currentText, expected.toString(), 'Only exact obsolete rule bytes may change');
  assert.deepEqual(semantic(current), semantic(expected), 'Retained rule declarations/order/context');
}

const frontendFiles = git('ls-files', '-z', 'apps/arkscope-web').split('\0').filter(Boolean);
const changedFrontend = [];
const identity = {};
for (const file of frontendFiles) {
  const value = read(file);
  identity[file] = sha(value);
  if (value !== git('show', `${base}:${file}`)) changedFrontend.push(file);
}
assert.deepEqual(changedFrontend, phase === 'before' ? [] : [cssPath]);
const test = 'apps/arkscope-web/src/retiredPageHeader.test.tsx';
identity[test] = sha(read(test));
const sources = frontendFiles.filter((file) => /\.(?:[cm]?[jt]sx?|html)$/.test(file)
  && !/\.test[.-]/.test(file) && !file.includes('/scripts/'));
const classAttributes = [];
const stringsWithHeader = [];
for (const file of sources.filter((file) => /\.[jt]sx?$/.test(file))) {
  const source = ts.createSourceFile(file, read(file), ts.ScriptTarget.Latest, true);
  function visit(node) {
    const location = () => ({ file, line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1 });
    if ((ts.isJsxAttribute(node) || ts.isPropertyAssignment(node))
      && node.name.getText(source) === 'className') {
      classAttributes.push({ ...location(), text: node.getText(source),
        dynamic: ts.isJsxAttribute(node) && node.initializer && ts.isJsxExpression(node.initializer) });
    }
    if ((ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node)
      || ts.isTemplateTail(node)) && /page|head/.test(node.text)) {
      stringsWithHeader.push({ ...location(), text: node.text });
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
}
const searches = [
  ['exact-product-tokens', '(^|[^[:alnum:]_-])page-head(-actions)?([^[:alnum:]_-]|$)'],
  ['retained-and-fragments', 'page-head|head-actions|classList|setAttribute\\('],
  ['dynamic-classes', 'className=\\{|className:|className =|cls='],
].map(([name, pattern]) => {
  const args = ['-n', pattern, ...sources];
  const result = spawnSync('rg', args, { cwd: root, encoding: 'utf8' });
  assert.ok([0, 1].includes(result.status), result.stderr);
  return { name, command: ['rg', ...args], exitCode: result.status, output: result.stdout };
});
assert.equal(searches[0].exitCode, 1, 'No exact retired tokens in actual frontend consumers');
const rules = inventory(current);
const retained = semantic(expected);
const record = {
  phase, base, head, command: process.argv, node: process.version,
  postcss: requireWeb('postcss/package.json').version, typescript: ts.version,
  cssSha256: sha(currentText), expectedCleanedCssSha256: sha(expected.toString()),
  obsoleteRules: removed, remainingObsoleteRules: rules.filter((r) => retired.test(r.selector)),
  ruleCountBefore: baseRules.length, ruleCountCurrent: rules.length,
  retainedRuleCount: retained.length,
  retainedDeclarationCount: retained.reduce((n, r) => n + r.declarations.length, 0),
  retainedSha256: sha(JSON.stringify(retained)),
  retainedDeclarationEquivalence: phase !== 'before', exactRetainedBytes: phase !== 'before',
  sourceCount: sources.length, classAttributeCount: classAttributes.length,
  dynamicClassAttributeCount: classAttributes.filter((r) => r.dynamic).length,
  classAttributes, stringsWithHeader, searches, changedFrontend, identity,
  runners: Object.fromEntries(['run_checks.py', 'offline_node.cjs', 'task1_css_audit.cjs',
    'task1_fixture_server.mjs', 'browser_check.py', 'task1-fixture/index.html',
    'task1-fixture/fixture.tsx'].map((file) => [file, sha(readFileSync(path.join(work, file)))])),
};
writeFileSync(path.join(work, `task1-css-${phase}.json`), JSON.stringify(record, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ phase, obsolete: record.remainingObsoleteRules.length,
  rules: rules.length, retainedRules: retained.length, retainedDeclarations: record.retainedDeclarationCount,
  retainedDeclarationEquivalence: record.retainedDeclarationEquivalence,
  exactRetainedBytes: record.exactRetainedBytes, sources: sources.length,
  classAttributes: classAttributes.length, dynamicClasses: record.dynamicClassAttributeCount,
  cssSha256: record.cssSha256, changedFrontend }, null, 2));
