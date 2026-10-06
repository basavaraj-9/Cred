// Contract smoke test: render the backend's complete fixture through the real React workspace.
// Run the Day 28 backend tests first to produce the fixture artifact.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const project = path.resolve(__dirname, '../../..');
const source = path.resolve(__dirname, '../components/company-intelligence-reports.tsx');
const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loaded = new Module(source, module);
loaded.filename = source;
loaded.paths = Module._nodeModulePaths(path.dirname(source));
const originalRequire = loaded.require.bind(loaded);
loaded.require = name => name === '@/lib/config'
  ? { BROWSER_API_BASE_URL: 'http://localhost:8000', API_V1_PATH: '/api/v1' }
  : name === "@/lib/http" ? { apiFetch: () => { throw new Error("Unexpected network call"); } }
  : name === "@/lib/use-runtime-actor" ? { useRuntimeActor: () => ["", () => {}] }
  : originalRequire(name);
loaded._compile(compiled, source);
const { CompanyIntelligenceReports } = loaded.exports;
const payload = JSON.parse(fs.readFileSync(path.join(project, 'output/day28-smoke/company-intelligence-360.json'), 'utf8'));
const tabs = ['summary', 'company_profile', 'documents', 'financials', 'credit', 'stock', 'validation', 'monitoring', 'evidence'];
for (const tab of tabs) {
  const html = renderToStaticMarkup(React.createElement(CompanyIntelligenceReports, {
    initialPreview: { payload_hash: 'fixture-hash', payload }, initialTab: tab,
  }));
  assert.ok(html.includes('Saved report preview'), tab);
  assert.ok(html.includes('Creditworthiness and equity-market analytical strength'), tab);
  for (const disclaimer of Object.values(payload.disclaimers)) assert.ok(html.includes(disclaimer), tab);
  if (tab === 'credit') assert.ok(html.includes('Credit Assessment'));
  if (tab === 'stock') assert.ok(html.includes('Stock Intelligence Research'));
  if (tab === 'summary') assert.ok(html.includes(payload.executive_summary.company));
  assert.ok(!html.includes('Unified Company Score'));
}
console.log(`Passed: ${tabs.length} report sections render the full backend fixture, with required separation and disclaimers.`);
