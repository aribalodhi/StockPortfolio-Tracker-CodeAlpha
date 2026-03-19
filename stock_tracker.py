from dataclasses import dataclass
from datetime import UTC, datetime
from contextlib import contextmanager
import csv
import sqlite3
from typing import Callable, Dict, List, TypedDict, Optional

import config
import price_service

# Hardcoded stock prices (can be moved to API later)
STOCK_PRICES = {
    "Apple": 180.0,
    "Tesla": 250.0,
    "Alphabet": 2800.0,
    "Microsoft": 320.0,
    "Amazon": 3500.0,
}

# Track the source of current prices (live, cached, fallback)
PRICE_SOURCE = "hardcoded"
PRICE_FETCH_TIME: Optional[str] = None


@dataclass
class PortfolioItem:
    symbol: str
    quantity: int
    price: float

    @property
    def value(self) -> float:
        return self.quantity * self.price


class PortfolioMetrics(TypedDict):
    total_value: float
    positions: int
    top_symbol: str
    top_value: float


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_live_prices() -> None:
    """
    Load prices from API with fallback chain: live API -> cache -> hardcoded.
    Updates global STOCK_PRICES and PRICE_SOURCE variables.
    """
    global STOCK_PRICES, PRICE_SOURCE, PRICE_FETCH_TIME
    try:
        prices, source = price_service.get_prices(use_cache_only=False)
        STOCK_PRICES = prices
        PRICE_SOURCE = source
        PRICE_FETCH_TIME = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    except Exception:
        # Silent fail - keeps existing prices
        pass


def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


def get_positive_int(
    prompt: str,
    input_fn: Callable[[str], str] = input,
    allow_zero: bool = False,
    print_fn: Callable[[str], None] = print,
) -> int:
    while True:
        raw = input_fn(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print_fn("Invalid input. Please enter a whole number.")
            continue

        if value < 0 or (value == 0 and not allow_zero):
            if allow_zero:
                print_fn("Please enter 0 or a positive whole number.")
            else:
                print_fn("Please enter a positive whole number.")
            continue
        return value


def build_portfolio(
    stock_prices: Dict[str, float],
    num_entries: int,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> List[PortfolioItem]:
    quantities: Dict[str, int] = {}

    for _ in range(num_entries):
        symbol = input_fn("Enter stock name (e.g., Apple): ").strip().title()
        if symbol not in stock_prices:
            print_fn("Stock not found in price list. Entry skipped.\n")
            continue

        quantity = get_positive_int(
            "Enter quantity: ",
            input_fn=input_fn,
            print_fn=print_fn,
        )
        quantities[symbol] = quantities.get(symbol, 0) + quantity

        entry_value = quantity * stock_prices[symbol]
        print_fn(f"Added {quantity} shares of {symbol}")
        print_fn(f"Investment value: {format_currency(entry_value)}\n")

    return build_items_from_quantities(quantities, stock_prices)


def build_items_from_quantities(
    quantities: Dict[str, int],
    stock_prices: Dict[str, float],
) -> List[PortfolioItem]:
    return [
        PortfolioItem(symbol=symbol, quantity=qty, price=stock_prices[symbol])
        for symbol, qty in sorted(quantities.items())
        if symbol in stock_prices and qty > 0
    ]


def calculate_total_value(items: List[PortfolioItem]) -> float:
    return sum(item.value for item in items)


def calculate_portfolio_metrics(items: List[PortfolioItem]) -> PortfolioMetrics:
    total_value = calculate_total_value(items)
    if not items:
        return {
            "total_value": 0.0,
            "positions": 0,
            "top_symbol": "-",
            "top_value": 0.0,
        }

    top_item = max(items, key=lambda item: item.value)
    return {
        "total_value": total_value,
        "positions": len(items),
        "top_symbol": top_item.symbol,
        "top_value": top_item.value,
    }


def calculate_allocation_percentages(items: List[PortfolioItem]) -> List[tuple[str, float]]:
    total = calculate_total_value(items)
    if total <= 0:
        return []
    return [(item.symbol, (item.value / total) * 100.0) for item in items]


def calculate_top_movers(
    items: List[PortfolioItem],
    previous_values: Dict[str, float],
    top_n: int = 3,
) -> List[tuple[str, float]]:
    deltas: List[tuple[str, float]] = []
    for item in items:
        previous_value = previous_values.get(item.symbol, 0.0)
        deltas.append((item.symbol, item.value - previous_value))

    deltas.sort(key=lambda row: abs(row[1]), reverse=True)
    return deltas[:top_n]


def generate_summary_lines(items: List[PortfolioItem], total_value: float) -> List[str]:
    lines = ["Stock Portfolio Summary", "------------------------"]
    for item in items:
        lines.append(
            f"{item.symbol} - {item.quantity} shares - {format_currency(item.value)}"
        )
    lines.append("")
    lines.append(f"Total Investment Value: {format_currency(total_value)}")
    return lines


def save_summary(filename: str, lines: List[str]) -> None:
    with open(filename, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def save_summary_csv(filename: str, items: List[PortfolioItem], total_value: float) -> None:
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Stock Name", "Quantity", "Price", "Position Value"])
        for item in items:
            writer.writerow(
                [
                    item.symbol,
                    item.quantity,
                    f"{item.price:.2f}",
                    f"{item.value:.2f}",
                ]
            )
        writer.writerow([])
        writer.writerow(["Total Investment Value", "", "", f"{total_value:.2f}"])


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def save_summary_pdf(filename: str, lines: List[str]) -> None:
    content_lines = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
    for line in lines:
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream_data = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            b"5 0 obj\n<< /Length "
            + str(len(stream_data)).encode("ascii")
            + b" >>\nstream\n"
            + stream_data
            + b"\nendstream\nendobj\n"
        ),
    ]

    pdf_data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf_data))
        pdf_data += obj

    xref_offset = len(pdf_data)
    pdf_data += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf_data += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf_data += f"{offset:010} 00000 n \n".encode("ascii")
    pdf_data += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")

    with open(filename, "wb") as file:
        file.write(pdf_data)


