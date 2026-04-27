# 01 — Trend Radar: Build Instructions

## Context
Read `00_master_context.md` before this file. This chat builds the Trend Radar — the most important pillar of the business. Everything else (supplier search, listings) flows from what this tool discovers.

---

## What We Are Building
A web application that:
- Runs daily automated scans across multiple data sources
- Scores products by trend velocity (how fast interest is growing)
- Filters by market: UK / Italy / Germany / France / EU-all
- Displays a ranked dashboard of trending product opportunities
- Sends alerts when a product crosses a score threshold
- Links directly to supplier search for each product found

**Deployed on:** Cloudflare Pages (frontend) + Cloudflare Workers (backend API calls)
**Built with:** Vite + React
**Data stored in:** Cloudflare KV

---

## Architecture Overview

```
[Cloudflare Cron Trigger] — fires daily at 6am UTC
        ↓
[Cloudflare Worker: scanner.js]
        ↓ queries all sources
[Data sources] → results stored in Cloudflare KV
        ↓
[Vite + React frontend] — reads from KV via Worker API
        ↓
[User sees dashboard in browser]
```

---

## Data Sources — Implementation Details

### 1. Google Trends
- **Library:** `google-trends-api` (npm) — unofficial but stable
- **What to fetch:** interest over time for keyword lists, filtered by country (GB, IT, DE, FR)
- **Key metric:** velocity = (current week value) - (4 week average). High velocity = rising fast
- **Breakout detection:** if Google returns "Breakout" flag, score +40 points immediately
- **Rate limiting:** add 1–2 second delays between requests, Google blocks aggressive scraping
- **Free:** yes, no API key needed

### 2. Meta (Facebook) Ad Library
- **Access:** public API, requires a Facebook developer account (free)
- **Endpoint:** `https://www.facebook.com/ads/library/api/`
- **What to fetch:** active ads by search term, filtered by country, sorted by creation date
- **Signal:** ads running for 3+ weeks = advertiser is profitable = product sells
- **What to extract:** ad text, product keywords, how long ad has been active
- **Free:** yes, requires free Facebook developer app registration

### 3. Amazon Movers & Shakers
- **Method:** web scraping (no official API for this data)
- **URLs to scrape:**
  - UK: `https://www.amazon.co.uk/gp/movers-and-shakers/`
  - IT: `https://www.amazon.it/gp/movers-and-shakers/`
  - DE: `https://www.amazon.de/gp/movers-and-shakers/`
- **What to extract:** product name, category, rank change (e.g. "↑ 1,240%"), ASIN
- **Tool:** Cheerio (npm) for HTML parsing inside Cloudflare Worker
- **Run frequency:** twice daily (6am + 6pm UTC)
- **Note:** Amazon occasionally blocks scrapers — add rotating user-agent headers

### 4. TikTok Creative Center
- **Access:** public, no auth needed for trending data
- **Endpoint:** `https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en`
- **What to fetch:** trending hashtags and products in UK category
- **Alternative:** TikTok Research API (apply for free access — takes a few days approval)
- **Signal:** products appearing in trending ads = high purchase intent right now

### 5. Reddit
- **API:** free, requires Reddit developer account (free)
- **Subreddits to monitor:** r/HotDeals (UK), r/deals, r/entrepreneur, r/dropship, r/flipping
- **What to fetch:** top posts this week containing product keywords
- **Signal:** high upvote post about a product = organic demand emerging
- **Library:** use Reddit JSON API directly (`subreddit.json?sort=top&t=week`)

### 6. eBay Trending
- **API:** eBay Finding API — free, requires eBay developer account (free)
- **What to fetch:** trending searches, most watched items by category
- **Signal:** items with high watch counts but few sellers = opportunity

### 7. AliExpress
- **API:** AliExpress Affiliate API — free, requires affiliate account registration
- **What to fetch:** new arrivals with fast order growth, top selling in categories
- **Signal:** product with <6 months on platform but 1000+ orders = catching fire

---

## Scoring System

Each product gets a score 0–100 built from:

| Signal | Points |
|---|---|
| Google Trends velocity >50% week-on-week | +20 |
| Google Trends "Breakout" flag | +40 |
| Active Meta ads running 3+ weeks | +15 |
| Amazon Movers rank jump >500% | +20 |
| Appears on TikTok trending | +20 |
| Reddit post >500 upvotes this week | +10 |
| eBay high watch count, low sellers | +15 |
| Found on 3+ sources simultaneously | +20 bonus |
| Already heavily listed on Amazon UK | -20 |

Score bands:
- **80–100:** 🔴 Act now — rising fast, window is short
- **60–79:** 🟠 Strong signal — research supplier immediately  
- **40–59:** 🟡 Watch — flag for next week rescan
- **0–39:** ⚪ Weak — ignore for now

---

## Dashboard UI — What to Build

