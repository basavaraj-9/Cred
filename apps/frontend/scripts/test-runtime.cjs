const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');

const source = path.resolve(__dirname, '../lib/http.ts');
const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loaded = new Module(source, module);
loaded.filename = source;
loaded.paths = Module._nodeModulePaths(path.dirname(source));
const originalRequire = loaded.require.bind(loaded);
loaded.require = name => name === '@/lib/config'
  ? { BROWSER_API_BASE_URL: 'https://api.example.test' } : originalRequire(name);
loaded._compile(compiled, source);
const { apiFetch, setSession, sessionIdentity } = loaded.exports;

(async () => {
  let received;
  global.fetch = async (url, init) => {
    received = { url, init };
    return new Response('{}', { status: 200 });
  };
  setSession('test-token', { user_id: 'authenticated-user', role: 'VIEWER', environment: 'test', permissions: [] });
  await apiFetch('https://api.example.test/api/v1/test?actor_user_id=someone-else', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actor_user_id: 'someone-else', company_id: 'unchanged-company' }),
  });
  assert.equal(received.init.headers.get('Authorization'), 'Bearer test-token');
  assert.equal(received.url.searchParams.get('actor_user_id'), 'authenticated-user');
  assert.deepEqual(JSON.parse(received.init.body), {
    actor_user_id: 'authenticated-user', company_id: 'unchanged-company',
  });
  await assert.rejects(apiFetch('https://external.example.test/steal'), /Unexpected API destination/);
  global.fetch = async () => new Response('{}', { status: 403 });
  await assert.rejects(apiFetch('https://api.example.test/private'), /does not have access/);
  global.fetch = async () => new Response('{}', { status: 401 });
  await assert.rejects(apiFetch('https://api.example.test/private'), /Sign in/);
  assert.equal(sessionIdentity(), null);
  global.fetch = async (url, init) => {
    assert.equal(init.headers.has('Authorization'), false);
    return new Response('{}', { status: 200 });
  };
  await apiFetch('https://api.example.test/public');
  console.log('Passed: authenticated requests, actor binding, destination restriction, 401/403 handling and sign-out.');
})().catch(error => { console.error(error); process.exitCode = 1; });
