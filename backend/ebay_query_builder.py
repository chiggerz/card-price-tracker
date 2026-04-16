from __future__ import annotations

import re
from typing import Any

_SEASON_TOKEN_RE = re.compile(r"^(?:\d{2}/\d{2}|(?:19|20)\d{2}/(?:19|20)?\d{2})$")
_CORE_MARKET_TERMS = (
    "premier league",
    "champions league",
    "europa league",
    "la liga",
    "bundesliga",
    "serie a",
)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_season_tokens(text: str) -> str:
    tokens = text.split()
    filtered = [token for token in tokens if not _SEASON_TOKEN_RE.match(token)]
    return _normalize_whitespace(" ".join(filtered))


def _has_auto_term(text: str) -> bool:
    lowered = text.lower()
    return "auto" in lowered or "autograph" in lowered


def build_ebay_search_query(raw_query: str, parsed_query: dict[str, Any]) -> str:
    """Build a broader, marketplace-friendly query for eBay sold/completed fetches."""
    cleaned_raw = _strip_season_tokens(raw_query)

    parts: list[str] = []
    player_name = _normalize_whitespace(str(parsed_query.get("player_name") or ""))
    if player_name:
        parts.append(player_name)

    product = _strip_season_tokens(_normalize_whitespace(str(parsed_query.get("product") or "")))
    if product:
        parts.append(product)

    subset = _strip_season_tokens(_normalize_whitespace(str(parsed_query.get("subset") or "")))
    if subset:
        parts.append(subset)

    cleaned_lower = cleaned_raw.lower()
    for term in _CORE_MARKET_TERMS:
        if term in cleaned_lower and not any(term in part.lower() for part in parts):
            parts.append(term.title())

    numbering = _normalize_whitespace(str(parsed_query.get("numbering") or ""))
    if numbering:
        parts.append(numbering)

    if _has_auto_term(cleaned_raw) or bool(parsed_query.get("is_auto")):
        if not any("autograph" in part.lower() or "auto" in part.lower() for part in parts):
            parts.append("Autograph")

    candidate = _normalize_whitespace(" ".join(part for part in parts if part))
    if not candidate:
        candidate = cleaned_raw

    # Keep query concise and avoid overstuffing with every extra token.
    if len(candidate.split()) > 12:
        candidate = " ".join(candidate.split()[:12])

    return candidate or raw_query.strip()
