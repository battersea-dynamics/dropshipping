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
    pip install requests beautifulsoup4 schedule
"""

import time
import json
import logging
import schedule
import requests
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup


# ── CONFIG ────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN  = "8225165494:AAG9lDDBCrn3GHVe2UM0N_oa7m07bBJZ7Ho"
TELEGRAM_CHAT_ID    = "8739473584"
CLOUDFLARE_PUSH_URL = "https://dropshipping.battersea-dynamics.workers.dev/api/push"

# eBay API credentials — add when developer account is approved
# Register at: https://developer.ebay.com

# TikTok session cookie — refresh every 2-3 weeks from browser Network tab
TIKTOK_COOKIE = "cookie-consent={%22optional%22:true%2C%22ga%22:true%2C%22af%22:true%2C%22fbp%22:true%2C%22lip%22:true%2C%22bing%22:true%2C%22ttads%22:true%2C%22reddit%22:true%2C%22hubspot%22:true%2C%22version%22:%22v10%22}; passport_csrf_token=a361dbe437ad3b626267790864afdc30; passport_csrf_token_default=a361dbe437ad3b626267790864afdc30; odin_tt=09758de13055decfa5ee9d64d4f9b9f380e7ac0541c0f0d14d392572df1f03104a6fad160a709a5e80fcf04a6acba1a0188af9befd0aeeac20920889c2a40233; lang_type=en; from_way=paid; tta_attr_id_mirror=0.1777959892.7636279588034248712; _ga=GA1.1.8778693.1777959898; _gcl_au=1.1.261568115.1777959898; _rdt_uuid=1777959897853.579be9e5-acb8-4595-9b25-6b0b6f35fe39; _uetmsclkid=_uetb4fb26d5862415731d3e4f2c05eb93f7; _tt_enable_cookie=1; _fbp=fb.1.1777959898459.1735095388; _ttp=3DIBr5GilQr31bYf8z4hlv3fWe4.tt.1; ttcsid=1777959898094::MnNXHrh2ImZQKf0XDZ08.1.1777959908990.0::1.-8409.882::9443.1.1005.17::9520.2.0; msToken=NcuNC4M1T18ToosuafMpf2T5CtQUmHO_ZkvQ0VFagR34joWxxh8Fb4mzza3PxKuYS5s8O18HxEiQ9tHjE41lDnMNht4Ms-5E1zFatSFnjXT0iWVZfQbCVP_1bqRNjIRYXp3M9DrOFyVdowL6xh1IRVQ=; ttwid=1%7CuCryuyyJfpHnru2LKFcExSScvkbtrc2K4MlIHtzCDOo%7C1777961593%7Cc50a06b7c147ff6e901b98fa23f44df2bae6ef8ab586558a0286313667285b7d"

EBAY_APP_ID  = ""   # Your App ID (Client ID)
EBAY_CERT_ID = ""   # Your Cert ID (Client Secret)

SCHEDULE_TIMES      = ["08:00", "20:00"]
AMAZON_MAX_PRODUCTS = 20

AMAZON_CATEGORIES = {
    "beauty":     "beauty",
    "kitchen":    "kitchen",
    "pet":        "pet-supplies",
    "tech":       "electronics",
    "diy":        "diy",
    "baby":       "baby",
    "automotive": "automotive",
    "music":      "musical-instruments",
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
    ebay_name:     Optional[str] = None
    ebay_url:      Optional[str] = None
    ebay_watches:  int = 0
    ebay_price:      float = 0.0
    tiktok_hashtag:  Optional[str] = None
    tiktok_posts:    int = 0
    detected_at:   str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    @property
    def strength(self) -> str:
        sources_count = len(self.sources)
        if sources_count >= 2 and self.rank <= 10: return "STRONG"
        if self.rank <= 5:  return "STRONG"
        if self.rank <= 15: return "MEDIUM"
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
            "reddit_title":  self.reddit_title,
            "reddit_url":    self.reddit_url,
            "reddit_score":  self.reddit_score,
            "ebay_name":     self.ebay_name,
            "ebay_url":      self.ebay_url,
            "ebay_watches":  self.ebay_watches,
            "ebay_price":      self.ebay_price,
            "tiktok_hashtag":  self.tiktok_hashtag,
            "tiktok_posts":    self.tiktok_posts,
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

    def scan_all(self) -> list[Product]:
        all_products = []
        for label, slug in AMAZON_CATEGORIES.items():
            log.info(f"[Amazon] Scanning: {label}")
            try:
                products = self._scrape_category(label, slug)
                all_products.extend(products)
                log.info(f"[Amazon] {label}: {len(products)} products found")
                time.sleep(4)
            except Exception as e:
                log.warning(f"[Amazon] Error scanning {label}: {e}")
        log.info(f"[Amazon] Total products discovered: {len(all_products)}")
        return all_products

    def _scrape_category(self, label: str, slug: str) -> list[Product]:
        url      = self.BASE_URL.format(category=slug)
        response = requests.Session().get(url, headers=HEADERS, timeout=8)
        response.raise_for_status()
        soup     = BeautifulSoup(response.text, "html.parser")
        items    = []

        for selector in self.SELECTORS:
            items = soup.select(selector)[:AMAZON_MAX_PRODUCTS]
            if items:
                log.info(f"[Amazon] Selector: '{selector}' ({len(items)} items)")
                break

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
    Fetches trending hashtags from TikTok Creative Center.
    Uses the internal API endpoint — no API key needed.
    Endpoint: ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list
    """

    API_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"

    # Map TikTok industry names to our Amazon categories
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

    HEADERS = {
        "accept":           "application/json, text/plain, */*",
        "accept-language":  "en-GB,en;q=0.9",
        "referer":          "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
        "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "sec-fetch-dest":   "empty",
        "sec-fetch-mode":   "cors",
        "sec-fetch-site":   "same-origin",
        "cookie":           TIKTOK_COOKIE,
    }

    def scan(self) -> list[dict]:
        """
        Fetches top trending hashtags for UK across all categories.
        Returns: [{ "hashtag": str, "posts": int, "category": str, "rank": int }]
        """
        results = []

        params = {
            "page":         1,
            "limit":        20,
            "period":       7,
            "country_code": "GB",
            "sort_by":      "popular",
        }

        try:
            resp = requests.get(
                self.API_URL,
                headers=self.HEADERS,
                params=params,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                log.warning(f"[TikTok] API error: {data.get('msg', 'unknown')}")
                return []

            items = data.get("data", {}).get("list", [])
            log.info(f"[TikTok] {len(items)} trending hashtags found")

            for i, item in enumerate(items):
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
            log.warning(f"[TikTok] Scan error: {e}")

        return results

    def match_product(self, product: object, tiktok_trends: list[dict]) -> Optional[dict]:
        """
        Checks if a product's category has trending hashtags on TikTok.
        Returns the most popular matching hashtag or None.
        """
        category = getattr(product, "category", "")
        tokens   = [t for t in product.name.lower().split() if len(t) > 3]

        best_match = None
        best_posts = 0

        for trend in tiktok_trends:
            # Match by category
            category_match = trend["category"] == category

            # Match by keyword in hashtag
            hashtag_lower  = trend["hashtag"].lower()
            keyword_match  = any(t in hashtag_lower for t in tokens)

            if (category_match or keyword_match) and trend["posts"] > best_posts:
                best_posts = trend["posts"]
                best_match = trend

        return best_match

# ── EBAY SCANNER ──────────────────────────────────────────────────────────────

class eBayScanner:
    """
    Fetches trending items from eBay UK using the Browse API.
    Signal: items with high watch counts = strong buyer demand.
    
    API registration: https://developer.ebay.com (free)
    Add key to CONFIG section when approved: EBAY_APP_ID
    """

    # eBay Browse API endpoint
    API_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"

    # Categories to scan (eBay UK category IDs)
    CATEGORIES = {
        "beauty":     "26395",   # Health & Beauty
        "kitchen":    "20625",   # Kitchen & Home
        "pet":        "1281",    # Pet Supplies
        "tech":       "58058",   # Consumer Electronics
        "diy":        "11700",   # Home & Garden
        "baby":       "2984",    # Baby
        "automotive": "9800",    # Vehicle Parts & Accessories
        "music":      "619",     # Musical Instruments
    }

    def __init__(self, app_id: str, cert_id: str):
        self.app_id  = app_id
        self.cert_id = cert_id
        self._token  = None

    def _get_token(self) -> Optional[str]:
        """Gets OAuth token for eBay API."""
        if self._token:
            return self._token
        try:
            import base64
            credentials = base64.b64encode(
                f"{self.app_id}:{self.cert_id}".encode()
            ).decode()

            resp = requests.post(
                self.AUTH_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope",
                timeout=10
            )
            resp.raise_for_status()
            self._token = resp.json().get("access_token")
            return self._token
        except Exception as e:
            log.warning(f"[eBay] Token error: {e}")
            return None

    def scan_all(self) -> list[dict]:
        """
        Scans all categories and returns trending items.
        Each item: { "name": str, "category": str, "watch_count": int,
                     "price": float, "url": str, "seller_count": int }
        """
        token = self._get_token()
        if not token:
            log.warning("[eBay] No token — check APP_ID and CERT_ID")
            return []

        all_items = []

        for label, cat_id in self.CATEGORIES.items():
            log.info(f"[eBay] Scanning: {label}")
            try:
                items = self._fetch_category(token, label, cat_id)
                all_items.extend(items)
                log.info(f"[eBay] {label}: {len(items)} items found")
                time.sleep(1)
            except Exception as e:
                log.warning(f"[eBay] Error scanning {label}: {e}")

        log.info(f"[eBay] Total items discovered: {len(all_items)}")
        return all_items

    def _fetch_category(self, token: str, label: str, cat_id: str) -> list[dict]:
        resp = requests.get(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DGB",
            },
            params={
                "category_ids": cat_id,
                "sort":         "watchCount",   # sort by most watched
                "limit":        20,
                "filter":       "buyingOptions:{FIXED_PRICE}",  # no auctions
            },
            timeout=10
        )
        resp.raise_for_status()
        data  = resp.json()
        items = data.get("itemSummaries", [])

        results = []
        for item in items:
            price = 0.0
            if item.get("price"):
                try:
                    price = float(item["price"].get("value", 0))
                except (ValueError, TypeError):
                    pass

            results.append({
                "name":         item.get("title", ""),
                "category":     label,
                "watch_count":  item.get("watchCount", 0),
                "price":        price,
                "url":          item.get("itemWebUrl", ""),
                "item_id":      item.get("itemId", ""),
            })

        # Sort by watch count — most watched first
        results.sort(key=lambda x: x["watch_count"], reverse=True)
        return results

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
        self.amazon   = AmazonScanner()
        self.reddit   = RedditScanner()
        self.telegram = TelegramAlerter()
        self.ebay    = eBayScanner(EBAY_APP_ID, EBAY_CERT_ID) if EBAY_APP_ID else None
        self.tiktok  = TikTokScanner()

    def run(self) -> list[Product]:
        log.info("=" * 60)
        log.info("TREND RADAR v2 — Starting scan")
        log.info("=" * 60)
        start = time.time()

        log.info("[1/3] Scanning Amazon UK Movers & Shakers...")
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
        
        # Step 2: TikTok trending hashtags
        log.info("[2/4] Scanning TikTok Creative Center...")
        tiktok_trends = self.tiktok.scan()

        if tiktok_trends:
            for product in products:
                match = self.tiktok.match_product(product, tiktok_trends)
                if match:
                    product.sources.append("TikTok")
                    log.info(f"[TikTok] Match: '{truncate(product.name, 40)}' → #{match['hashtag']} ({match['posts']} posts)")
        
        # Step 2: TikTok trending hashtags
        log.info("[2/4] Scanning TikTok Creative Center...")
        tiktok_trends = self.tiktok.scan()

        if tiktok_trends:
            for product in products:
                match = self.tiktok.match_product(product, tiktok_trends)
                if match:
                    product.sources.append("TikTok")
                    log.info(f"[TikTok] Match: '{truncate(product.name, 40)}' → #{match['hashtag']} ({match['posts']} posts)")
        
        # Step 2: eBay cross-reference
        if self.ebay:
            log.info("[2/3] Scanning eBay UK trending items...")
            ebay_items = self.ebay.scan_all()

            # Match Amazon products against eBay trending items
            for product in products:
                match = self._match_ebay(product.name, ebay_items)
                if match:
                    product.ebay_name    = match["name"]
                    product.ebay_url     = match["url"]
                    product.ebay_watches = match["watch_count"]
                    product.ebay_price   = match["price"]
                    product.sources.append("eBay")
                    log.info(f"[eBay] Match: '{truncate(product.name, 40)}' — {match['watch_count']} watches")
        else:
            log.info("[2/3] eBay scanning disabled — add EBAY_APP_ID to enable")
        
        # REDDIT PLAN (to activate later):
        # Instead of matching products to Reddit posts (too noisy),
        # use Reddit as a CATEGORY HEAT SIGNAL:
        # - Count posts per category keyword this week (e.g. "hair", "skincare" → beauty is hot)
        # - Generate one heat score per category (0-100)
        # - Boost all products in that category by the heat score
        # - This is more accurate than per-product matching
        # To activate: uncomment the block above and implement category_heat_score()

        log.info("[2/3] Saving results...")
        self._save(products)

        log.info("[3/3] Sending Telegram alert...")
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

        try:
            resp = requests.post(CLOUDFLARE_PUSH_URL, json=data, timeout=15)
            if resp.status_code == 200:
                log.info("[Save] Pushed to Cloudflare KV")
            else:
                log.warning(f"[Save] Cloudflare push failed: {resp.status_code}")
        except Exception as e:
            log.warning(f"[Save] Cloudflare push error: {e}")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

def _match_ebay(self, product_name: str, ebay_items: list[dict]) -> Optional[dict]:
        """Matches Amazon product name against eBay trending items."""
        tokens = [t for t in product_name.lower().split() if len(t) > 3]
        if not tokens:
            return None

        best_match = None
        best_watches = 0

        for item in ebay_items:
            name_lower = item["name"].lower()
            matches = sum(1 for t in tokens if t in name_lower)
            ratio = matches / len(tokens)
            if ratio >= 0.5 and item["watch_count"] > best_watches:
                best_watches = item["watch_count"]
                best_match = item

        return best_match

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
