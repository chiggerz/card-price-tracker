from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import hashlib
import json
import logging
import os
import re
from datetime import UTC, datetime


@dataclass(frozen=True)
class EbayScrapedListing:
    title: str
    price: float
    sold_date: str | None
    url: str | None
    image_url: str | None
    source: str
    currency: str


@dataclass(frozen=True)
class EbayPageParseResult:
    listings: list[EbayScrapedListing]
    page_kind: str
    summary: str
    debug_html_path: str | None = None
    fetched_url: str | None = None


class _EbaySoldItemsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_item = False
        self._item_depth = 0
        self._current_item: dict[str, str] | None = None
        self._capture_field: str | None = None
        self._results: list[dict[str, str]] = []

    @property
    def results(self) -> list[dict[str, str]]:
        return self._results

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v or "") for k, v in attrs}
        class_attr = attrs_dict.get("class", "")

        if tag == "li" and "s-item" in class_attr.split():
            self._in_item = True
            self._item_depth = 1
            self._current_item = {}
            self._capture_field = None
            return

        if not self._in_item:
            return

        self._item_depth += 1

        if tag == "a" and "s-item__link" in class_attr.split() and self._current_item is not None:
            self._current_item["url"] = attrs_dict.get("href", "")

        if tag == "img" and self._current_item is not None:
            image_url = attrs_dict.get("src") or attrs_dict.get("data-src") or attrs_dict.get("data-lazy")
            if image_url:
                self._current_item.setdefault("image_url", image_url)

        if self._current_item is None:
            return

        if tag in {"div", "span"} and "s-item__title" in class_attr.split():
            self._capture_field = "title"
        elif tag in {"span", "div"} and "s-item__price" in class_attr.split():
            self._capture_field = "price_text"
        elif tag in {"span", "div"} and "POSITIVE" in class_attr and "s-item__title--tagblock" in class_attr:
            self._capture_field = "sold_date"
        else:
            self._capture_field = None

    def handle_data(self, data: str) -> None:
        if not self._in_item or not self._capture_field or not self._current_item:
            return

        text = data.strip()
        if not text:
            return

        existing = self._current_item.get(self._capture_field, "")
        self._current_item[self._capture_field] = f"{existing} {text}".strip() if existing else text

    def handle_endtag(self, tag: str) -> None:
        _ = tag
        if not self._in_item:
            return

        self._item_depth -= 1
        if self._item_depth <= 0:
            if self._current_item:
                self._results.append(self._current_item)
            self._in_item = False
            self._current_item = None
            self._capture_field = None


def build_sold_completed_search_url(query: str) -> str:
    encoded_query = quote_plus(query.strip())
    return (
        "https://www.ebay.com/sch/i.html"
        f"?_nkw={encoded_query}"
        "&LH_Sold=1"
        "&LH_Complete=1"
        "&_sop=13"
        "&rt=nc"
    )


def fetch_sold_completed_html(search_url: str, timeout_seconds: int = 15) -> str:
    request = Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="ignore")


def _extract_first_price(price_text: str) -> tuple[float | None, str]:
    if not price_text:
        return None, "USD"

    currency = "USD"
    if "C$" in price_text:
        currency = "CAD"
    elif "£" in price_text:
        currency = "GBP"
    elif "EUR" in price_text or "€" in price_text:
        currency = "EUR"

    match = re.search(r"([0-9][0-9,]*(?:\.[0-9]{2})?)", price_text)
    if not match:
        return None, currency

    try:
        return float(match.group(1).replace(",", "")), currency
    except ValueError:
        return None, currency


def _normalize_sold_date(sold_date_text: str | None) -> str | None:
    if not sold_date_text:
        return None
    normalized = sold_date_text.replace("Sold", "").replace("on", "").strip(" :-")
    return normalized or None


