import json
import os
import time
import pandas as pd
import streamlit as st
import yfinance as yf

# 設定網頁標題與頁面佈局
st.set_page_config(
    page_title="股票資產即時追蹤器", page_icon="📈", layout="centered"
)

CONFIG_FILE = "portfolio.json"


# --- 讀取與儲存設定檔 ---
def load_portfolio():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_portfolio(portfolio):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=4)


# 使用 st.session_state 保存資料狀態
if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()


# --- 抓取股價邏輯 (快取 15 秒避免請求過於頻繁) ---
@st.cache_data(ttl=15)
def get_latest_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        price = stock.fast_info.get("last_price")
        if price is None or price != price:  # 檢查是否為 None 或 NaN
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
        return price
    except Exception:
        return None


# --- UI 畫面設計 ---
st.title("📈 股票資產即時追蹤器")

# 左側邊欄：新增股票與設定
with st.sidebar:
    st.header("⚙️ 選單與設定")

    st.subheader("新增 / 更新股票")
    symbol_input = (
        st.text_input("股票代號 (例如 2330.TW 或 AAPL)").strip().upper()
    )
    shares_input = st.number_input(
        "持有股數 (預設 0)", min_value=0.0, value=0.0, step=100.0
    )

    if st.button("➕ 新增 / 更新股票", type="primary"):
        if symbol_input:
            with st.spinner("驗證股票代號中..."):
                price = get_latest_price(symbol_input)
            if price is not None:
                st.session_state.portfolio[symbol_input] = shares_input
                save_portfolio(st.session_state.portfolio)
                st.success(f"已成功新增/更新 {symbol_input}！")
                st.rerun()
            else:
                st.error(
                    f"無法抓取 {symbol_input} 價格，請確認代號（台股請加 .TW）。"
                )
        else:
            st.warning("請輸入股票代號！")

    st.divider()

    # 定時自動刷新開關
    auto_refresh = st.checkbox("開啟自動刷新", value=False)
    refresh_interval = (
        st.selectbox("刷新間隔", [10, 30, 60], index=1)
        if auto_refresh
        else None
    )

# 主要內容區：資產清單
if st.session_state.portfolio:
    data = []
    grand_total = 0.0

    with st.spinner("更新最新股價中..."):
        for symbol, shares in list(st.session_state.portfolio.items()):
            price = get_latest_price(symbol) or 0.0
            total_val = price * shares
            grand_total += total_val
            data.append({
                "股票代號": symbol,
                "持有股數": f"{shares:,.0f}",
                "最新股價": f"${price:,.2f}",
                "總價值": f"${total_val:,.2f}",
            })

    # 展示總資產
    st.metric(label="💰 目前總資產估計", value=f"${grand_total:,.2f}")

    # 展示股票表格
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 刪除股票區塊
    st.subheader("🗑️ 刪除股票")
    col1, col2 = st.columns([3, 1])
    with col1:
        delete_symbol = st.selectbox(
            "選擇要刪除的股票",
            list(st.session_state.portfolio.keys()),
            label_visibility="collapsed",
        )
    with col2:
        if st.button("刪除股票", type="secondary"):
            if delete_symbol in st.session_state.portfolio:
                del st.session_state.portfolio[delete_symbol]
                save_portfolio(st.session_state.portfolio)
                st.toast(f"已刪除 {delete_symbol}")
                st.rerun()
else:
    st.info("目前清單中尚無股票，請利用左側選單新增股票！")

# 自動刷新處理
if auto_refresh and refresh_interval:
    time.sleep(refresh_interval)
    st.rerun()
