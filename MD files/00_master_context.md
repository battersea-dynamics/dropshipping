# 00 — Master Context: Dropshipping Business

## What This Project Is
A semi-automated dropshipping business built and operated by one person (the owner), assisted by AI at every stage. The system has three pillars:

1. **Trend Radar** — scans the web daily to find products gaining momentum before they peak
2. **Supplier Engine** — finds and evaluates manufacturers/distributors for any trending product
3. **Sales Channels** — lists and sells products across multiple platforms with maximum automation

No warehousing. No stock. Pure dropshipping: supplier ships directly to customer.

---

## Owner Profile
- Based in **United Kingdom**
- Has an active **UK Ltd company** (below £90k VAT threshold — NOT VAT registered)
- Italian nationality — plans to expand to Italy/EU when ready
- Technical level: low-to-medium coding knowledge, builds apps with Claude + VS Code
- Has already built 2 apps using this workflow

---

## Tech Stack
- **Frontend:** Vite + React
- **Deployment:** Cloudflare Pages (free tier)
- **Backend/API layer:** Cloudflare Workers (free tier — 100k req/day)
- **Storage:** Cloudflare KV (free tier)
- **Scheduled jobs:** Cloudflare Cron Triggers (free)
- **Alerts:** Telegram bot (already set up) — used for trend alerts and daily digest
- **IDE:** VS Code with Claude assistance
- **Version control:** Git / GitHub

---

## Tax & Legal Context
- UK Ltd company — corporation tax on profit only, filed annually
- **No VAT to collect** until £90k turnover threshold is hit
- When selling to EU customers: buyer pays their local VAT/duties at customs — not the owner's responsibility at this stage
- For orders under £135 to UK customers from China: no customs fee for the buyer
- All business expenses (subscriptions, tools, hosting) are tax-deductible — keep records
- When expanding to EU/Italy: OSS (One Stop Shop) VAT registration will be needed — handle at that stage

---

## Markets — Priority Order
1. **UK** — primary market, start here
2. **Italy** — secondary, owner speaks the language, expand when UK is stable
3. **EU (DE, FR, ES)** — tertiary, scale after Italy

---

## Sales Channels (All Separate, One Fulfillment Backend)
| Channel | Status | Notes |
|---|---|---|
| TikTok Shop UK | Start immediately | Most mature TikTok Shop in Western markets |
| eBay UK | Start immediately | Explicitly allows dropshipping |
| Shopify | Start immediately | Master catalog, drives other channels |
| Amazon UK | Start soon | White label or small FBA batches |
| OnBuy | Start soon | UK-only, less saturated than Amazon |
| Etsy | Where relevant | Good for niche/personalised products |
| Amazon.it | Italy expansion | Owner speaks Italian |
| TikTok Shop IT | Future | Not yet live in Italy |

**Architecture principle:** Shopify is the master product catalog. All other channels are satellites. One fulfillment system handles all orders regardless of channel.

---

## Fulfillment Stack (Free to Start)
- **DSers** (free plan) — Shopify ↔ AliExpress auto-fulfillment
- **CJ Dropshipping** — free account, API available, has UK warehouse (no customs issues)
- **Zendrop** — backup, free tier
- Supplier ships directly to customer — owner never touches stock

---

## Supplier Strategy
- **Priority 1:** CJ Dropshipping UK warehouse stock (zero customs, fast delivery)
- **Priority 2:** EU-based suppliers via Spocket/Ankorstore (fast EU delivery)
- **Priority 3:** Chinese suppliers via AliExpress/Alibaba (cheapest, slower)
- White-label packaging preferred — no supplier branding on parcels
- Minimum order = 1 unit (true dropship model)

---

## Product Criteria (What Makes a Good Product)
- Supplier price: under £15
- Target selling price: £35–£65
- Minimum margin: £20 per unit
- Not easily found on Amazon UK already
- Solves a visible problem OR creates a strong desire
- Lightweight (cheaper to ship)
- Not fragile, not regulated (no electronics with safety certs, no food, no cosmetics initially)

---

## Free-First Philosophy
Try every free tier first. Only pay for a tool if:
- Free tier is genuinely blocking progress, AND
- The paid tool has no free alternative

Current paid tools budget: £0 until revenue starts.

---

## Expansion Triggers (When to Move to Italy/EU)
- UK monthly revenue consistently above £2,000
- At least 2 products proven to sell repeatedly
- Owner has bandwidth to manage a second market
- See `04_expansion_playbook.md` for full detail

---

## File Map
| File | Purpose |
|---|---|
| `00_master_context.md` | This file — shared context for all chats |
| `01_trend_radar_build.md` | Build the Vite + Cloudflare trend scanning app |
| `02_supplier_engine.md` | Find, evaluate and contact suppliers |
| `03_sales_channels.md` | Set up and automate all sales platforms |
| `04_expansion_playbook.md` | Italy and EU expansion plan |

---

## How to Use These Files
Each MD file is a **self-contained briefing** for a Claude chat. When starting a new chat for a specific pillar:
1. Paste `00_master_context.md` first
2. Then paste the relevant pillar MD file
3. Tell Claude: *"Read both files and help me execute this"*

The chat will have full context and can guide you step by step without you re-explaining the business.
