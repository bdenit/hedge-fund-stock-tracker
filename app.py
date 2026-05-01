import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import re
from datetime import datetime

# VADER Sentiment
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

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
        cost_basis = position["shares"] * position["avg_cost"]
        unrealized = market_value - cost_basis
        daily_change = self.get_daily_change(position["ticker"])

        return {
            "current_price": round(price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "daily_change": daily_change
        }

    # ====================== CLEAN NEWS + SENTIMENT ======================
    def analyze_sentiment(self, text):
        if not text:
            return "⚪ Neutral", 0.0
        scores = sia.polarity_scores(str(text))
        compound = scores['compound']
        if compound >= 0.15:
            return "🟢 Positive", compound
        elif compound <= -0.15:
            return "🔴 Negative", compound
        else:
            return "⚪ Neutral", compound

    def get_news(self, ticker, limit=5):
        """Final robust news extraction with JSON parsing fallback"""
        try:
            stock = yf.Ticker(ticker)
            raw_news = stock.news[:limit]
            processed = []

            for item in raw_news:
                # If item is a string (JSON string), try to parse it
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except:
                        # If parsing fails, try to extract title from the string
                        match = re.search(r"'title':\s*'([^']+)'", item)
                        if match:
                            title = match.group(1)
                        else:
                            title = "Market Update"
                        link = "#"
                        processed.append({
                            "title": title,
                            "link": link,
                            "publisher": "Unknown",
                            "sentiment": "⚪ Neutral",
                            "score": 0.0
                        })
                        continue

                if not isinstance(item, dict):
                    continue

                # Extract title
                title = (item.get('title') or
                         item.get('content') or
                         item.get('headline') or
                         "Market Update")

                # Clean title - remove JSON fragments
                title = re.sub(r'\{.*?\}', '', str(title))
                title = re.sub(r'\[.*?\]', '', title)
                title = title.strip()[:250]

                # Extract link
                link = "#"
                for key in ['link', 'url', 'canonicalUrl', 'clickThroughUrl']:
                    if key in item and isinstance(item[key], str) and item[key].startswith('http'):
                        link = item[key]
                        break

                publisher = item.get('publisher', 'Unknown Source')

                sentiment_label, score = self.analyze_sentiment(title)

                processed.append({
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "sentiment": sentiment_label,
                    "score": round(score, 3)
                })

            return processed if processed else [
                {"title": "No recent news available", "link": "#", "publisher": "System", "sentiment": "⚪ Neutral",
                 "score": 0.0}]
        except Exception:
            return [{"title": "Unable to fetch news at this time", "link": "#", "publisher": "System",
                     "sentiment": "⚪ Neutral", "score": 0.0}]


# ====================== Streamlit UI ======================
pm = PortfolioManager()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Main Portfolio",
    "📤 Import CSV",
    "✏️ Edit Positions",
    "📈 Dividends & Forecast",
    "📰 News & Sentiment"
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
                "Unrealized P&L": pnl["unrealized_pnl"]
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
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
        for pos in pm.portfolio:
            with st.expander(f"**{pos['ticker']}** - Latest News"):
                news_items = pm.get_news(pos["ticker"], limit=5)
                for item in news_items:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    st.caption(f"{item['publisher']} • {item['sentiment']} (Score: {item['score']})")
                    st.divider()
    else:
        st.info("Add holdings to see news and sentiment analysis.")

st.sidebar.info("Data synchronized with console_tracker.py")
