"""Binance Futures Testnet REST API client."""

import hashlib
import hmac
import time
from typing import Any, Dict

import requests

from .logging_config import get_general_logger

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
REQUEST_TIMEOUT = 10  # seconds


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, message: str, code: int = 0, response_data: Dict = None):
        super().__init__(message)
        self.code = code
        self.response_data = response_data or {}


class NetworkError(Exception):
    """Raised on network/connectivity failures."""


class BinanceTestnetClient:
    """Thin wrapper around Binance Futures Testnet REST API."""

    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise ValueError("API key and secret must not be empty")
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = TESTNET_BASE_URL
        self.logger = get_general_logger()

        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self.api_key})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_params(self, **kwargs: Any) -> Dict[str, Any]:
        params = {k: v for k, v in kwargs.items() if v is not None}
        params["timestamp"] = self._timestamp()
        params["signature"] = self._sign(params)
        return params

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_order(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Place a new futures order.

        Keyword args are forwarded directly as Binance API parameters
        (symbol, side, type, quantity, price, timeInForce, …).
        """
        endpoint = "/fapi/v1/order"
        url = f"{self.base_url}{endpoint}"

        log_safe = {k: v for k, v in kwargs.items()}
        self.logger.info("POST %s | params=%s", endpoint, log_safe)

        params = self._signed_params(**kwargs)

        try:
            response = self._session.post(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            self.logger.info("Response %s | %s", response.status_code, data)
            return data

        except requests.exceptions.HTTPError as exc:
            error_data: Dict[str, Any] = {}
            try:
                error_data = exc.response.json()
            except Exception:
                pass
            code = error_data.get("code", exc.response.status_code)
            msg = error_data.get("msg", str(exc))
            self.logger.error(
                "HTTP %s | code=%s | msg=%s", exc.response.status_code, code, msg
            )
            raise BinanceAPIError(
                f"Binance API error (code {code}): {msg}",
                code=code,
                response_data=error_data,
            ) from exc

        except requests.exceptions.ConnectionError as exc:
            self.logger.error("Connection error: %s", exc)
            raise NetworkError(
                f"Could not connect to Binance Testnet ({TESTNET_BASE_URL}). "
                "Check your internet connection."
            ) from exc

        except requests.exceptions.Timeout as exc:
            self.logger.error("Request timed out after %ss: %s", REQUEST_TIMEOUT, exc)
            raise NetworkError(
                f"Request timed out after {REQUEST_TIMEOUT}s. "
                "The testnet may be slow — try again."
            ) from exc

        except Exception as exc:
            self.logger.error("Unexpected error: %s", exc, exc_info=True)
            raise
