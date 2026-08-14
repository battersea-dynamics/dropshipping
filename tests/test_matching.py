"""
Regression tests for the cross-source matching and scoring logic.

Run with:  python -m pytest tests -q      (or: python tests/test_matching.py)

The cases below are taken from the real 17/05/2026 scan that was live on the
dashboard, where an Amazon eye serum was reported as confirmed by eBay with a
£250 perfume attached to it.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trend_radar import (  # noqa: E402
    Product,
    eBayScanner,
    PinterestScanner,
    TikTokScanner,
    hashtag_match,
    token_overlap,
    tokens,
)

SERUM = (
    "medicube Salmon DNA PDRN Pink Peptide Eye Serum with Niacinamide and 99% "
    "Purity Retinol for Fine Lines, Uneven Skin Tone, Korean Skin Care 1.01fl.oz"
)
PERFUME = "Amouage Jubilation 25 100ml"


def test_tokens_drop_noise_words():
    assert "with" not in tokens(SERUM)
    assert "serum" in tokens(SERUM)
    assert tokens("") == set()


def test_the_live_false_positive_scores_zero_overlap():
    """The exact pair that was live on the dashboard."""
    assert token_overlap(SERUM, PERFUME) == 0


def test_ebay_only_keeps_relevant_listings():
    """A perfume must not survive the relevance filter for a serum query."""
    listings = [
        {"title": PERFUME, "price": {"value": "250.30"}},
        {"title": "medicube PDRN Pink Peptide Serum 30ml Korean Skin Care",
         "price": {"value": "28.50"}},
    ]
    kept = [i for i in listings if token_overlap(SERUM, i["title"]) >= 2]
    assert len(kept) == 1
    assert kept[0]["title"].startswith("medicube")


def test_ebay_search_query_is_trimmed():
    """Amazon titles are too long to search eBay with verbatim."""
    query = eBayScanner._search_query(SERUM)
    assert len(query.split()) <= 5
    assert "medicube" in query
    assert "with" not in query.split()


def test_hashtag_match_handles_runtogether_words():
    assert hashtag_match(SERUM, "retinolserum") is True
    assert hashtag_match(SERUM, "koreanskincare") is True
    assert hashtag_match(SERUM, "grwm") is False
    assert hashtag_match(SERUM, "") is False
    # A single short coincidence is not enough on its own.
    assert hashtag_match("Resistance Bands Set", "bandsofbrothers") is False


def test_tiktok_requires_word_overlap_not_just_category():
    scanner = TikTokScanner()
    product = Product(name=SERUM, rank=1, category="beauty", url="")
    trends = [
        # Same category, nothing to do with the product — this is what the old
        # code matched on, and it is what made everything look STRONG.
        {"hashtag": "grwm", "posts": 900_000, "category": "beauty", "rank": 1},
    ]
    assert scanner.match_product(product, trends) is None

    trends.append(
        {"hashtag": "retinolserum", "posts": 12_000, "category": "beauty", "rank": 2}
    )
    match = scanner.match_product(product, trends)
    assert match is not None and match["hashtag"] == "retinolserum"


def test_pinterest_requires_word_overlap_not_just_category():
    scanner = PinterestScanner()
    product = Product(name=SERUM, rank=1, category="beauty", url="")
    assert scanner.match_product(
        product, [{"keyword": "summer nails", "category": "beauty", "rank": 1}]
    ) is None
    assert scanner.match_product(
        product, [{"keyword": "korean skin care routine", "category": "beauty", "rank": 1}]
    ) is not None


def test_rank_alone_is_not_strong():
    """Old rule: rank <= 5 => STRONG. That is now MEDIUM without confirmation."""
    p = Product(name=SERUM, rank=1, category="beauty", url="")
    assert p.score == 40
    assert p.strength == "MEDIUM"


def test_confirmed_product_scores_strong():
    p = Product(name=SERUM, rank=1, category="beauty", url="")
    p.tiktok_hashtag = "retinolserum"
    p.pinterest_keyword = "korean skin care routine"
    p.ebay_listings = 40
    assert p.score == 40 + 20 + 10 + 15 + 15
    assert p.strength == "STRONG"


def test_saturated_product_is_penalised():
    p = Product(name=SERUM, rank=1, category="beauty", url="")
    p.ebay_listings = 5000
    assert p.score == 25
    assert p.strength == "WEAK"


def test_score_never_leaves_0_100():
    p = Product(name="x", rank=999, category="misc", url="")
    p.ebay_listings = 5000
    assert 0 <= p.score <= 100


def test_to_dict_keeps_dashboard_fields():
    """The dashboard reads these keys — don't rename them without updating it."""
    d = Product(name=SERUM, rank=3, category="beauty", url="").to_dict()
    for key in (
        "keyword", "amazon_rank", "amazon_url", "category", "sources",
        "strength", "detected_at", "ebay_name", "ebay_url", "reddit_title",
    ):
        assert key in d, key
    assert d["ebay_watches"] is None  # never faked


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
