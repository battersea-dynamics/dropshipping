export default {
  // Manual trigger: fetch https://dropshipping.battersea-dynamics.workers.dev/api/scan
  // Auto trigger: Cron (disabled for now, enable later with one line)
  
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // CORS headers so dashboard can call this
    const headers = {
      'Access-Control-Allow-Origin': '*',
      'Content-Type': 'application/json'
    };

    // GET /api/results → return latest scan from KV
    if (url.pathname === '/api/results') {
      const data = await env.TREND_RADAR_KV.get('latest_scan');
      if (!data) {
        return new Response(JSON.stringify({
          status: 'empty',
          message: 'No scan yet. Call /api/scan to run one.',
          signals: [],
          keywords_used: []
        }), { headers });
      }
      return new Response(data, { headers });
    }

    // GET /api/scan → run a full scan manually
    if (url.pathname === '/api/scan') {
      const keywords = await getKeywords(env);
      const results = await runScan(keywords, env);
      await env.TREND_RADAR_KV.put('latest_scan', JSON.stringify(results));
      await sendTelegram(results, env);
      return new Response(JSON.stringify(results), { headers });
    }

    // GET /api/keywords → return saved keywords
    if (url.pathname === '/api/keywords') {
      const kw = await env.TREND_RADAR_KV.get('keywords');
      return new Response(kw || '{"keywords":[]}', { headers });
    }

    // POST /api/keywords → save keywords
    if (url.pathname === '/api/keywords' && request.method === 'POST') {
      const body = await request.json();
      await env.TREND_RADAR_KV.put('keywords', JSON.stringify(body));
      return new Response('{"status":"saved"}', { headers });
    }

    // DEBUG — remove after testing
    if (url.pathname === '/api/debug') {
      const result = await fetchGoogleTrends('wireless charger', 'GB');
      return new Response(JSON.stringify(result), { headers });
    }
    // POST /api/push → receive results from Python and store in KV
    if (url.pathname === '/api/push' && request.method === 'POST') {
      const body = await request.json();
      await env.TREND_RADAR_KV.put('latest_scan', JSON.stringify(body));
      return new Response('{"status":"saved"}', { headers });
    }

    // DEBUG — remove after testing
    if (url.pathname === '/api/debug') {
      const result = await fetchGoogleTrends('wireless charger', 'GB');
      return new Response(JSON.stringify(result), { headers });
    }

    return new Response('Trend Radar API running', { headers });
  },

  // Cron trigger — uncomment this when ready for automatic daily scans
  // async scheduled(event, env, ctx) {
  //   const keywords = await getKeywords(env);
  //   const results = await runScan(keywords, env);
  //   await env.TREND_RADAR_KV.put('latest_scan', JSON.stringify(results));
  //   await sendTelegram(results, env);
  // }
};

// ── KEYWORDS ──────────────────────────────────────────────────────────────────

async function getKeywords(env) {
  const saved = await env.TREND_RADAR_KV.get('keywords');
  if (saved) {
    const parsed = JSON.parse(saved);
    return parsed.keywords || parsed;
  }
  // Default keywords if none saved yet
  return [
    'bone conduction headphones',
    'wireless charger',
    'posture corrector',
    'led face mask',
    'cat water fountain',
    'mini dehumidifier',
    'massage gun',
    'resistance bands'
  ];
}

// ── GOOGLE TRENDS ─────────────────────────────────────────────────────────────

async function fetchGoogleTrends(keyword, geo = 'GB') {
  try {
    // Step 1: get widget token
    const exploreUrl = `https://trends.google.com/trends/api/explore?hl=en-GB&tz=-60&req=${encodeURIComponent(JSON.stringify({
      comparisonItem: [{ keyword, geo, time: 'today 3-m' }],
      category: 0,
      property: ''
    }))}&tz=-60`;

    const exploreResp = await fetch(exploreUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });

    const exploreText = await exploreResp.text();
    const exploreJson = JSON.parse(exploreText.replace(")]}'," , ''));
    const widgets = exploreJson.widgets;
    const timeWidget = widgets.find(w => w.id === 'TIMESERIES');
    if (!timeWidget) return null;

    const token = timeWidget.token;
    const req = timeWidget.request;

    // Step 2: get actual data
    const dataUrl = `https://trends.google.com/trends/api/widgetdata/multiline?hl=en-GB&tz=-60&req=${encodeURIComponent(JSON.stringify(req))}&token=${encodeURIComponent(token)}&tz=-60`;

    const dataResp = await fetch(dataUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });

    const dataText = await dataResp.text();
    const dataJson = JSON.parse(dataText.replace(")]}'," , ''));
    const points = dataJson.default.timelineData;

    if (!points || points.length < 4) return null;

    // Calculate growth: compare last quarter vs first quarter
    const values = points.map(p => p.value[0]);
    const mid = Math.floor(values.length / 2);
    const pastAvg = values.slice(0, mid).reduce((a, b) => a + b, 0) / mid || 1;
    const presentAvg = values.slice(mid).reduce((a, b) => a + b, 0) / (values.length - mid);
    const growth = Math.round((presentAvg - pastAvg) / pastAvg * 100);
    const currentScore = values[values.length - 1];

    return { keyword, score: currentScore, growth, geo };

  } catch (e) {
    console.error(`Trends error for ${keyword}:`, e.message);
    return null;
  }
}

