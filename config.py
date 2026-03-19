import os

# Alpha Vantage API Configuration
ALPHA_VANTAGE_API_KEY = os.environ.get("STOCK_TRACKER_API_KEY", "")

# Supported stocks to track
SUPPORTED_STOCKS = ["Apple", "Tesla", "Alphabet", "Microsoft", "Amazon"]

# Cache configuration
CACHE_FILE = "price_cache.json"
CACHE_EXPIRY_MINUTES = 60

# API configuration
API_TIMEOUT = 10  # seconds
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Default hardcoded prices (fallback)
DEFAULT_PRICES = {
    "Apple": 180.0,
    "Tesla": 250.0,
    "Alphabet": 2800.0,
    "Microsoft": 320.0,
    "Amazon": 3500.0,
}
