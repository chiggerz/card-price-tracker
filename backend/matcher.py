
# IMPORTANT:
# Use package-based imports (backend.<module>)

from __future__ import annotations

from typing import Any
import re


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


def _extract_numbering(title: str) -> str | None:
    match = re.search(r"/\d+", title)
    if not match:
        return None
    return match.group(0)


def _score_listing(parsed_query: dict[str, Any], listing: dict[str, Any]) -> tuple[int, str, dict[str, bool]]:
    title = listing["title"]
    score = 0
    reasons: list[str] = []
    flags: dict[str, bool] = {}

    query_player = parsed_query.get("player_name")
    player_match = _contains(title, query_player)
    flags["has_player_query"] = bool(query_player)
    flags["player_match"] = player_match
    flags["player_ok"] = query_player is None or player_match
    if player_match:
        score += 40
        reasons.append("player match")
    elif query_player is None:
        reasons.append("player unspecified")
    else:
        reasons.append("player mismatch")

    product = parsed_query.get("product")
    product_match = bool(product and _contains(title, product))
    flags["product_match"] = product_match
    if product_match:
        score += 20
        reasons.append("product match")
    elif product:
        reasons.append("product mismatch")

    subset = parsed_query.get("subset")
    subset_match = bool(subset and _contains(title, subset))
    flags["subset_match"] = subset_match
    flags["subset_ok"] = subset is None or subset_match
    if subset_match:
        score += 15
        reasons.append("subset match")
    elif subset:
        reasons.append("subset mismatch")

    query_numbering = parsed_query.get("numbering")
    listing_numbering = _extract_numbering(title)
    numbering_match = bool(query_numbering and query_numbering in title)
    flags["numbering_match"] = numbering_match
    flags["numbering_ok"] = query_numbering is None or numbering_match
    flags["both_numbered"] = bool(query_numbering and listing_numbering)
    flags["different_numbering"] = bool(
        query_numbering and listing_numbering and query_numbering != listing_numbering
    )
    if numbering_match:
        score += 15
        reasons.append("numbering match")
    elif query_numbering:
        reasons.append("numbering mismatch")

    query_is_auto = bool(parsed_query.get("is_auto"))
    listing_is_auto = "auto" in title.lower()
    auto_match = query_is_auto == listing_is_auto
    flags["auto_match"] = auto_match
    if auto_match:
        score += 10
        reasons.append("auto match")
    else:
        reasons.append("auto mismatch")

    reason = ", ".join(reasons)
    return score, reason, flags


def _assign_bucket(flags: dict[str, bool]) -> tuple[str, str]:
    if (
        flags["player_ok"]
        and flags["product_match"]
        and flags["subset_ok"]
        and flags["numbering_ok"]
        and flags["auto_match"]
    ):
        return "exact_matches", "Same player/card profile including numbering and auto."

    if (
        flags["player_ok"]
        and flags["product_match"]
        and flags["subset_ok"]
        and flags["auto_match"]
        and flags["different_numbering"]
    ):
        return "same_player_different_number", "Same player and card type, different serial numbering."

    if flags["player_match"] and (not flags["subset_ok"] or not flags["auto_match"]):
        return "same_player_other_variant", "Same player with nearby variant differences."

    if (
        flags["has_player_query"]
        and not flags["player_match"]
        and flags["product_match"]
        and flags["subset_ok"]
        and flags["auto_match"]
        and (flags["numbering_match"] or flags["both_numbered"] or flags["numbering_ok"])
    ):
        return "different_player_same_card_type", "Different player, but very similar card structure."

    return "low_relevance_results", "Weaker match, retained as a fallback comp."


def match_candidates(parsed_query: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for listing in SAMPLE_SOLD_LISTINGS:
        relevance_score, score_reason, flags = _score_listing(parsed_query, listing)
        bucket, bucket_reason = _assign_bucket(flags)
        results.append(
            {
                "title": listing["title"],
                "price": listing["price"],
                "relevance_score": relevance_score,
                "bucket": bucket,
                "reason": f"{bucket_reason} ({score_reason})",
            }
        )

    return sorted(results, key=lambda item: item["relevance_score"], reverse=True)
