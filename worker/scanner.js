/**
 * TREND RADAR v2 — Cloudflare Worker
 * ====================================
 * Routes:
 *   GET  /              → serve dashboard HTML
 *   GET  /api/results   → return latest scan from KV
 *   POST /api/push      → receive scan results from Python, store in KV
 *
 * To enable automatic daily scans, uncomment the `scheduled` block
 * and add this to wrangler.toml:
 *   [triggers]
 *   crons = ["0 6 * * *"]
 */

export default {

  async fetch(request, env) {
    const url = new URL(request.url);

    const jsonHeaders = {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    };

    // ── GET / → serve dashboard ──────────────────────────────────────
    if (url.pathname === '/' || url.pathname === '/index.html') {
      const resp = await fetch(
        'https://raw.githubusercontent.com/battersea-dynamics/dropshipping/main/index.html'
      );
      const html = await resp.text();
      return new Response(html, {
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      });
    }

    // ── GET /api/results → return latest scan ───────────────────────
    if (url.pathname === '/api/results' && request.method === 'GET') {
      const data = await env.TREND_RADAR_KV.get('latest_scan');
      if (!data) {
        return new Response(JSON.stringify({
          status:        'empty',
          message:       'No scan yet. Run: python trend_radar.py',
          signals:       [],
          keywords_used: [],
        }), { headers: jsonHeaders });
      }
      return new Response(data, { headers: jsonHeaders });
    }

    // ── POST /api/push → receive results from Python ─────────────────
    if (url.pathname === '/api/push' && request.method === 'POST') {
      const body = await request.json();
      await env.TREND_RADAR_KV.put('latest_scan', JSON.stringify(body));
      return new Response(JSON.stringify({ status: 'saved' }), { headers: jsonHeaders });
    }

    // ── Fallback ──────────────────────────────────────────────────────
    return new Response(
      JSON.stringify({ status: 'ok', message: 'Trend Radar API v2' }),
      { headers: jsonHeaders }
    );
  },

  // ── CRON TRIGGER (disabled — enable when ready for full automation) ─
  // async scheduled(event, env, ctx) {
  //   await runDiscoveryScan(env);
  // },
};


// ── DISCOVERY SCAN (runs inside Worker when cron is enabled) ──────────────────

async function runDiscoveryScan(env) {
  const categories = ['health', 'beauty', 'kitchen', 'electronics', 'pet-supplies', 'sporting-goods', 'toys', 'apparel'];
  const products   = [];

  for (const cat of categories) {
    try {
      const url  = `https://www.amazon.co.uk/gp/movers-and-shakers/${cat}`;
      const resp = await fetch(url, {
        headers: {
          'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept-Language': 'en-GB,en;q=0.9',
          'Accept':          'text/html',
        }
      });
      const html = await resp.text();

      const nameMatches = [...html.matchAll(/class="p13n-sc-truncate[^"]*"[^>]*>([^<]{10,100})</g)];
      const rankMatches = [...html.matchAll(/class="zg-bdg-text[^"]*"[^>]*>#?(\d+)</g)];

      nameMatches.slice(0, 15).forEach((m, i) => {
        products.push({
          keyword:       m[1].trim(),
          amazon_name:   m[1].trim(),
          amazon_rank:   parseInt(rankMatches[i]?.[1] || i + 1),
          category:      cat,
          sources:       ['Amazon M&S'],
          strength:      parseInt(rankMatches[i]?.[1] || 99) <= 5 ? 'STRONG' : 'MEDIUM',
          trends_score:  0,
          trends_growth: 0,
          detected_at:   new Date().toLocaleString('en-GB'),
        });
      });

      await sleep(2000);
    } catch (e) {
      console.error(`Amazon error for ${cat}:`, e.message);
    }
  }

  const data = {
    status:        'ok',
    scan_date:     new Date().toLocaleString('en-GB'),
    keywords_used: [],
    signals:       products,
  };

  await env.TREND_RADAR_KV.put('latest_scan', JSON.stringify(data));
  await sendTelegram(data, env);
}


// ── TELEGRAM ──────────────────────────────────────────────────────────────────

async function sendTelegram(data, env) {
  const token  = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return;

  const signals = data.signals || [];
  const strong  = signals.filter(s => s.strength === 'STRONG');

  await tgSend(token, chatId,
    `TREND RADAR — ${data.scan_date}\n` +
    `Products found: ${signals.length}\n` +
    `Strong signals: ${strong.length}`
  );

  for (const s of strong.slice(0, 5)) {
    await tgSend(token, chatId,
      `#${s.amazon_rank} ${s.amazon_name?.slice(0, 60)}\n` +
      `Category: ${s.category} | ${s.strength}`
    );
    await sleep(500);
  }
}

async function tgSend(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ chat_id: chatId, text }),
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