### Main View
- Header: last scan time + next scan countdown
- Market filter tabs: ALL / UK / IT / DE / FR
- Sort options: Score / Velocity / Newest
- Product cards (see below)

### Product Card (per trending item)
- Product name + category
- Score badge (colour coded)
- Source icons showing which platforms flagged it (Google / Meta / Amazon / TikTok / Reddit)
- Sparkline: 30-day interest trend
- Estimated margin: AliExpress price vs Amazon UK selling price
- Two buttons: **"Find Supplier"** (links to Pillar 2 flow) | **"View on Amazon"**

### Alert Panel (sidebar)
- New this scan: products that just crossed 60+ score
- Rising fast: products whose score increased >20 since yesterday
- Peaked warning: products showing declining velocity (sell signal — don't enter)

---

## Build Order (Step by Step)

Follow this sequence — do not skip ahead:

### Phase 1 — Project Setup
1. Create Vite + React project: `npm create vite@latest trend-radar -- --template react`
2. Install dependencies: `cheerio`, `google-trends-api`, `axios`, `recharts` (for sparklines)
3. Set up Cloudflare Pages connection to GitHub repo
4. Set up Cloudflare Workers for backend API calls
5. Test deploy with a simple "Hello World" to confirm pipeline works

### Phase 2 — First Data Source (Google Trends)
1. Build the Cloudflare Worker to call Google Trends for 10 test keywords
2. Store results in Cloudflare KV
3. Build a simple React component to display raw results
4. Add velocity calculation logic
5. Confirm end-to-end works before adding more sources

### Phase 3 — Add Amazon Scraper
1. Add Amazon Movers & Shakers scraper to the Worker
2. Parse rank change percentages
3. Merge results with Google Trends data in KV
4. Update React display to show combined results

### Phase 4 — Add Meta Ad Library
1. Register free Facebook developer account
2. Get Ad Library API access token
3. Add API calls to Worker
4. Store ad age + keyword data
5. Add to scoring engine

### Phase 5 — Scoring Engine
1. Build the scoring function that takes all source data per product
2. Apply weights from the scoring table above
3. Sort products by score
4. Add score badges and colour coding to UI

### Phase 6 — Full Dashboard UI
1. Add market filter tabs
2. Add sparkline charts per product (recharts)
3. Add alert panel
4. Add supplier link button (passes product name to Pillar 2)
5. Mobile-friendly check (should work on tablet at minimum)

### Phase 7 — Cron + Alerts
1. Set up Cloudflare Cron Trigger for 6am UTC daily
2. Add Telegram alert via the owner's existing Telegram bot (already set up — just needs the Worker to call it)
3. Test full automated cycle without manual intervention

**Telegram alert implementation (inside Cloudflare Worker):**
```javascript
const TELEGRAM_BOT_TOKEN = env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = env.TELEGRAM_CHAT_ID;

async function sendTelegramAlert(message) {
  await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text: message,
      parse_mode: 'Markdown'
    })
  });
}
```

**When to trigger alerts:**
- Product crosses 60+ score for the first time → send immediately
- Product score jumps >20 points since yesterday → send immediately
- Daily summary at end of scan: top 3 products with scores
- Peaked warning: product was 70+ last week, now dropping → "⚠️ [Product] may be peaking — check before listing"

**Example alert message format:**
```
🔴 *New Trend Alert*
Product: Magnetic Phone Mount
Score: 78/100
Sources: Google Trends 📈 | Amazon M&S ⬆️ | TikTok 🎵
Est. margin: £24 (AliExpress £9 → Amazon £45)
Market: UK 🇬🇧

→ [Open Dashboard]
```

### Phase 8 — Remaining Sources
1. Reddit API integration
2. eBay API integration  
3. TikTok Creative Center scraping
4. AliExpress Affiliate API

---

## Environment Variables (Store in Cloudflare Workers Secrets)
```
TELEGRAM_BOT_TOKEN=        ← already have this
TELEGRAM_CHAT_ID=          ← already have this
FACEBOOK_ACCESS_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
EBAY_APP_ID=
ALIEXPRESS_APP_KEY=
ALIEXPRESS_APP_SECRET=
```
Never put these in your frontend code or commit them to GitHub.

---

## Free Account Registrations Needed
Before starting Phase 4+, register these (all free):
- [ ] Facebook Developer account → Ad Library API access
- [ ] Reddit Developer account → API credentials
- [ ] eBay Developer account → Finding API key
- [ ] AliExpress Affiliate account → API access

---

## Notes for the Claude Chat Building This
- Owner has built 2 React apps before with Claude assistance — familiar with the workflow
- Build one phase at a time, test before moving to next
- If a source blocks scraping, skip it and move to next — don't get stuck
- Cloudflare free tier limits: Workers 100k req/day, KV 100k reads/day — more than enough for this use case
- Keep all API keys in Cloudflare secrets, never in frontend code
- The goal is working > perfect — get data flowing first, polish UI after
