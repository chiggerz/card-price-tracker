from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderSearchResult:
    listings: list[dict[str, Any]]
    message: str | None = None


class ListingProvider(Protocol):
    name: str

    def search_sold_items(self, query: str) -> ProviderSearchResult:
        ...


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


class MockListingProvider:
    name = "sample_mock"

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

    def search_sold_items(self, query: str) -> ProviderSearchResult:
        _ = query
        listings: list[dict[str, Any]] = []
        for raw_item in self._SAMPLE_SOLD_LISTINGS:
            price = _safe_float(raw_item.get("price"))
            if price is None:
                continue
            normalized = dict(raw_item)
            normalized["price"] = price
            listings.append(normalized)

        return ProviderSearchResult(listings=listings)
