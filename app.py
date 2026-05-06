import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO

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
            return {"current_price": "N/A", "market_value": 0, "unrealized_pnl": 0, "daily_change": None}

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

    def get_total_mv(self):
        total = 0.0
        for pos in self.portfolio:
            price = self.get_current_price(pos["ticker"])
            if price:
                total += pos["shares"] * price
        return total

    def get_esg_score(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            esg = stock.sustainability
            if esg is not None and not esg.empty:
                return round(esg.get('totalEsg', 0), 1)
            return None
        except:
            return None

    def calculate_var(self, confidence=0.95):
        if not self.portfolio:
            return 0.0
        try:
            returns = []
            for pos in self.portfolio:
                hist = yf.Ticker(pos["ticker"]).history(period="1y")['Close'].pct_change().dropna()
                if len(hist) > 30:
                    returns.append(hist)
            if not returns:
                return 0.0
            portfolio_returns = pd.concat(returns, axis=1).mean(axis=1)
            var = np.percentile(portfolio_returns, (1 - confidence) * 100)
            return round(-var * self.get_total_mv(), 2)
        except:
            return 0.0

    def run_stress_test(self):
        total_mv = self.get_total_mv()
        scenarios = {
            "Market Crash (-20%)": total_mv * -0.20,
            "Recession (-12%)": total_mv * -0.12,
            "Inflation Spike (-8%)": total_mv * -0.08,
            "Geopolitical Shock (-15%)": total_mv * -0.15,
            "Base Case (+6%)": total_mv * 0.06
        }
        return scenarios


# ====================== Streamlit UI ======================
pm = PortfolioManager()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Main Portfolio",
    "📤 Import CSV",
    "✏️ Edit Positions",
    "📈 Dividends & Forecast",
    "📉 Risk & Stress Testing"
])

with tab1:
    st.header("Portfolio Overview")
    if st.button("🔄 Refresh All Data"):
        st.rerun()

    # Portfolio table and summary (same as before)
    if pm.portfolio:
        # ... existing table code ...
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

with tab5:
    st.header("📉 Risk Analytics & Stress Testing")

    # ESG Metrics
    st.subheader("ESG Scoring")
    esg_scores = []
    for pos in pm.portfolio:
        score = pm.get_esg_score(pos["ticker"])
        if score:
            esg_scores.append(score)
    if esg_scores:
        avg_esg = round(np.mean(esg_scores), 1)
        st.metric("Portfolio Average ESG Score", f"{avg_esg}/100")
    else:
        st.info("ESG data not available for current holdings.")

    # VaR Visualization
    st.subheader("Value at Risk (VaR)")
    var_90 = pm.calculate_var(0.90)
    var_95 = pm.calculate_var(0.95)
    var_99 = pm.calculate_var(0.99)

    var_df = pd.DataFrame({
        "Confidence Level": ["90%", "95%", "99%"],
        "1-Day VaR ($)": [var_90, var_95, var_99]
    })
    fig_var = px.bar(var_df, x="Confidence Level", y="1-Day VaR ($)",
                     title="Value at Risk by Confidence Level",
                     color="1-Day VaR ($)", color_continuous_scale="Reds")
    st.plotly_chart(fig_var, use_container_width=True)

    # Stress Testing
    st.subheader("Stress Testing Scenarios")
    stress = pm.run_stress_test()
    stress_df = pd.DataFrame(list(stress.items()), columns=["Scenario", "Impact ($)"])
    fig_stress = px.bar(stress_df, x="Scenario", y="Impact ($)",
                        title="Portfolio Impact Under Stress Scenarios",
                        color="Impact ($)", color_continuous_scale="RdYlGn_r")
    st.plotly_chart(fig_stress, use_container_width=True)

    # Monte Carlo (polished)
    st.subheader("Monte Carlo Simulation (1 Year)")
    mean_mc, p5, p95 = pm.run_monte_carlo()
    if mean_mc:
        st.metric("Expected Portfolio Value", f"${mean_mc:,.2f}")
        st.metric("5th Percentile (Worst Case)", f"${p5:,.2f}")
        st.metric("95th Percentile (Best Case)", f"${p95:,.2f}")

st.sidebar.info("Added: Stress Testing + ESG Metrics + Polished VaR")
