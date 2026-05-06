import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import numpy as np
from datetime import datetime
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

    def get_esg_score(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            esg = stock.sustainability
            if esg is not None and not esg.empty:
                return round(float(esg.get('totalEsg', 0)), 1)
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


# ====================== Streamlit UI ======================
pm = PortfolioManager()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Main Portfolio",
    "📤 Import CSV",
    "✏️ Edit Positions",
    "📈 Dividends & Forecast",
    "🌍 Markets & Risk"
])

with tab1:
    st.header("Portfolio Overview")
    if st.button("🔄 Refresh All Data"):
        st.rerun()

    if pm.portfolio:
        data = []
        total_mv = pm.get_total_mv()
        total_unreal = 0.0

        sector_data = {}
        industry_data = {}
        geo_data = {}

        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"]
            total_unreal += pnl["unrealized_pnl"]

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
                "Market Value": mv,
                "Daily %": pnl["daily_change"],
                "Unrealized P&L": pnl["unrealized_pnl"],
                "Sector": sector,
                "Industry": industry
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        col1, col2 = st.columns([2, 3])
        with col1:
            st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
            color = "#00ff88" if total_unreal >= 0 else "#ff4444"
            st.markdown(
                f"<div style='background-color:#1E1E1E;padding:20px;border-radius:10px;text-align:center'><h4>Unrealized P&L</h4><h2 style='color:{color}'>${total_unreal:,.2f}</h2></div>",
                unsafe_allow_html=True)

        # Charts
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

with tab5:
    st.header("🌍 Markets & Advanced Risk")

    # Precious Metals + Crypto
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.subheader("Precious Metals (AUD)")
        metals = {"Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F", "Platinum": "PL=F"}
        aud_rate = pm.get_current_price("AUDUSD=X") or 1.0
        metal_data = []
        for name, symbol in metals.items():
            usd = pm.get_current_price(symbol)
            aud = usd / aud_rate if usd else None
            metal_data.append({"Metal": name, "USD": usd, "AUD": round(aud, 2) if aud else "N/A"})
        st.dataframe(pd.DataFrame(metal_data), use_container_width=True, hide_index=True)

    with col_m2:
        st.subheader("Cryptocurrencies (AUD)")
        cryptos = {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD"}
        crypto_data = []
        for name, symbol in cryptos.items():
            price = pm.get_current_price(symbol)
            crypto_data.append({"Asset": name, "Price (AUD)": round(price, 2) if price else "N/A"})
        st.dataframe(pd.DataFrame(crypto_data), use_container_width=True, hide_index=True)

    # World Markets
    st.subheader("Major World Indices")
    indices = {
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "ASX 200": "^AXJO",
        "FTSE 100": "^FTSE", "DAX": "^GDAXI", "Nikkei 225": "^N225",
        "Shanghai": "^SSEC", "Hong Kong": "^HSI", "Toronto": "^GSPTSE"
    }
    index_data = []
    for name, symbol in indices.items():
        price = pm.get_current_price(symbol)
        change = pm.get_daily_change(symbol)
        index_data.append({"Index": name, "Price": price, "Daily %": change})
    st.dataframe(pd.DataFrame(index_data), use_container_width=True, hide_index=True)

    # Risk Section (VaR, Stress Test, etc.)
    st.subheader("Risk Analytics")
    if pm.portfolio:
        var_95 = pm.calculate_var(0.95)
        st.metric("1-Day VaR (95%)", f"-${var_95:,.2f}")

st.sidebar.info("Full Professional Version - Ready for Peer Demo")
