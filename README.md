# CodeAlpha Stock Portfolio Tracker

A portfolio tracker built around a shared Python core with two usable interfaces:
- `CLI` for quick terminal-based workflows
- `GUI` for a richer desktop dashboard with analytics
- `docs/` browser demo for a lightweight showcase in HTML, CSS, and JavaScript

The application stores holdings in SQLite, records transactions and snapshots, exports portfolio summaries in TXT, CSV, and PDF formats, and can refresh prices through Alpha Vantage with cache and fallback support.

## Features

### Core tracking
- Track holdings by supported stock name and quantity
- Aggregate duplicate entries into a single position
- Calculate total portfolio value and per-position value
- Format values consistently for reports and UI
- Persist holdings, transactions, snapshots, and export history in SQLite
- Support live price loading with cache and hardcoded fallback

### Desktop GUI
- KPI cards for total value, number of positions, and top holding
- Add mode and Set mode for flexible quantity updates
- Sortable holdings table with live filtering
- Refresh button for loading current prices
- Allocation chart and top movers panel
- Recent export history panel
- Keyboard shortcuts for save, remove, and export actions

### Browser demo
- Static demo in `docs/` built with plain `HTML`, `CSS`, and `JavaScript`
- Responsive layout suitable for GitHub Pages
- Local-storage portfolio editing with live metrics and allocation display
- Text summary export directly from the browser

### Reporting
- TXT export to `portfolio_summary.txt`
- CSV export to `portfolio_summary.csv`
- PDF export to `portfolio_summary.pdf`

## Tech Stack
- Python 3
- Tkinter
- SQLite (`sqlite3`)
- Alpha Vantage API integration
- HTML5
- CSS3
- JavaScript
- `unittest`
- GitHub Actions
- Ruff

## Project Structure
- `stock_tracker.py` - core domain logic and CLI entrypoint
- `stock_tracker_gui.py` - desktop GUI entrypoint
- `price_service.py` - API, cache, and fallback price loading
- `config.py` - runtime configuration and defaults
- `test_stock_tracker.py` - automated tests
- `docs/index.html` - browser showcase entrypoint
- `docs/styles.css` - browser demo styling
- `docs/app.js` - browser demo interactions
- `.github/workflows/ci.yml` - CI workflow
- `.gitattributes` - GitHub Linguist overrides

Generated runtime files:
- `portfolio.db`
- `price_cache.json`
- `portfolio_summary.txt`
- `portfolio_summary.csv`
- `portfolio_summary.pdf`

## Supported Stocks
- `Apple`: 180
- `Tesla`: 250
- `Alphabet`: 2800
- `Microsoft`: 320
- `Amazon`: 3500

## Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/zahram456/CodeAlpha-StockPortfolioTracker.git
cd CodeAlpha-StockPortfolioTracker
```

### 2. Run the CLI
```bash
python stock_tracker.py
```

### 3. Run the GUI
```bash
python stock_tracker_gui.py
```

### 4. Optional API key
```powershell
$env:STOCK_TRACKER_API_KEY="your_api_key_here"
```

### 5. Open the browser demo
Open `docs/index.html` in a browser, or publish the `docs/` folder with GitHub Pages.

## Testing
Run the test suite:
```bash
python -m unittest -v
```

## Notes
- Input is normalized to title case stock names.
- Invalid stock names are rejected before persistence.
- SQLite tables cover `holdings`, `transactions`, `snapshots`, `snapshot_items`, and `export_history`.
- Price loading follows `live API -> cache -> hardcoded defaults`.
- `README.md` is excluded from GitHub Linguist language stats so documentation does not take a primary language slot.

## License
This project is intended for learning and practice.
