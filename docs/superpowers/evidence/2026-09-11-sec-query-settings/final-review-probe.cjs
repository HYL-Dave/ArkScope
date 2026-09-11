// Bounded probe: unchanged Records renderer, conflict-bearing page to next page.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../../..');
const local = createRequire(path.join(root, 'apps/arkscope-web/package.json'));
const ts = local('typescript');
const { JSDOM } = local('jsdom');
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://fixture.invalid' });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.IS_REACT_ACT_ENVIRONMENT = true;
const React = local('react');
const { createRoot } = local('react-dom/client');
const filename = path.join(root, 'apps/arkscope-web/src/settings/SecResearchPanel.tsx');
const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = new Set(['stateLabel', 'Observation', 'safeCatalogUrl', 'Records']);
const selected = source.statements.filter(node => ts.isFunctionDeclaration(node) && names.has(node.name?.text));
if (selected.length !== 4) throw new Error('renderer extraction mismatch');
const code = ts.transpileModule(selected.map(node => node.getText(source)).join('\n'), {
  compilerOptions: { jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022 },
}).outputText;
const context = { React, URL, ExternalLink: local('lucide-react').ExternalLink, formatSystemTimestamp: value => value };
vm.createContext(context);
vm.runInContext(code, context);
const labels = new Proxy({}, { get: (_, key) => String(key) });
const t = selector => selector({ secResearch: labels });
const row = (id, form = '10-K') => ({ filing_id: id, accession: id, form, filed_date: '2026-01-01' });
const page = data => ({ status: 'partial', data, observed_at: null, coverage: {}, gaps: [{ code: 'filing_metadata_conflict' }], next_cursor: null });
const host = document.getElementById('root');
const renderer = createRoot(host);
const warnings = [];
const originalError = console.error;
console.error = (...args) => warnings.push(args.map(String).join(' '));
(async () => {
  const first = [row('same-filing', '10-K'), row('same-filing', '10-Q'), ...Array.from({ length: 18 }, (_, i) => row('first-' + i))];
  await React.act(async () => renderer.render(React.createElement(context.Records, { page: page(first), view: 'filings', t })));
  const before = host.querySelectorAll('tbody tr').length;
  await React.act(async () => renderer.render(React.createElement(context.Records, { page: page([row('next-page')]), view: 'filings', t })));
  const after = [...host.querySelectorAll('tbody tr')].map(node => node.textContent);
  await React.act(async () => renderer.unmount());
  const controlRoot = createRoot(host);
  const unique = first.map((item, index) => ({ ...item, filing_id: 'unique-' + index }));
  await React.act(async () => controlRoot.render(React.createElement(context.Records, { page: page(unique), view: 'filings', t })));
  await React.act(async () => controlRoot.render(React.createElement(context.Records, { page: page([row('next-page')]), view: 'filings', t })));
  const control = [...host.querySelectorAll('tbody tr')].map(node => node.textContent);
  await React.act(async () => controlRoot.unmount());
  console.error = originalError;
  const result = {
    source: path.relative(root, filename),
    source_sha256: require('node:crypto').createHash('sha256').update(fs.readFileSync(filename)).digest('hex'),
    before, expected_after_count: 1, actual_after_count: after.length, after,
    unique_key_control_count: control.length, unique_key_control: control, warnings,
    exit_code: after.length === 1 && control.length === 1 ? 0 : 1,
  };
  fs.writeFileSync(path.join(__dirname, 'final-review-probe-result.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
  dom.window.close();
  process.exitCode = result.exit_code;
})().catch(error => { console.error = originalError; console.error(error); process.exitCode = 2; });
