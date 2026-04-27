# 03 — Sales Channels Setup & Automation

## Context
Read `00_master_context.md` before this file. This chat handles Pillar 3: setting up every sales channel, connecting them to one fulfillment backend, and automating as much of the order flow as possible.

---

## Architecture Principle
**Shopify = master catalog. Everything else = satellite.**

You manage products in one place (Shopify). Listings push out to other channels from there. All orders — regardless of channel — route to the same fulfillment system (CJ Dropshipping / DSers). You never manually forward an order.

```
[Shopify Master Catalog]
        ↓ sync
[eBay] [TikTok Shop] [OnBuy] [Etsy] [Amazon*]
        ↓ all orders
[DSers / CJ Dropshipping]
        ↓
[Supplier ships to customer]

*Amazon managed separately due to different rules
```

---

## Channel Setup — Priority Order

### 1. Shopify (Master Store)

**Setup steps:**
1. Sign up at shopify.com — use the 3-day free trial + £1/month for 3 months offer
2. Choose a clean, fast theme — "Dawn" (free default) is fine to start
3. Domain: buy a `.co.uk` domain via Cloudflare Registrar (~£8/year, cheapest option)
4. Connect Shopify Payments — requires Ltd company details + bank account
5. Install **DSers** app (free plan) — connects to AliExpress
6. Install **CJ Dropshipping** app (free) — connects to CJ for UK warehouse stock
7. Set up basic pages: About, Contact, Returns Policy, Privacy Policy (use Shopify's auto-generator)
8. Set up shipping zones: UK standard, EU standard, Rest of World
9. **Important:** In Shopify tax settings, set "I am not VAT registered" — do not charge VAT until you hit the threshold

**First product listing checklist:**
- [ ] Product title: clear, searchable, includes main keyword
- [ ] Description: benefit-focused, not spec-focused. Use AI to write this.
- [ ] Images: at least 4, white background main image + lifestyle shots
- [ ] Price: set to your target sell price with margin applied
- [ ] Weight/dimensions: needed for accurate shipping rates
- [ ] Inventory: set to "don't track inventory" for dropshipping
- [ ] Fulfillment: linked to DSers or CJ app for auto-fulfillment

---

### 2. TikTok Shop UK

**Why prioritise this:**
TikTok Shop UK is the least saturated major sales channel right now. The affiliate system means creators promote your products for free — you only pay commission on sales made.

**Setup steps:**
1. Go to seller-uk.tiktok.com
2. Register with your Ltd company details (Companies House number, UTR or corporation tax reference)
3. Bank account must match Ltd company name
4. Upload products — can sync from Shopify via TikTok's Shopify app (free)
5. Set up the **Affiliate Program**: set a commission rate (10–20% is standard) — creators will find your products and promote them organically

**TikTok-specific product requirements:**
- High visual impact — products that look impressive in a 15-second video
- Clear "wow factor" or problem-solving demonstration
- Good quality images and at minimum one short video clip

**Fulfillment:** TikTok Shop UK supports dropshipping — you fulfill via your supplier as normal. Dispatch must be within 3 business days. CJ UK warehouse is ideal for this.

---

### 3. eBay UK

**Why include this:**
eBay explicitly allows dropshipping. It has built-in traffic. It's the fastest channel to get a first sale on.

**Setup steps:**
1. Create eBay business account using Ltd company details
2. Verify identity + bank account
3. Start with 10 free listings (new accounts are limited — limits increase as you sell)
4. List products manually at first — use eBay's listing tool
5. When you have 20+ products, install **AutoDS** (has a free trial) to sync from Shopify to eBay automatically

**eBay-specific tips:**
- Offer free shipping (build it into price) — converts better
- Use eBay's "Best Match" algorithm — it rewards fast dispatch and good feedback
- Aim for 1-day dispatch — achievable with CJ UK warehouse
- Price slightly below Amazon for the same product — eBay buyers are price-sensitive

**Fulfillment note:** You are allowed to dropship on eBay but you must be listed as the seller of record. CJ/AliExpress packing slips must not show their name — request white label.

---

### 4. OnBuy

**Why include this:**
UK-only marketplace, far less competition than Amazon, explicitly allows dropshipping. Growing fast.

**Setup steps:**
1. Register at onbuy.com/sell
2. £49 one-time setup fee (worth it — waived sometimes with promo codes, check before paying)
3. Monthly subscription: £19–£39 depending on plan
4. Upload product feed via CSV or their API
5. No fulfillment service — you ship directly (via your supplier)

**Note:** OnBuy is the only channel here with a small upfront cost. Defer until you have first sales from eBay/TikTok Shop if budget is tight.

---

### 5. Amazon UK

**Why it's separate:**
Amazon has different rules — pure dropshipping (AliExpress → customer) violates their policy. You must be the seller of record and control the packaging. Two compliant approaches:

**Option A — White Label Dropship:**
- Use CJ Dropshipping UK warehouse with your branding on parcels
- List on Amazon, CJ fulfills — technically compliant because the customer sees your brand
- Slower to set up but scalable

**Option B — FBA Test Batches:**
- Buy 20–30 units from supplier
- Send to Amazon FBA warehouse
- Amazon handles fulfillment, returns, customer service
- Low risk because small quantities — if it sells, reorder and scale

**Setup steps:**
1. Register at sell.amazon.co.uk — Individual plan (£0.75/item sold) or Professional (£25/month)
2. Start with Individual plan until you're selling 40+ items/month
3. EAN/barcode required for most products — buy from GS1 UK (£49 for 1 barcode, or buy cheap ones from Speedy Barcodes for testing)
4. Product images must meet Amazon standards: pure white background, product fills 85% of frame
5. For FBA: create shipment plan in Seller Central, print labels, ship to Amazon warehouse

---

### 6. Etsy

**Best for:**
Personalised products, niche items, homeware, gifts. Less price competition than Amazon.

**Setup steps:**
1. Open Etsy shop — free, just needs a bank account
2. 20p listing fee per item, 6.5% transaction fee on sale
3. Products can be dropshipped — just must be handmade, vintage, or "craft supplies" (broad interpretation possible)
4. For genuine dropship products: list as "craft supplies" or find items that genuinely fit Etsy's categories
5. Etsy has its own search algorithm — keyword research matters, use **EverBee** (free tier) for Etsy SEO

---

## Automation Stack

### Order Fulfillment (Most Important)
- **DSers (free):** Shopify orders → auto-sent to AliExpress supplier. One-click fulfillment or full auto.
- **CJ Dropshipping app (free):** Same but for CJ. Preferred because of UK warehouse.
- These apps mark orders as fulfilled and add tracking numbers automatically.

### Channel Sync
- **TikTok Shop ↔ Shopify:** Official TikTok Shopify app (free) — syncs inventory and orders
- **eBay ↔ Shopify:** Shopify's official eBay sales channel app (free for basic) — syncs listings
- **Amazon ↔ Shopify:** Shopify's Amazon sales channel or Codisto (paid) — manual sync is fine to start

### Pricing Automation
Set pricing rules once, apply to all products:
- Cost from supplier × 3 = listing price (rough starting rule)
- Adjust per channel: Amazon price slightly higher to cover 15% fees, eBay slightly lower
- Use Shopify's bulk price editor when adjusting margins

### Customer Service
- All channels send order/query notifications to your email
- Use a dedicated business email (set up free with Cloudflare Email or Google Workspace £5/month)
- **Response time target:** under 24 hours — this protects your seller ratings on all platforms
- Write template responses for: "where is my order", "item not as described", "I want a return"

---

## Returns Policy (Keep Simple)
Standard policy for all channels:
- 30-day returns accepted
- Buyer pays return shipping (standard for dropshipping)
- Refund processed within 5 days of receiving return
- For cheap items under £15: just refund without requesting return (saves admin)

For items lost in shipping: CJ and AliExpress both have buyer protection — you can claim from them, then refund the customer. You're rarely out of pocket.

---

## Launch Sequence (Do This in Order)

**Week 1:**
- [ ] Shopify store live with first 3 products
- [ ] DSers or CJ app connected and tested (place a test order to yourself)
- [ ] TikTok Shop UK account approved and first product listed

**Week 2:**
- [ ] eBay business account live, first 5 listings
- [ ] Shopify ↔ TikTok sync confirmed working
- [ ] First affiliate creator found for TikTok (search your product hashtag, message 10 creators)

**Week 3:**
- [ ] Amazon Individual account live
- [ ] First Amazon listing (white label via CJ UK warehouse)
- [ ] Etsy shop open if products fit

**Week 4:**
- [ ] Review what's working — double down on the best channel
- [ ] OnBuy if budget allows
- [ ] Analyse: which channel got first sale? Which has best margin after fees?

---

## Metrics to Track (Weekly)
| Metric | Target |
|---|---|
| Orders per channel | Track separately |
| Margin per channel (after fees) | >£20 per order |
| Dispatch time | <2 business days |
| Seller feedback score | >98% positive |
| Return rate | <5% |
| Best selling product | Double its listings |

---

## Notes for the Claude Chat Building This
- Set up channels one at a time — don't try to do all simultaneously
- Test the full order flow on each channel before moving to next (buy from yourself)
- Shopify first, then TikTok Shop, then eBay — this order matters
- If a channel requires manual work that can't be automated yet, note it and revisit after revenue starts
- The goal in month 1 is: first sale on at least 2 channels, full automation on at least 1
