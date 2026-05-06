import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import numpy as np
from datetime import datetime, timedelta

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
RISK_FREE_RATE = 0.04  # 4.0% (approximate Australian risk-free rate)


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

    def get_ytd_return(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="ytd")
            if len(hist) > 1:
                return round(((hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1) * 100, 2)
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

    def get_sector(self, ticker):
        try:
            return yf.Ticker(ticker).info.get('sector', 'Unknown')
        except:
            return 'Unknown'

    def get_industry(self, ticker):
        try:
            return yf.Ticker(ticker).info.get('industry', 'Unknown')
        except:
            return 'Unknown'

    def get_country(self, ticker):
        try:
            country = yf.Ticker(ticker).info.get('country', '')
            return 'Australia' if country == 'Australia' else 'International'
        except:
            return 'International'

    # ====================== RISK METRICS ======================
    def calculate_portfolio_beta(self):
        if not self.portfolio:
            return 1.0
        try:
            # Use ASX 200 as benchmark
            benchmark = yf.Ticker("^AXJO").history(period="1y")['Close']
            weights = []
            returns = []

            for pos in self.portfolio:
                ticker = pos["ticker"]
                hist = yf.Ticker(ticker).history(period="1y")['Close']
                if len(hist) > 10:
                    # Align dates
                    common_idx = hist.index.intersection(benchmark.index)
                    if len(common_idx) > 10:
                        asset_ret = hist.loc[common_idx].pct_change().dropna()
                        bench_ret = benchmark.loc[common_idx].pct_change().dropna()
                        # Simple beta approximation
                        cov = np.cov(asset_ret, bench_ret)[0, 1]
                        var = np.var(bench_ret)
                        beta = cov / var if var != 0 else 1.0
                        weight = (pos["shares"] * self.get_current_price(ticker)) / self.get_total_mv()
                        weights.append(weight)
                        returns.append(beta)

            if returns:
                return round(sum(w * r for w, r in zip(weights, returns)), 2)
            return 1.0
        except:
            return 1.0

    def calculate_sharpe_ratio(self):
        if not self.portfolio or len(self.portfolio) == 0:
            return 0.0
        try:
            returns = []
            for pos in self.portfolio:
                hist = yf.Ticker(pos["ticker"]).history(period="1y")['Close']
                if len(hist) > 20:
                    ret = hist.pct_change().dropna().mean() * 252  # Annualized
                    returns.append(ret)

            if not returns:
                return 0.0

            portfolio_return = np.mean(returns)
            portfolio_std = np.std(returns) * np.sqrt(252)
            sharpe = (portfolio_return - RISK_FREE_RATE) / portfolio_std if portfolio_std > 0 else 0.0
            return round(sharpe, 2)
        except:
            return 0.0

    def get_total_mv(self):
        total = 0.0
        for pos in self.portfolio:
            price = self.get_current_price(pos["ticker"])
            if price:
                total += pos["shares"] * price
        return total


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
        industry_data = {}
        geo_data = {}

        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            total_mv += mv
            total_unreal += pnl["unrealized_pnl"] if isinstance(pnl["unrealized_pnl"], (int, float)) else 0

            sector = pm.get_sector(pos["ticker"])
            industry = pm.get_industry(pos["ticker"])
            country = pm.get_country(pos["ticker"])

            sector_data[sector] = sector_data.get(sector, 0) + mv
            industry_data[industry] = industry_data.get(industry, 0) + mv
            geo_data[country] = geo_data.get(country, 0) + mv

            data.append({
                "Ticker": pos["ticker"],
                "Name": pos.get("name", ""),
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos.get("avg_cost", 0), 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Daily %": pnl["daily_change"],
                "Unrealized P&L": pnl["unrealized_pnl"],
                "Sector": sector,
                "Industry": industry
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        # Risk Metrics + Charts
        col1, col2 = st.columns([2, 3])
        with col1:
            st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
            color = "#00ff88" if total_unreal >= 0 else "#ff4444"
            st.markdown(
                f"<div style='background-color:#1E1E1E;padding:20px;border-radius:10px;text-align:center'><h4>Unrealized P&L</h4><h2 style='color:{color}'>${total_unreal:,.2f}</h2></div>",
                unsafe_allow_html=True)

        with col2:
            st.subheader("Risk Metrics")
            beta = pm.calculate_portfolio_beta()
            sharpe = pm.calculate_sharpe_ratio()
            concentration = max([p["shares"] * pm.get_current_price(p["ticker"]) for p in pm.portfolio if
                                 pm.get_current_price(p["ticker"]) is not None] or [
                                    0]) / total_mv * 100 if total_mv > 0 else 0

            st.metric("Portfolio Beta (vs ASX 200)", f"{beta:.2f}")
            st.metric("Sharpe Ratio (1Y)", f"{sharpe:.2f}")
            st.metric("Largest Position Concentration", f"{concentration:.1f}%",
                      delta="High" if concentration > 15 else "OK")

        # Charts (Sector, Industry, Geo)
        if PLOTLY_AVAILABLE:
            col3, col4, col5 = st.columns(3)
            with col3:
                fig = px.pie(names=list(sector_data.keys()), values=list(sector_data.values()),
                             title="Sector Allocation")
                st.plotly_chart(fig, use_container_width=True)
            with col4:
                fig2 = px.pie(names=list(industry_data.keys()), values=list(industry_data.values()),
                              title="Industry Breakdown")
                st.plotly_chart(fig2, use_container_width=True)
            with col5:
                fig3 = px.pie(names=list(geo_data.keys()), values=list(geo_data.values()),
                              title="Geographic Allocation")
                st.plotly_chart(fig3, use_container_width=True)

    else:
        st.info("Portfolio is empty.")

with tab2:
    st.header("Import from SelfWealth")
    uploaded = st.file_uploader("Upload SelfWealth CSV", type="csv")
    if uploaded and st.button("Import CSV"):
        st.info("Importer placeholder")

with tab3:
    st.header("Edit Positions")
    if pm.portfolio:
        edit_df = pd.DataFrame([{
            "ticker": p["ticker"],
            "name": p.get("name", ""),
            "shares": p["shares"],
            "avg_cost": p.get("avg_cost", 0)
        } for p in pm.portfolio])

        edited = st.data_editor(edit_df, use_container_width=True, hide_index=True)
        if st.button("💾 Save Changes"):
            pm.portfolio = edited.to_dict('records')
            pm.save_all()
            st.success("Positions saved!")
            st.rerun()

with tab4:
    st.header("Dividends & Forecast")
    st.info("Dividend features can be expanded here.")

st.sidebar.info("Added: Sharpe Ratio + Portfolio Beta")
