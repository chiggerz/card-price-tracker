from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from backend.listing_providers import ListingProvider, MockListingProvider, ProviderSearchResult

logger = logging.getLogger(__name__)


class EbayConfigurationError(RuntimeError):
    """Raised when eBay integration is not configured."""


class EbayRequestError(RuntimeError):
    """Raised when eBay API request/response handling fails."""


@dataclass(frozen=True)
class EbayConfig:
    client_id: str
    client_secret: str
    environment: str
    marketplace_id: str
    oauth_scope: str


class EbayApiClient:
    """Small eBay REST client that handles OAuth app token acquisition."""

    _TOKEN_PATH = "/identity/v1/oauth2/token"

    def __init__(self, config: EbayConfig):
        self._config = config

    @property
    def _api_base_url(self) -> str:
        if self._config.environment == "production":
            return "https://api.ebay.com"
        return "https://api.sandbox.ebay.com"

    def _oauth_token_url(self) -> str:
        return f"{self._api_base_url}{self._TOKEN_PATH}"

    def get_application_access_token(self) -> str:
        credentials = f"{self._config.client_id}:{self._config.client_secret}".encode("utf-8")
        basic_auth = base64.b64encode(credentials).decode("ascii")

        payload = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "scope": self._config.oauth_scope,
            }
        ).encode("utf-8")

        req = request.Request(
            self._oauth_token_url(),
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            logger.warning("eBay OAuth request failed: status=%s", exc.code)
            raise EbayRequestError(f"OAuth token request failed with status {exc.code}. {detail}") from exc
        except URLError as exc:
            raise EbayRequestError(f"OAuth token request failed: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise EbayRequestError("Unable to parse OAuth token response from eBay.") from exc

        token = parsed.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise EbayRequestError("OAuth token response did not contain a usable access_token.")
        return token

    def browse_search(self, query: str, limit: int = 10) -> dict[str, Any]:
        token = self.get_application_access_token()
        browse_url = f"{self._api_base_url}/buy/browse/v1/item_summary/search"
        params = parse.urlencode({"q": query, "limit": limit})
        req = request.Request(
            f"{browse_url}?{params}",
            method="GET",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self._config.marketplace_id,
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            raise EbayRequestError(f"Browse API request failed with status {exc.code}. {detail}") from exc
        except URLError as exc:
            raise EbayRequestError(f"Browse API request failed: {exc.reason}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise EbayRequestError("Unable to parse Browse API response from eBay.") from exc


class EbayBrowseProvider:
    name = "ebay_browse"

    def __init__(self, client: EbayApiClient):
        self._client = client

    def search_sold_items(self, query: str) -> ProviderSearchResult:
        _ = query
        return ProviderSearchResult(
            listings=[],
            message=(
                "Official eBay Browse provider is configured, but sold/completed comps are not "
                "currently exposed through this provider path. Falling back to sample/mock sold listings."
            ),
        )


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
        return ProviderSearchResult(listings=fallback_result.listings, message=combined_message or None)


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


def _active_provider() -> ListingProvider:
    provider_name = os.getenv("LISTING_PROVIDER", "mock").strip().lower()
    mock_provider = MockListingProvider()

    if provider_name == "mock":
        return mock_provider

    if provider_name == "ebay_browse":
        client = EbayApiClient(_build_ebay_config_from_env())
        browse_provider = EbayBrowseProvider(client)
        return FallbackListingProvider(primary=browse_provider, fallback=mock_provider)

    raise EbayConfigurationError(
        "Unsupported LISTING_PROVIDER value. Use 'mock' or 'ebay_browse'."
    )


def live_data_status_message() -> str | None:
    provider_name = os.getenv("LISTING_PROVIDER", "mock").strip().lower()
    if provider_name == "ebay_browse":
        return (
            "Configured provider: ebay_browse with OAuth scaffolding. "
            "Official live sold-comps are not currently available in this provider path."
        )
    return "Configured provider: mock sample data."


def search_sold_items(query: str) -> list[dict[str, Any]]:
    provider = _active_provider()
    result = provider.search_sold_items(query)
    if result.message:
        logger.info("Listing provider message: %s", result.message)
    return result.listings


def search_sold_items_with_status(query: str) -> ProviderSearchResult:
    provider = _active_provider()
    return provider.search_sold_items(query)
