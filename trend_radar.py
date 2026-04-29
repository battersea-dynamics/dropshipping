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

SCHEDULE_TIMES      = ["08:00", "20:00"]
AMAZON_MAX_PRODUCTS = 20

AMAZON_CATEGORIES = {
    "health":      "health",
    "beauty":      "beauty",
    "kitchen":     "kitchen",
    "sport":       "sporting-goods",
    "pet":         "pet-supplies",
    "tech":        "electronics",
    "toys":        "toys",
    "clothing":    "apparel",
    "garden":      "garden",
    "diy":         "diy",
    "office":      "office-products",
    "baby":        "baby",
    "automotive":  "automotive",
    "music":       "musical-instruments",
    "luggage":     "luggage",
    "jewellery":   "jewelry",
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
    name:        str
    rank:        int
    category:    str
    url:         str
    sources:     list = field(default_factory=list)
    detected_at: str  = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    @property
    def strength(self) -> str:
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
        response = requests.Session().get(url, headers=HEADERS, timeout=15)
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
        self.telegram = TelegramAlerter()

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

        filename = f"radar_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"[Save] Local: {filename}")

        try:
            resp = requests.post(CLOUDFLARE_PUSH_URL, json=data, timeout=15)
            if resp.status_code == 200:
                log.info("[Save] Pushed to Cloudflare KV")
            else:
                log.warning(f"[Save] Cloudflare push failed: {resp.status_code}")
        except Exception as e:
            log.warning(f"[Save] Cloudflare push error: {e}")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

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
