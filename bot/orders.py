"""Order placement logic.

Orchestrates validation -> API call -> result formatting for each order type.
This module is the bridge between the CLI layer and the raw client.
"""

from __future__ import annotations

import logging
from typing import Any

from bot.client import BinanceClient
from bot.validators import (
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

logger = logging.getLogger("trading_bot.orders")


def _format_result(response: dict[str, Any]) -> dict[str, Any]:
    """Extract the most relevant fields from a Binance order response.

    Handles both standard order responses (orderId, status) and
    algo/conditional order responses (algoId, algoStatus).
    """
    return {
        "orderId": response.get("orderId") or response.get("algoId"),
        "symbol": response.get("symbol"),
        "side": response.get("side"),
        "type": response.get("type") or response.get("orderType"),
        "status": response.get("status") or response.get("algoStatus"),
        "origQty": response.get("origQty") or response.get("quantity"),
        "executedQty": response.get("executedQty"),
        "avgPrice": response.get("avgPrice", "N/A"),
        "price": response.get("price", "N/A"),
        "stopPrice": response.get("stopPrice") or response.get("triggerPrice", "N/A"),
        "timeInForce": response.get("timeInForce", "N/A"),
        "updateTime": response.get("updateTime"),
    }


def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: float,
) -> dict[str, Any]:
    """Validate inputs and place a MARKET order.

    Returns a formatted result dict.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    validate_order_type("MARKET")
    quantity = validate_quantity(quantity)

    logger.info(
        "Placing MARKET %s order: %s qty=%s", side, symbol, quantity
    )

    response = client.place_order(
        symbol=symbol,
        side=side,
        order_type="MARKET",
        quantity=quantity,
    )

    result = _format_result(response)
    logger.info("Order placed successfully -- orderId=%s status=%s", result["orderId"], result["status"])
    return result


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    time_in_force: str = "GTC",
) -> dict[str, Any]:
    """Validate inputs and place a LIMIT order.

    Returns a formatted result dict.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    validate_order_type("LIMIT")
    quantity = validate_quantity(quantity)
    price = validate_price(price, "LIMIT")

    logger.info(
        "Placing LIMIT %s order: %s qty=%s price=%s tif=%s",
        side, symbol, quantity, price, time_in_force,
    )

    response = client.place_order(
        symbol=symbol,
        side=side,
        order_type="LIMIT",
        quantity=quantity,
        price=price,
        time_in_force=time_in_force,
    )

    result = _format_result(response)
    logger.info("Order placed successfully -- orderId=%s status=%s", result["orderId"], result["status"])
    return result


def place_stop_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
) -> dict[str, Any]:
    """Validate inputs and place a STOP-MARKET order (bonus feature).

    A stop-market order triggers a market order when *stop_price* is reached.
    No limit price is needed.

    Returns a formatted result dict.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    validate_order_type("STOP_MARKET")
    quantity = validate_quantity(quantity)
    stop_price = validate_stop_price(stop_price, "STOP_MARKET")

    logger.info(
        "Placing STOP_MARKET %s order: %s qty=%s stopPrice=%s",
        side, symbol, quantity, stop_price,
    )

    response = client.place_order(
        symbol=symbol,
        side=side,
        order_type="STOP_MARKET",
        quantity=quantity,
        stop_price=stop_price,
    )

    result = _format_result(response)
    logger.info("Order placed successfully -- orderId=%s status=%s", result["orderId"], result["status"])
    return result

