/**
 * Worker route tests. Run with:  node tests/worker.test.mjs
 *
 * The important case is /api/push: in v2 it accepted any request at all, so
 * anyone who knew the URL could replace the dashboard's data.
 */

import worker from '../worker/scanner.js';

let failures = 0;

function check(name, condition, detail = '') {
  if (condition) {
    console.log(`PASS  ${name}`);
  } else {
    failures++;
    console.log(`FAIL  ${name}  ${detail}`);
  }
}

function makeEnv(overrides = {}) {
  const store = new Map();
  return {
    TREND_RADAR_KV: {
      get: async k => (store.has(k) ? store.get(k) : null),
      put: async (k, v) => void store.set(k, v),
    },
    ASSETS: { fetch: async () => new Response('<html>dashboard</html>') },
    ...overrides,
  };
}

const url = 'https://example.workers.dev';

const push = (body, headers = {}) =>
  new Request(`${url}/api/push`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });

// ── /api/push ────────────────────────────────────────────────────────────────

{
  const env = makeEnv();  // no PUSH_SECRET configured
  const res = await worker.fetch(push({ signals: [] }), env);
  check('push fails closed when no secret is configured', res.status === 503, `got ${res.status}`);
}

{
  const env = makeEnv({ PUSH_SECRET: 'correct-horse' });
  const res = await worker.fetch(push({ signals: [] }), env);
  check('push rejects a request with no secret', res.status === 401, `got ${res.status}`);
}

{
  const env = makeEnv({ PUSH_SECRET: 'correct-horse' });
  const res = await worker.fetch(push({ signals: [] }, { 'X-Push-Secret': 'wrong' }), env);
  check('push rejects a wrong secret', res.status === 401, `got ${res.status}`);
}

{
  const env = makeEnv({ PUSH_SECRET: 'correct-horse' });
  const res = await worker.fetch(
    push({ signals: [{ keyword: 'x' }] }, { 'X-Push-Secret': 'correct-horse' }), env);
  const body = await res.json();
  check('push accepts the correct secret', res.status === 200 && body.signals === 1,
        `got ${res.status} ${JSON.stringify(body)}`);

  const stored = await worker.fetch(new Request(`${url}/api/results`), env);
  const data = await stored.json();
  check('stored scan is returned by /api/results', data.signals?.[0]?.keyword === 'x');
  check('stored scan is stamped with received_at', typeof data.received_at === 'string');
}

{
  const env = makeEnv({ PUSH_SECRET: 'correct-horse' });
  const res = await worker.fetch(push('not json', { 'X-Push-Secret': 'correct-horse' }), env);
  check('push rejects malformed json', res.status === 400, `got ${res.status}`);
}

{
  const env = makeEnv({ PUSH_SECRET: 'correct-horse' });
  const res = await worker.fetch(push({ nope: true }, { 'X-Push-Secret': 'correct-horse' }), env);
  check('push rejects a payload with no signals array', res.status === 400, `got ${res.status}`);
}

{
  const env = makeEnv({ PUSH_SECRET: 'correct-horse' });
  const res = await worker.fetch(new Request(`${url}/api/push`), env);
  check('push rejects GET', res.status === 405, `got ${res.status}`);
}

// ── /api/results ─────────────────────────────────────────────────────────────

{
  const res = await worker.fetch(new Request(`${url}/api/results`), makeEnv());
  const body = await res.json();
  check('results returns empty state before any scan', body.status === 'empty');
}

// ── /api/health ──────────────────────────────────────────────────────────────

{
  const env = makeEnv({ PUSH_SECRET: 'sekrit', EBAY_VERIFICATION_TOKEN: 'tok' });
  const body = await (await worker.fetch(new Request(`${url}/api/health`), env)).json();
  check('health reports configuration', body.push_secret_configured === true &&
        body.ebay_token_configured === true && body.assets_bound === true);
  check('health never leaks secret values', !JSON.stringify(body).includes('sekrit'));
}

// ── /ebay/notifications ──────────────────────────────────────────────────────

{
  const env = makeEnv();  // token not configured
  const res = await worker.fetch(
    new Request(`${url}/ebay/notifications?challenge_code=abc`), env);
  check('ebay challenge fails cleanly with no token', res.status === 503, `got ${res.status}`);
}

{
  const env = makeEnv({ EBAY_VERIFICATION_TOKEN: 'verification-token-value' });
  const res = await worker.fetch(
    new Request(`${url}/ebay/notifications?challenge_code=abc123`), env);
  const body = await res.json();

  // Recompute eBay's expected hash independently: challenge + token + endpoint.
  const expected = [...new Uint8Array(await crypto.subtle.digest('SHA-256',
    new TextEncoder().encode('abc123' + 'verification-token-value' + `${url}/ebay/notifications`)))]
    .map(b => b.toString(16).padStart(2, '0')).join('');

  check('ebay challenge response matches eBay\'s algorithm',
        body.challengeResponse === expected, `got ${body.challengeResponse}`);
}

// ── / ───────────────────────────────────────────────────────────────────────

{
  const res = await worker.fetch(new Request(`${url}/`), makeEnv());
  check('root serves the dashboard asset', (await res.text()).includes('dashboard'));
}

console.log(`\n${failures ? failures + ' FAILED' : 'ALL PASSED'}`);
process.exit(failures ? 1 : 0);
