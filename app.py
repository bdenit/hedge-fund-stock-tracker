import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime
import plotly.express as px
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

    def get_sector(self, ticker):
        try:
            return yf.Ticker(ticker).info.get('sector', 'Unknown')
        except:
            return 'Unknown'

    # ====================== NEWS WITH SENTIMENT & CLICKABLE LINKS ======================
    def get_news(self, ticker, limit=5):
        try:
            stock = yf.Ticker(ticker)
            news_list = stock.news[:limit]
            processed = []
            for item in news_list:
                title = item.get('title', 'No Title')
                link = item.get('link', '#')
                publisher = item.get('publisher', 'Unknown')

                # Simple sentiment analysis
                sentiment = self.analyze_sentiment(title)

                processed.append({
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "sentiment": sentiment
                })
            return processed
        except:
            return []

    def analyze_sentiment(self, text):
        text_lower = text.lower()
        positive_words = ['rise', 'up', 'gain', 'beat', 'strong', 'surge', 'higher', 'positive']
        negative_words = ['fall', 'down', 'drop', 'miss', 'weak', 'decline', 'lower', 'negative']

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        if pos_count > neg_count:
            return "🟢 Positive"
        elif neg_count > pos_count:
            return "🔴 Negative"
        else:
            return "⚪ Neutral"

    # ====================== ECONOMIC CALENDAR (Simple Version) ======================
    def get_economic_calendar(self):
        # For a real app we'd use an API. Here we show a clean static + dynamic version
        events = [
            {"Time": "10:00 AM", "Event": "Australia CPI (MoM)", "Impact": "High", "Forecast": "0.3%",
             "Previous": "0.2%"},
            {"Time": "10:30 AM", "Event": "US Initial Jobless Claims", "Impact": "Medium", "Forecast": "220K",
             "Previous": "215K"},
            {"Time": "8:00 PM", "Event": "FOMC Interest Rate Decision", "Impact": "High", "Forecast": "4.25%",
             "Previous": "4.25%"},
        ]
        return pd.DataFrame(events)


# ====================== Main App ======================
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
                f"<div style='background:#1E1E1E;padding:15px;border-radius:10px;text-align:center'><h4>Unrealized P&L</h4><h2 style='color:{color}'>${total_unreal:,.2f}</h2></div>",
                unsafe_allow_html=True)

    else:
        st.info("Portfolio is empty.")

with tab5:
    st.header("📰 News & Sentiment Analysis")
    if pm.portfolio:
        for pos in pm.portfolio:
            with st.expander(f"**{pos['ticker']}** - Recent News"):
                news_items = pm.get_news(pos["ticker"], limit=6)
                for item in news_items:
                    sentiment_color = "#00ff88" if "Positive" in item["sentiment"] else "#ff4444" if "Negative" in item[
                        "sentiment"] else "#aaaaaa"
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    st.caption(f"{item['publisher']} • {item['sentiment']}")
                    st.divider()
    else:
        st.info("No holdings to show news for.")

with tab6:
    st.header("🌍 World Markets & Economic Calendar")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Precious Metals & Commodities (AUD)")
        commodities = {"Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F", "Platinum": "PL=F"}
        aud_rate = pm.get_current_price("AUDUSD=X") or 1.0

        comm_data = []
        for name, symbol in commodities.items():
            usd_price = pm.get_current_price(symbol)
            aud_price = usd_price / aud_rate if usd_price else None
            comm_data.append({"Commodity": name, "USD": usd_price, "AUD": round(aud_price, 2) if aud_price else "N/A"})
        st.dataframe(pd.DataFrame(comm_data), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Economic Calendar")
        calendar_df = pm.get_economic_calendar()
        st.dataframe(calendar_df, use_container_width=True, hide_index=True)

st.sidebar.info("Data synchronized with console_tracker.py")
