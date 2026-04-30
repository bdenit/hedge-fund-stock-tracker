import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Download VADER lexicon (first run only)
import nltk

nltk.download('vader_lexicon', quiet=True)

try:
    import plotly.express as px

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide", page_icon="📈")

st.title("Hedge Fund Stock Tracker")
st.markdown("**Professional Multi-Asset Portfolio Intelligence Platform**")

PORTFOLIO_FILE = "hedge_fund_portfolio.json"

# Initialize VADER
sia = SentimentIntensityAnalyzer()


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
        cost_basis = position["shares"] * position["avg_cost"]
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

    # ====================== ADVANCED SENTIMENT ANALYSIS ======================
    def analyze_sentiment(self, text):
        if not text:
            return "Neutral", 0.0
        scores = sia.polarity_scores(text)
        compound = scores['compound']

        if compound >= 0.15:
            return "🟢 Positive", compound
        elif compound <= -0.15:
            return "🔴 Negative", compound
        else:
            return "⚪ Neutral", compound

    def get_news(self, ticker, limit=6):
        try:
            stock = yf.Ticker(ticker)
            news_list = stock.news[:limit]
            processed = []
            for item in news_list:
                title = item.get('title', 'No Title')
                link = item.get('link', '#')
                publisher = item.get('publisher', 'Unknown')
                sentiment_label, score = self.analyze_sentiment(title)

                processed.append({
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "sentiment": sentiment_label,
                    "score": round(score, 3)
                })
            return processed
        except:
            return []


# ====================== Initialize ======================
pm = PortfolioManager()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Main Portfolio",
    "📤 Import CSV",
    "✏️ Edit Positions",
    "📈 Dividends & Forecast",
    "📰 News & Sentiment",
    "🌍 Markets & Calendar"
])

with tab1:
    st.header("Portfolio Overview")
    if st.button("🔄 Refresh All Data"):
        st.rerun()

    if pm.portfolio:
        data = []
        total_mv = 0.0
        total_unreal = 0.0

        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            total_mv += mv
            total_unreal += pnl["unrealized_pnl"] if isinstance(pnl["unrealized_pnl"], (int, float)) else 0

            data.append({
                "Ticker": pos["ticker"],
                "Name": pos.get("name", ""),
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos.get("avg_cost", 0), 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Unrealized P&L": pnl["unrealized_pnl"],
                "Daily Change %": pnl.get("daily_change")
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
        with col2:
            color = "#00ff88" if total_unreal >= 0 else "#ff4444"
            st.markdown(
                f"<div style='background-color:#1E1E1E;padding:15px;border-radius:10px;text-align:center'><h4>Unrealized P&L</h4><h2 style='color:{color}'>${total_unreal:,.2f}</h2></div>",
                unsafe_allow_html=True)

    else:
        st.info("Portfolio is empty.")

with tab5:
    st.header("📰 News & Sentiment Analysis")
    if pm.portfolio:
        for pos in pm.portfolio[:10]:  # Limit to top 10 holdings
            with st.expander(f"**{pos['ticker']}** - Latest News & Sentiment"):
                news_items = pm.get_news(pos["ticker"], limit=5)
                for item in news_items:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    st.caption(f"{item['publisher']} • Sentiment: {item['sentiment']} (Score: {item['score']})")
                    st.divider()
    else:
        st.info("Add holdings to see news and sentiment analysis.")

with tab6:
    st.header("🌍 World Markets & Economic Calendar")
    # Precious Metals in AUD (as requested)
    st.subheader("Precious Metals & Commodities (in AUD)")
    commodities = {"Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F", "Platinum": "PL=F"}
    aud_rate = pm.get_current_price("AUDUSD=X") or 1.0

    comm_data = []
    for name, symbol in commodities.items():
        usd_price = pm.get_current_price(symbol)
        aud_price = usd_price / aud_rate if usd_price else None
        comm_data.append(
            {"Commodity": name, "USD Price": usd_price, "AUD Price": round(aud_price, 2) if aud_price else "N/A"})
    st.dataframe(pd.DataFrame(comm_data), use_container_width=True, hide_index=True)

    # Economic Calendar (placeholder - can be expanded with real API later)
    st.subheader("Economic Calendar")
    calendar_data = [
        {"Time": "Today 10:30 AM", "Event": "Australia CPI", "Impact": "High"},
        {"Time": "Tomorrow 8:00 PM", "Event": "FOMC Rate Decision", "Impact": "Very High"},
    ]
    st.dataframe(pd.DataFrame(calendar_data), use_container_width=True, hide_index=True)

st.sidebar.info("Data synchronized with console_tracker.py | News powered by yfinance + VADER Sentiment")
