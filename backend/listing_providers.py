from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.error import URLError

from backend.ebay_client import (
    EbayApiClient,
    EbayConfig,
    EbayConfigurationError,
    EbayRequestError,
)
from backend.ebay_scraper import (
    build_sold_completed_search_url,
    fetch_sold_completed_html,
    parse_sold_listing_cards,
)


@dataclass(frozen=True)
class ProviderSearchResult:
    listings: list[dict[str, Any]]
    provider_name: str
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
    name = "mock"

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

        return ProviderSearchResult(listings=listings, provider_name=self.name)


class EbayBrowseProvider:
    name = "ebay_browse"

    def __init__(self, client: EbayApiClient):
        self._client = client

    def search_sold_items(self, query: str) -> ProviderSearchResult:
        try:
            self._client.browse_search(query=query, limit=3)
        except EbayRequestError as exc:
            return ProviderSearchResult(
                listings=[],
                provider_name=self.name,
                message=(
                    "Official eBay Browse provider is configured but could not complete a Browse API "
                    f"request for this query: {exc}"
                ),
            )

        return ProviderSearchResult(
            listings=[],
            provider_name=self.name,
            message=(
                "Official eBay Browse provider is configured, but real sold/completed comps are not "
                "currently available through this supported provider path."
            ),
        )


class EbaySoldScrapeProvider:
    name = "ebay_sold_scrape"

    def search_sold_items(self, query: str) -> ProviderSearchResult:
        try:
            search_url = build_sold_completed_search_url(query)
            html = fetch_sold_completed_html(search_url)
            parsed_listings = parse_sold_listing_cards(html)
        except (URLError, TimeoutError, ValueError) as exc:
            return ProviderSearchResult(
                listings=[],
                provider_name=self.name,
                message=f"eBay sold/completed scraping request failed: {exc}",
            )
        except Exception as exc:
            return ProviderSearchResult(
                listings=[],
                provider_name=self.name,
                message=f"Unexpected scrape parsing failure: {exc}",
            )

        listings: list[dict[str, Any]] = []
        for item in parsed_listings:
            listings.append(
                {
                    "title": item.title,
                    "price": item.price,
                    "sold_date": item.sold_date,
                    "url": item.url,
                    "image_url": item.image_url,
                    "source": item.source,
                    "currency": item.currency,
                }
            )

        if not listings:
            return ProviderSearchResult(
                listings=[],
                provider_name=self.name,
                message=(
                    "eBay sold/completed scrape succeeded but no listing cards could be normalized "
                    "from the page response."
                ),
            )

        return ProviderSearchResult(listings=listings, provider_name=self.name)


class FallbackListingProvider:
    name = "fallback"

    def __init__(self, primary: ListingProvider, fallback: ListingProvider):
        self._primary = primary
        self._fallback = fallback

    def search_sold_items(self, query: str) -> ProviderSearchResult:
        primary_result = self._primary.search_sold_items(query)
        if primary_result.listings:
            return primary_result

        fallback_result = self._fallback.search_sold_items(query)
        combined_message = " ".join(
            part.strip()
            for part in [primary_result.message, fallback_result.message]
            if isinstance(part, str) and part.strip()
        )
        if combined_message:
            combined_message = f"{combined_message} Falling back to mock sample sold listings."
        else:
            combined_message = "Falling back to mock sample sold listings."

        return ProviderSearchResult(
            listings=fallback_result.listings,
            provider_name=f"{primary_result.provider_name}->{fallback_result.provider_name}",
            message=combined_message,
        )


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise EbayConfigurationError(f"Missing required environment variable: {name}")
    return value


def _build_ebay_config_from_env() -> EbayConfig:
    environment = os.getenv("EBAY_ENVIRONMENT", "sandbox").strip().lower()
    if environment not in {"sandbox", "production"}:
        raise EbayConfigurationError("EBAY_ENVIRONMENT must be either 'sandbox' or 'production'.")

    return EbayConfig(
        client_id=_require_env("EBAY_CLIENT_ID"),
        client_secret=_require_env("EBAY_CLIENT_SECRET"),
        environment=environment,
        marketplace_id=os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip() or "EBAY_US",
        oauth_scope=os.getenv("EBAY_OAUTH_SCOPE", "https://api.ebay.com/oauth/api_scope").strip()
        or "https://api.ebay.com/oauth/api_scope",
    )


def get_listing_provider() -> ListingProvider:
    provider_name = os.getenv("LISTING_PROVIDER", "mock").strip().lower()
    mock_provider = MockListingProvider()

    if provider_name == "mock":
        return mock_provider

    if provider_name == "ebay_browse":
        client = EbayApiClient(_build_ebay_config_from_env())
        browse_provider = EbayBrowseProvider(client)
        return FallbackListingProvider(primary=browse_provider, fallback=mock_provider)

    if provider_name == "ebay_sold_scrape":
        scrape_provider = EbaySoldScrapeProvider()
        return FallbackListingProvider(primary=scrape_provider, fallback=mock_provider)

    raise EbayConfigurationError(
        "Unsupported LISTING_PROVIDER value. Use 'mock', 'ebay_browse', or 'ebay_sold_scrape'."
    )


def live_data_status_message() -> str:
    provider_name = os.getenv("LISTING_PROVIDER", "mock").strip().lower()
    if provider_name == "ebay_browse":
        return (
            "Configured provider: ebay_browse OAuth/Browse scaffold. "
            "Real sold-comps are not implemented through an official supported sold endpoint yet."
        )
    if provider_name == "ebay_sold_scrape":
        return (
            "Configured provider: ebay_sold_scrape HTML scraping of eBay sold/completed search pages. "
            "Results may vary if eBay page markup or anti-bot behavior changes."
        )
    return "Configured provider: mock sample data."
