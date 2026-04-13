from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

_EBAY_FINDING_ENDPOINT = "https://svcs.ebay.com/services/search/FindingService/v1"


class EbayConfigurationError(RuntimeError):
    """Raised when eBay integration is not configured."""


class EbayRequestError(RuntimeError):
    """Raised when eBay API request/response handling fails."""


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(value))
    except (InvalidOperation, ValueError):
        return None


def _normalize_listing(raw_item: dict[str, Any]) -> dict[str, Any] | None:
    title = (raw_item.get("title") or [None])[0]
    if not title:
        return None

    selling_status = (raw_item.get("sellingStatus") or [{}])[0]
    current_price = (selling_status.get("currentPrice") or [{}])[0]
    price = _safe_float(current_price.get("__value__"))
    if price is None:
        return None

    listing: dict[str, Any] = {
        "title": title,
        "price": price,
        "source": "ebay",
    }

    currency = current_price.get("@currencyId")
    if currency:
        listing["currency"] = currency

    sold_date_raw = (raw_item.get("listingInfo") or [{}])[0].get("endTime")
    sold_date = sold_date_raw
    if sold_date:
        listing["sold_date"] = sold_date
        try:
            dt = datetime.fromisoformat(sold_date.replace("Z", "+00:00"))
            listing["sold_date"] = dt.date().isoformat()
        except ValueError:
            listing["sold_date"] = sold_date_raw

    view_item_url = (raw_item.get("viewItemURL") or [None])[0]
    if view_item_url:
        listing["url"] = view_item_url

    return listing


def search_sold_items(query: str) -> list[dict[str, Any]]:
    """Search sold/completed eBay listings using Finding API."""
    app_id = os.getenv("EBAY_APP_ID")
    if not app_id:
        raise EbayConfigurationError(
            "Missing EBAY_APP_ID. Set EBAY_APP_ID to your eBay App ID before running live sold searches."
        )

    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.13.0",
        "SECURITY-APPNAME": app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "REST-PAYLOAD": "",
        "keywords": query,
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "paginationInput.entriesPerPage": "50",
        "sortOrder": "EndTimeSoonest",
    }
    url = f"{_EBAY_FINDING_ENDPOINT}?{urlencode(params)}"

    try:
        with urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EbayRequestError(f"eBay request failed: {exc}") from exc

    responses = payload.get("findCompletedItemsResponse") or []
    first_response = responses[0] if responses else {}
    search_results = first_response.get("searchResult") or []
    first_search_result = search_results[0] if search_results else {}
    raw_items = first_search_result.get("item") or []

    normalized_items = [item for item in (_normalize_listing(raw_item) for raw_item in raw_items) if item]

    logger.debug("eBay sold results fetched: raw_count=%s normalized_count=%s", len(raw_items), len(normalized_items))

    return normalized_items
