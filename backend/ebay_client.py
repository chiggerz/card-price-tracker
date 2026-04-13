from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

class EbayConfigurationError(RuntimeError):
    """Raised when eBay integration is not configured."""


class EbayRequestError(RuntimeError):
    """Raised when eBay API request/response handling fails."""


_LIVE_PROVIDER_ENV = "ENABLE_LIVE_EBAY"

# NOTE:
# The legacy Finding API is deprecated/decommissioned and intentionally disabled.
# Keep the module surface stable while serving predictable sample listings.
_SAMPLE_SOLD_LISTINGS: tuple[dict[str, Any], ...] = (
    {
        "title": "2024 Topps Chrome Elly De La Cruz Rookie RC #44 /299 Auto",
        "price": 212.5,
        "source": "sample_mock",
        "currency": "USD",
        "sold_date": "2025-01-09",
        "url": "https://example.com/mock/elly-44-299-auto",
    },
    {
        "title": "2024 Topps Chrome Elly De La Cruz Rookie RC #44 /499",
        "price": 98.0,
        "source": "sample_mock",
        "currency": "USD",
        "sold_date": "2024-12-18",
        "url": "https://example.com/mock/elly-44-499",
    },
    {
        "title": "2024 Topps Chrome Elly De La Cruz Prism Refractor #44",
        "price": 42.25,
        "source": "sample_mock",
        "currency": "USD",
        "sold_date": "2024-11-22",
        "url": "https://example.com/mock/elly-44-prism",
    },
    {
        "title": "2024 Topps Chrome Jackson Chourio Rookie RC #44 /299 Auto",
        "price": 137.75,
        "source": "sample_mock",
        "currency": "USD",
        "sold_date": "2024-10-29",
        "url": "https://example.com/mock/chourio-44-299-auto",
    },
    {
        "title": "2024 Topps Chrome Elly De La Cruz Rookie RC #121",
        "price": 24.0,
        "source": "sample_mock",
        "currency": "USD",
        "sold_date": "2024-09-16",
        "url": "https://example.com/mock/elly-121-base",
    },
)


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(value))
    except (InvalidOperation, ValueError):
        return None


def live_data_status_message() -> str | None:
    """Return a user-facing status message about live sold data availability."""
    if os.getenv(_LIVE_PROVIDER_ENV, "").strip().lower() == "true":
        return (
            "Live sold eBay data is not currently configured in this build. "
            "Using sample/mock sold listings."
        )
    return (
        "Live sold eBay data is currently disabled (Finding API removed). "
        "Using sample/mock sold listings."
    )


def search_sold_items(query: str) -> list[dict[str, Any]]:
    """Return sold listings from the active provider (sample/mock only for now)."""
    _ = query
    listings: list[dict[str, Any]] = []
    for raw_item in _SAMPLE_SOLD_LISTINGS:
        price = _safe_float(str(raw_item.get("price")))
        if price is None:
            continue
        normalized = dict(raw_item)
        normalized["price"] = price
        listings.append(normalized)

    logger.debug("Sample sold results returned: normalized_count=%s", len(listings))
    return listings
