import json
import os
import time
from datetime import datetime, UTC
from typing import Dict, Optional, Tuple

import config


class PriceCache:
    """Manages JSON file-based price caching with expiry."""

    def __init__(self, cache_file: str = config.CACHE_FILE) -> None:
        self.cache_file = cache_file

    def load(self) -> Optional[Dict[str, float]]:
        """Load prices from cache file if valid and not expired."""
        if not os.path.exists(self.cache_file):
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "prices" not in data or "timestamp" not in data:
                return None

            # Check if cache is expired
            timestamp_str = data["timestamp"]
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            age_minutes = (datetime.now(UTC) - timestamp).total_seconds() / 60

            if age_minutes > config.CACHE_EXPIRY_MINUTES:
                return None  # Cache expired

            return data["prices"]
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    def save(self, prices: Dict[str, float]) -> None:
        """Save prices to cache file with timestamp."""
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        data = {
            "timestamp": timestamp,
            "prices": prices,
        }
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass  # Silently fail if can't write cache

    def get_timestamp(self) -> Optional[str]:
        """Get the timestamp of cached prices."""
        if not os.path.exists(self.cache_file):
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("timestamp")
        except (json.JSONDecodeError, OSError):
            return None


class PriceProvider:
    """Abstract base class for price providers."""

    def fetch_prices(self) -> Tuple[Dict[str, float], str]:
        """
        Fetch prices from provider.
        Returns: (prices dict, source string)
        Raises: Exception if fetch fails
        """
        raise NotImplementedError


class AlphaVantageProvider(PriceProvider):
    """Fetches prices from Alpha Vantage API."""

    def __init__(self, api_key: str = config.ALPHA_VANTAGE_API_KEY) -> None:
        self.api_key = api_key
        self.stocks = config.SUPPORTED_STOCKS

    def fetch_prices(self) -> Tuple[Dict[str, float], str]:
        """Fetch prices from Alpha Vantage API."""
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not configured")

        try:
            import requests
        except ImportError:
            raise ImportError("requests library required for API integration")

        prices = {}
        for symbol in self.stocks:
            try:
                response = requests.get(
                    config.ALPHA_VANTAGE_BASE_URL,
                    params={
                        "function": "GLOBAL_QUOTE",
                        "symbol": symbol,
                        "apikey": self.api_key,
                    },
                    timeout=config.API_TIMEOUT,
                )
                response.raise_for_status()

                data = response.json()

                # Check for API errors
                if "Error Message" in data:
                    raise ValueError(f"API Error: {data['Error Message']}")
                if "Note" in data:
                    raise ValueError("API rate limit reached")

                quote = data.get("Global Quote", {})
                price = quote.get("05. price")

                if price:
                    prices[symbol] = float(price)
                else:
                    raise ValueError(f"No price data for {symbol}")

            except Exception as e:
                raise ValueError(f"Failed to fetch price for {symbol}: {str(e)}")

        return prices, "live"


class CombinedPriceProvider:
    """Tries multiple price sources with fallback chain."""

    def __init__(
        self,
        cache: Optional[PriceCache] = None,
        api_provider: Optional[AlphaVantageProvider] = None,
    ) -> None:
        self.cache = cache or PriceCache()
        self.api_provider = api_provider

    def get_prices(self, use_cache_only: bool = False) -> Tuple[Dict[str, float], str]:
        """
        Get prices using fallback chain:
        1. Try API (if use_cache_only=False and configured)
        2. Try cache file
        3. Use hardcoded defaults

        Returns: (prices dict, source string)
        """
        # Option 1: Try API if enabled
        if not use_cache_only and self.api_provider:
            try:
                prices, source = self.api_provider.fetch_prices()
                self.cache.save(prices)  # Update cache
                return prices, source
            except Exception:
                pass  # Fallback to cache on API failure

        # Option 2: Try cache
        cached_prices = self.cache.load()
        if cached_prices:
            return cached_prices, "cached"

        # Option 3: Use hardcoded defaults
        return config.DEFAULT_PRICES.copy(), "fallback"


def get_prices(use_cache_only: bool = False) -> Tuple[Dict[str, float], str]:
    """
    Convenience function to get prices with default provider setup.

    Returns: (prices dict, source string)
    """
    api_provider = AlphaVantageProvider() if config.ALPHA_VANTAGE_API_KEY else None
    provider = CombinedPriceProvider(api_provider=api_provider)
    return provider.get_prices(use_cache_only=use_cache_only)
