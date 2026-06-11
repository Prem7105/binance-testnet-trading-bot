#!/usr/bin/env python3
"""CLI entry point for the Binance Futures Testnet Trading Bot.

Usage examples
--------------
    # Market order
    python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

    # Limit order
    python cli.py order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000

    # Stop-market order (bonus)
    python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET \
        --quantity 0.001 --stop-price 60000
"""

from __future__ import annotations

import os
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot.client import BinanceAPIError, BinanceClient, NetworkError
from bot.logging_config import setup_logging
from bot.orders import place_limit_order, place_market_order, place_stop_market_order

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv()  # Load .env from project root
logger = setup_logging()
console = Console(force_terminal=True)
app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet Trading Bot - place MARKET, LIMIT, and STOP_MARKET orders.",
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> BinanceClient:
    """Build a ``BinanceClient`` from environment variables."""
    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "")
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "")
    return BinanceClient(api_key=api_key, api_secret=api_secret)


def _print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float],
    stop_price: Optional[float],
) -> None:
    """Display a Rich table summarising the order request."""
    table = Table(title="[bold cyan]Order Request Summary[/]", show_header=True, header_style="bold cyan")
    table.add_column("Parameter", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Symbol", symbol.upper())
    table.add_row("Side", side.upper())
    table.add_row("Order Type", order_type.upper())
    table.add_row("Quantity", str(quantity))

    if price is not None:
        table.add_row("Price", str(price))
    if stop_price is not None:
        table.add_row("Stop Price", str(stop_price))

    console.print()
    console.print(table)


def _print_response(result: dict) -> None:
    """Display a Rich table with key fields from the API response."""
    table = Table(title="[bold magenta]Order Response[/]", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="bold")
    table.add_column("Value", style="yellow")

    display_fields = [
        ("Order ID", "orderId"),
        ("Symbol", "symbol"),
        ("Side", "side"),
        ("Type", "type"),
        ("Status", "status"),
        ("Ordered Qty", "origQty"),
        ("Executed Qty", "executedQty"),
        ("Avg Price", "avgPrice"),
        ("Limit Price", "price"),
        ("Stop Price", "stopPrice"),
        ("Time In Force", "timeInForce"),
    ]

    for label, key in display_fields:
        value = result.get(key)
        if value is None or str(value) == "N/A":
            continue
        # Skip zero-value prices/quantities (e.g. "0.00", "0.0000")
        str_val = str(value).strip()
        if str_val.replace(".", "").replace("0", "") == "":
            continue
        table.add_row(label, str_val)

    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def order(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", "-S", help="Order side: BUY or SELL"),
    order_type: str = typer.Option(
        ..., "--type", "-t", help="Order type: MARKET, LIMIT, or STOP_MARKET"
    ),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Order quantity"),
    price: Optional[float] = typer.Option(
        None, "--price", "-p", help="Limit price (required for LIMIT orders)"
    ),
    stop_price: Optional[float] = typer.Option(
        None, "--stop-price", help="Stop trigger price (required for STOP_MARKET)"
    ),
) -> None:
    """Place an order on Binance Futures Testnet (USDT-M)."""

    # --- Request summary ---
    _print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    try:
        client = _make_client()
    except ValueError as exc:
        console.print(Panel(f"[bold red]Configuration Error:[/] {exc}", title="[red]Error[/]"))
        logger.error("Configuration error: %s", exc)
        raise typer.Exit(code=1)

    try:
        ot = order_type.strip().upper()

        if ot == "MARKET":
            result = place_market_order(client, symbol, side, quantity)
        elif ot == "LIMIT":
            if price is None:
                console.print(
                    Panel("[bold red]Price is required for LIMIT orders.[/]", title="[red]Validation Error[/]")
                )
                logger.error("Missing price for LIMIT order")
                raise typer.Exit(code=1)
            result = place_limit_order(client, symbol, side, quantity, price)
        elif ot == "STOP_MARKET":
            if stop_price is None:
                console.print(
                    Panel(
                        "[bold red]--stop-price is required for STOP_MARKET orders.[/]",
                        title="[red]Validation Error[/]",
                    )
                )
                logger.error("Missing stop-price for STOP_MARKET order")
                raise typer.Exit(code=1)
            result = place_stop_market_order(client, symbol, side, quantity, stop_price)
        else:
            console.print(
                Panel(
                    f"[bold red]Unknown order type '{order_type}'. "
                    f"Use MARKET, LIMIT, or STOP_MARKET.[/]",
                    title="[red]Validation Error[/]",
                )
            )
            logger.error("Invalid order type: %s", order_type)
            raise typer.Exit(code=1)

        # --- Success ---
        _print_response(result)
        console.print()
        console.print(
            Panel(
                f"[bold green]Order placed successfully![/]\n"
                f"Order ID: [bold]{result.get('orderId')}[/]  |  "
                f"Status: [bold]{result.get('status')}[/]",
                title="Success",
                border_style="green",
            )
        )

    except ValueError as exc:
        console.print(Panel(f"[bold red]{exc}[/]", title="[red]Validation Error[/]"))
        logger.error("Validation error: %s", exc)
        raise typer.Exit(code=1)

    except BinanceAPIError as exc:
        console.print(Panel(f"[bold red]{exc}[/]", title="[red]API Error[/]"))
        logger.error("Binance API error: %s", exc)
        raise typer.Exit(code=1)

    except NetworkError as exc:
        console.print(Panel(f"[bold red]{exc}[/]", title="[red]Network Error[/]"))
        logger.error("Network error: %s", exc)
        raise typer.Exit(code=1)

    except Exception as exc:
        console.print(
            Panel(f"[bold red]Unexpected error: {exc}[/]", title="[red]Unexpected Error[/]")
        )
        logger.exception("Unexpected error during order placement")
        raise typer.Exit(code=1)

    finally:
        try:
            client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
