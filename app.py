import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide")
st.title("Hedge Fund Stock Tracker v9.2")
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

    def get_current_price(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            return float(price) if price else None
        except:
            return None

    def calculate_pnl(self, position):
        price = self.get_current_price(position["ticker"])
        if price is None:
            return {"current_price": "N/A", "market_value": "N/A", "unrealized_pnl": "N/A"}
        mv = position["shares"] * price
        cost = position["shares"] * position["avg_cost"]
        unreal = mv - cost
        return {
            "current_price": round(price, 4),
            "market_value": round(mv, 2),
            "unrealized_pnl": round(unreal, 2)
        }

    def import_selfwealth_csv(self, uploaded_file):
        df = pd.read_csv(uploaded_file)
        ticker_col = next((col for col in df.columns if str(col).lower() in ['ticker', 'code']), None)
        shares_col = next((col for col in df.columns if any(w in str(col).lower()
            for w in ['units', 'quantity', 'shares'])), None)

        if not ticker_col or not shares_col:
            st.error("Could not detect Ticker and Quantity columns.")
            return False

        for _, row in df.iterrows():
            ticker = str(row[ticker_col]).strip().upper()
            if '.' not in ticker:
                ticker += '.AX'
            try:
                shares = float(row[shares_col])
                if shares <= 0: continue
            except:
                continue

            existing = next((p for p in self.portfolio if p["ticker"] == ticker), None)
            if existing:
                existing["shares"] = shares
            else:
                price = self.get_current_price(ticker) or 0.0
                self.portfolio.append({
                    "ticker": ticker,
                    "shares": shares,
                    "avg_cost": price,
                    "name": ticker
                })

        self.save_all()
        st.success("SelfWealth CSV imported successfully!")
        return True


pm = PortfolioManager()

tab1, tab2, tab3 = st.tabs(["Portfolio", "Import CSV", "Edit Positions"])

with tab1:
    st.header("Portfolio Overview")
    if pm.portfolio:
        data = []
        total = 0.0
        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            total += pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            data.append({
                "Ticker": pos["ticker"],
                "Shares": pos["shares"],
                "Avg Cost": round(pos["avg_cost"], 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"]
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        st.metric("Total Portfolio Value", f"${total:,.2f}")
    else:
        st.info("Portfolio is empty.")

with tab2:
    st.header("Import from SelfWealth")
    uploaded = st.file_uploader("Upload SelfWealth Portfolio CSV", type="csv")
    if uploaded and st.button("Import CSV"):
        pm.import_selfwealth_csv(uploaded)

with tab3:
    st.header("Edit Positions")
    if pm.portfolio:
        df = pd.DataFrame(pm.portfolio)
        edited = st.data_editor(df[["ticker", "name", "shares", "avg_cost"]], use_container_width=True)
        if st.button("Save Changes"):
            pm.portfolio = edited.to_dict('records')
            pm.save_all()
            st.success("Changes saved!")
            st.rerun()

st.sidebar.info("Data is shared with console_tracker.py")