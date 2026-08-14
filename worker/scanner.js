/**
 * TREND RADAR v3 — Cloudflare Worker
 * ====================================
 * Routes:
 *   GET  /                    → dashboard (served from ./public via [assets])
 *   GET  /api/health          → config sanity check, no secrets returned
 *   GET  /api/results         → latest scan from KV (public, read-only)
 *   POST /api/push            → store a scan in KV (requires X-Push-Secret)
 *   GET  /ebay/notifications  → eBay marketplace-account-deletion challenge
 *
 * Secrets — set these with `wrangler secret put <NAME>`, never in this file:
 *   PUSH_SECRET               required, or /api/push refuses every request
 *   EBAY_VERIFICATION_TOKEN   required only if the eBay webhook is in use
 *
 * v2 notes, for context: /api/push had no authentication at all, so anyone
 * who knew the URL could overwrite the dashboard; the eBay verification token
 * was hardcoded in this file in a public repo; and the dashboard HTML was
 * re-fetched from raw.githubusercontent.com on every single request.
 */

const JSON_HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Cache-Control': 'no-store',
  'X-Content-Type-Options': 'nosniff',
};

// A full 10-category scan is roughly 150 KB. This is a generous ceiling that
// still stops anyone filling the KV namespace with a single request.
const MAX_PUSH_BYTES = 2_000_000;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── GET / → dashboard ────────────────────────────────────────────────────
    if (request.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
      if (env.ASSETS) return env.ASSETS.fetch(request);
      return new Response(
        'Dashboard asset binding missing — check [assets] in wrangler.toml, then redeploy.',
        { status: 500, headers: { 'Content-Type': 'text/plain' } }
      );
    }

    // ── GET /api/health → is this Worker configured correctly? ───────────────
    if (url.pathname === '/api/health') {
      return json({
        status: 'ok',
        version: 'v3',
        // Booleans only — never echo the values themselves.
        push_secret_configured: Boolean(env.PUSH_SECRET),
        ebay_token_configured: Boolean(env.EBAY_VERIFICATION_TOKEN),
        kv_bound: Boolean(env.TREND_RADAR_KV),
        assets_bound: Boolean(env.ASSETS),
      });
    }

    // ── GET /api/results → latest scan (public) ──────────────────────────────
    if (url.pathname === '/api/results' && request.method === 'GET') {
      const data = await env.TREND_RADAR_KV.get('latest_scan');
      if (!data) {
        return json({
          status: 'empty',
          message: 'No scan yet. Run: python trend_radar.py',
          signals: [],
          keywords_used: [],
        });
      }
      return new Response(data, { headers: JSON_HEADERS });
    }

    // ── POST /api/push → store a scan (authenticated) ────────────────────────
    if (url.pathname === '/api/push') {
      if (request.method !== 'POST') {
        return json({ error: 'method_not_allowed' }, 405);
      }

      // Fail closed. If the secret was never set, the endpoint stays shut
      // rather than silently reverting to v2's open-to-the-world behaviour.
      if (!env.PUSH_SECRET) {
        return json({
          error: 'push_disabled',
          message: 'PUSH_SECRET is not configured. Run: wrangler secret put PUSH_SECRET',
        }, 503);
      }

      if (!timingSafeEqual(request.headers.get('X-Push-Secret') || '', env.PUSH_SECRET)) {
        return json({ error: 'unauthorized' }, 401);
      }

      if (Number(request.headers.get('Content-Length') || 0) > MAX_PUSH_BYTES) {
        return json({ error: 'payload_too_large' }, 413);
      }

      const raw = await request.text();
      if (raw.length > MAX_PUSH_BYTES) {
        return json({ error: 'payload_too_large' }, 413);
      }

      let body;
      try {
        body = JSON.parse(raw);
      } catch {
        return json({ error: 'invalid_json' }, 400);
      }

      if (!body || typeof body !== 'object' || !Array.isArray(body.signals)) {
        return json({ error: 'invalid_payload', message: 'Expected { signals: [...] }' }, 400);
      }

      body.received_at = new Date().toISOString();
      await env.TREND_RADAR_KV.put('latest_scan', JSON.stringify(body));
      return json({ status: 'saved', signals: body.signals.length });
    }

    // ── GET /ebay/notifications → eBay account-deletion webhook ──────────────
    if (url.pathname === '/ebay/notifications') {
      const challengeCode = url.searchParams.get('challenge_code');

      if (challengeCode) {
        const token = env.EBAY_VERIFICATION_TOKEN;
        if (!token) {
          return json({
            error: 'ebay_token_not_configured',
            message: 'Run: wrangler secret put EBAY_VERIFICATION_TOKEN',
          }, 503);
        }
        // eBay hashes challenge + token + the endpoint URL it called.
        // Derive the endpoint from the request so it cannot drift out of sync.
        const endpoint = `${url.origin}${url.pathname}`;
        const digest = await crypto.subtle.digest(
          'SHA-256',
          new TextEncoder().encode(challengeCode + token + endpoint)
        );
        const challengeResponse = [...new Uint8Array(digest)]
          .map(b => b.toString(16).padStart(2, '0'))
          .join('');
        return json({ challengeResponse });
      }

      // Real deletion notifications arrive as POSTs; acknowledge them.
      return new Response('OK', { status: 200 });
    }

    return json({ status: 'ok', message: 'Trend Radar API v3' });
  },
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: JSON_HEADERS });
}

/**
 * Constant-time comparison, so the response time of a wrong secret does not
 * reveal how many leading characters were correct.
 */
function timingSafeEqual(a, b) {
  const encoder = new TextEncoder();
  const left = encoder.encode(a);
  const right = encoder.encode(b);
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i++) diff |= left[i] ^ right[i];
  return diff === 0;
}
