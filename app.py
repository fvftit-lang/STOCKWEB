import json
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import yfinance as yf

CONFIG_FILE = "config.json"


class StockTrackerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("股票資產即時追蹤器 v2.0")
        self.root.geometry("700x520")

        # 儲存股票資料: { symbol: {"shares": float, "price": float, "total": float} }
        self.portfolio = {}

        # 載入設定檔 ( config.json )
        self.load_config()

        self.setup_ui()

        # 初始化後先刷新一次表格（載入存檔的股票）
        self.refresh_treeview()

        # 啟動背景自動更新 Thread
        self.is_running = True
        self.update_interval = 30  # 預設 30 秒更新一次
        self.update_thread = threading.Thread(
            target=self.auto_update_loop, daemon=True
        )
        self.update_thread.start()

        # 首次啟動時在背景自動更新一次股價
        if self.portfolio:
            threading.Thread(
                target=self.update_all_stocks_bg, daemon=True
            ).start()

    def setup_ui(self):
        # --- 1. 上方輸入區塊 ---
        input_frame = ttk.LabelFrame(self.root, text="新增 / 更新股票", padding=10)
        input_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(input_frame, text="股票代號:").grid(
            row=0, column=0, padx=5, pady=5
        )
        self.symbol_entry = ttk.Entry(input_frame, width=12)
        self.symbol_entry.grid(row=0, column=1, padx=5, pady=5)
        self.symbol_entry.bind("<Return>", lambda event: self.add_stock())

        ttk.Label(input_frame, text="持有股數 (選填):").grid(
            row=0, column=2, padx=5, pady=5
        )
        self.shares_entry = ttk.Entry(input_frame, width=10)
        self.shares_entry.grid(row=0, column=3, padx=5, pady=5)
        self.shares_entry.bind("<Return>", lambda event: self.add_stock())

        add_btn = ttk.Button(
            input_frame, text="新增/更新", command=self.add_stock
        )
        add_btn.grid(row=0, column=4, padx=10, pady=5)

        # --- 2. 中間表格區塊 ---
        table_frame = ttk.Frame(self.root, padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("symbol", "shares", "price", "total_val")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=12
        )

        self.tree.heading("symbol", text="股票代號")
        self.tree.heading("shares", text="持有股數")
        self.tree.heading("price", text="最新股價")
        self.tree.heading("total_val", text="總價值")

        self.tree.column("symbol", anchor="center", width=130)
        self.tree.column("shares", anchor="e", width=120)
        self.tree.column("price", anchor="e", width=130)
        self.tree.column("total_val", anchor="e", width=160)

        # 雙擊列表項目也可進行刪除
        self.tree.bind("<Double-1>", lambda event: self.delete_selected_stock())

        scrollbar = ttk.Scrollbar(
            table_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- 3. 控制列 (刪除按鈕 & 自動更新設定) ---
        ctrl_frame = ttk.Frame(self.root, padding=(10, 0))
        ctrl_frame.pack(fill="x", padx=10, pady=2)

        delete_btn = ttk.Button(
            ctrl_frame, text="刪除選取項目", command=self.delete_selected_stock
        )
        delete_btn.pack(side="left")

        # 自動更新計時器下拉選單
        ttk.Label(ctrl_frame, text="  自動更新頻率:").pack(
            side="left", padx=(15, 2)
        )
        self.timer_combobox = ttk.Combobox(
            ctrl_frame,
            values=["10 秒", "30 秒", "1 分鐘", "關閉"],
            width=8,
            state="readonly",
        )
        self.timer_combobox.set("30 秒")
        self.timer_combobox.pack(side="left")
        self.timer_combobox.bind(
            "<<ComboboxSelected>>", self.on_timer_change
        )

        manual_ref_btn = ttk.Button(
            ctrl_frame,
            text="手動刷新",
            command=lambda: threading.Thread(
                target=self.update_all_stocks_bg, daemon=True
            ).start(),
        )
        manual_ref_btn.pack(side="left", padx=5)

        # --- 4. 下方狀態與總資產列 ---
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill="x", padx=10, pady=5)

        self.status_label = ttk.Label(
            bottom_frame, text="就緒", foreground="gray"
        )
        self.status_label.pack(side="left")

        self.grand_total_label = ttk.Label(
            bottom_frame,
            text="資產總計: $0.00",
            font=("Microsoft JhengHei", 12, "bold"),
        )
        self.grand_total_label.pack(side="right")

    # ================= 檔案存取 (Config) =================
    def load_config(self):
        """啟動時讀取 config.json"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    # 載入股票代號與股數，股價預設為 0，等背景 Task 更新
                    for symbol, info in saved_data.items():
                        shares = info.get("shares", 0.0)
                        self.portfolio[symbol] = {
                            "shares": shares,
                            "price": 0.0,
                            "total": 0.0,
                        }
            except Exception as e:
                print(f"讀取設定檔失敗: {e}")

    def save_config(self):
        """變更股票清單時寫入 config.json"""
        save_data = {}
        for symbol, info in self.portfolio.items():
            save_data[symbol] = {"shares": info["shares"]}

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")

    # ================= 新增 / 刪除邏輯 =================
    def add_stock(self):
        symbol = self.symbol_entry.get().strip().upper()
        shares_str = self.shares_entry.get().strip()

        if not symbol:
            messagebox.showwarning("輸入錯誤", "請輸入股票代號！")
            return

        # 需求 1: 若未輸入股數，預設為 0
        if not shares_str:
            shares = 0.0
        else:
            try:
                shares = float(shares_str)
                if shares < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "輸入錯誤", "股數必須為大於或等於 0 的數字！"
                )
                return

        self.status_label.config(
            text=f"正在抓取 {symbol} 最新價格...", foreground="blue"
        )

        threading.Thread(
            target=self._fetch_and_add_stock_bg,
            args=(symbol, shares),
            daemon=True,
        ).start()

    def _fetch_and_add_stock_bg(self, symbol, shares):
        """背景抓取單支股票價格"""
        price = self.get_latest_price(symbol)

        if price is None:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "抓取失敗",
                    f"無法取得 {symbol} 的數據，請確認代號是否正確。\n(台股請加 .TW，如 2330.TW)",
                ),
            )
            self.root.after(
                0,
                lambda: self.status_label.config(
                    text="抓取失敗", foreground="red"
                ),
            )
            return

        self.portfolio[symbol] = {
            "shares": shares,
            "price": price,
            "total": price * shares,
        }

        # 存檔 config.json
        self.save_config()

        # 更新 UI
        self.root.after(0, self.refresh_treeview)
        self.root.after(
            0,
            lambda: self.status_label.config(
                text=f"已成功新增/更新 {symbol}", foreground="green"
            ),
        )
        self.root.after(0, self._clear_entries)

    def delete_selected_stock(self):
        """需求 2: 刪除選取的股票"""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "請先點擊列表選取要刪除的股票！")
            return

        symbol = selected_item[0]
        if messagebox.askyesno("確認刪除", f"確定要刪除 {symbol} 嗎？"):
            if symbol in self.portfolio:
                del self.portfolio[symbol]
                self.save_config()  # 寫入設定檔
                self.refresh_treeview()
                self.status_label.config(
                    text=f"已刪除 {symbol}", foreground="orange"
                )

    def _clear_entries(self):
        self.symbol_entry.delete(0, tk.END)
        self.shares_entry.delete(0, tk.END)
        self.symbol_entry.focus()

    # ================= 股價抓取與自動定時器 =================
    def get_latest_price(self, symbol):
        """yfinance 抓取即時價格"""
        try:
            stock = yf.Ticker(symbol)
            price = stock.fast_info.get("last_price")
            if price is None or price != price:  # 檢查 NaN
                hist = stock.history(period="1d")
                if not hist.empty:
                    price = hist["Close"].iloc[-1]
            return price
        except Exception:
            return None

    def on_timer_change(self, event):
        """需求 3: 修改 Timer 間隔"""
        val = self.timer_combobox.get()
        if val == "10 秒":
            self.update_interval = 10
        elif val == "30 秒":
            self.update_interval = 30
        elif val == "1 分鐘":
            self.update_interval = 60
        else:
            self.update_interval = 0  # 關閉自動更新

        if self.update_interval > 0:
            self.status_label.config(
                text=f"自動更新設定為每 {val}", foreground="gray"
            )
        else:
            self.status_label.config(text="已關閉自動更新", foreground="gray")

    def auto_update_loop(self):
        """需求 3: 背景定時循環"""
        while self.is_running:
            if self.update_interval > 0:
                time.sleep(self.update_interval)
                if self.portfolio and self.update_interval > 0:
                    self.update_all_stocks_bg()
            else:
                time.sleep(2)  # 關閉自動更新時保持輪詢狀態

    def update_all_stocks_bg(self):
        """背景更新全清單價格"""
        self.root.after(
            0,
            lambda: self.status_label.config(
                text="背景更新全清單股價中...", foreground="blue"
            ),
        )

        for symbol in list(self.portfolio.keys()):
            new_price = self.get_latest_price(symbol)
            if new_price:
                shares = self.portfolio[symbol]["shares"]
                self.portfolio[symbol]["price"] = new_price
                self.portfolio[symbol]["total"] = new_price * shares

        self.root.after(0, self.refresh_treeview)
        current_time = time.strftime("%H:%M:%S")
        self.root.after(
            0,
            lambda: self.status_label.config(
                text=f"最後更新時間：{current_time}", foreground="gray"
            ),
        )

    # ================= 繪製表格 UI =================
    def refresh_treeview(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        grand_total = 0.0

        for symbol, data in self.portfolio.items():
            shares = data["shares"]
            price = data["price"]
            total_val = data["total"]
            grand_total += total_val

            self.tree.insert(
                "",
                "end",
                iid=symbol,
                values=(
                    symbol,
                    f"{shares:,.0f}",
                    f"{price:,.2f}",
                    f"{total_val:,.2f}",
                ),
            )

        self.grand_total_label.config(text=f"資產總計: ${grand_total:,.2f}")


if __name__ == "__main__":
    root = tk.Tk()
    app = StockTrackerApp(root)
    root.mainloop()