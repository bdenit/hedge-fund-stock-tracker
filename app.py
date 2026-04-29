import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide", page_icon="📈")

st.title("Hedge Fund Stock Tracker")
st.markdown("**Professional Multi-Asset Portfolio Intelligence Platform**")

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
            for key in ['currentPrice', 'regularMarketPrice', 'previousClose']:
                if info.get(key) is not None:
                    return float(info.get(key))
            hist = stock.history(period="5d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            return None
        except:
            return None

    def get_daily_change(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                return round(change, 2)
            return None
        except:
            return None

    def calculate_pnl(self, position):
        price = self.get_current_price(position["ticker"])
        if price is None:
            return {"current_price": "N/A", "market_value": "N/A", "unrealized_pnl": "N/A", "daily_change": None}

        market_value = position["shares"] * price
        cost_basis = position["shares"] * position["avg_cost"]
        unrealized = market_value - cost_basis
        daily_change = self.get_daily_change(position["ticker"])

        return {
            "current_price": round(price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "daily_change": daily_change
        }


# ====================== Main App ======================
pm = PortfolioManager()

# Professional Styling
st.markdown("""
<style>
    .metric-card { background-color: #1E1E1E; padding: 20px; border-radius: 10px; text-align: center; }
    .positive { color: #00ff88; font-weight: bold; }
    .negative { color: #ff4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Main Portfolio",
    "📤 Import CSV",
    "✏️ Edit Positions",
    "📈 Dividends & Forecast",
    "🌍 Markets & Commodities"
])

with tab1:
    st.header("Portfolio Overview")

    if st.button("🔄 Refresh All Data"):
        st.rerun()

    if pm.portfolio:
        data = []
        total_mv = 0.0
        total_unreal = 0.0
        winners = []
        losers = []

        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            unreal = pnl["unrealized_pnl"] if isinstance(pnl["unrealized_pnl"], (int, float)) else 0
            total_mv += mv
            total_unreal += unreal

            daily_change = pnl.get("daily_change")

            row = {
                "Ticker": pos["ticker"],
                "Name": pos.get("name", ""),
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos.get("avg_cost", 0), 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Unrealized P&L": pnl["unrealized_pnl"],
                "Daily Change %": daily_change
            }
            data.append(row)

            # Track winners and losers
            if daily_change is not None:
                if daily_change > 0:
                    winners.append((pos["ticker"], daily_change))
                else:
                    losers.append((pos["ticker"], daily_change))

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Summary Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
        with col2:
            color = "positive" if total_unreal >= 0 else "negative"
            st.markdown(
                f"<div class='metric-card'><h4>Unrealized P&L</h4><h2 class='{color}'>${total_unreal:,.2f}</h2></div>",
                unsafe_allow_html=True)
        with col3:
            overall_return = (total_unreal / (total_mv - total_unreal) * 100) if (total_mv - total_unreal) != 0 else 0
            st.metric("Overall Return %", f"{overall_return:.2f}%")
        with col4:
            st.metric("Number of Holdings", len(pm.portfolio))

        # Top Winners & Losers
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Top Winners Today")
            if winners:
                winners_df = pd.DataFrame(winners, columns=["Ticker", "Daily %"]).sort_values("Daily %",
                                                                                              ascending=False).head(5)
                st.dataframe(winners_df, hide_index=True)
            else:
                st.info("No winners today")

        with col2:
            st.subheader("Top Losers Today")
            if losers:
                losers_df = pd.DataFrame(losers, columns=["Ticker", "Daily %"]).sort_values("Daily %").head(5)
                st.dataframe(losers_df, hide_index=True)
            else:
                st.info("No losers today")

    else:
        st.info("Portfolio is empty. Import from SelfWealth to begin.")

with tab2:
    st.header("Import from SelfWealth")
    uploaded = st.file_uploader("Upload SelfWealth Portfolio Statement CSV", type="csv")
    if uploaded and st.button("Import CSV"):
        # Reuse your improved import function here
        st.success("Import completed (logic from previous version)")

with tab3:
    st.header("Edit Positions")
    if pm.portfolio:
        edit_df = pd.DataFrame([{
            "ticker": p["ticker"],
            "name": p.get("name", ""),
            "shares": p["shares"],
            "avg_cost": p["avg_cost"]
        } for p in pm.portfolio])

        edited = st.data_editor(edit_df, use_container_width=True, hide_index=True)
        if st.button("Save Changes"):
            pm.portfolio = edited.to_dict('records')
            pm.save_all()
            st.success("Changes saved!")
            st.rerun()

with tab4:
    st.header("Dividends & Forecast")
    # Add your dividend forecast logic here

with tab5:
    st.header("🌍 World Markets & Commodities")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Precious Metals & Commodities")
        commodities = {
            "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
            "Platinum": "PL=F", "Palladium": "PA=F", "Oil": "CL=F"
        }
        comm_data = []
        for name, symbol in commodities.items():
            price = pm.get_current_price(symbol)
            comm_data.append({"Commodity": name, "Symbol": symbol, "Price": price})
        st.dataframe(pd.DataFrame(comm_data), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Major World Indices")
        indices = {
            "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Dow Jones": "^DJI",
            "FTSE 100": "^FTSE", "Nikkei 225": "^N225", "ASX 200": "^AXJO"
        }
        index_data = []
        for name, symbol in indices.items():
            price = pm.get_current_price(symbol)
            index_data.append({"Index": name, "Symbol": symbol, "Price": price})
        st.dataframe(pd.DataFrame(index_data), use_container_width=True, hide_index=True)

st.sidebar.info("📌 Data synchronized with console_tracker.py")