// ── AMAZON MOVERS & SHAKERS ───────────────────────────────────────────────────

async function fetchAmazonMovers(geo = 'UK') {
  const domain = geo === 'UK' ? 'amazon.co.uk' : 'amazon.it';
  const categories = ['health', 'beauty', 'kitchen', 'electronics', 'pet-supplies', 'sporting-goods'];
  const products = [];

  for (const cat of categories) {
    try {
      const url = `https://www.${domain}/gp/movers-and-shakers/${cat}`;
      const resp = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept-Language': 'en-GB,en;q=0.9',
          'Accept': 'text/html'
        }
      });
      const html = await resp.text();

      // Extract product names using regex (no DOM parser in Workers)
      const nameMatches = html.matchAll(/class="p13n-sc-truncate[^"]*"[^>]*>([^<]{10,80})</g);
      const rankMatches = html.matchAll(/class="zg-bdg-text[^"]*"[^>]*>#?(\d+)</g);

      const names = [...nameMatches].map(m => m[1].trim());
      const ranks = [...rankMatches].map(m => parseInt(m[1]));

      names.slice(0, 15).forEach((name, i) => {
        products.push({ name, rank: ranks[i] || i + 1, category: cat });
      });

      await sleep(2000);
    } catch (e) {
      console.error(`Amazon error for ${cat}:`, e.message);
    }
  }

  return products;
}

// ── TELEGRAM ──────────────────────────────────────────────────────────────────

async function sendTelegram(results, env) {
  const token = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return;

  const signals = results.signals || [];
  if (!signals.length) {
    await tgSend(token, chatId, 'TREND RADAR — No signals above threshold this scan.');
    return;
  }

  const header = `TREND RADAR — Scan ${results.scan_date}\n` +
    `Keywords: ${results.keywords_used?.length || 0}\n` +
    `Signals: ${signals.length} | Amazon confirmed: ${signals.filter(s => s.amazon_rank).length}`;
  await tgSend(token, chatId, header);

  for (const s of signals.slice(0, 5)) {
    const msg = `${s.keyword.toUpperCase()}\n` +
      `Growth: +${s.trends_growth}% | Score: ${s.trends_score}/100\n` +
      `Amazon: ${s.amazon_rank ? '#' + s.amazon_rank + ' — ' + s.amazon_name : 'not found'}\n` +
      `Strength: ${s.strength}`;
    await tgSend(token, chatId, msg);
    await sleep(500);
  }
}

async function tgSend(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text })
  });
}

// ── MAIN SCAN ─────────────────────────────────────────────────────────────────

async function runScan(keywords, env) {
  const scanDate = new Date().toLocaleString('en-GB');
  const signals = [];

  // 1. Google Trends — UK market first
  console.log('Scanning Google Trends...');
  const trendsResults = [];
  for (const kw of keywords) {
    const result = await fetchGoogleTrends(kw, 'GB');
    if (result && result.growth >= -50) trendsResults.push(result);
    await sleep(8000); // respect rate limits
  }

  // 2. Amazon Movers & Shakers — UK
  console.log('Scanning Amazon UK...');
  const amazonProducts = await fetchAmazonMovers('UK');

  // 3. Match and score
  for (const trend of trendsResults) {
    const amazonMatch = findAmazonMatch(trend.keyword, amazonProducts);
    const strength = getStrength(trend.growth, amazonMatch);

    signals.push({
      keyword: trend.keyword,
      trends_score: trend.score,
      trends_growth: trend.growth,
      amazon_rank: amazonMatch?.rank || null,
      amazon_name: amazonMatch?.name || null,
      sources: amazonMatch ? ['Google Trends', 'Amazon M&S'] : ['Google Trends'],
      strength,
      detected_at: scanDate
    });
  }

  // Sort: Amazon confirmed first, then by growth
  signals.sort((a, b) => (b.amazon_rank ? 1 : 0) - (a.amazon_rank ? 1 : 0) || b.trends_growth - a.trends_growth);

  return {
    status: 'ok',
    scan_date: scanDate,
    keywords_used: keywords,
    signals
  };
}

// ── HELPERS ───────────────────────────────────────────────────────────────────

function findAmazonMatch(keyword, products) {
  const tokens = keyword.toLowerCase().split(' ').filter(t => t.length > 3);
  for (const p of products) {
    const name = p.name.toLowerCase();
    const matches = tokens.filter(t => name.includes(t)).length;
    if (matches >= Math.max(1, Math.floor(tokens.length / 2))) return p;
  }
  return null;
}

function getStrength(growth, amazonMatch) {
  const score = growth + (amazonMatch ? 50 : 0);
  if (score >= 100) return 'STRONG';
  if (score >= 50)  return 'MEDIUM';
  return 'WEAK';
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}