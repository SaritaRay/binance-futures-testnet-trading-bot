"""Order placement logic for Binance Futures Testnet."""

from typing import Any, Dict, Optional

from .client import BinanceTestnetClient
from .logging_config import get_limit_logger, get_market_logger, get_stop_limit_logger


class OrderManager:
    """High-level order placement manager."""

    def __init__(self, client: BinanceTestnetClient):
        self.client = client
        self._market_log = get_market_logger()
        self._limit_log = get_limit_logger()
        self._stop_limit_log = get_stop_limit_logger()

    # ------------------------------------------------------------------
    # Market orders
    # ------------------------------------------------------------------

    def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> Dict[str, Any]:
        params = dict(symbol=symbol, side=side, type="MARKET", quantity=quantity)
        self._market_log.info("Placing MARKET order | %s", params)
        result = self.client.new_order(**params)
        self._market_log.info("MARKET order result | %s", result)
        return result

    # ------------------------------------------------------------------
    # Limit orders
    # ------------------------------------------------------------------

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        params = dict(
            symbol=symbol,
            side=side,
            type="LIMIT",
            quantity=quantity,
            price=price,
            timeInForce=time_in_force,
        )
        self._limit_log.info("Placing LIMIT order | %s", params)
        result = self.client.new_order(**params)
        self._limit_log.info("LIMIT order result | %s", result)
        return result

    # ------------------------------------------------------------------
    # Stop-Limit orders
    # ------------------------------------------------------------------

    def place_stop_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_price: float,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """
        Place a Stop-Limit order on Binance Futures.

        Binance Futures uses type="STOP" for stop-limit orders:
          - stopPrice: the trigger price that activates the order
          - price:     the limit price at which to execute once triggered
        """
        params = dict(
            symbol=symbol,
            side=side,
            type="STOP",          # Binance Futures API name for Stop-Limit
            quantity=quantity,
            price=price,
            stopPrice=stop_price,
            timeInForce=time_in_force,
        )
        self._stop_limit_log.info("Placing STOP_LIMIT order | %s", params)
        result = self.client.new_order(**params)
        self._stop_limit_log.info("STOP_LIMIT order result | %s", result)
        return result

    # ------------------------------------------------------------------
    # Generic dispatcher
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Dispatch to the correct order placement method."""
        if order_type == "MARKET":
            return self.place_market_order(symbol, side, quantity)

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("Price is required for LIMIT orders")
            return self.place_limit_order(symbol, side, quantity, price)

        if order_type == "STOP_LIMIT":
            if price is None:
                raise ValueError("Price is required for STOP_LIMIT orders")
            if stop_price is None:
                raise ValueError("Stop price is required for STOP_LIMIT orders")
            return self.place_stop_limit_order(symbol, side, quantity, price, stop_price)

        raise ValueError(f"Unsupported order type: {order_type!r}")
