"""Binance Futures Testnet REST client.

Handles request signing (HMAC-SHA256), order placement, and
exchange-info queries against the USDT-M testnet API.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("trading_bot.client")

BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10  # seconds

# Map common Binance error codes to human-readable messages
_ERROR_HINTS: dict[int, str] = {
    -1021: "Timestamp for this request is outside the recvWindow. Check your system clock.",
    -1022: "Signature for this request is not valid.",
    -1100: "Illegal characters found in a parameter.",
    -1111: "Precision is over the maximum defined for this asset.",
    -2019: "Margin is insufficient.",
    -2022: "ReduceOnly order is rejected.",
    -4003: "Quantity less than minimum.",
    -4014: "Price not increased by tick size.",
    -4015: "Client order ID is not valid.",
}


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, status_code: int, code: int, msg: str):
        self.status_code = status_code
        self.code = code
        self.msg = msg
        hint = _ERROR_HINTS.get(code, "")
        detail = f" - {hint}" if hint else ""
        super().__init__(f"Binance API error {code}: {msg}{detail}")


class NetworkError(Exception):
    """Raised on network-level failures (timeouts, DNS, connection refused)."""


class BinanceClient:
    """Lightweight wrapper around the Binance Futures Testnet REST API.

    Handles request signing, time synchronisation, and error handling.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not api_key or not api_secret:
            raise ValueError(
                "API key and secret are required. "
                "Set BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET "
                "in your .env file."
            )
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._time_offset: int = 0  # ms difference: server_time - local_time
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"X-MBX-APIKEY": self._api_key},
        )
        self._sync_time()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_exchange_info(self) -> dict[str, Any]:
        """Fetch exchange info (symbol metadata, filters, precision)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_ticker_price(self, symbol: str) -> dict[str, Any]:
        """Fetch the latest ticker price for *symbol*."""
        return self._request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str | None = None,
    ) -> dict[str, Any]:
        """Place a new order on Binance Futures Testnet.

        Routes conditional order types (STOP_MARKET, TAKE_PROFIT_MARKET, etc.)
        to the Algo Order API endpoint, and standard types (MARKET, LIMIT)
        to the regular order endpoint.
        """
        # Conditional order types must go through the Algo Order API
        conditional_types = {"STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT", "TRAILING_STOP_MARKET"}
        if order_type in conditional_types:
            return self._place_algo_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                trigger_price=stop_price,
            )

        # Standard order types: MARKET, LIMIT
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price is not None:
            params["price"] = price
        if time_in_force is not None:
            params["timeInForce"] = time_in_force

        return self._signed_request("POST", "/fapi/v1/order", params=params)

    def _place_algo_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        trigger_price: float | None = None,
    ) -> dict[str, Any]:
        """Place a conditional order via the Algo Order API.

        Uses ``POST /fapi/v1/algoOrder`` with ``algoType=CONDITIONAL``.
        """
        params: dict[str, Any] = {
            "algoType": "CONDITIONAL",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if trigger_price is not None:
            params["triggerPrice"] = trigger_price

        return self._signed_request("POST", "/fapi/v1/algoOrder", params=params)

    # ------------------------------------------------------------------
    # Internal machinery
    # ------------------------------------------------------------------

    def _sync_time(self) -> None:
        """Synchronise local clock with Binance server time.

        Computes the offset (server_time - local_time) so that all
        subsequent signed requests use a corrected timestamp.
        """
        try:
            local_before = int(time.time() * 1000)
            data = self._request("GET", "/fapi/v1/time")
            server_time = data["serverTime"]
            local_after = int(time.time() * 1000)
            # Use the midpoint of the round-trip for best accuracy
            local_mid = (local_before + local_after) // 2
            self._time_offset = server_time - local_mid
            logger.info(
                "Time synced with Binance server (offset: %+d ms)", self._time_offset
            )
        except Exception as exc:
            logger.warning("Could not sync time with server: %s (using local clock)", exc)
            self._time_offset = 0

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add ``timestamp`` and HMAC-SHA256 ``signature`` to *params*."""
        params["timestamp"] = int(time.time() * 1000) + self._time_offset
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an **unsigned** request."""
        logger.debug(">>> %s %s params=%s", method, path, params)
        try:
            resp = self._client.request(method, path, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Network timeout: %s", exc)
            raise NetworkError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("Network error: %s", exc)
            raise NetworkError(f"Network error: {exc}") from exc

        return self._handle_response(resp)

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a **signed** request (adds timestamp + HMAC signature)."""
        params = dict(params or {})
        signed = self._sign(params)

        # Log without exposing the secret / signature
        safe_params = {k: v for k, v in signed.items() if k != "signature"}
        logger.debug(">>> %s %s params=%s", method, path, safe_params)

        try:
            resp = self._client.request(method, path, params=signed)
        except httpx.TimeoutException as exc:
            logger.error("Network timeout: %s", exc)
            raise NetworkError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("Network error: %s", exc)
            raise NetworkError(f"Network error: {exc}") from exc

        return self._handle_response(resp)

    def _handle_response(self, resp: httpx.Response) -> dict[str, Any]:
        """Parse response JSON; raise ``BinanceAPIError`` on error codes."""
        logger.debug("<<< %s %s", resp.status_code, resp.text[:500])

        try:
            data = resp.json()
        except ValueError:
            logger.error("Non-JSON response: %s", resp.text[:300])
            raise BinanceAPIError(resp.status_code, -1, "Non-JSON response from API")

        if resp.status_code >= 400 or "code" in data and data.get("code", 0) < 0:
            code = data.get("code", resp.status_code)
            msg = data.get("msg", resp.text[:200])
            logger.error("API error - code=%s msg=%s", code, msg)
            raise BinanceAPIError(resp.status_code, code, msg)

        return data

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
