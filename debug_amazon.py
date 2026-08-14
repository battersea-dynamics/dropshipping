"""
One-off diagnostic. Saves an Amazon Movers & Shakers page to disk and reports
how it is structured, so the CSS selectors in trend_radar.py can be updated.

Run:  python debug_amazon.py

Writes amazon_debug.html next to this file. Nothing is sent anywhere.

This mimics what trend_radar.py does — one reused session, homepage first to
pick up cookies — because a bare one-off request gets served a bot-check page.
"""

import collections
import time
import requests
from bs4 import BeautifulSoup

URL = "https://www.amazon.co.uk/gp/movers-and-shakers/beauty"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)

# Warm up: collect cookies from the homepage the way a real browser would.
print("warming up on the homepage...")
try:
    session.get("https://www.amazon.co.uk/", timeout=15)
except Exception as e:
    print(f"  (warm-up failed, continuing anyway: {e})")
time.sleep(3)

html = ""
for attempt in range(1, 4):
    resp = session.get(URL, timeout=20)
    html = resp.text
    print(f"attempt {attempt}: status={resp.status_code} bytes={len(html)}")
    if len(html) > 50_000:
        break
    print("  looks like a bot-check page, waiting 10s and retrying...")
    time.sleep(10)

with open("amazon_debug.html", "w", encoding="utf-8") as f:
    f.write(html)

soup = BeautifulSoup(html, "html.parser")
title = soup.title.get_text(strip=True)[:100] if soup.title else "NONE"
print(f"\nsaved amazon_debug.html  bytes={len(html)}")
print(f"title={title}")

if len(html) < 50_000:
    print("\nStill blocked. Try again in a few minutes, or open the page in your "
          "browser first and then re-run this.")
    raise SystemExit(0)

print("\n--- current selectors ---")
for sel in [".p13n-desktop-grid li", "li.zg-item-immersion",
            "div.zg-item-immersion", "li[class*='zg-item']"]:
    print(f"{len(soup.select(sel)):5}  {sel}")

print("\n--- most repeated elements (candidates for the product row) ---")
counts = collections.Counter()
for tag in soup.find_all(True):
    classes = tag.get("class")
    if classes:
        counts[(tag.name, ".".join(classes))] += 1
for (name, cls), n in counts.most_common(80):
    if 8 <= n <= 150:
        print(f"{n:5}  {name}.{cls[:100]}")

print("\n--- possible embedded data ---")
for marker in ["p13n-sc-uncoverable-faceout", "faceout", "gridItemRoot",
               "zg-bdg-text", "p13n-sc-truncate", '"asin"',
               "data-client-recs-list", "aok-inline-block", "_cDEzb_"]:
    print(f"{html.count(marker):6}  occurrences of  {marker}")

print("\n--- where do rank badges like #1 live? ---")
for tag in soup.find_all(string=lambda s: s and s.strip().startswith("#") and s.strip()[1:].strip().isdigit()):
    parent = tag.parent
    print(f"  {tag.strip()[:8]:8} inside <{parent.name} class={parent.get('class')}>")
    if parent.parent is not None:
        print(f"           parent: <{parent.parent.name} class={parent.parent.get('class')}>")
    break
