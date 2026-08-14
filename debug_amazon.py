"""
One-off diagnostic. Saves an Amazon Movers & Shakers page to disk and reports
how it is structured, so the CSS selectors in trend_radar.py can be updated.

Run:  python debug_amazon.py

It writes amazon_debug.html next to this file. Nothing is sent anywhere.
"""

import collections
import requests
from bs4 import BeautifulSoup

URL = "https://www.amazon.co.uk/gp/movers-and-shakers/beauty"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

resp = requests.get(URL, headers=HEADERS, timeout=20)
with open("amazon_debug.html", "w", encoding="utf-8") as f:
    f.write(resp.text)

print(f"status={resp.status_code}  bytes={len(resp.text)}  saved to amazon_debug.html")

soup = BeautifulSoup(resp.text, "html.parser")
print(f"title={soup.title.get_text(strip=True)[:100] if soup.title else 'NONE'}")
print()

# Which selectors does trend_radar.py currently try, and do any of them hit?
print("--- current selectors ---")
for sel in [".p13n-desktop-grid li", "li.zg-item-immersion",
            "div.zg-item-immersion", "li[class*='zg-item']"]:
    print(f"{len(soup.select(sel)):5}  {sel}")
print()

# What repeated blocks does the page actually contain now?
print("--- most repeated elements (candidates for the product row) ---")
counts = collections.Counter()
for tag in soup.find_all(True):
    classes = tag.get("class")
    if classes:
        counts[(tag.name, ".".join(classes))] += 1
for (name, cls), n in counts.most_common(60):
    if 8 <= n <= 120:
        print(f"{n:5}  {name}.{cls[:100]}")
print()

# Amazon often ships the data as JSON inside the page rather than as HTML.
print("--- possible embedded data ---")
for marker in ["p13n-sc-uncoverable-faceout", "faceout", "gridItemRoot",
               "aok-inline-block", '"asin"', "data-client-recs-list"]:
    print(f"{resp.text.count(marker):6}  occurrences of  {marker}")
