# 02 — Supplier Engine

## Context
Read `00_master_context.md` before this file. This chat handles Pillar 2: given a product name (usually coming from the Trend Radar), find the best supplier to dropship it from, evaluate them, and prepare outreach if needed.

---

## What This Pillar Does
1. Takes a product name as input
2. Queries multiple supplier databases simultaneously
3. Returns a scored comparison of available suppliers
4. Flags which suppliers support white-label, UK warehouse, API integration
5. Generates a contact/outreach email for suppliers without API access
6. Feeds the winning supplier back into Pillar 3 (sales channel setup)

---

## Supplier Sources — Priority Order

### Tier 1: API-Connected (Fully Automated)

**CJ Dropshipping**
- Free account at cjdropshipping.com
- Has a proper REST API — search products, get prices, check stock
- **Key advantage: UK warehouse** — orders from UK stock = no customs, 3–5 day delivery
- Supports white-label packaging (request per product)
- API docs: https://cjdropshipping.com/api-doc.html
- What to query: product search by keyword, filter by warehouse=UK first, then global

**AliExpress Affiliate API**
- Free via AliExpress affiliate program registration
- Search products, get prices, order counts, shipping options
- Filter by: ePacket shipping available, min order = 1
- Order count is a proxy for demand — 1000+ orders on a new product = validated

**Spocket**
- EU and US suppliers, faster shipping than China
- Free plan allows browsing but not ordering — need paid plan to fulfil
- Use free plan for supplier research and pricing only
- Particularly good for: homeware, beauty, pet products from EU suppliers

**Syncee**
- Global supplier network, free tier available
- Good coverage of EU suppliers
- API available on paid plan — use manually for now

### Tier 2: Manual Search (No API, High Value)

**Alibaba**
- Best for finding the actual manufacturer (not a reseller)
- No official product search API — use web search approach
- Search: `site:alibaba.com [product name]`
- Look for: "Verified Supplier" badge, Trade Assurance, 3+ years on platform
- Good for negotiating custom packaging and lower unit prices at small MOQ

**Ankorstore**
- European wholesale marketplace, UK-accessible
- Brands with minimum orders often as low as €100
- Good for differentiated products not on AliExpress
- No dropship API — manual ordering, not ideal for automation

**Faire**
- Similar to Ankorstore, strong in UK/EU
- Independent brands, artisan products
- Good for Etsy-type products

**Google Search Operators**
Use these to find direct suppliers not on marketplaces:
```
"[product name]" "dropship" "wholesale" "UK"
"[product name]" "private label" "no minimum order"
"[product name]" supplier site:.co.uk
"[product name]" manufacturer "OEM" "MOQ 1"
```

---

## Supplier Evaluation Scorecard

For each supplier found, score them on these criteria:

| Criterion | Weight | How to check |
|---|---|---|
| Price (margin potential) | High | (Amazon UK sell price - supplier price) / sell price > 50% |
| Shipping time to UK | High | Under 7 days = best, 7–14 = acceptable, 15+ = flag |
| White label available | Medium | Ask directly or check product page |
| UK/EU warehouse stock | High | Check warehouse options in their platform |
| API or app integration | Medium | Does it connect to Shopify/DSers automatically? |
| Minimum order quantity | High | Must be 1 unit for true dropshipping |
| Return policy | Medium | Do they accept returns? Who pays? |
| Seller reviews/rating | Medium | 4.5+ stars, 50+ reviews minimum |
| Order fulfilment speed | High | How fast do they process and ship after order? |

**Scoring:**
- 8–9 criteria met: ✅ Use this supplier
- 5–7 criteria met: 🟡 Acceptable, note the gaps
- Under 5: ❌ Skip unless no alternatives exist

---

## Margin Calculator (Apply to Every Product)

```
Supplier price (landed cost):     £___
Shipping cost to customer:        £___  (often included in supplier price)
Platform fees (% of sale price):  £___
  - Shopify: £0 per transaction (own store)
  - eBay: ~12% of sale price
  - Amazon: ~15% of sale price
  - TikTok Shop: ~5% currently
  - Etsy: ~10% total fees
Payment processing (Stripe etc):  ~2.5%
Total cost:                       £___

Target sell price:                £___
Gross margin per unit:            £___
Margin %:                         ___%

Target: minimum £20 margin, minimum 40% margin %
```

---

## Outreach Email Template

Use this when a supplier has no API and needs to be contacted directly:

```
Subject: Dropshipping Partnership Enquiry — [Your Ltd Company Name]

Hi [Supplier name],

I'm reaching out from [Ltd Name], a UK-registered e-commerce business.

I'm interested in dropshipping your [product name/category] to UK and European customers.

Could you confirm:
1. Do you offer dropshipping (ship directly to my customers, 1 unit minimum)?
2. Can you ship without your company branding on the parcel (white label)?
3. What is your typical dispatch time after order placement?
4. Do you have a product feed (CSV, API, or Shopify app) for inventory sync?
5. What is your wholesale pricing for [product]?

We are looking to start with initial test orders and scale quickly if results are positive.

Looking forward to hearing from you.

[Your name]
[Ltd Company Name]
[Your email]
[Website if available]
```

---

## What to Build (Integration with Trend Radar)

The Supplier Engine can start as a **manual research process** guided by this document, then be automated progressively.

### Phase 1 — Manual (Start Here)
- Trend Radar flags a product
- You manually search CJ Dropshipping and AliExpress using the product name
- Apply the scorecard
- Record the winning supplier in a simple Google Sheet or Notion table

### Phase 2 — Semi-Automated
Add a feature to the Trend Radar app:
- "Find Supplier" button on each product card
- Clicking it calls the CJ Dropshipping API and AliExpress API
- Returns a side-by-side comparison using the scorecard
- Highlights best option automatically

### Phase 3 — Fully Automated
- Trend Radar auto-triggers supplier search when a product scores 60+
- Supplier results stored in Cloudflare KV alongside trend data
- Dashboard shows "Supplier found: CJ UK warehouse, £8.50, 4-day delivery" directly on product card

---

## Supplier Tracking Sheet (Keep This Updated)

Maintain a record for every supplier you work with:

| Product | Supplier | Platform | Price | Ship time | White label | API connected | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

---

## Key Rules
- **Never commit to a supplier before selling one unit** — test the full order flow first (order to yourself)
- **Always order a test product** before listing — check quality, packaging, actual delivery time
- **Have a backup supplier** for any product generating consistent sales
- **CJ UK warehouse first** — always check UK stock before defaulting to China shipping
- Post-Brexit, Chinese goods to UK customers: under £135 = no customs for buyer. Over £135 = buyer may face customs fees. Keep products under this threshold where possible.
