"""
TREND RADAR v2 — UK Dropshipping Intelligence
==============================================
Scans Amazon UK Movers & Shakers daily to discover
trending products worth dropshipping.

No keywords needed — discovery mode only.
Results pushed to Cloudflare KV and sent via Telegram.

Usage:
    python trend_radar.py        → run scan immediately
    python trend_radar.py auto   → run on schedule (08:00 + 20:00)

Dependencies:
    pip install -r requirements.txt
    playwright install chromium
"""

import os
import re
import json
import time
import logging
import schedule
import requests
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
load_dotenv(override=True)

# ── CONFIG ────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")
CLOUDFLARE_PUSH_URL = os.getenv("CLOUDFLARE_PUSH_URL", "")

# eBay API credentials — add when developer account is approved
# Register at: https://developer.ebay.com

TIKTOK_APP_ID     = os.getenv("TIKTOK_APP_ID", "")
TIKTOK_APP_SECRET = os.getenv("TIKTOK_APP_SECRET", "")

EBAY_APP_ID  = os.getenv("EBAY_APP_ID", "")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID", "")

# Shared secret required by the Worker's POST /api/push endpoint.
# Must match the value set with: wrangler secret put PUSH_SECRET
PUSH_SECRET = os.getenv("PUSH_SECRET", "")

SCHEDULE_TIMES      = ["08:00", "20:00"]
AMAZON_MAX_PRODUCTS = 20

# Each eBay price check is one API call — only run them for the
# highest-ranked products rather than the whole scan.
EBAY_MAX_LOOKUPS = 25

# Minimum number of shared meaningful words before a cross-source match is
# accepted. Below this a "match" is noise: this threshold is what stops the
# medicube-eye-serum -> Amouage-perfume false positive seen in the 17/05 scan.
MIN_TOKEN_OVERLAP = 2

AMAZON_CATEGORIES = {
    "beauty":     "beauty",
    "kitchen":    "kitchen",
    "pet":        "pet-supplies",
    "tech":       "electronics",
    "diy":        "diy",
    "baby":       "baby",
    "automotive": "automotive",
    "music":      "musical-instruments",
    "health":     "health-personal-care",
    "sport":      "sports",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}


# ── TEXT MATCHING ─────────────────────────────────────────────────────────────
#
# Cross-source matching used to compare categories only, which meant every
# product in a category "matched" every trend in that category. Everything
# below exists so that a match has to be backed by shared words.

STOPWORDS = {
    "the", "and", "for", "with", "your", "from", "that", "this", "you", "our",
    "pack", "set", "pcs", "piece", "pieces", "size", "new", "free", "gift",
    "gifts", "best", "premium", "quality", "professional", "original", "official",
    "genuine", "kit", "pro", "plus", "max", "mini", "large", "small", "medium",
    "black", "white", "blue", "red", "green", "pink", "grey", "gray", "silver",
    "gold", "colour", "color", "inch", "count", "pcs", "each", "type", "style",
    "home", "super", "ultra", "heavy", "duty", "multi", "made", "including",
}

_TOKEN_RE = re.compile(r"[a-z]+")


def tokens(text: str) -> set:
    """Lowercased, de-noised words used for cross-source matching."""
    if not text:
        return set()
    return {
        t for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 3 and t not in STOPWORDS
    }


def token_overlap(a: str, b: str) -> int:
    """How many meaningful words two product/keyword strings share."""
    return len(tokens(a) & tokens(b))


def hashtag_match(product_name: str, hashtag: str) -> bool:
    """
    Whether a hashtag genuinely refers to this product.

    Hashtags are written as one run-together word (#retinolserum,
    #skincareroutine), so plain word-boundary overlap never fires on them.
    Test containment instead — but containment alone is too loose, because
    "Resistance Bands" is contained in #bandsofbrothers. So also require the
    matched words to account for most of the hashtag.
    """
    tag = re.sub(r"[^a-z]", "", str(hashtag).lower())
    if not tag:
        return False
    hits = [t for t in tokens(product_name) if t in tag]
    if not hits:
        return False
    coverage = min(1.0, sum(len(t) for t in hits) / len(tag))
    return coverage >= 0.5


# ── LOGGING ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("TrendRadar")


# ── DATA MODEL ────────────────────────────────────────────────────────────────