def _extract_embedded_json_payloads(html: str) -> list[tuple[str, object]]:
    payloads: list[tuple[str, object]] = []
    script_pattern = re.compile(r"<script([^>]*)>(.*?)</script>", flags=re.IGNORECASE | re.DOTALL)
    for script_attrs, script_body in script_pattern.findall(html):
        id_match = re.search(r'id="([^"]+)"', script_attrs, flags=re.IGNORECASE)
        type_match = re.search(r'type="([^"]+)"', script_attrs, flags=re.IGNORECASE)
        normalized_script_id = (id_match.group(1) if id_match else "").strip()
        normalized_script_type = (type_match.group(1) if type_match else "").strip().lower()
        body = (script_body or "").strip()
        if not body:
            continue

        if normalized_script_id == "__NEXT_DATA__" or normalized_script_type == "application/ld+json":
            try:
                payloads.append((normalized_script_id or normalized_script_type, json.loads(unescape(body))))
            except json.JSONDecodeError:
                continue

    json_blob_patterns = [
        (
            "window.__INITIAL_STATE__",
            r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;",
        ),
        (
            "window.__PRELOADED_STATE__",
            r"window\.__PRELOADED_STATE__\s*=\s*({.*?})\s*;",
        ),
    ]
    for blob_label, pattern in json_blob_patterns:
        for match in re.finditer(pattern, html, flags=re.DOTALL):
            blob_text = unescape(match.group(1)).strip()
            try:
                payloads.append((blob_label, json.loads(blob_text)))
            except json.JSONDecodeError:
                continue

    return payloads


def _read_nested(mapping: dict[str, object], key_path: list[str]) -> object | None:
    current: object | None = mapping
    for key in key_path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_card_from_json_node(node: dict[str, object], payload_source: str) -> dict[str, str] | None:
    title = (
        _read_nested(node, ["title"])
        or _read_nested(node, ["name"])
        or _read_nested(node, ["headline"])
    )
    if isinstance(title, dict):
        title = title.get("text")

    url = (
        _read_nested(node, ["url"])
        or _read_nested(node, ["itemWebUrl"])
        or _read_nested(node, ["itemUrl"])
        or _read_nested(node, ["item", "url"])
    )
    if isinstance(url, dict):
        url = url.get("url")

    image_url = (
        _read_nested(node, ["image_url"])
        or _read_nested(node, ["imageUrl"])
        or _read_nested(node, ["image", "url"])
        or _read_nested(node, ["image", "imageUrl"])
        or _read_nested(node, ["thumbnail", "imageUrl"])
        or _read_nested(node, ["item", "image", "url"])
    )
    if isinstance(image_url, list):
        image_url = image_url[0] if image_url else None
    if isinstance(image_url, dict):
        image_url = image_url.get("url")

    raw_price = (
        _read_nested(node, ["price", "value"])
        or _read_nested(node, ["price", "amount"])
        or _read_nested(node, ["currentPrice", "value"])
        or _read_nested(node, ["sellingStatus", "currentPrice", "__value__"])
        or _read_nested(node, ["displayPrice"])
        or _read_nested(node, ["price"])
    )
    raw_currency = (
        _read_nested(node, ["price", "currency"])
        or _read_nested(node, ["priceCurrency"])
        or _read_nested(node, ["currentPrice", "currency"])
        or _read_nested(node, ["sellingStatus", "currentPrice", "@currencyId"])
        or _read_nested(node, ["currency"])
    )
    sold_date = (
        _read_nested(node, ["soldDate"])
        or _read_nested(node, ["endedDate"])
        or _read_nested(node, ["endDate"])
        or _read_nested(node, ["itemEndDate"])
        or _read_nested(node, ["purchaseDate"])
    )

    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(raw_price, (str, int, float)):
        return None
    if not isinstance(url, str) and not _read_nested(node, ["itemId"]):
        return None

    card: dict[str, str] = {
        "title": unescape(title.strip()),
        "price_text": str(raw_price),
        "json_source": payload_source,
    }
    if isinstance(url, str) and url.strip():
        card["url"] = unescape(url.strip())
    if isinstance(image_url, str) and image_url.strip():
        card["image_url"] = unescape(image_url.strip())
    if isinstance(sold_date, str) and sold_date.strip():
        card["sold_date"] = sold_date.strip()
    if isinstance(raw_currency, str) and raw_currency.strip():
        card["currency"] = raw_currency.strip().upper()
    return card


