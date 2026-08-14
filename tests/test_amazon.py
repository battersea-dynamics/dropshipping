"""
Tests for the Amazon scanner's failure diagnosis.

The point of these is that "0 products" has four different causes that need
opposite responses, and on 14/08/2026 two of them were confused for each other:
Amazon was serving an empty list, and the log said the CSS selectors were stale.

Run with:  python tests/test_amazon.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trend_radar  # noqa: E402
from trend_radar import AmazonScanner  # noqa: E402

FILLER = "<!-- " + ("x" * 60_000) + " -->"


def page(title, body):
    return f"<html><head><title>{title}</title></head><body>{body}{FILLER}</body></html>"


REAL_TITLE = "Amazon.co.uk Movers and Shakers: The biggest gainers in Beauty sales rank"

BLOCK_PAGE = "<html><head><title>Amazon.co.uk</title></head><body>short</body></html>"

EMPTY_PAGE = page(REAL_TITLE, """
  <div class="p13n-desktop-grid" data-client-recs-list="[]">
    <h4>Sorry, there are no movers and shakers available in this category.
    Please check back later.</h4>
  </div>""")

UNDEFINED_PAGE = page(
    "Amazon.co.uk Movers and Shakers: The biggest gainers in undefined sales rank",
    '<div class="p13n-desktop-grid"></div>')

GOOD_PAGE = page(REAL_TITLE, """
  <div class="p13n-desktop-grid"><ul>
    <li><span class="zg-bdg-text">#1</span>
        <div class="p13n-sc-truncate">Turmeric Gummies 120ct</div>
        <a class="a-link-normal" href="/dp/B01"></a></li>
    <li><span class="zg-bdg-text">#2</span>
        <div class="p13n-sc-truncate">Magnetic Knife Holder</div>
        <a class="a-link-normal" href="/dp/B02"></a></li>
  </ul></div>""")

LAYOUT_CHANGED_PAGE = page(REAL_TITLE, '<div class="brand-new-grid"><li>thing</li></div>')

GRID_BUT_NO_ROWS_PAGE = page(REAL_TITLE, '<div class="p13n-desktop-grid"><p>x</p></div>')


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    """Serves a chosen page for the category URL, ignoring the warm-up call."""

    def __init__(self, by_slug, default=BLOCK_PAGE):
        self.by_slug = by_slug
        self.default = default
        self.headers = {}
        self.urls = []

    def update(self, *_a, **_k):
        pass

    def get(self, url, **_kwargs):
        self.urls.append(url)
        if "movers-and-shakers" not in url:
            return FakeResponse("<html><title>Amazon.co.uk</title></html>")
        for slug, html in self.by_slug.items():
            if url.rstrip("/").endswith("/" + slug):
                return FakeResponse(html)
        return FakeResponse(self.default)


def build(by_slug, default=BLOCK_PAGE):
    scanner = AmazonScanner()
    scanner.session = FakeSession(by_slug, default)
    return scanner


def reasons_for(scanner):
    return [reason for _, reason in scanner.notes]


def test_good_page_returns_products():
    s = build({"beauty": GOOD_PAGE})
    products = s._scrape_category("beauty", ["beauty"])
    assert len(products) == 2, products
    assert products[0].name == "Turmeric Gummies 120ct"
    assert products[0].rank == 1
    assert products[0].url.endswith("/dp/B01")
    assert s.notes == []


def test_empty_list_is_reported_as_amazon_having_no_data():
    """The 14/08 case. Must NOT be reported as a selector problem."""
    s = build({"beauty": EMPTY_PAGE})
    assert s._scrape_category("beauty", ["beauty"]) == []
    assert reasons_for(s) == ["Amazon returned an empty list"]


def test_bot_check_is_reported_as_blocked():
    s = build({"beauty": BLOCK_PAGE})
    assert s._scrape_category("beauty", ["beauty"]) == []
    assert reasons_for(s) == ["blocked by Amazon"]


def test_missing_grid_is_reported_as_layout_change():
    s = build({"beauty": LAYOUT_CHANGED_PAGE})
    assert s._scrape_category("beauty", ["beauty"]) == []
    assert reasons_for(s) == ["page layout changed"]


def test_grid_present_but_no_rows_is_reported_separately():
    s = build({"beauty": GRID_BUT_NO_ROWS_PAGE})
    assert s._scrape_category("beauty", ["beauty"]) == []
    assert reasons_for(s) == ["grid rows not recognised"]


def test_unrecognised_slug_falls_through_to_the_next_one():
    """The health category: the US slug returns a page titled 'undefined'."""
    s = build({"health-personal-care": UNDEFINED_PAGE, "drugstore": GOOD_PAGE})
    products = s._scrape_category("health", ["health-personal-care", "drugstore"])
    assert len(products) == 2
    assert s.notes == []


def test_all_slugs_unrecognised_is_reported():
    s = build({"health-personal-care": UNDEFINED_PAGE, "hpc": UNDEFINED_PAGE})
    assert s._scrape_category("health", ["health-personal-care", "hpc"]) == []
    assert reasons_for(s) == ["no working URL"]


def test_health_category_tries_the_uk_slug_first():
    assert trend_radar.AMAZON_CATEGORIES["health"][0] == "drugstore"


def test_playwright_scanners_skip_when_unavailable():
    """A missing Playwright must not stop the Amazon scan."""
    original = trend_radar.PLAYWRIGHT_AVAILABLE
    try:
        trend_radar.PLAYWRIGHT_AVAILABLE = False
        assert trend_radar.TikTokScanner().scan() == []
        assert trend_radar.PinterestScanner().scan() == []
    finally:
        trend_radar.PLAYWRIGHT_AVAILABLE = original


def test_scan_all_warms_up_before_the_first_category():
    s = build({"beauty": GOOD_PAGE})
    s.scan_all()
    assert "movers-and-shakers" not in s.session.urls[0], s.session.urls[0]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}  {e}")
    print(f"\n{'ALL PASSED' if not failures else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