class PortfolioDB:
    def __init__(self, db_path: str = "portfolio.db") -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _validate_stock_name(self, symbol: str) -> str:
        normalized = symbol.title()
        if normalized not in STOCK_PRICES:
            raise ValueError(f"Unsupported stock name: {symbol}")
        return normalized

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS holdings (
                    symbol TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('ADD','SET','REMOVE','CLEAR')),
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    price REAL NOT NULL CHECK (price >= 0),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    total_value REAL NOT NULL CHECK (total_value >= 0)
                );

                CREATE TABLE IF NOT EXISTS snapshot_items (
                    snapshot_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    price REAL NOT NULL CHECK (price >= 0),
                    value REAL NOT NULL CHECK (value >= 0),
                    PRIMARY KEY (snapshot_id, symbol),
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS export_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    export_format TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS price_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    old_price REAL NOT NULL CHECK (old_price >= 0),
                    new_price REAL NOT NULL CHECK (new_price >= 0),
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def load_holdings(self) -> Dict[str, int]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT symbol, quantity
                FROM holdings
                WHERE quantity > 0
                ORDER BY symbol
                """
            ).fetchall()
        return {row["symbol"]: int(row["quantity"]) for row in rows}

    def add_holding(self, symbol: str, quantity: int, price: float) -> None:
        symbol = self._validate_stock_name(symbol)
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        with self._connection() as conn:
            row = conn.execute(
                "SELECT quantity FROM holdings WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            current_qty = int(row["quantity"]) if row else 0
            new_qty = current_qty + quantity
            now = utc_timestamp()
            conn.execute(
                """
                INSERT INTO holdings(symbol, quantity, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    quantity=excluded.quantity,
                    updated_at=excluded.updated_at
                """,
                (symbol, new_qty, now),
            )
            conn.execute(
                """
                INSERT INTO transactions(symbol, action, quantity, price, created_at)
                VALUES(?, 'ADD', ?, ?, ?)
                """,
                (symbol, quantity, price, now),
            )

    def set_holding(self, symbol: str, quantity: int, price: float) -> None:
        symbol = self._validate_stock_name(symbol)
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        now = utc_timestamp()

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO holdings(symbol, quantity, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    quantity=excluded.quantity,
                    updated_at=excluded.updated_at
                """,
                (symbol, quantity, now),
            )
            conn.execute(
                """
                INSERT INTO transactions(symbol, action, quantity, price, created_at)
                VALUES(?, 'SET', ?, ?, ?)
                """,
                (symbol, quantity, price, now),
            )

    def remove_holding(self, symbol: str) -> None:
        symbol = self._validate_stock_name(symbol)
        now = utc_timestamp()

        with self._connection() as conn:
            row = conn.execute(
                "SELECT quantity FROM holdings WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            if row is None:
                return
            removed_qty = int(row["quantity"])
            conn.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))
            conn.execute(
                """
                INSERT INTO transactions(symbol, action, quantity, price, created_at)
                VALUES(?, 'REMOVE', ?, 0, ?)
                """,
                (symbol, removed_qty, now),
            )

    def clear_holdings(self) -> None:
        now = utc_timestamp()
        with self._connection() as conn:
            conn.execute("DELETE FROM holdings")
            conn.execute(
                """
                INSERT INTO transactions(symbol, action, quantity, price, created_at)
                VALUES('ALL', 'CLEAR', 0, 0, ?)
                """,
                (now,),
            )

    def record_snapshot(self, stock_prices: Dict[str, float]) -> int:
        holdings = self.load_holdings()
        items = build_items_from_quantities(holdings, stock_prices)
        total_value = calculate_total_value(items)
        now = utc_timestamp()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO snapshots(created_at, total_value)
                VALUES(?, ?)
                """,
                (now, total_value),
            )
            snapshot_id = int(cursor.lastrowid)
            conn.executemany(
                """
                INSERT INTO snapshot_items(snapshot_id, symbol, quantity, price, value)
                VALUES(?, ?, ?, ?, ?)
                """,
                [
                    (snapshot_id, item.symbol, item.quantity, item.price, item.value)
                    for item in items
                ],
            )
        return snapshot_id

    def get_previous_snapshot_values(self) -> Dict[str, float]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id
                FROM snapshots
                ORDER BY id DESC
                LIMIT 2
                """
            ).fetchall()
            if len(rows) < 2:
                return {}
            previous_snapshot_id = int(rows[1]["id"])
            value_rows = conn.execute(
                """
                SELECT symbol, value
                FROM snapshot_items
                WHERE snapshot_id = ?
                """,
                (previous_snapshot_id,),
            ).fetchall()
        return {row["symbol"]: float(row["value"]) for row in value_rows}

    def get_snapshot_count(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM snapshots").fetchone()
        return int(row["count"]) if row is not None else 0

    def record_export(self, export_format: str, filename: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO export_history(export_format, filename, created_at)
                VALUES(?, ?, ?)
                """,
                (export_format, filename, utc_timestamp()),
            )

    def get_export_history(self, limit: int = 20) -> List[dict]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT export_format, filename, created_at
                FROM export_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "export_format": row["export_format"],
                "filename": row["filename"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def record_price_update(self, symbol: str, old_price: float, new_price: float, source: str) -> None:
        """Record price change in price_updates table for audit trail."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO price_updates(symbol, old_price, new_price, source, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (symbol, old_price, new_price, source, utc_timestamp()),
            )


def main() -> None:
    print("Welcome to Stock Portfolio Tracker\n")
    num_entries = get_positive_int(
        "How many different stocks do you want to add? ",
        allow_zero=True,
    )
    portfolio_items = build_portfolio(STOCK_PRICES, num_entries)
    total_value = calculate_total_value(portfolio_items)
    summary_lines = generate_summary_lines(portfolio_items, total_value)

    print("----- Portfolio Summary -----")
    for line in summary_lines[2:]:
        print(line)

    output_file = "portfolio_summary.txt"
    save_summary(output_file, summary_lines)
    print(f"\nPortfolio saved to '{output_file}'")


if __name__ == "__main__":
    main()
