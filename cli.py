#!/usr/bin/env python3
"""Binance Futures Testnet Trading Bot — CLI entry point."""

import argparse
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from bot.client import BinanceAPIError, BinanceTestnetClient, NetworkError
from bot.logging_config import (
    get_general_logger,
    get_limit_logger,
    get_market_logger,
    get_stop_limit_logger,
)
from bot.orders import OrderManager
from bot.validators import (
    validate_all,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

load_dotenv()

console = Console()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANNER = """[bold cyan]  ╔══════════════════════════════════════════╗
  ║   Binance Futures Testnet Trading Bot    ║
  ║          USDT-M Perpetual Futures        ║
  ╚══════════════════════════════════════════╝[/bold cyan]"""

ORDER_TYPE_DESCRIPTIONS = {
    "MARKET":     "Execute immediately at the best available price",
    "LIMIT":      "Execute at a specific price or better",
    "STOP_LIMIT": "Trigger a limit order when the market hits a stop price",
}

# Realistic simulated mid-prices for common pairs (dry-run only)
_SIMULATED_PRICES: Dict[str, float] = {
    "BTCUSDT": 43521.50,
    "ETHUSDT":  2318.75,
    "BNBUSDT":   412.30,
    "SOLUSDT":   148.90,
    "XRPUSDT":     0.5921,
}
_DEFAULT_PRICE = 100.0


# ---------------------------------------------------------------------------
# Shared display helpers
# ---------------------------------------------------------------------------

def _side_color(side: str) -> str:
    return "green" if side.upper() == "BUY" else "red"


def load_credentials() -> tuple[str, str]:
    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "").strip()

    if not api_key or not api_secret:
        console.print(
            Panel(
                "[bold red]Missing API credentials.[/bold red]\n\n"
                "Set the following environment variables (or add a [cyan].env[/cyan] file):\n\n"
                "  [yellow]BINANCE_TESTNET_API_KEY[/yellow]=your_key\n"
                "  [yellow]BINANCE_TESTNET_API_SECRET[/yellow]=your_secret\n\n"
                "Register and generate keys at:\n"
                "  [cyan underline]https://testnet.binancefuture.com[/cyan underline]",
                title="[red]⚠  Configuration Error[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        sys.exit(1)

    return api_key, api_secret


def print_request_summary(params: Dict[str, Any]) -> None:
    side = params["side"]
    color = _side_color(side)
    order_type = params["order_type"]

    table = Table(
        title="[bold]Order Request[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
    )
    table.add_column("Field", style="bold dim", width=16)
    table.add_column("Value")

    table.add_row("Symbol", f"[bold white]{params['symbol']}[/bold white]")
    table.add_row("Side", f"[bold {color}]{side}[/bold {color}]")
    table.add_row("Type", f"[bold]{order_type}[/bold]")
    table.add_row("Quantity", str(params["quantity"]))

    if params.get("stop_price") is not None:
        table.add_row("Stop (Trigger)", f"[yellow]{params['stop_price']:.8g}[/yellow]")

    if params.get("price") is not None:
        label = "Limit Price" if order_type in ("LIMIT", "STOP_LIMIT") else "Price"
        table.add_row(label, f"{params['price']:.8g}")

    console.print(table)

    if order_type == "STOP_LIMIT":
        console.print(
            f"  [dim]When price reaches [yellow]{params['stop_price']:.8g}[/yellow], "
            f"a limit order at [white]{params['price']:.8g}[/white] will be placed.[/dim]"
        )
        console.print()


def print_order_response(response: Dict[str, Any], dry_run: bool = False) -> None:
    side = response.get("side", "")
    color = _side_color(side)
    status = response.get("status", "N/A")

    title = "[bold]Order Response[/bold]"
    if dry_run:
        title += "  [dim yellow][DRY RUN][/dim yellow]"

    table = Table(
        title=title,
        box=box.ROUNDED,
        border_style="green" if not dry_run else "yellow",
        show_header=True,
        header_style="bold green" if not dry_run else "bold yellow",
        padding=(0, 1),
    )
    table.add_column("Field", style="bold dim", width=18)
    table.add_column("Value")

    avg_price = response.get("avgPrice", "0") or "0"
    limit_price = response.get("price", "0") or "0"
    stop_price = response.get("stopPrice", "0") or "0"
    status_color = "green" if status in ("FILLED", "NEW") else "yellow"

    table.add_row("Order ID", f"[bold white]{response.get('orderId', 'N/A')}[/bold white]")
    table.add_row("Symbol", str(response.get("symbol", "N/A")))
    table.add_row("Status", f"[bold {status_color}]{status}[/bold {status_color}]")
    table.add_row("Side", f"[bold {color}]{side}[/bold {color}]")
    table.add_row("Type", str(response.get("type", "N/A")))
    table.add_row("Ordered Qty", str(response.get("origQty", "N/A")))
    table.add_row("Executed Qty", str(response.get("executedQty", "N/A")))

    if float(avg_price) > 0:
        table.add_row("Avg Fill Price", f"{float(avg_price):.8g}")

    if float(stop_price) > 0:
        table.add_row("Stop (Trigger)", f"[yellow]{float(stop_price):.8g}[/yellow]")

    if float(limit_price) > 0:
        table.add_row("Limit Price", f"{float(limit_price):.8g}")

    table.add_row("Time in Force", str(response.get("timeInForce", "N/A")))
    table.add_row("Update Time (ms)", str(response.get("updateTime", "N/A")))

    console.print(table)


def confirm_order() -> bool:
    console.print()
    try:
        answer = console.input(
            "[yellow]Confirm order? [[bold]y[/bold]/N]: [/yellow]"
        ).strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Aborted.[/dim]")
        return False
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Dry-run helpers
# ---------------------------------------------------------------------------

def _simulated_price(symbol: str) -> float:
    base = _SIMULATED_PRICES.get(symbol, _DEFAULT_PRICE)
    # tiny random jitter so repeated runs differ slightly
    return round(base * random.uniform(0.9995, 1.0005), 2)


def generate_dry_run_response(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a realistic-looking Binance Futures order response without
    touching the network. Used exclusively by --dry-run.
    """
    symbol = params["symbol"]
    side = params["side"]
    order_type = params["order_type"]
    quantity = params["quantity"]
    price = params.get("price")
    stop_price = params.get("stop_price")

    now_ms = int(time.time() * 1000)
    order_id = int(now_ms / 1000) * 1000 + random.randint(100, 999)

    mid = _simulated_price(symbol)

    if order_type == "MARKET":
        # Market orders fill immediately
        avg_fill = mid
        executed_qty = quantity
        status = "FILLED"
        api_type = "MARKET"
        resp_price = "0"
        resp_stop = "0"
        tif = "GTC"
    elif order_type == "LIMIT":
        # Limit orders are open (NEW) unless price crosses mid
        executed_qty = 0.0
        status = "NEW"
        api_type = "LIMIT"
        avg_fill = 0.0
        resp_price = str(price)
        resp_stop = "0"
        tif = "GTC"
    else:  # STOP_LIMIT
        executed_qty = 0.0
        status = "NEW"
        api_type = "STOP"
        avg_fill = 0.0
        resp_price = str(price)
        resp_stop = str(stop_price)
        tif = "GTC"

    return {
        "orderId": order_id,
        "symbol": symbol,
        "status": status,
        "clientOrderId": f"dryrn_{order_id}",
        "price": resp_price,
        "avgPrice": f"{avg_fill:.2f}" if avg_fill else "0",
        "origQty": str(quantity),
        "executedQty": str(executed_qty),
        "cumQty": str(executed_qty),
        "cumQuote": f"{executed_qty * avg_fill:.4f}",
        "timeInForce": tif,
        "type": api_type,
        "side": side,
        "stopPrice": resp_stop,
        "updateTime": now_ms,
    }


def run_dry_run(params: Dict[str, Any]) -> None:
    """
    Validate → generate a simulated response → log it → display it.
    No credentials required. No network calls made.
    """
    console.print()
    console.print(
        Panel(
            "[bold yellow]DRY RUN — no order will be sent to the exchange[/bold yellow]\n"
            "[dim]Simulating a realistic API response based on your inputs.[/dim]",
            border_style="yellow",
            padding=(0, 2),
        )
    )
    console.print(Rule("[dim]Simulating order…[/dim]"))

    response = generate_dry_run_response(params)
    order_type = params["order_type"]

    # Log exactly as a real order would, clearly marked DRY RUN
    if order_type == "MARKET":
        log = get_market_logger()
    elif order_type == "LIMIT":
        log = get_limit_logger()
    else:
        log = get_stop_limit_logger()

    log.info("[DRY RUN] Request params | %s", params)
    log.info("[DRY RUN] Simulated response | %s", response)

    general = get_general_logger()
    general.info("[DRY RUN] %s %s %s qty=%s → simulated orderId=%s status=%s",
                 order_type, params["side"], params["symbol"],
                 params["quantity"], response["orderId"], response["status"])

    console.print()
    print_order_response(response, dry_run=True)
    console.print()
    console.print(
        Panel(
            "[bold yellow]✓  Dry run complete — no order was sent.[/bold yellow]\n"
            "[dim]All inputs are valid. Remove [cyan]--dry-run[/cyan] to place a real order.[/dim]",
            border_style="yellow",
            padding=(0, 2),
        )
    )


# ---------------------------------------------------------------------------
# Real order submission
# ---------------------------------------------------------------------------

def submit_order(params: Dict[str, Any]) -> None:
    """Connect to the API and place the order. Handles all errors."""
    console.print()
    console.print(Rule("[dim]Submitting order…[/dim]"))

    api_key, api_secret = load_credentials()

    try:
        client = BinanceTestnetClient(api_key, api_secret)
        manager = OrderManager(client)

        response = manager.place_order(
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params.get("price"),
            stop_price=params.get("stop_price"),
        )
    except BinanceAPIError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]\n\n"
                + (f"[dim]Raw: {exc.response_data}[/dim]" if exc.response_data else ""),
                title="[red]⚠  API Error[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        sys.exit(1)
    except NetworkError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[red]⚠  Network Error[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        sys.exit(1)
    except Exception as exc:
        console.print(
            Panel(
                f"[red]Unexpected error:[/red] {exc}",
                title="[red]⚠  Error[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        sys.exit(1)

    console.print()
    print_order_response(response)
    console.print()
    console.print(
        Panel(
            "[bold green]✓  Order placed successfully![/bold green]",
            border_style="green",
            padding=(0, 2),
        )
    )


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def _prompt(label: str, hint: str = "") -> str:
    hint_text = f" [dim]{hint}[/dim]" if hint else ""
    try:
        value = console.input(f"  [bold cyan]{label}[/bold cyan]{hint_text}: ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[dim]Aborted.[/dim]")
        sys.exit(0)
    return value


def _prompt_choice(label: str, choices: List[str], descriptions: Dict[str, str] = None) -> str:
    while True:
        console.print(f"\n  [bold cyan]{label}[/bold cyan]")
        for i, choice in enumerate(choices, 1):
            desc = f"  [dim]{descriptions[choice]}[/dim]" if descriptions and choice in descriptions else ""
            console.print(f"    [bold white]{i}[/bold white]  {choice}{desc}")

        try:
            raw = console.input("\n  Enter number or name: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n\n[dim]Aborted.[/dim]")
            sys.exit(0)

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                chosen = choices[idx]
                console.print(f"  [green]✓[/green]  {chosen}")
                return chosen
            console.print(f"  [red]✗[/red]  Please enter a number between 1 and {len(choices)}")
            continue

        upper = raw.upper()
        if upper in choices:
            console.print(f"  [green]✓[/green]  {upper}")
            return upper

        console.print(
            f"  [red]✗[/red]  Invalid choice '{raw}'. "
            f"Enter a number (1–{len(choices)}) or one of: {', '.join(choices)}"
        )


def _prompt_validated(label: str, validator, hint: str = "") -> Optional[str]:
    while True:
        raw = _prompt(label, hint)
        if not raw:
            console.print(f"  [red]✗[/red]  This field is required.")
            continue
        ok, result = validator(raw)
        if ok:
            console.print(f"  [green]✓[/green]  {result}")
            return raw
        console.print(f"  [red]✗[/red]  {result}")


def _step_header(step: int, total: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold]Step {step}/{total} — {title}[/bold]", style="cyan"))


def _show_progress(collected: Dict[str, Any]) -> None:
    if not collected:
        return
    parts = []
    for k, v in collected.items():
        if v is not None:
            label = k.replace("_", " ").title()
            parts.append(f"[dim]{label}:[/dim] [white]{v}[/white]")
    console.print("  " + "  │  ".join(parts))


def run_interactive(dry_run: bool = False) -> None:
    console.print(BANNER)
    console.print()
    mode_note = "  [yellow][DRY RUN — no order will be sent][/yellow]\n" if dry_run else ""
    console.print(
        Panel(
            f"[bold]Interactive Order Builder[/bold]\n"
            f"{mode_note}"
            "[dim]Answer each prompt — press Enter to confirm, Ctrl+C to abort.[/dim]",
            border_style="cyan" if not dry_run else "yellow",
            padding=(0, 2),
        )
    )

    collected: Dict[str, Any] = {}

    _step_header(1, "?", "Symbol")
    console.print("  [dim]Enter a USDT-M futures trading pair, e.g. BTCUSDT, ETHUSDT[/dim]")
    raw_symbol = _prompt_validated("Symbol", lambda v: validate_symbol(v), hint="e.g. BTCUSDT")
    collected["symbol"] = raw_symbol.upper()

    _step_header(2, "?", "Side")
    _show_progress(collected)
    side = _prompt_choice(
        "Which side?",
        ["BUY", "SELL"],
        {"BUY": "Open a long / close a short", "SELL": "Open a short / close a long"},
    )
    collected["side"] = side

    _step_header(3, "?", "Order Type")
    _show_progress(collected)
    order_type = _prompt_choice("Which order type?", ["MARKET", "LIMIT", "STOP_LIMIT"], ORDER_TYPE_DESCRIPTIONS)
    collected["order_type"] = order_type

    if order_type == "MARKET":
        total_steps = 5
    elif order_type == "LIMIT":
        total_steps = 6
    else:
        total_steps = 7

    _step_header(4, total_steps, "Quantity")
    _show_progress(collected)
    console.print("  [dim]How many contracts? (e.g. 0.001 for 0.001 BTC)[/dim]")
    raw_qty = _prompt_validated("Quantity", lambda v: validate_quantity(v), hint="e.g. 0.001")
    collected["quantity"] = float(raw_qty)

    raw_stop_price: Optional[str] = None
    if order_type == "STOP_LIMIT":
        _step_header(5, total_steps, "Stop (Trigger) Price")
        _show_progress(collected)
        console.print("  [dim]The market price that [bold]activates[/bold] your limit order.[/dim]")
        raw_stop_price = _prompt_validated(
            "Stop Price", lambda v: validate_stop_price(v, "STOP_LIMIT"), hint="trigger price"
        )
        collected["stop_price"] = float(raw_stop_price)

    raw_price: Optional[str] = None
    if order_type in ("LIMIT", "STOP_LIMIT"):
        step_n = 6 if order_type == "STOP_LIMIT" else 5
        _step_header(step_n, total_steps, "Limit Price")
        _show_progress(collected)
        if order_type == "STOP_LIMIT":
            console.print("  [dim]The price at which to [bold]execute[/bold] once the stop triggers.[/dim]")
        else:
            console.print("  [dim]The order executes at this price or better.[/dim]")
        raw_price = _prompt_validated(
            "Limit Price", lambda v: validate_price(v, order_type), hint="e.g. 44100"
        )
        collected["price"] = float(raw_price)

    _step_header(total_steps, total_steps, "Review & Confirm")

    params: Dict[str, Any] = {
        "symbol":     collected["symbol"],
        "side":       collected["side"],
        "order_type": collected["order_type"],
        "quantity":   collected["quantity"],
        "price":      collected.get("price"),
        "stop_price": collected.get("stop_price"),
    }

    print_request_summary(params)

    if not confirm_order():
        console.print("[dim]Order cancelled.[/dim]")
        sys.exit(0)

    if dry_run:
        run_dry_run(params)
    else:
        submit_order(params)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Place orders on Binance Futures Testnet (USDT-M)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Order types:
  MARKET      Execute immediately at best price
  LIMIT       Execute at --price or better
  STOP_LIMIT  Trigger a limit at --price when market hits --stop-price

Modes:
  Interactive (guided):
    python cli.py --interactive
    python cli.py --interactive --dry-run

  Direct:
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

  Dry-run (no order sent, log files written):
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --dry-run

Examples:
  Market BUY:
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

  Limit SELL:
    python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3200

  Stop-Limit BUY (trigger 44000, limit 44100):
    python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT \\
        --quantity 0.001 --stop-price 44000 --price 44100

  Dry-run any order (no credentials needed):
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --dry-run
""",
    )

    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Launch interactive step-by-step order builder")
    parser.add_argument("--dry-run", "-n", dest="dry_run", action="store_true",
                        help="Validate and simulate — no order sent, log files written")
    parser.add_argument("--symbol", metavar="SYMBOL", help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--type", dest="order_type", choices=["MARKET", "LIMIT", "STOP_LIMIT"],
                        help="Order type")
    parser.add_argument("--quantity", metavar="QTY", help="Order quantity")
    parser.add_argument("--price", metavar="PRICE", default=None,
                        help="Limit price — required for LIMIT and STOP_LIMIT")
    parser.add_argument("--stop-price", dest="stop_price", metavar="STOP_PRICE", default=None,
                        help="Trigger price — required for STOP_LIMIT")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    return parser


# ---------------------------------------------------------------------------
# Non-interactive flow
# ---------------------------------------------------------------------------

def run_direct(args: argparse.Namespace) -> None:
    required = ["symbol", "side", "order_type", "quantity"]
    missing = [f"--{f.replace('_', '-')}" for f in required if not getattr(args, f, None)]
    if missing:
        console.print(
            Panel(
                "The following arguments are required when not using [cyan]--interactive[/cyan]:\n"
                + "\n".join(f"  [yellow]{m}[/yellow]" for m in missing),
                title="[red]Missing Arguments[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        console.print("[dim]Tip: run [cyan]python cli.py --interactive[/cyan] to be guided step by step.[/dim]\n")
        sys.exit(1)

    ok, result = validate_all(
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
        stop_price=args.stop_price,
    )

    if not ok:
        console.print(
            Panel(
                "\n".join(f"  [red]✗[/red]  {e}" for e in result),
                title="[red]Validation Errors[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        if args.order_type == "STOP_LIMIT":
            console.print(
                "  [dim]Tip: STOP_LIMIT needs both [yellow]--stop-price[/yellow] "
                "(trigger) and [yellow]--price[/yellow] (limit).[/dim]\n"
            )
        sys.exit(1)

    params: Dict[str, Any] = result

    print_request_summary(params)

    if not args.yes and not args.dry_run:
        if not confirm_order():
            console.print("[dim]Order cancelled.[/dim]")
            sys.exit(0)

    if args.dry_run:
        run_dry_run(params)
    else:
        submit_order(params)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.interactive:
        run_interactive(dry_run=args.dry_run)
    else:
        console.print(BANNER)
        console.print()
        run_direct(args)


if __name__ == "__main__":
    main()
