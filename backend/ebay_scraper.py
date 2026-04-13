from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import re


@dataclass(frozen=True)
class EbayScrapedListing:
    title: str
    price: float
    sold_date: str | None
    url: str | None
    image_url: str | None
    source: str
    currency: str


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
    return f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1"


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


def parse_sold_listing_cards(html: str) -> list[EbayScrapedListing]:
    parser = _EbaySoldItemsParser()
    parser.feed(html)

    normalized: list[EbayScrapedListing] = []
    for item in parser.results:
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
