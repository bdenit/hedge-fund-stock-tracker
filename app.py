import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide")
st.title("Hedge Fund Stock Tracker v9.3")
st.markdown("**Professional Portfolio Tool with SelfWealth Import**")

PORTFOLIO_FILE = "hedge_fund_portfolio.json"


class PortfolioManager:
    def __init__(self):
        self.portfolio = self.load_portfolio()

    def load_portfolio(self):
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("open_positions", [])
            except:
                return []
        return []

    def save_all(self):
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump({"open_positions": self.portfolio}, f, indent=2)

    # Improved price fetching with multiple fallbacks
    def get_current_price(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Try multiple price fields
            for key in ['currentPrice', 'regularMarketPrice', 'previousClose', 'lastPrice']:
                price = info.get(key)
                if price is not None:
                    return float(price)

            # Fallback: get history for latest close
            hist = stock.history(period="5d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])

            return None
        except Exception as e:
            st.warning(f"Could not fetch price for {ticker}: {e}")
            return None

    def calculate_pnl(self, position):
        price = self.get_current_price(position["ticker"])
        if price is None:
            return {
                "current_price": "N/A",
                "market_value": "N/A",
                "unrealized_pnl": "N/A"
            }

        market_value = position["shares"] * price
        cost_basis = position["shares"] * position["avg_cost"]
        unrealized = market_value - cost_basis

        return {
            "current_price": round(price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2)
        }

    def import_selfwealth_csv(self, uploaded_file):
        df = pd.read_csv(uploaded_file)

        ticker_col = next((col for col in df.columns if str(col).lower() in ['ticker', 'code', 'symbol']), None)
        shares_col = next((col for col in df.columns if any(w in str(col).lower()
                                                            for w in ['units', 'quantity', 'shares', 'held'])), None)

        if not ticker_col or not shares_col:
            st.error("Could not detect Ticker and Quantity columns in CSV.")
            st.dataframe(df.head())
            return False

        imported = 0
        for _, row in df.iterrows():
            ticker_raw = str(row[ticker_col]).strip().upper()
            if not ticker_raw or ticker_raw.lower() == 'nan':
                continue

            ticker = ticker_raw + '.AX' if '.' not in ticker_raw else ticker_raw

            try:
                shares = float(row[shares_col])
                if shares <= 0:
                    continue
            except:
                continue

            existing = next((p for p in self.portfolio if p["ticker"] == ticker), None)
            if existing:
                existing["shares"] = shares
            else:
                current_price = self.get_current_price(ticker) or 0.0
                self.portfolio.append({
                    "ticker": ticker,
                    "shares": shares,
                    "avg_cost": current_price,
                    "name": ticker
                })
                imported += 1

        self.save_all()
        st.success(f"Imported/Updated {imported} positions successfully!")
        return True


# ====================== Streamlit UI ======================
pm = PortfolioManager()

tab1, tab2, tab3 = st.tabs(["📊 Portfolio", "📤 Import CSV", "✏️ Edit Positions"])

with tab1:
    st.header("Portfolio Overview")

    if st.button("Refresh All Prices"):
        st.rerun()

    if pm.portfolio:
        data = []
        total_mv = 0.0

        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            total_mv += mv

            data.append({
                "Ticker": pos["ticker"],
                "Name": pos.get("name", ""),
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos.get("avg_cost", 0), 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Unrealized P&L": pnl["unrealized_pnl"]
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
    else:
        st.info("Portfolio is empty. Import a CSV from SelfWealth to begin.")

with tab2:
    st.header("Import from SelfWealth")
    uploaded = st.file_uploader("Upload SelfWealth Portfolio Statement CSV", type="csv")
    if uploaded and st.button("Process CSV"):
        pm.import_selfwealth_csv(uploaded)

with tab3:
    st.header("Edit Positions")
    if pm.portfolio:
        df = pd.DataFrame([{
            "ticker": p["ticker"],
            "name": p.get("name", ""),
            "shares": p["shares"],
            "avg_cost": p["avg_cost"]
        } for p in pm.portfolio])

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ticker": st.column_config.TextColumn("Ticker", disabled=True),
                "name": st.column_config.TextColumn("Name"),
                "shares": st.column_config.NumberColumn("Shares", min_value=0.0, format="%.4f"),
                "avg_cost": st.column_config.NumberColumn("Avg Cost", min_value=0.0, format="%.4f")
            }
        )

        if st.button("Save Changes"):
            pm.portfolio = edited_df.to_dict('records')
            pm.save_all()
            st.success("Changes saved!")
            st.rerun()
    else:
        st.info("No positions to edit.")

st.sidebar.info("Data is shared with console_tracker.py")