@dataclass
class Product:
    name:          str
    rank:          int
    category:      str
    url:           str
    sources:       list = field(default_factory=list)
    reddit_title:  Optional[str] = None
    reddit_url:    Optional[str] = None
    reddit_score:  int = 0
    ebay_name:         Optional[str] = None
    ebay_url:          Optional[str] = None
    ebay_listings:     int = 0
    ebay_median_price: float = 0.0
    ebay_low_price:    float = 0.0
    tiktok_hashtag:    Optional[str] = None
    tiktok_posts:      int = 0
    pinterest_keyword: Optional[str] = None
    detected_at:   str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    # ── SCORING ───────────────────────────────────────────────────────────────
    # The old rule was: STRONG if len(sources) >= 2 and rank <= 10. Because the
    # eBay step handed every product an (unrelated) match, len(sources) was
    # always >= 2, so every top-10 product was reported STRONG. Every component
    # below now requires a verified match, and each one is shown to the user.

    def score_breakdown(self) -> list:
        parts = []

        if   self.rank <= 5:  parts.append(("Amazon M&S rank 1-5", 40))
        elif self.rank <= 15: parts.append(("Amazon M&S rank 6-15", 25))
        elif self.rank <= 30: parts.append(("Amazon M&S rank 16-30", 10))

        if self.tiktok_hashtag:
            parts.append((f"TikTok hashtag #{self.tiktok_hashtag}", 20))
        if self.pinterest_keyword:
            parts.append((f"Pinterest trend '{self.pinterest_keyword}'", 10))
        if self.reddit_title:
            parts.append(("Reddit mention", 10))

        # eBay is a saturation signal, not a demand signal — see eBayScanner.
        if self.ebay_listings:
            if self.ebay_listings < 100:
                parts.append((f"Low eBay competition ({self.ebay_listings} listings)", 15))
            elif self.ebay_listings > 1000:
                parts.append((f"Saturated on eBay ({self.ebay_listings} listings)", -15))

        confirmations = sum(
            1 for x in (self.tiktok_hashtag, self.pinterest_keyword, self.reddit_title) if x
        )
        if confirmations >= 2:
            parts.append((f"Confirmed by {confirmations} independent sources", 15))

        return parts

    @property
    def score(self) -> int:
        return max(0, min(100, sum(points for _, points in self.score_breakdown())))

    @property
    def strength(self) -> str:
        s = self.score
        if s >= 65: return "STRONG"
        if s >= 40: return "MEDIUM"
        return "WEAK"

    def to_dict(self) -> dict:
        return {
            "keyword":       self.name,
            "amazon_rank":   self.rank,
            "amazon_name":   self.name,
            "amazon_url":    self.url,
            "category":      self.category,
            "sources":       self.sources,
            "strength":      self.strength,
            "score":         self.score,
            "score_reasons": [f"{label} ({pts:+d})" for label, pts in self.score_breakdown()],
            "reddit_title":  self.reddit_title,
            "reddit_url":    self.reddit_url,
            "reddit_score":  self.reddit_score,
            "ebay_name":         self.ebay_name,
            "ebay_url":          self.ebay_url,
            # The Browse API does not expose watch counts without a separate
            # App Check grant from eBay. Reported as null rather than faked.
            "ebay_watches":      None,
            "ebay_listings":     self.ebay_listings,
            "ebay_median_price": self.ebay_median_price,
            "ebay_low_price":    self.ebay_low_price,
            "tiktok_hashtag":    self.tiktok_hashtag,
            "tiktok_posts":      self.tiktok_posts,
            "pinterest_keyword": self.pinterest_keyword,
            "trends_score":  0,
            "trends_growth": 0,
            "detected_at":   self.detected_at,
        }


# ── AMAZON SCANNER ────────────────────────────────────────────────────────────

