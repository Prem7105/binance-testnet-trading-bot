"""Input validators for order parameters.

Every public function raises ``ValueError`` with a clear message on invalid
input so the CLI layer can catch and display it to the user.
"""

from __future__ import annotations

VALID_SIDES = ("BUY", "SELL")
VALID_ORDER_TYPES = ("MARKET", "LIMIT", "STOP_MARKET")


def validate_symbol(symbol: str) -> str:
    """Return the upper-cased symbol after basic sanity checks."""
    if not symbol or not symbol.strip():
        raise ValueError("Symbol must not be empty.")
    cleaned = symbol.strip().upper()
    if not cleaned.isalnum():
        raise ValueError(
            f"Symbol must be alphanumeric (got '{symbol}'). Example: BTCUSDT"
        )
    return cleaned


def validate_side(side: str) -> str:
    """Return the validated side (BUY or SELL)."""
    if not side:
        raise ValueError("Side must not be empty.")
    upper = side.strip().upper()
    if upper not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(VALID_SIDES)}"
        )
    return upper


def validate_order_type(order_type: str) -> str:
    """Return the validated order type."""
    if not order_type:
        raise ValueError("Order type must not be empty.")
    upper = order_type.strip().upper()
    if upper not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(VALID_ORDER_TYPES)}"
        )
    return upper


def validate_quantity(quantity: float) -> float:
    """Ensure quantity is a positive number."""
    try:
        qty = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a number (got '{quantity}').")
    if qty <= 0:
        raise ValueError(f"Quantity must be positive (got {qty}).")
    return qty


def validate_price(price: float | None, order_type: str) -> float | None:
    """Validate price based on order type.

    - MARKET orders: price is ignored (returns None).
    - LIMIT orders: price is required and must be positive.
    - STOP_MARKET orders: price is ignored (uses stopPrice instead).
    """
    if order_type in ("MARKET", "STOP_MARKET"):
        return None  # price not applicable
    if price is None:
        raise ValueError(f"Price is required for {order_type} orders.")
    try:
        p = float(price)
    except (TypeError, ValueError):
        raise ValueError(f"Price must be a number (got '{price}').")
    if p <= 0:
        raise ValueError(f"Price must be positive (got {p}).")
    return p


def validate_stop_price(stop_price: float | None, order_type: str) -> float | None:
    """Validate stop price -- required only for STOP_MARKET orders."""
    if order_type != "STOP_MARKET":
        return None

    if stop_price is None:
        raise ValueError("Stop price is required for STOP_MARKET orders.")
    try:
        sp = float(stop_price)
    except (TypeError, ValueError):
        raise ValueError(f"Stop price must be a number (got '{stop_price}').")
    if sp <= 0:
        raise ValueError(f"Stop price must be positive (got {sp}).")
    return sp
