from __future__ import annotations

from typing import Any


SAMPLE_SOLD_LISTINGS: list[dict[str, Any]] = [
    {
        "title": "2023 Topps Chrome Sapphire Erling Haaland Auto /10",
        "price": 1850.00,
        "source": "ebay_sample",
        "sold_date": "2026-04-03",
    },
    {
        "title": "2023 Topps Chrome Sapphire Erling Haaland Auto /25",
        "price": 940.00,
        "source": "ebay_sample",
        "sold_date": "2026-04-01",
    },
    {
        "title": "2023 Topps Chrome Sapphire Erling Haaland /10",
        "price": 620.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-30",
    },
    {
        "title": "2023 Topps Chrome Erling Haaland Auto /10",
        "price": 980.00,
        "source": "ebay_sample",
        "sold_date": "2026-04-02",
    },
    {
        "title": "2023 Topps Chrome Sapphire Phil Foden Auto /10",
        "price": 460.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-29",
    },
    {
        "title": "2023 Topps Chrome Bukayo Saka /75",
        "price": 275.00,
        "source": "ebay_sample",
        "sold_date": "2026-04-04",
    },
    {
        "title": "2023 Topps Chrome Bukayo Saka /99",
        "price": 190.00,
        "source": "ebay_sample",
        "sold_date": "2026-04-01",
    },
    {
        "title": "2024 Arsenal Team Set Northern Stars",
        "price": 55.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-31",
    },
    {
        "title": "2024 Arsenal Team Set Northern Star",
        "price": 40.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-28",
    },
]


def _contains(haystack: str, needle: str | None) -> bool:
    if not needle:
        return False
    return needle.lower() in haystack.lower()


def _score_listing(parsed_query: dict[str, Any], listing: dict[str, Any]) -> tuple[int, bool, str]:
    title = listing["title"]
    score = 0
    reasons: list[str] = []

    if _contains(title, parsed_query.get("player_name")):
        score += 40
        reasons.append("player match")
    else:
        reasons.append("player mismatch")

    product = parsed_query.get("product")
    if product and _contains(title, product):
        score += 20
        reasons.append("product match")
    elif product:
        reasons.append("product mismatch")

    subset = parsed_query.get("subset")
    if subset and _contains(title, subset):
        score += 15
        reasons.append("subset match")
    elif subset:
        reasons.append("subset mismatch")

    numbering = parsed_query.get("numbering")
    if numbering and numbering in title:
        score += 15
        reasons.append("numbering match")
    elif numbering:
        reasons.append("numbering mismatch")

    query_is_auto = bool(parsed_query.get("is_auto"))
    listing_is_auto = "auto" in title.lower()
    if query_is_auto == listing_is_auto:
        score += 10
        reasons.append("auto match")
    else:
        reasons.append("auto mismatch")

    included = score >= 70
    reason = ", ".join(reasons)
    return score, included, reason


def match_candidates(parsed_query: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for listing in SAMPLE_SOLD_LISTINGS:
        relevance_score, included, reason = _score_listing(parsed_query, listing)
        results.append(
            {
                "title": listing["title"],
                "price": listing["price"],
                "relevance_score": relevance_score,
                "included": included,
                "reason": reason,
            }
        )

    return results