class AmazonScanner:
    """
    Scrapes Amazon UK Movers & Shakers across all categories.
    Returns top trending products — no keywords needed.
    """

    BASE_URL  = "https://www.amazon.co.uk/gp/movers-and-shakers/{category}"
    SELECTORS = [
        ".p13n-desktop-grid li",
        "li.zg-item-immersion",
        "div.zg-item-immersion",
        "li[class*='zg-item']",
    ]

    def __init__(self):
        # One session for all categories — keeps the connection alive and
        # carries cookies between requests, which reduces bot challenges.
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scan_all(self) -> list[Product]:
        all_products = []
        for label, slug in AMAZON_CATEGORIES.items():
            log.info(f"[Amazon] Scanning: {label}")
            try:
                products = self._scrape_category(label, slug)
                all_products.extend(products)
                log.info(f"[Amazon] {label}: {len(products)} products found")
                time.sleep(3)
            except Exception as e:
                log.warning(f"[Amazon] Error scanning {label}: {e} — retrying in 5s")
                time.sleep(5)
                try:
                    products = self._scrape_category(label, slug)
                    all_products.extend(products)
                    log.info(f"[Amazon] {label} (retry): {len(products)} products found")
                except Exception as e2:
                    log.warning(f"[Amazon] {label} retry failed: {e2} — skipping")
        log.info(f"[Amazon] Total products discovered: {len(all_products)}")
        return all_products

    def _scrape_category(self, label: str, slug: str) -> list[Product]:
        url      = self.BASE_URL.format(category=slug)
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        soup     = BeautifulSoup(response.text, "html.parser")
        items    = []

        for selector in self.SELECTORS:
            items = soup.select(selector)[:AMAZON_MAX_PRODUCTS]
            if items:
                log.info(f"[Amazon] Selector: '{selector}' ({len(items)} items)")
                break

        if not items:
            # When this happens it is nearly always a bot check rather than a
            # layout change, and the two need completely different fixes — so
            # print enough to tell them apart instead of silently returning [].
            title = (soup.title.get_text(strip=True) if soup.title else "")[:80]
            log.warning(
                f"[Amazon] {label}: no items matched any selector "
                f"(page_title={title!r}, bytes={len(response.text)}). "
                f"A title mentioning 'Robot Check' or 'Sorry' means Amazon is "
                f"blocking this IP; otherwise the CSS selectors need updating."
            )

        return [p for item in items for p in [self._parse_item(item, label)] if p]

    def _parse_item(self, item, category: str) -> Optional[Product]:
        rank_el = (
            item.select_one(".zg-badge-text") or
            item.select_one("span.zg-bdg-text") or
            item.select_one("[class*='badge']")
        )
        name_el = (
            item.select_one(".p13n-sc-truncate") or
            item.select_one(".p13n-sc-line-clamp-1") or
            item.select_one("._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y") or
            item.select_one("a span") or
            item.select_one(".a-size-small.a-color-base")
        )
        link_el = item.select_one("a.a-link-normal")

        if not (rank_el and name_el):
            return None

        rank_text = rank_el.get_text(strip=True).replace("#", "").replace(",", "").replace(".", "")
        try:
            rank = int(rank_text)
        except ValueError:
            return None

        return Product(
            name     = name_el.get_text(strip=True),
            rank     = rank,
            category = category,
            url      = ("https://www.amazon.co.uk" + link_el["href"]) if link_el else "",
            sources  = ["Amazon M&S"]
        )

# ── TIKTOK SCANNER ────────────────────────────────────────────────────────────

