from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import hashlib
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


def _classify_page_kind(html: str) -> tuple[str, str]:
    lower = html.lower()
    if "captcha" in lower or "robot check" in lower or "automated access" in lower:
        return "anti_bot", "eBay returned an anti-bot / CAPTCHA challenge page."
    if "consent" in lower and ("gdpr" in lower or "privacy" in lower):
        return "consent", "eBay returned a consent/privacy interstitial page."
    if "ebay" not in lower or "<html" not in lower:
        return "non_results", "Response does not appear to be a normal eBay HTML page."
    if (
        "no exact matches found" in lower
        or "0 results for" in lower
        or "did not match any items" in lower
    ):
        return "empty_results", "eBay results page indicates no sold/completed matches."
    if "s-item" in lower or "srp-results" in lower or "_item" in lower:
        return "results", "Detected eBay results-page markers."
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
    parser = _EbaySoldItemsParser()
    parser.feed(html)
    cards = parser.results
    if cards:
        return cards

    fallback_cards: list[dict[str, str]] = []
    card_patterns = [
        r"<li[^>]+class=\"[^\"]*\bs-item\b[^\"]*\"[^>]*>.*?</li>",
        r"<div[^>]+class=\"[^\"]*\bs-item__wrapper\b[^\"]*\"[^>]*>.*?</div>",
    ]
    for pattern in card_patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
            block = match.group(0)
            title_match = re.search(
                r'class="[^"]*s-item__title[^"]*"[^>]*>(.*?)<',
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            price_match = re.search(
                r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)<',
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            href_match = re.search(
                r'class="[^"]*s-item__link[^"]*"[^>]*href="([^"]+)"',
                block,
                flags=re.IGNORECASE,
            )
            sold_match = re.search(
                r'(?:sold|ended)\s+(?:on\s+)?([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',
                block,
                flags=re.IGNORECASE,
            )
            image_match = re.search(
                r'<img[^>]+(?:src|data-src|data-lazy)="([^"]+)"',
                block,
                flags=re.IGNORECASE,
            )
            item: dict[str, str] = {}
            if title_match:
                item["title"] = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip()
            if price_match:
                item["price_text"] = re.sub(r"<[^>]+>", " ", price_match.group(1)).strip()
            if href_match:
                item["url"] = href_match.group(1).strip()
            if sold_match:
                item["sold_date"] = sold_match.group(1).strip()
            if image_match:
                item["image_url"] = image_match.group(1).strip()
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

        price, currency = _extract_first_price(item.get("price_text", ""))
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
