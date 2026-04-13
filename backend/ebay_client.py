from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

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
    """Small eBay REST client that handles OAuth app token acquisition and Browse requests."""

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