def _iter_json_objects(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_json_objects(child)


def _extract_cards_from_embedded_data(html: str) -> list[dict[str, str]]:
    extracted_cards: list[dict[str, str]] = []
    seen_card_keys: set[str] = set()
    for payload_source, payload in _extract_embedded_json_payloads(html):
        for node in _iter_json_objects(payload):
            card = _extract_card_from_json_node(node, payload_source)
            if not card:
                continue
            dedupe_key = "|".join(
                [
                    card.get("title", "").lower(),
                    card.get("price_text", "").lower(),
                    card.get("url", "").lower(),
                ]
            )
            if dedupe_key in seen_card_keys:
                continue
            seen_card_keys.add(dedupe_key)
            extracted_cards.append(card)
    return extracted_cards


def _has_listing_signals(html: str) -> bool:
    lower = html.lower()
    listing_markers = [
        "srp-river-results",
        "srp-results",
        "s-item",
        "s-card__title",
        "itemid",
        "/itm/",
        "i.ebayimg.com",
    ]
    return any(marker in lower for marker in listing_markers)


def _classify_page_kind(html: str) -> tuple[str, str]:
    lower = html.lower()
    if "captcha" in lower or "robot check" in lower or "automated access" in lower:
        return "anti_bot", "eBay returned an anti-bot / CAPTCHA challenge page."
    if "consent" in lower and ("gdpr" in lower or "privacy" in lower):
        return "consent", "eBay returned a consent/privacy interstitial page."
    if "ebay" not in lower or "<html" not in lower:
        return "non_results", "Response does not appear to be a normal eBay HTML page."
    if _extract_cards_from_embedded_data(html):
        return "results", "Detected embedded sold/completed result payloads in page scripts."
    if _has_listing_signals(html):
        return "results", "Detected eBay listing/result markup markers."
    if (
        "no exact matches found" in lower
        or "0 results for" in lower
        or "did not match any items" in lower
    ):
        return "empty_results", "eBay results page indicates no sold/completed matches."
    if "bos-items__loader" in lower or "bos-items" in lower:
        return "results", "Detected newer eBay results shell markers (bos-items)."
    return "unknown_ebay", "Detected eBay page, but results markup markers were not found."


def _save_debug_html(html: str, reason: str) -> str | None:
    enabled = os.getenv("EBAY_SCRAPER_DEBUG_HTML", "1").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        return None

    debug_dir = Path(os.getenv("EBAY_SCRAPER_DEBUG_DIR", ".debug/ebay_scrape_html"))
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha1(html.encode("utf-8", errors="ignore")).hexdigest()[:10]
    reason_slug = re.sub(r"[^a-z0-9]+", "-", reason.lower()).strip("-") or "parse-failure"
    file_path = debug_dir / f"{timestamp}-{reason_slug}-{digest}.html"
    file_path.write_text(html, encoding="utf-8")
    return str(file_path)


def _extract_raw_cards(html: str) -> list[dict[str, str]]:
    embedded_cards = _extract_cards_from_embedded_data(html)
    if embedded_cards:
        return embedded_cards

    parser = _EbaySoldItemsParser()
    parser.feed(html)
    cards = parser.results
    if cards:
        return cards

    fallback_cards: list[dict[str, str]] = []
    card_patterns = [
        r"<li[^>]+class=\"[^\"]*\bs-item\b[^\"]*\"[^>]*>.*?</li>",
        r"<div[^>]+class=\"[^\"]*\bs-item__wrapper\b[^\"]*\"[^>]*>.*?</div>",
        r"<article[^>]+class=\"[^\"]*\bs-card\b[^\"]*\"[^>]*>.*?</article>",
        r"<div[^>]+class=\"[^\"]*\bsrp-river-results\b[^\"]*\"[^>]*>.*?</div>",
    ]
    for pattern in card_patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
            block = match.group(0)
            title_match = re.search(
                r'class="[^"]*(?:s-item__title|s-card__title)[^"]*"[^>]*>(.*?)<',
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            price_match = re.search(
                r'class="[^"]*(?:s-item__price|s-card__price|s-card__attribute-text)[^"]*"[^>]*>(.*?)<',
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            href_match = re.search(
                r'(?:class="[^"]*(?:s-item__link|s-card__image|s-card__title-link)[^"]*"[^>]*href="([^"]+)"|href="([^"]*?/itm/[^"]+)"|\"url\"\s*:\s*\"(https?://[^\"]*?/itm/[^\"]+)\")',
                block,
                flags=re.IGNORECASE,
            )
            sold_match = re.search(
                r'(?:sold|ended)\s+(?:on\s+)?([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',
                block,
                flags=re.IGNORECASE,
            )
            image_match = re.search(
                r'(?:<img[^>]+(?:src|data-src|data-lazy)="([^"]+)"|\"image(?:Url|_url)?\"\s*:\s*\"(https?://i\.ebayimg\.com/[^\"]+)\")',
                block,
                flags=re.IGNORECASE,
            )
            item_id_match = re.search(
                r'(?:\bitemid\b\s*[:=]\s*["\']?(\d{8,15})["\']?|/itm/(?:[^/]+/)?(\d{8,15})|\"itemId\"\s*:\s*\"?(\d{8,15})\"?)',
                block,
                flags=re.IGNORECASE,
            )
            item: dict[str, str] = {}
            if title_match:
                item["title"] = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip()
            if price_match:
                item["price_text"] = re.sub(r"<[^>]+>", " ", price_match.group(1)).strip()
            if href_match:
                href = next((group for group in href_match.groups() if group), "")
                if href:
                    item["url"] = href.strip().replace("\\/", "/")
            if sold_match:
                item["sold_date"] = sold_match.group(1).strip()
            if image_match:
                image = next((group for group in image_match.groups() if group), "")
                if image:
                    item["image_url"] = image.strip().replace("\\/", "/")
            if item_id_match and "url" not in item:
                item_id = next((group for group in item_id_match.groups() if group), "")
                if item_id:
                    item["url"] = f"https://www.ebay.com/itm/{item_id}"
            if item:
                fallback_cards.append(item)
        if fallback_cards:
            break

    return fallback_cards


def parse_sold_listing_cards(html: str) -> list[EbayScrapedListing]:
    normalized: list[EbayScrapedListing] = []
    for item in _extract_raw_cards(html):
        title = item.get("title", "").strip()
        if not title or title.lower() in {"shop on ebay", "new listing"}:
            continue

        price, parsed_currency = _extract_first_price(item.get("price_text", ""))
        currency = item.get("currency", "").strip().upper() or parsed_currency
        if price is None:
            continue

        normalized.append(
            EbayScrapedListing(
                title=title,
                price=price,
                sold_date=_normalize_sold_date(item.get("sold_date")),
                url=item.get("url") or None,
                image_url=item.get("image_url") or None,
                source="ebay_sold_scrape",
                currency=currency,
            )
        )

    return normalized


def parse_sold_listing_cards_with_context(html: str, fetched_url: str | None = None) -> EbayPageParseResult:
    page_kind, summary = _classify_page_kind(html)
    listings = parse_sold_listing_cards(html)
    debug_html_path: str | None = None

    if page_kind == "results" and not listings:
        debug_html_path = _save_debug_html(html, reason="results-no-normalized-cards")
    elif page_kind in {"empty_results", "unknown_ebay", "anti_bot", "consent", "non_results"}:
        debug_html_path = _save_debug_html(html, reason=page_kind)

    logging.getLogger(__name__).info(
        "eBay scrape classification=%s listings=%d url=%s debug_html_path=%s summary=%s",
        page_kind,
        len(listings),
        fetched_url,
        debug_html_path,
        summary,
    )

    return EbayPageParseResult(
        listings=listings,
        page_kind=page_kind,
        summary=summary,
        debug_html_path=debug_html_path,
        fetched_url=fetched_url,
    )
