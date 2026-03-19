import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from typing import Optional
import threading

from stock_tracker import (
    STOCK_PRICES,
    PortfolioDB,
    PortfolioItem,
    calculate_allocation_percentages,
    calculate_portfolio_metrics,
    calculate_top_movers,
    calculate_total_value,
    format_currency,
    generate_summary_lines,
    save_summary,
    save_summary_csv,
    save_summary_pdf,
    PRICE_SOURCE,
    PRICE_FETCH_TIME,
)
import price_service

DB_FILE = "portfolio.db"
PIE_COLORS = [
    "#2E86DE",
    "#E67E22",
    "#16A085",
    "#8E44AD",
    "#E74C3C",
    "#34495E",
]


class PortfolioTrackerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Stock Portfolio Tracker")
        self.root.geometry("1120x700")
        self.root.minsize(980, 620)
        self.root.configure(bg="#f4f8ff")

        self.db = PortfolioDB(DB_FILE)
        self.db.initialize()
        self.quantities = self.db.load_holdings()
        self.db.record_snapshot(STOCK_PRICES)

        self.sort_column = "symbol"
        self.sort_reverse = False
        self.mover_labels: list[ttk.Label] = []
        self.export_labels: list[ttk.Label] = []

        # Price tracking
        self.current_prices = STOCK_PRICES.copy()
        self.price_source = "hardcoded"
        self.last_price_update: Optional[str] = None
        self.refresh_in_progress = False

        self._setup_style()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._refresh_table()

    def _setup_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("App.TFrame", background="#f4f8ff")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure(
            "Title.TLabel",
            font=("Segoe UI Semibold", 20),
            background="#f4f8ff",
            foreground="#152238",
        )
        style.configure(
            "Sub.TLabel",
            font=("Segoe UI", 10),
            background="#f4f8ff",
            foreground="#425466",
        )
        style.configure(
            "CardTitle.TLabel",
            font=("Segoe UI Semibold", 11),
            background="#ffffff",
            foreground="#25364d",
        )
        style.configure(
            "KpiLabel.TLabel",
            font=("Segoe UI", 9),
            background="#ffffff",
            foreground="#56657a",
        )
        style.configure(
            "Value.TLabel",
            font=("Segoe UI Semibold", 14),
            background="#ffffff",
            foreground="#0f9d58",
        )
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.map(
            "Accent.TButton",
            background=[("!disabled", "#1f6feb"), ("active", "#1859bb")],
            foreground=[("!disabled", "#ffffff")],
        )
        style.configure("Danger.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.map(
            "Danger.TButton",
            background=[("!disabled", "#cc3a3a"), ("active", "#a82f2f")],
            foreground=[("!disabled", "#ffffff")],
        )
        style.configure(
            "Treeview",
            font=("Segoe UI", 10),
            rowheight=30,
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1f2d3d",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI Semibold", 10),
            background="#e7eefb",
            foreground="#203047",
        )

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Export Summary (.txt)", command=self.export_summary)
        file_menu.add_command(label="Export CSV (.csv)", command=self.export_csv)
        file_menu.add_command(label="Export PDF (.pdf)", command=self.export_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Remove Selected", command=self.remove_selected)
        edit_menu.add_command(label="Clear Portfolio", command=self.clear_portfolio)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menu_bar)

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="App.TFrame", padding=18)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Stock Portfolio Tracker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="SQLite-backed portfolio manager with snapshots, exports, and analytics.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            header,
            text="Shortcuts: Enter=Save Holding | Delete=Remove | Ctrl+S=TXT | Ctrl+Shift+S=CSV | Ctrl+P=PDF",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        top_row = ttk.Frame(container, style="App.TFrame")
        top_row.pack(fill="x", pady=(0, 12))

        input_card = ttk.Frame(top_row, style="Card.TFrame", padding=14)
        input_card.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(input_card, text="Add or Update Holding", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )
        ttk.Label(input_card, text="Stock Name").grid(row=1, column=0, sticky="w")
        ttk.Label(input_card, text="Quantity").grid(row=1, column=2, sticky="w", padx=(12, 0))

        self.symbol_var = tk.StringVar(value="Apple")
        self.quantity_var = tk.StringVar()
        self.entry_mode_var = tk.StringVar(value="add")
        self.symbol_combo = ttk.Combobox(
            input_card,
            textvariable=self.symbol_var,
            values=sorted(STOCK_PRICES.keys()),
            width=16,
        )
        self.symbol_combo.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.quantity_entry = ttk.Entry(input_card, textvariable=self.quantity_var, width=14)
        self.quantity_entry.grid(row=2, column=2, sticky="w", padx=(12, 0), pady=(4, 0))

        mode_frame = ttk.Frame(input_card, style="Card.TFrame")
        mode_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Radiobutton(
            mode_frame,
            text="Add Quantity",
            variable=self.entry_mode_var,
            value="add",
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frame,
            text="Set Exact Quantity",
            variable=self.entry_mode_var,
            value="set",
        ).pack(side="left", padx=(12, 0))
        ttk.Button(
            input_card,
            text="Add / Update",
            style="Accent.TButton",
            command=self.add_or_update_holding,
        ).grid(row=2, column=3, sticky="w", padx=(12, 0), pady=(4, 0))
        ttk.Label(
            input_card,
            text="Tip: select a table row to load it in Set mode quickly.",
            style="Sub.TLabel",
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))

        summary_card = ttk.Frame(top_row, style="Card.TFrame", padding=14)
        summary_card.pack(side="left", fill="both", padx=(0, 10))
        ttk.Label(summary_card, text="Portfolio Snapshot", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(summary_card, text="Total Value", style="KpiLabel.TLabel").pack(
            anchor="w", pady=(8, 0)
        )
        self.total_value_label = ttk.Label(summary_card, text="$0.00", style="Value.TLabel")
        self.total_value_label.pack(anchor="w")
        ttk.Label(summary_card, text="Positions", style="KpiLabel.TLabel").pack(
            anchor="w", pady=(8, 0)
        )
        self.positions_value_label = ttk.Label(summary_card, text="0", style="Value.TLabel")
        self.positions_value_label.pack(anchor="w")
        ttk.Label(summary_card, text="Top Holding", style="KpiLabel.TLabel").pack(
            anchor="w", pady=(8, 0)
        )
        self.top_holding_label = ttk.Label(summary_card, text="-", style="Value.TLabel")
        self.top_holding_label.pack(anchor="w")

        ttk.Button(
            summary_card,
            text="Refresh Prices",
            command=self.refresh_prices,
        ).pack(anchor="w", pady=(12, 0))

        analytics_card = ttk.Frame(top_row, style="Card.TFrame", padding=14)
        analytics_card.pack(side="left", fill="both", expand=True)
        ttk.Label(analytics_card, text="Allocation & Movers", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        analytics_body = ttk.Frame(analytics_card, style="Card.TFrame")
        analytics_body.pack(fill="both", expand=True, pady=(8, 0))
        self.pie_canvas = tk.Canvas(
            analytics_body,
            width=220,
            height=170,
            bg="#ffffff",
            highlightthickness=0,
        )
        self.pie_canvas.pack(side="left", padx=(0, 18))
        movers_frame = ttk.Frame(analytics_body, style="Card.TFrame")
        movers_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(movers_frame, text="Top Movers", style="KpiLabel.TLabel").pack(anchor="w")
        for _ in range(3):
            label = ttk.Label(movers_frame, text="-", style="Sub.TLabel")
            label.pack(anchor="w", pady=(8, 0))
            self.mover_labels.append(label)
        ttk.Label(
            movers_frame,
            text="Recent Exports",
            style="KpiLabel.TLabel",
        ).pack(anchor="w", pady=(16, 0))
        for _ in range(3):
            label = ttk.Label(movers_frame, text="-", style="Sub.TLabel")
            label.pack(anchor="w", pady=(6, 0))
            self.export_labels.append(label)

        table_card = ttk.Frame(container, style="Card.TFrame", padding=12)
        table_card.pack(fill="both", expand=True, pady=(0, 12))
        filter_row = ttk.Frame(table_card, style="Card.TFrame")
        filter_row.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_row, text="Filter Stock").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(filter_row, textvariable=self.filter_var, width=20)
        self.filter_entry.pack(side="left", padx=(8, 0))
        ttk.Button(filter_row, text="Clear", command=self.clear_filter).pack(
            side="left", padx=(8, 0)
        )

        columns = ("symbol", "quantity", "price", "value", "weight")
        self.table = ttk.Treeview(table_card, columns=columns, show="headings")
        self.table.heading("symbol", text="Stock", command=lambda: self.sort_by("symbol"))
        self.table.heading("quantity", text="Quantity", command=lambda: self.sort_by("quantity"))
        self.table.heading("price", text="Price", command=lambda: self.sort_by("price"))
        self.table.heading("value", text="Position Value", command=lambda: self.sort_by("value"))
        self.table.heading(
            "weight",
            text="Portfolio Weight",
            command=lambda: self.sort_by("weight"),
        )
        self.table.column("symbol", anchor="center", width=90)
        self.table.column("quantity", anchor="center", width=90)
        self.table.column("price", anchor="e", width=140)
        self.table.column("value", anchor="e", width=160)
        self.table.column("weight", anchor="e", width=130)
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.tag_configure("odd", background="#ffffff")
        self.table.tag_configure("even", background="#f7faff")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        actions = ttk.Frame(container, style="App.TFrame")
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="Remove Selected",
            style="Danger.TButton",
            command=self.remove_selected,
        ).pack(side="left")
        ttk.Button(actions, text="Clear Portfolio", command=self.clear_portfolio).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Export PDF", command=self.export_pdf).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(actions, text="Export CSV", command=self.export_csv).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(
            actions,
            text="Export Summary",
            style="Accent.TButton",
            command=self.export_summary,
        ).pack(side="right")

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status_var, style="Sub.TLabel").pack(
            anchor="w", pady=(8, 0)
        )

        self.quantity_entry.bind("<Return>", self._on_enter_pressed)
        self.symbol_combo.bind("<Return>", self._on_enter_pressed)
        self.filter_entry.bind("<Return>", lambda _event: self._refresh_table())
        self.table.bind("<<TreeviewSelect>>", self._load_selected_into_form)
        self.filter_var.trace_add("write", self._on_filter_change)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Delete>", lambda _event: self.remove_selected())
        self.root.bind("<Control-s>", lambda _event: self.export_summary())
        self.root.bind("<Control-Shift-s>", lambda _event: self.export_csv())
        self.root.bind("<Control-Shift-S>", lambda _event: self.export_csv())
        self.root.bind("<Control-p>", lambda _event: self.export_pdf())

    def _validated_inputs(self) -> tuple[str, int] | None:
        symbol = self.symbol_var.get().strip().title()
        qty_raw = self.quantity_var.get().strip()
        if symbol not in STOCK_PRICES:
            messagebox.showerror(
                "Invalid Stock",
                f"Stock '{symbol}' is not in the supported list: {', '.join(STOCK_PRICES)}",
            )
            return None
        if not qty_raw.isdigit() or int(qty_raw) <= 0:
            messagebox.showerror("Invalid Quantity", "Quantity must be a positive integer.")
            return None
        return symbol, int(qty_raw)

    def _portfolio_items(self) -> list[PortfolioItem]:
        return [
            PortfolioItem(symbol=symbol, quantity=qty, price=self.current_prices[symbol])
            for symbol, qty in sorted(self.quantities.items())
            if symbol in self.current_prices and qty > 0
        ]

    def _visible_items(self, items: list[PortfolioItem]) -> list[PortfolioItem]:
        filter_text = self.filter_var.get().strip().upper()
        visible = items if not filter_text else [i for i in items if filter_text in i.symbol]

        if self.sort_column == "symbol":
            key_fn = lambda item: item.symbol
        elif self.sort_column == "quantity":
            key_fn = lambda item: item.quantity
        elif self.sort_column == "price":
            key_fn = lambda item: item.price
        else:
            key_fn = lambda item: item.value
        return sorted(visible, key=key_fn, reverse=self.sort_reverse)

    def _draw_allocation_chart(self, items: list[PortfolioItem]) -> None:
        self.pie_canvas.delete("all")
        allocations = calculate_allocation_percentages(items)
        if not allocations:
            self.pie_canvas.create_text(110, 85, text="No data", fill="#66788a")
            return

        start_angle = 0.0
        legend_x = 130
        legend_y = 10
        for idx, (symbol, percent) in enumerate(allocations):
            extent = (percent / 100.0) * 360.0
            color = PIE_COLORS[idx % len(PIE_COLORS)]
            self.pie_canvas.create_arc(
                10,
                10,
                110,
                110,
                start=start_angle,
                extent=extent,
                fill=color,
                outline="#ffffff",
            )
            self.pie_canvas.create_rectangle(
                legend_x,
                legend_y + idx * 20,
                legend_x + 10,
                legend_y + idx * 20 + 10,
                fill=color,
                outline=color,
            )
            self.pie_canvas.create_text(
                legend_x + 14,
                legend_y + idx * 20 + 5,
                text=f"{symbol} {percent:.1f}%",
                anchor="w",
                fill="#33485c",
                font=("Segoe UI", 9),
            )
            start_angle += extent

    def _refresh_top_movers(self, items: list[PortfolioItem]) -> None:
        if self.db.get_snapshot_count() < 2:
            for label in self.mover_labels:
                label.configure(text="No baseline snapshot yet")
            return

        previous_values = self.db.get_previous_snapshot_values()
        movers = calculate_top_movers(items, previous_values, top_n=3)
        for idx, label in enumerate(self.mover_labels):
            if idx >= len(movers):
                label.configure(text="-")
                continue
            symbol, delta = movers[idx]
            sign = "+" if delta >= 0 else "-"
            label.configure(text=f"{symbol}: {sign}{format_currency(abs(delta))}")

    def _refresh_export_history(self) -> None:
        history = self.db.get_export_history(limit=3)
        for idx, label in enumerate(self.export_labels):
            if idx >= len(history):
                label.configure(text="-")
                continue
            row = history[idx]
            time_part = row["created_at"].split("T")[-1].replace("Z", "")
            label.configure(
                text=f'{row["export_format"].upper()} -> {row["filename"]} ({time_part})'
            )

    def _refresh_table(self) -> None:
        for row in self.table.get_children():
            self.table.delete(row)

        all_items = self._portfolio_items()
        visible_items = self._visible_items(all_items)
        total = calculate_total_value(all_items)
        for row_idx, item in enumerate(visible_items):
            weight = 0 if total == 0 else (item.value / total) * 100
            self.table.insert(
                "",
                "end",
                iid=item.symbol,
                values=(
                    item.symbol,
                    item.quantity,
                    format_currency(item.price),
                    format_currency(item.value),
                    f"{weight:.1f}%",
                ),
                tags=("even" if row_idx % 2 == 0 else "odd",),
            )

        metrics = calculate_portfolio_metrics(all_items)
        self.total_value_label.configure(text=format_currency(metrics["total_value"]))
        self.positions_value_label.configure(text=str(metrics["positions"]))
        self.top_holding_label.configure(
            text=f'{metrics["top_symbol"]} ({format_currency(metrics["top_value"])})'
            if metrics["positions"] > 0
            else "-"
        )
        self._draw_allocation_chart(all_items)
        self._refresh_top_movers(all_items)
        self._refresh_export_history()

        timestamp = datetime.now().strftime("%H:%M:%S")
        source_str = (
            f"Prices: {self.price_source.title()} "
            f"({self.last_price_update or 'Not loaded'})"
            if self.last_price_update
            else f"Prices: {self.price_source.title()}"
        )
        self.status_var.set(
            f"Showing {len(visible_items)} of {metrics['positions']} holdings | {source_str} | {timestamp}"
        )

    def _on_enter_pressed(self, _event: tk.Event) -> None:
        self.add_or_update_holding()

    def _on_filter_change(self, *_: object) -> None:
        self._refresh_table()

    def clear_filter(self) -> None:
        self.filter_var.set("")

    def sort_by(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self._refresh_table()

    def show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Stock Portfolio Tracker\nSQLite + Snapshots + Exports\nBuilt with Python + Tkinter",
        )

    def _load_selected_into_form(self, _event: tk.Event) -> None:
        selected = self.table.selection()
        if not selected:
            return
        symbol = selected[0]
        quantity = self.quantities.get(symbol)
        if quantity is None:
            return
        self.symbol_var.set(symbol)
        self.quantity_var.set(str(quantity))
        self.entry_mode_var.set("set")

    def _reload_from_db(self) -> None:
        self.quantities = self.db.load_holdings()
        self.db.record_snapshot(STOCK_PRICES)
        self._refresh_table()

    def add_or_update_holding(self) -> None:
        parsed = self._validated_inputs()
        if parsed is None:
            return
        symbol, quantity = parsed
        price = STOCK_PRICES[symbol]
        if self.entry_mode_var.get() == "set":
            self.db.set_holding(symbol, quantity, price)
        else:
            self.db.add_holding(symbol, quantity, price)
        self._reload_from_db()
        self.quantity_var.set("")
        self.status_var.set(f"Updated {symbol}.")

    def remove_selected(self) -> None:
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a row to remove.")
            return
        for row_id in selected:
            self.db.remove_holding(row_id)
        self._reload_from_db()
        self.status_var.set("Removed selected holding(s).")

    def clear_portfolio(self) -> None:
        if not self.quantities:
            return
        if messagebox.askyesno("Clear Portfolio", "Remove all holdings from the portfolio?"):
            self.db.clear_holdings()
            self._reload_from_db()
            self.status_var.set("Portfolio cleared.")

    def _export(self, export_format: str, filename: str) -> None:
        items = self._portfolio_items()
        total = calculate_total_value(items)
        lines = generate_summary_lines(items, total)
        if export_format == "txt":
            save_summary(filename, lines)
        elif export_format == "csv":
            save_summary_csv(filename, items, total)
        else:
            save_summary_pdf(filename, lines)
        self.db.record_export(export_format, filename)

    def export_summary(self) -> None:
        self._export("txt", "portfolio_summary.txt")
        messagebox.showinfo("Saved", "Portfolio saved to 'portfolio_summary.txt'.")
        self.status_var.set("Exported summary text file.")

    def export_csv(self) -> None:
        self._export("csv", "portfolio_summary.csv")
        messagebox.showinfo("Saved", "Portfolio saved to 'portfolio_summary.csv'.")
        self.status_var.set("Exported CSV file.")

    def export_pdf(self) -> None:
        self._export("pdf", "portfolio_summary.pdf")
        messagebox.showinfo("Saved", "Portfolio saved to 'portfolio_summary.pdf'.")
        self.status_var.set("Exported PDF file.")

    def refresh_prices(self) -> None:
        """Refresh prices from live API in background thread."""
        if self.refresh_in_progress:
            messagebox.showinfo("In Progress", "Price refresh already in progress.")
            return

        self.refresh_in_progress = True
        self.status_var.set("Refreshing prices...")
        thread = threading.Thread(target=self._refresh_prices_async, daemon=True)
        thread.start()

    def _refresh_prices_async(self) -> None:
        """Fetch prices in background (runs in thread)."""
        try:
            prices, source = price_service.get_prices(use_cache_only=False)
            # Update on main thread
            self.root.after(0, lambda: self._on_prices_updated(prices, source))
        except Exception as e:
            self.root.after(0, lambda: self._on_price_refresh_error(str(e)))

    def _on_prices_updated(self, prices: dict, source: str) -> None:
        """Callback when prices are successfully fetched."""
        self.current_prices = prices
        self.price_source = source
        self.last_price_update = datetime.now().strftime("%I:%M %p")
        self.refresh_in_progress = False

        # Record price changes
        old_prices = STOCK_PRICES
        for symbol, new_price in prices.items():
            old_price = old_prices.get(symbol, new_price)
            if old_price != new_price:
                self.db.record_price_update(symbol, old_price, new_price, source)

        self._reload_from_db()
        source_display = "Live API" if source == "live" else (
            "Cached" if source == "cached" else "Hardcoded (Fallback)"
        )
        messagebox.showinfo(
            "Prices Updated",
            f"Prices updated from {source_display}.\nRefresh again in {max(60 - int(self.last_price_update.split(':')[0]) % 60, 1)} minutes for live data.",
        )

    def _on_price_refresh_error(self, error: str) -> None:
        """Callback when price refresh fails."""
        self.refresh_in_progress = False
        messagebox.showerror("Price Refresh Failed", f"Could not refresh prices:\n{error}")
        if self.current_prices == STOCK_PRICES:
            self.status_var.set("Using hardcoded prices (refresh failed).")
        else:
            self.status_var.set("Using cached prices (refresh failed).")


def main() -> None:
    root = tk.Tk()
    PortfolioTrackerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
