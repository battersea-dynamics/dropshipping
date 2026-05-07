# Platforms, Accounts & Tools — Master Reference
## Last updated: May 2026

---

## Code & Deployment
| Platform | URL | What for |
|---|---|---|
| GitHub | github.com/battersea-dynamics | Code repositories |
| GitHub repo — dropshipping | github.com/battersea-dynamics/dropshipping | Main scanner project |
| GitHub repo — gazzaopportunity | github.com/battersea-dynamics/gazzaopportunity | gazza.ltd landing page |
| Cloudflare | dash.cloudflare.com | Worker, KV storage, dashboard hosting |
| VS Code | Local IDE | Writing and editing code |
| Python | Local | Running trend_radar.py scanner |
| Wrangler | CLI tool | Deploy Cloudflare Worker from cmd |

---

## Live URLs
| URL | What it is |
|---|---|
| dropshipping.battersea-dynamics.workers.dev | Live dashboard + API |
| dropshipping.battersea-dynamics.workers.dev/api/results | Latest scan JSON |
| dropshipping.battersea-dynamics.workers.dev/api/push | Push results from Python |
| dropshipping.battersea-dynamics.workers.dev/ebay/notifications | eBay webhook endpoint |

---

## Domains & Email
| Platform | URL | What for |
|---|---|---|
| Spaceship | spaceship.com | Domain registrar — gazza.ltd |
| gazza.ltd | Email forwarding set up via Spaceship | hello@gazza.ltd forwards to Gmail |
| Cloudflare | dash.cloudflare.com | DNS (when gazza.ltd is connected) |

---

## Alerts & Messaging
| Platform | URL | What for |
|---|---|---|
| Telegram | t.me / @BotFather | Scan alerts — bot: @TrendradarIT_bot |

---

## Data Sources — Scanning
| Platform | URL | Status | What we scan |
|---|---|---|---|
| Amazon UK M&S | amazon.co.uk/gp/movers-and-shakers | ✅ Working | Top trending products — 8 categories, 160 products |
| eBay UK | developer.ebay.com | ✅ Working | Most watched items by category — 160 items |
| Reddit | reddit.com | ⚠️ Disabled | Category heat signal — needs better matching approach |
| TikTok Creative Center | ads.tiktok.com/business/creativecenter | ⏳ Pending approval | Trending hashtags UK — developer account applied |
| Google Trends | trends.google.com | ⚠️ Blocked | Needs SerpAPI (~£3/month) — add when revenue starts |
| Meta Ad Library | facebook.com/ads/library | 🔜 Not built | Long-running ads = profitable products |

---

## TikTok Accounts
| Account | URL | Status | What for |
|---|---|---|---|
| TikTok Business Center | business.tiktok.com | ✅ Active | Central hub for all TikTok business tools |
| TikTok Ads Manager | ads.tiktok.com | ✅ Active | Running ads (future) |
| TikTok Developer Portal | business-api.tiktok.com/portal | ⏳ Pending (up to 3 days) | API access for Creative Center trending data |
| TikTok App — TrendRadar | business-api.tiktok.com/portal | ⏳ Pending | App ID + Secret needed for scanner |
| TikTok Shop UK | seller-uk.tiktok.com | 🔜 Future | Selling products (Pillar 3) |

---

## Developer Accounts & APIs
| Platform | URL | Status | Notes |
|---|---|---|---|
| eBay Developer | developer.ebay.com | ✅ Active | App: TrendRadar — keys in .env file |
| TikTok Developer | business-api.tiktok.com/portal | ⏳ Pending | Use hello@gazza.ltd email |
| SerpAPI | serpapi.com | 🔜 When revenue starts | Google Trends — ~£3/month |
| Meta Developer | developers.facebook.com | 🔜 Not started | For Meta Ad Library |
| Reddit Developer | reddit.com/prefs/apps | ⚠️ Blocked | Network blocked during setup — retry later |

---

## Sales Channels (Future — Pillar 3)
| Platform | URL | Status |
|---|---|---|
| Shopify | shopify.com | Not set up yet |
| TikTok Shop UK | seller-uk.tiktok.com | Not set up yet |
| eBay UK seller | ebay.co.uk | Not set up yet |
| Amazon UK seller | sell.amazon.co.uk | Not set up yet |
| OnBuy | onbuy.com/sell | Not set up yet |
| Etsy | etsy.com | Not set up yet |
| Amazon.it | sell.amazon.it | Future — Italy expansion |

---

## Supplier Platforms (Future — Pillar 2)
| Platform | URL | What for |
|---|---|---|
| CJ Dropshipping | cjdropshipping.com | Primary supplier, UK warehouse |
| AliExpress | aliexpress.com | Backup supplier |
| Spocket | spocket.co | EU suppliers |
| DSers | dsers.com | Shopify ↔ AliExpress automation |
| Avasam | avasam.com | UK-native suppliers |

---

## Business & Legal
| Item | Detail |
|---|---|
| UK Ltd Company | Battersea Dynamics |
| VAT | Not registered (below £90k threshold) |
| Tax | Corporation tax only, filed annually |

---

## Key Files in the Repo (dropshipping)
| File | What it does |
|---|---|
| trend_radar.py | Main scanner — runs on your PC |
| worker/scanner.js | Cloudflare Worker — serves API + dashboard |
| index.html | Dashboard — live at dropshipping.battersea-dynamics.workers.dev |
| wrangler.toml | Cloudflare config |
| .env | API keys and secrets — NOT pushed to GitHub |
| .gitignore | Excludes .env and JSON files from GitHub |
| 00_master_context.md | Full business context |
| 01_trend_radar_build.md | Trend radar build notes |
| 02_supplier_engine.md | Supplier finding guide |
| 03_sales_channels.md | Sales channel setup guide |
| 04_expansion_playbook.md | Italy/EU expansion plan |
| platforms_and_accounts.md | This file |

---

## Deployment Rules
| Changed file | Command needed |
|---|---|
| worker/scanner.js | `wrangler deploy` then `git push` |
| Anything else | `git push` only |

---

## Pending Actions
- [ ] Wait for TikTok Developer approval (up to 3 days) → add App ID + Secret to .env
- [ ] Add gazza.ltd to Cloudflare (for custom domain)
- [ ] Upload landing page to gazzaopportunity repo → enable GitHub Pages
- [ ] Fix eBay watch count (currently returns 0)
- [ ] Implement Reddit category heat signal
- [ ] Add SerpAPI for Google Trends when revenue starts
- [ ] Register Meta Developer account
- [ ] Set up Shopify store (Pillar 3)
- [ ] Set up TikTok Shop UK seller account (Pillar 3)
