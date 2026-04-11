from __future__ import annotations

from typing import Any

from backend.parser import parse_card_query


SAMPLE_SOLD_LISTINGS: list[dict[str, Any]] = [
    {
        "title": "2024 Topps Chrome Sapphire Elly De La Cruz Auto /50",
        "price": 425.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-30",
    },
    {
        "title": "2024 Topps Chrome Sapphire Elly De La Cruz Auto /99",
        "price": 315.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-28",
    },
    {
        "title": "2024 Topps Chrome Sapphire Elly De La Cruz /50",
        "price": 180.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-29",
    },
    {
        "title": "2024 Topps Chrome Elly De La Cruz Auto /50",
        "price": 260.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-27",
    },
    {
        "title": "2024 Topps Chrome Sapphire Noelvi Marte Auto /50",
        "price": 120.00,
        "source": "ebay_sample",
        "sold_date": "2026-03-25",
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
