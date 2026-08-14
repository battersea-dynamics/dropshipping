# Trend Radar

Finds products worth dropshipping, and tells you what they already sell for.

Part of the NexVita business (Battersea Dynamics Ltd). If you have been away
from this repo for a while, **read `RESTART_HERE.md` first** — it is the
shortest path back to a working system.

---

## What this actually is

One Python script that runs on your PC, and one Cloudflare Worker that stores
and displays what the script found.

```
python trend_radar.py                     (your PC)
  ├── scrapes Amazon UK Movers & Shakers   → the product list
  ├── TikTok Creative Center (Playwright)  → trending hashtags
  ├── Pinterest Trends (Playwright)        → trending keywords
  ├── eBay Browse API                      → price + how saturated it is
  ├── writes radar_results_<date>.json     (local backup)
  └── POST /api/push  ──────────────┐
                                    ▼
              Cloudflare Worker (worker/scanner.js)
                    └── Cloudflare KV: "latest_scan"
                                    ▼
              Dashboard (public/index.html)
              https://dropshipping.battersea-dynamics.workers.dev
```

Telegram alerts are sent by the Python script, not by the Worker.

## Files

| File | What it is |
|---|---|
| `trend_radar.py` | The whole scanner. Everything happens here. |
| `worker/scanner.js` | Cloudflare Worker — API + serves the dashboard |
| `public/index.html` | The dashboard, shipped with the Worker |
| `wrangler.toml` | Worker config (KV binding, asset binding) |
| `requirements.txt` | Python dependencies |
| `.env` | Your secrets. Gitignored. Copy from `.env.example`. |
| `RESTART_HERE.md` | Do-this-now list after time away |
| `MD files/` | Business context docs (also in the Claude project) |

## Running it

```bash
pip install -r requirements.txt
playwright install chromium          # once

python trend_radar.py                # scan now
python trend_radar.py auto           # scan at 08:00 and 20:00, PC must stay on
```

Deploying:

```bash
wrangler deploy                      # after changing worker/ or public/
git push                             # everything else
curl https://dropshipping.battersea-dynamics.workers.dev/api/health
```

## Scoring

Each product gets 0–100. Every component requires a *verified* match — the
reasons are returned in `score_reasons` and shown on the dashboard, so a score
can always be explained.

| Signal | Points |
|---|---|
| Amazon M&S rank 1–5 | +40 |
| Amazon M&S rank 6–15 | +25 |
| Amazon M&S rank 16–30 | +10 |
| TikTok hashtag match | +20 |
| Pinterest keyword match | +10 |
| Reddit mention | +10 |
| Fewer than 100 eBay listings (low competition) | +15 |
| More than 1000 eBay listings (saturated) | −15 |
| Confirmed by 2+ independent sources | +15 |

`STRONG` ≥ 65 · `MEDIUM` ≥ 40 · `WEAK` below that.

**Expect zero STRONG results at first, and that is correct.** Amazon rank on
its own tops out at 40 points, so a product cannot reach STRONG without a
second source confirming it. Right now only the Amazon scraper is reliable, so
the honest answer is "no confirmed signals" — the old version showed 25 STRONG
products out of 100 on the same data, every one of them on Amazon rank alone
plus an unrelated eBay listing. Getting real STRONG results means fixing
TikTok/Pinterest capture, not loosening the threshold.

## Things that are true and worth not rediscovering the hard way

**eBay has no sold-count.** The Browse API's `ItemSummary` exposes no
`soldCount`, `totalSoldItems` or `soldQuantity`. `watchCount` exists but needs
a separate App Check permission grant from eBay. Do not go looking for the
"right field name" — there isn't one. eBay is used here for price and
saturation instead, which is what you actually need before sourcing anything.

**Amazon M&S mostly returns brands you cannot dropship.** The top beauty
result in the last scan was a branded Korean serum. Movers & Shakers ranks by
24-hour rank change, so it surfaces things that have *already* broken out.
Treat it as one input, not the product pipeline.

**Cross-source matching needs word overlap.** Matching on category alone means
every product in a category matches every trend in that category. The 17/05
scan credited an eye serum with a £250 perfume for exactly this reason.
`MIN_TOKEN_OVERLAP` in `trend_radar.py` is the guard.

**The Worker cannot do the scraping.** There was a commented-out cron block in
`worker/scanner.js` that scraped Amazon from inside the Worker. It has been
removed: Amazon blocks datacenter IPs, and Cloudflare's egress is a datacenter
IP, so it would never have returned data. Scheduling options that do work are
in `RESTART_HERE.md`.

**If a scan returns no products,** the log now prints the page title and byte
count per category. A title mentioning "Robot Check" or "Sorry" means Amazon
is blocking the IP — a different problem from the CSS selectors going stale.

## Security

- `POST /api/push` requires the `X-Push-Secret` header to match the
  `PUSH_SECRET` Worker secret. With no secret set, the endpoint returns 503 —
  it fails closed rather than open.
- The eBay verification token is a Worker secret, not a literal in the source.
- `/api/health` reports whether secrets are set, never their values.
- The dashboard escapes all scraped text before inserting it into the DOM.
