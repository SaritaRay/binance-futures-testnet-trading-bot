"""Input validation for trading bot CLI arguments."""

from typing import Any, Dict, List, Optional, Tuple

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}


def validate_symbol(symbol: str) -> Tuple[bool, Any]:
    symbol = symbol.strip().upper()
    if not symbol:
        return False, "Symbol cannot be empty"
    if not symbol.endswith("USDT"):
        return False, (
            f"Symbol '{symbol}' should end with 'USDT' for USDT-M futures "
            f"(e.g. BTCUSDT, ETHUSDT)"
        )
    if len(symbol) < 6:
        return False, f"Symbol '{symbol}' is too short"
    return True, symbol


def validate_side(side: str) -> Tuple[bool, Any]:
    side = side.strip().upper()
    if side not in VALID_SIDES:
        return False, f"Side must be one of: {', '.join(sorted(VALID_SIDES))}"
    return True, side


def validate_order_type(order_type: str) -> Tuple[bool, Any]:
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        return False, f"Order type must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}"
    return True, order_type


def validate_quantity(quantity: str) -> Tuple[bool, Any]:
    try:
        qty = float(quantity)
        if qty <= 0:
            return False, "Quantity must be greater than 0"
        return True, qty
    except (ValueError, TypeError):
        return False, f"Invalid quantity '{quantity}': must be a positive number"


def validate_price(price: Optional[str], order_type: str) -> Tuple[bool, Any]:
    if order_type in ("LIMIT", "STOP_LIMIT"):
        if price is None or price == "":
            return False, f"Price is required for {order_type} orders (use --price)"
        try:
            p = float(price)
            if p <= 0:
                return False, "Price must be greater than 0"
            return True, p
        except (ValueError, TypeError):
            return False, f"Invalid price '{price}': must be a positive number"
    return True, None


def validate_stop_price(stop_price: Optional[str], order_type: str) -> Tuple[bool, Any]:
    if order_type == "STOP_LIMIT":
        if stop_price is None or stop_price == "":
            return False, "Stop price is required for STOP_LIMIT orders (use --stop-price)"
        try:
            sp = float(stop_price)
            if sp <= 0:
                return False, "Stop price must be greater than 0"
            return True, sp
        except (ValueError, TypeError):
            return False, f"Invalid stop price '{stop_price}': must be a positive number"
    return True, None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> Tuple[bool, Any]:
    """
    Validate all order inputs.

    Returns:
        (True, params_dict)  on success
        (False, [error_msg, ...])  on failure
    """
    errors: List[str] = []
    params: Dict[str, Any] = {}

    ok, result = validate_symbol(symbol)
    if ok:
        params["symbol"] = result
    else:
        errors.append(f"Symbol     — {result}")

    ok, result = validate_side(side)
    if ok:
        params["side"] = result
    else:
        errors.append(f"Side       — {result}")

    ok, result = validate_order_type(order_type)
    if ok:
        params["order_type"] = result
    else:
        errors.append(f"Order type — {result}")

    ok, result = validate_quantity(quantity)
    if ok:
        params["quantity"] = result
    else:
        errors.append(f"Quantity   — {result}")

    resolved_type = params.get("order_type", order_type.strip().upper())

    ok, result = validate_price(price, resolved_type)
    if ok:
        params["price"] = result
    else:
        errors.append(f"Price      — {result}")

    ok, result = validate_stop_price(stop_price, resolved_type)
    if ok:
        params["stop_price"] = result
    else:
        errors.append(f"Stop price — {result}")

    if errors:
        return False, errors
    return True, params