class TikTokScanner:
    """
    Fetches trending hashtags from TikTok Creative Center via Playwright.
    Opens a headless browser and intercepts the hashtag API response.
    """

    INDUSTRY_MAP = {
        "Beauty & Personal Care": "beauty",
        "Household Products":     "kitchen",
        "Pets":                   "pet",
        "Tech & Electronics":     "tech",
        "Home Improvement":       "diy",
        "Baby, Kids & Maternity": "baby",
        "Vehicle & Trans":        "automotive",
        "Sports & Outdoor":       "sport",
        "Health":                 "health",
        "Apparel & Accessories":  "clothing",
    }

    def scan(self) -> list[dict]:
        """
        Fetches top trending hashtags from TikTok Creative Center via Playwright.
        Returns: [{ "hashtag": str, "posts": int, "category": str, "rank": int }]
        """
        results = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
                    locale="en-GB",
                )
                page = context.new_page()
                log.info("[TikTok] Opening Creative Center...")

                hashtag_data = []
                def handle_response(response):
                    if "popular_trend/hashtag/list" in response.url:
                        try:
                            data = response.json()
                            if data.get("code") == 0:
                                hashtag_data.extend(data.get("data", {}).get("list", []))
                                log.info(f"[TikTok] Intercepted {len(hashtag_data)} hashtags")
                        except Exception:
                            pass

                page.on("response", handle_response)
                page.goto("https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(10000)
                browser.close()

                for i, item in enumerate(hashtag_data):
                    hashtag  = item.get("hashtag_name", "")
                    posts    = item.get("publish_cnt", 0)
                    industry = item.get("industry_name", "")
                    category = self.INDUSTRY_MAP.get(industry, "general")
                    results.append({
                        "hashtag":  hashtag,
                        "posts":    posts,
                        "category": category,
                        "industry": industry,
                        "rank":     i + 1,
                    })
                    log.info(f"[TikTok] #{i+1} #{hashtag} — {posts} posts ({industry})")

        except Exception as e:
            log.warning(f"[TikTok] Playwright error: {e}")
        return results

    def match_product(self, product: object, tiktok_trends: list[dict]) -> Optional[dict]:
        """
        Returns the trending hashtag that genuinely relates to this product,
        or None.

        The previous version accepted `category_match OR keyword_match`, and
        category_match was true for every product in the category — so every
        beauty product was credited with the biggest hashtag in beauty. The
        hashtag must now actually name the product; category only breaks ties
        between hashtags that already match.
        """
        name     = getattr(product, "name", "")
        category = getattr(product, "category", "")

        best_match = None
        best_key   = (0, 0)   # (same category, post count)

        for trend in tiktok_trends:
            if not hashtag_match(name, trend.get("hashtag", "")):
                continue
            key = (1 if trend.get("category") == category else 0,
                   trend.get("posts", 0))
            if key > best_key:
                best_key, best_match = key, trend

        return best_match

# ── PINTEREST SCANNER ────────────────────────────────────────────────────────

class PinterestScanner:
    """
    Fetches trending keywords from Pinterest Trends via Playwright.
    Opens headless Chrome, intercepts the trends API response.
    No API key required.
    """

    CATEGORY_MAP = {
        "beauty":           "beauty",
        "hair":             "beauty",
        "skincare":         "beauty",
        "makeup":           "beauty",
        "health":           "health",
        "wellness":         "health",
        "fitness":          "sport",
        "exercise":         "sport",
        "sport":            "sport",
        "home decor":       "kitchen",
        "kitchen":          "kitchen",
        "cooking":          "kitchen",
        "food":             "kitchen",
        "pets":             "pet",
        "dogs":             "pet",
        "cats":             "pet",
        "technology":       "tech",
        "gadgets":          "tech",
        "electronics":      "tech",
        "diy":              "diy",
        "home improvement": "diy",
        "baby":             "baby",
        "kids":             "baby",
        "parenting":        "baby",
        "automotive":       "automotive",
        "cars":             "automotive",
        "music":            "music",
    }

    def scan(self) -> list[dict]:
        """
        Opens trends.pinterest.com via Playwright and intercepts the trends API call.
        Returns: [{ "keyword": str, "category": str, "rank": int }]
        Logs a warning and returns [] on any error — never crashes.
        """
        results = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="en-GB",
                )
                page = context.new_page()
                log.info("[Pinterest] Opening trends.pinterest.com...")

                trend_data = []

                def handle_response(response):
                    url = response.url
                    if "pinterest.com" not in url:
                        return
                    if not any(k in url for k in ["trend", "keyword", "search", "popular", "explore"]):
                        return
                    try:
                        body = response.json()
                        # Handle various Pinterest API response shapes
                        keywords = (
                            body.get("data", {}).get("results") or
                            body.get("data", {}).get("keywords") or
                            body.get("data", {}).get("trends") or
                            body.get("keywords") or
                            body.get("results") or
                            body.get("trends") or
                            []
                        )
                        if keywords and isinstance(keywords, list) and len(keywords) > 0:
                            trend_data.extend(keywords)
                            log.info(f"[Pinterest] Intercepted {len(keywords)} items from {url[:80]}")
                    except Exception:
                        pass

                page.on("response", handle_response)
                page.goto("https://trends.pinterest.com/?country=gb", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(5000)
                browser.close()

            if not trend_data:
                log.warning("[Pinterest] No trend data intercepted — skipping")
                return []

            for i, item in enumerate(trend_data[:20]):
                keyword = (
                    item.get("keyword") or
                    item.get("query") or
                    item.get("name") or
                    item.get("term") or
                    (item if isinstance(item, str) else "")
                )
                if not keyword:
                    continue
                category = self._map_category(str(keyword))
                results.append({"keyword": keyword, "category": category, "rank": i + 1})
                log.info(f"[Pinterest] #{i+1} {keyword} → {category}")

            log.info(f"[Pinterest] {len(results)} trending keywords found")

        except Exception as e:
            log.warning(f"[Pinterest] Playwright error: {e} — skipping")

        return results

    def _map_category(self, name: str) -> str:
        name_lower = name.lower()
        for key, val in self.CATEGORY_MAP.items():
            if key in name_lower:
                return val
        return "general"

    def match_product(self, product: object, pinterest_trends: list[dict]) -> Optional[dict]:
        """
        Returns the trending Pinterest keyword that genuinely relates to this
        product, or None.

        The previous version returned the first trend sharing the product's
        category, so every product in a category received the same "match".
        """
        name     = getattr(product, "name", "")
        category = getattr(product, "category", "")

        best_match   = None
        best_overlap = 0

        for trend in pinterest_trends:
            overlap = token_overlap(name, str(trend.get("keyword", "")))
            if overlap < 1:
                continue
            if overlap < MIN_TOKEN_OVERLAP and trend.get("category") != category:
                continue
            if overlap > best_overlap:
                best_overlap, best_match = overlap, trend

        return best_match


# ── GOOGLE TRENDS SCANNER (commented out — activate when ready) ───────────────
#
# To activate:
# 1. Sign up at serpapi.com (~£3/month)
# 2. Add SERPAPI_KEY=your_key to .env
# 3. pip install google-search-results
# 4. Uncomment this entire class
# 5. In TrendRadar.__init__(), add:
#        self.google_trends = GoogleTrendsScanner()
# 6. In TrendRadar.run(), add a scan call per product:
#        trend = self.google_trends.scan(product.name)
#        if trend["growing"]:
#            product.sources.append("Google Trends")
#
# class GoogleTrendsScanner:
#     """
#     Checks Google Trends for a product or keyword using SerpAPI.
#     Signal: if last timelineData value > first value, trend is growing.
#     """
#
#     def scan(self, query: str) -> dict:
#         """
#         Returns trend info for a product name.
#         Result: { "query": str, "growing": bool, "score": int }
#         """
#         import serpapi
#         SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
#         if not SERPAPI_KEY:
#             log.warning("[Google Trends] SERPAPI_KEY not set — skipping")
#             return {"query": query, "growing": False, "score": 0}
#
#         try:
#             client = serpapi.Client(api_key=SERPAPI_KEY)
#             results = client.search({
#                 "engine": "google_trends",
#                 "q":      query,
#                 "geo":    "GB",
#                 "date":   "today 3-m",
#             })
#
#             timeline = results.get("interest_over_time", {}).get("timeline_data", [])
#             if len(timeline) < 2:
#                 return {"query": query, "growing": False, "score": 0}
#
#             first_val = timeline[0]["values"][0].get("extracted_value", 0)
#             last_val  = timeline[-1]["values"][0].get("extracted_value", 0)
#             growing   = last_val > first_val
#             score     = last_val
#             growth    = round(((last_val - first_val) / first_val) * 100) if first_val > 0 else 0
#
#             log.info(f"[Google Trends] '{query}': {first_val} → {last_val} ({growth:+d}% {'↑' if growing else '↓'})")
#             return {"query": query, "growing": growing, "score": score, "growth": growth}
#
#         except Exception as e:
#             log.warning(f"[Google Trends] Error for '{query}': {e}")
#             return {"query": query, "growing": False, "score": 0}

# ── EBAY PRICE & SATURATION SCANNER ───────────────────────────────────────────

class eBayScanner:
    """
    Looks up what a product actually sells for on eBay UK, and how many people
    are already selling it.

    This is deliberately NOT a demand signal, and that is a change from v2.
    The Browse API's ItemSummary type exposes no sold-count field of any kind —
    not soldCount, not totalSoldItems, not soldQuantity. (watchCount exists but
    requires a separate App Check permission grant from eBay.) v2 asked for
    `sort=newlyListed`, i.e. the newest listings, which by definition have no
    sales history, and then reported sold_count = 0 for every item forever.

    What this returns instead is directly useful for sourcing decisions:
        listings      → how saturated the product already is
        median_price  → the realistic market price
        low_price     → the price you would have to beat
    """

    API_URL  = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"

    def __init__(self, app_id: str, cert_id: str):
        self.app_id  = app_id
        self.cert_id = cert_id
        self._token  = None
        self._token_expires_at = 0.0
        self.session = requests.Session()

    def _get_token(self) -> Optional[str]:
        """Client-credentials token, cached until shortly before it expires."""
        if self._token and time.time() < self._token_expires_at:
            return self._token
        try:
            import base64
            credentials = base64.b64encode(
                f"{self.app_id}:{self.cert_id}".encode()
            ).decode()

            resp = self.session.post(
                self.AUTH_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type":  "application/x-www-form-urlencoded",
                },
                data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope",
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._token = payload.get("access_token")
            # Renew a minute early rather than waiting for a hard expiry.
            self._token_expires_at = time.time() + int(payload.get("expires_in", 7200)) - 60
            return self._token
        except Exception as e:
            log.warning(f"[eBay] Token error: {e}")
            return None

    def price_check(self, product_name: str) -> Optional[dict]:
        """
        Searches eBay UK for this specific product.
        Returns None when there is no usable match — never a fabricated one.
        """
        token = self._get_token()
        if not token:
            return None

        query = self._search_query(product_name)
        if not query:
            return None

        try:
            resp = self.session.get(
                self.API_URL,
                headers={
                    "Authorization":           f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                    "X-EBAY-C-ENDUSERCTX":     "contextualLocation=country%3DGB",
                },
                params={
                    "q":      query,
                    "limit":  50,
                    "sort":   "price",
                    "filter": "buyingOptions:{FIXED_PRICE},itemLocationCountry:GB",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"[eBay] Lookup failed for '{truncate(query, 40)}': {e}")
            return None

        items = data.get("itemSummaries") or []

        # Only keep listings that actually relate to the product. Without this
        # guard eBay's fuzzy search happily returns a GBP 250 perfume for an
        # eye-serum query, which is exactly how v2 produced its false matches.
        relevant = [
            i for i in items
            if token_overlap(product_name, i.get("title", "")) >= MIN_TOKEN_OVERLAP
        ]
        if not relevant:
            log.info(f"[eBay] No relevant listings for '{truncate(query, 40)}'")
            return None

        prices = sorted(p for p in (self._price_of(i) for i in relevant) if p > 0)
        if not prices:
            return None

        cheapest = min(relevant, key=lambda i: self._price_of(i) or float("inf"))

        return {
            "query":        query,
            "listings":     int(data.get("total") or len(items)),
            "matched":      len(relevant),
            "median_price": round(prices[len(prices) // 2], 2),
            "low_price":    round(prices[0], 2),
            "name":         cheapest.get("title", ""),
            "url":          cheapest.get("itemWebUrl", ""),
        }

    @staticmethod
    def _price_of(item: dict) -> float:
        try:
            return float((item.get("price") or {}).get("value", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _search_query(product_name: str) -> str:
        """
        Amazon titles are long and marketing-heavy ("... for Fine Lines, Uneven
        Skin Tone, Korean Skin Care 1.01fl.oz"). Searching eBay with the whole
        string returns nothing, so use the most distinctive words only.
        """
        words = [w for w in _TOKEN_RE.findall(product_name.lower())
                 if len(w) > 3 and w not in STOPWORDS]
        return " ".join(words[:5])


# ── REDDIT SCANNER ────────────────────────────────────────────────────────────

class RedditScanner:
    """
    Fetches top posts from UK-relevant subreddits using public JSON feeds.
    No API key needed. Extracts product mentions from post titles.
    """

    SUBREDDITS = [
        "hotdeals",
        "deals",
        "DIY",
        "CatAdvice",
        "dogs",
        "Frugal",
        "BabyBumps",
        "CarTalkUK",
        # UK-focused
        "UKPersonalFinance",
        "AskUK",
        "GiftIdeas",
        "malegrooming",
        "SkincareAddiction",
        "Homeimprovement",
        # Supplements/Health
        "Supplements",
        "Nootropics",
        "Vitamins",
        "HerbalMedicine",
        "nutrition",
        "HealthyFood",
        "intermittentfasting",
        "loseit",
        "fitness",
    ]

    BASE_URL = "https://www.reddit.com/r/{sub}/top.json?t=week&limit=25"

    HEADERS = {
        "User-Agent": "TrendRadar/2.0 (dropshipping research tool)"
    }

    def scan(self) -> list[dict]:
        """
        Returns a list of product mentions found on Reddit this week.
        Each item: { "title": str, "score": int, "subreddit": str, "url": str }
        """
        mentions = []

        for sub in self.SUBREDDITS:
            log.info(f"[Reddit] Scanning: r/{sub}")
            try:
                url  = self.BASE_URL.format(sub=sub)
                resp = requests.get(url, headers=self.HEADERS, timeout=6)
                resp.raise_for_status()
                data = resp.json()

                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    p = post.get("data", {})
                    title = p.get("title", "")
                    score = p.get("score", 0)
                    link  = f"https://reddit.com{p.get('permalink', '')}"

                    # Only keep posts with decent engagement
                    if score >= 10:
                        mentions.append({
                            "title":     title,
                            "score":     score,
                            "subreddit": sub,
                            "url":       link,
                        })

                log.info(f"[Reddit] r/{sub}: {len(posts)} posts, "
                         f"{sum(1 for m in mentions if m['subreddit'] == sub)} relevant")
                time.sleep(2)  # be polite to Reddit

            except Exception as e:
                log.warning(f"[Reddit] Error scanning r/{sub}: {e}")

        log.info(f"[Reddit] Total mentions collected: {len(mentions)}")
        return mentions

    # Category keywords — what to look for on Reddit per Amazon category
    CATEGORY_KEYWORDS = {
        "beauty":     {"keywords": ["makeup", "skincare", "moisturiser", "serum", "spf", "sunscreen", "hair", "shampoo"], "subreddits": ["deals", "Frugal", "hotdeals"]},
        "kitchen":    {"keywords": ["kitchen", "cooking", "recipe", "pan", "blender", "coffee", "air fryer"], "subreddits": ["deals", "Frugal", "hotdeals"]},
        "pet":        {"keywords": ["cat", "dog", "pet", "feed", "treat", "collar", "kitten", "puppy"], "subreddits": ["CatAdvice", "dogs", "deals"]},
        "tech":       {"keywords": ["phone", "charger", "battery", "headphone", "speaker", "tablet", "gadget", "smartwatch"], "subreddits": ["deals", "Frugal", "hotdeals"]},
        "diy":        {"keywords": ["paint", "drill", "shelf", "fix", "wall", "tool", "screw", "wood"], "subreddits": ["DIY", "deals"]},
        "baby":       {"keywords": ["baby", "nappy", "newborn", "toddler", "infant", "pram", "crib"], "subreddits": ["BabyBumps", "deals"]},
        "automotive": {"keywords": ["car", "tyre", "brake", "engine", "oil", "vehicle", "wash", "wiper"], "subreddits": ["CarTalkUK", "deals"]},
        "music":      {"keywords": ["guitar", "piano", "drum", "music", "instrument", "string", "amp"], "subreddits": ["deals", "Frugal"]},
        "health":     {
            "keywords": ["supplement", "vitamin", "protein", "omega", "magnesium", "collagen",
                         "probiotic", "herbal", "turmeric", "ashwagandha", "zinc", "iron",
                         "b12", "cbd", "creatine"],
            "subreddits": ["Supplements", "Vitamins", "nutrition", "HerbalMedicine", "fitness", "loseit"],
        },
        "sport":      {
            "keywords": ["gym", "workout", "fitness", "running", "yoga", "cycling", "protein",
                         "creatine", "pre-workout", "resistance"],
            "subreddits": ["fitness", "loseit", "intermittentfasting", "malegrooming"],
        },
    }

    def match_product(self, product_name: str, mentions: list[dict], category: str = "") -> Optional[dict]:
        config = self.CATEGORY_KEYWORDS.get(category)
        if not config:
            return None

        keywords   = config["keywords"]
        subreddits = config["subreddits"]

        best_match = None
        best_score = 0

        for mention in mentions:
            # Only check posts from relevant subreddits
            if mention["subreddit"] not in subreddits:
                continue
            title_lower = mention["title"].lower()
            matched = any(kw in title_lower for kw in keywords)
            if matched and mention["score"] > best_score:
                best_score = mention["score"]
                best_match = mention

        return best_match

# ── TELEGRAM ALERTER ──────────────────────────────────────────────────────────

class TelegramAlerter:

    API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def send(self, message: str) -> bool:
        try:
            resp = requests.post(
                self.API_URL,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
                timeout=10
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            log.error(f"[Telegram] Error: {e}")
            return False

    def send_report(self, products: list[Product]) -> None:
        if not products:
            self.send("TREND RADAR — No products found this scan.")
            return

        strong = [p for p in products if p.strength == "STRONG"]
        medium = [p for p in products if p.strength == "MEDIUM"]

        self.send(
            f"TREND RADAR — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"{'─' * 30}\n"
            f"Products found: {len(products)}\n"
            f"Strong: {len(strong)} | Medium: {len(medium)}"
        )

        for p in (strong + medium)[:5]:
            self.send(
                f"#{p.rank} {p.name[:60]}\n"
                f"Category: {p.category} | Signal: {p.strength}\n"
                f"{p.url[:80] if p.url else 'No link'}"
            )
            time.sleep(0.5)

        self.send("Source: Amazon UK Movers & Shakers")


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────

class TrendRadar:
    """
    1. Scan Amazon UK M&S → discover trending products
    2. Save results locally as JSON
    3. Push to Cloudflare KV → dashboard reads from here
    4. Send Telegram alert
    """

    def __init__(self):
        self.amazon    = AmazonScanner()
        self.reddit    = RedditScanner()
        self.telegram  = TelegramAlerter()
        self.ebay      = eBayScanner(EBAY_APP_ID, EBAY_CERT_ID) if EBAY_APP_ID else None
        self.tiktok    = TikTokScanner()
        self.pinterest = PinterestScanner()

    def run(self) -> list[Product]:
        log.info("=" * 60)
        log.info("TREND RADAR v2 — Starting scan")
        log.info("=" * 60)
        start = time.time()

        log.info("[1/5] Scanning Amazon UK Movers & Shakers...")
        products = self.amazon.scan_all()

        if not products:
            log.warning("No products found.")
            self.telegram.send("TREND RADAR — Scan failed. No products returned from Amazon.")
            return []

        products.sort(key=lambda p: p.rank)

        # Step 2: Reddit cross-reference (disabled — needs API access for accuracy)
        # reddit_mentions = self.reddit.scan()
        # for product in products:
        #     match = self.reddit.match_product(product.name, reddit_mentions, product.category)
        #     if match:
        #         product.reddit_title = match["title"]
        #         product.reddit_url   = match["url"]
        #         product.reddit_score = match["score"]
        #         product.sources.append("Reddit")

        # REDDIT PLAN (to activate later):
        # Instead of matching products to Reddit posts (too noisy),
        # use Reddit as a CATEGORY HEAT SIGNAL:
        # - Count posts per category keyword this week (e.g. "hair", "skincare" → beauty is hot)
        # - Generate one heat score per category (0-100)
        # - Boost all products in that category by the heat score
        # - This is more accurate than per-product matching
        # To activate: uncomment the block above and implement category_heat_score()

        # Step 2: TikTok trending hashtags
        log.info("[2/5] Scanning TikTok Creative Center...")
        tiktok_trends = self.tiktok.scan()
        if tiktok_trends:
            for product in products:
                match = self.tiktok.match_product(product, tiktok_trends)
                if match:
                    # v2 appended the source but never stored the hashtag, so
                    # tiktok_hashtag was null in every scan ever pushed.
                    product.tiktok_hashtag = match["hashtag"]
                    product.tiktok_posts   = match.get("posts", 0)
                    product.sources.append("TikTok")
                    log.info(f"[TikTok] Match: '{truncate(product.name, 40)}' → #{match['hashtag']} ({match['posts']} posts)")

        # Step 3: Pinterest trending categories
        log.info("[3/5] Scanning Pinterest Trends...")
        pinterest_trends = self.pinterest.scan()
        if pinterest_trends:
            for product in products:
                match = self.pinterest.match_product(product, pinterest_trends)
                if match:
                    product.pinterest_keyword = str(match["keyword"])
                    product.sources.append("Pinterest")
                    log.info(f"[Pinterest] Match: '{truncate(product.name, 40)}' → {match['keyword']}")
        else:
            log.warning("[Pinterest] No trends returned — skipping")

        # Step 4: eBay price + saturation check on the highest-ranked products
        if self.ebay:
            budget = min(len(products), EBAY_MAX_LOOKUPS)
            log.info(f"[4/5] eBay price check (top {budget} products)...")
            priced = 0
            for product in products[:budget]:
                info = self.ebay.price_check(product.name)
                if not info:
                    continue
                product.ebay_name         = info["name"]
                product.ebay_url          = info["url"]
                product.ebay_listings     = info["listings"]
                product.ebay_median_price = info["median_price"]
                product.ebay_low_price    = info["low_price"]
                product.sources.append("eBay")
                priced += 1
                log.info(
                    f"[eBay] '{truncate(product.name, 40)}' — {info['listings']} listings, "
                    f"median GBP {info['median_price']}, low GBP {info['low_price']}"
                )
                time.sleep(0.5)
            log.info(f"[eBay] Priced {priced}/{budget} products")
        else:
            log.info("[4/5] eBay price check disabled — add EBAY_APP_ID to enable")

        log.info("[5/5] Saving results and sending alert...")
        self._save(products)
        self.telegram.send_report(products)

        log.info(f"Scan complete in {round(time.time() - start, 1)}s — {len(products)} products")
        return products

    def _save(self, products: list[Product]) -> None:
        data = {
            "status":        "ok",
            "scan_date":     datetime.now().strftime("%d/%m/%Y %H:%M"),
            "keywords_used": [],
            "signals":       [p.to_dict() for p in products],
        }

        # Write a local copy first, so a scan is never lost to a network error.
        filename = f"radar_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log.info(f"[Save] Wrote {filename}")
        except Exception as e:
            log.warning(f"[Save] Could not write {filename}: {e}")

        if not CLOUDFLARE_PUSH_URL:
            log.warning("[Save] CLOUDFLARE_PUSH_URL not set — skipping dashboard push")
            return
        if not PUSH_SECRET:
            log.error(
                "[Save] PUSH_SECRET not set — the Worker rejects unauthenticated "
                "pushes. Add PUSH_SECRET to .env, and set the same value on the "
                "Worker with: wrangler secret put PUSH_SECRET"
            )
            return

        try:
            resp = requests.post(
                CLOUDFLARE_PUSH_URL,
                json=data,
                headers={"X-Push-Secret": PUSH_SECRET},
                timeout=15,
            )
            if resp.status_code == 200:
                log.info("[Save] Pushed to Cloudflare KV")
            elif resp.status_code == 401:
                log.error(
                    "[Save] Worker rejected the push secret (401) — the value in "
                    ".env does not match `wrangler secret put PUSH_SECRET`"
                )
            elif resp.status_code == 503:
                log.error(
                    "[Save] Worker has no PUSH_SECRET configured (503) — run: "
                    "wrangler secret put PUSH_SECRET"
                )
            else:
                log.warning(f"[Save] Cloudflare push failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            log.warning(f"[Save] Cloudflare push error: {e}")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────


def truncate(s: str, n: int) -> str:
    return s[:n] + '...' if len(s) > n else s
def run_scan():
    try:
        TrendRadar().run()
    except Exception as e:
        log.error(f"Scan error: {e}", exc_info=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        log.info("TREND RADAR v2 — Scheduler mode")
        log.info(f"Scans scheduled at: {', '.join(SCHEDULE_TIMES)}")
        for t in SCHEDULE_TIMES:
            schedule.every().day.at(t).do(run_scan)
        log.info("Running first scan now...")
        run_scan()
        while True:
            schedule.run_pending()
            time.sleep(30)
    else:
        run_scan()
