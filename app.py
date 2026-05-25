import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime

# Plotly for charts
try:
    import plotly.express as px

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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
            for key in ['currentPrice', 'regularMarketPrice', 'previousClose', 'lastPrice']:
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
        cost_basis = position["shares"] * position.get("avg_cost", 0)
        unrealized = market_value - cost_basis
        daily_change = self.get_daily_change(position["ticker"])

        return {
            "current_price": round(price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "daily_change": daily_change
        }

    def get_dividend_info(self, ticker):
        """Accurate dividend data from yfinance"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Best available dividend data
            annual_div = info.get('dividendRate') or info.get('trailingAnnualDividendRate') or 0.0
            yield_pct = info.get('dividendYield')
            if yield_pct is not None:
                yield_pct = yield_pct * 100
            else:
                yield_pct = 0.0

            return {
                "annual_div_per_share": round(float(annual_div), 4),
                "yield_pct": round(float(yield_pct), 2)
            }
        except:
            return {"annual_div_per_share": 0.0, "yield_pct": 0.0}

    def get_sector(self, ticker):
        try:
            return yf.Ticker(ticker).info.get('sector', 'Unknown')
        except:
            return 'Unknown'


# ====================== Streamlit UI ======================
pm = PortfolioManager()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Main Portfolio",
    "📤 Import CSV",
    "✏️ Edit Positions",
    "📈 Dividends & Forecast"
])

with tab1:
    st.header("Portfolio Overview")
    if st.button("🔄 Refresh All Data"):
        st.rerun()

    if pm.portfolio:
        data = []
        total_mv = 0.0
        total_unreal = 0.0
        sector_data = {}

        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            total_mv += mv
            total_unreal += pnl["unrealized_pnl"] if isinstance(pnl["unrealized_pnl"], (int, float)) else 0

            sector = pm.get_sector(pos["ticker"])
            sector_data[sector] = sector_data.get(sector, 0) + mv

            data.append({
                "Ticker": pos["ticker"],
                "Name": pos.get("name", ""),
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos.get("avg_cost", 0), 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Daily %": pnl["daily_change"],
                "Unrealized P&L": pnl["unrealized_pnl"]
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
        with col2:
            color = "#00ff88" if total_unreal >= 0 else "#ff4444"
            st.markdown(
                f"<div style='background-color:#1E1E1E;padding:20px;border-radius:10px;text-align:center'><h4>Unrealized P&L</h4><h2 style='color:{color}'>${total_unreal:,.2f}</h2></div>",
                unsafe_allow_html=True)

        with col3:
            if PLOTLY_AVAILABLE and sector_data:
                fig = px.pie(names=list(sector_data.keys()), values=list(sector_data.values()),
                             title="Sector Allocation")
                fig.update_traces(textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Portfolio is empty.")

with tab4:
    st.header("📈 Dividends & Forecast")
    if pm.portfolio:
        div_data = []
        total_12m_income = 0.0

        for pos in pm.portfolio:
            div_info = pm.get_dividend_info(pos["ticker"])
            annual_div = div_info["annual_div_per_share"]
            est_12m_income = pos["shares"] * annual_div
            total_12m_income += est_12m_income

            div_data.append({
                "Ticker": pos["ticker"],
                "Shares": round(pos["shares"], 2),
                "Est Annual Dividend": round(annual_div, 4),
                "Yield on Cost (%)": round((annual_div / pos.get("avg_cost", 1)) * 100, 2) if pos.get("avg_cost",
                                                                                                      0) > 0 else "N/A",
                "Est 12M Income": round(est_12m_income, 2)
            })

        st.dataframe(pd.DataFrame(div_data), use_container_width=True, hide_index=True)

        st.success(f"**Total Expected 12-Month Dividend Income: ${total_12m_income:,.2f}**")

    else:
        st.info("No holdings yet.")

st.sidebar.info("Dividend data from yfinance (forward + trailing)")
