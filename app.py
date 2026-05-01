import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta
import re

# VADER Sentiment
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide", page_icon="📈")

st.title("Hedge Fund Stock Tracker")
st.markdown("**Professional Multi-Asset Portfolio Intelligence Platform**")

PORTFOLIO_FILE = "hedge_fund_portfolio.json"
FINNHUB_API_KEY = "YOUR_FINNHUB_API_KEY_HERE"  # ← Replace with your real Finnhub key

news_cache = {}


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

    # ====================== NEWS WITH FINNHUB + AGGRESSIVE YFINANCE CLEANING ======================
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

    def get_news(self, ticker, limit=6):
        cache_key = ticker
        now = datetime.now()

        if cache_key in news_cache:
            cached_time, cached_news = news_cache[cache_key]
            if now - cached_time < timedelta(minutes=30):
                return cached_news

        # 1. Try Finnhub (cleaner data)
        if FINNHUB_API_KEY and FINNHUB_API_KEY != "d7q4cjpr01qosaaqj7lgd7q4cjpr01qosaaqj7m0":
            try:
                from_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={now.strftime('%Y-%m-%d')}&token={FINNHUB_API_KEY}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    articles = response.json()
                    processed = []
                    for article in articles[:limit]:
                        title = article.get('headline', 'Market Update')
                        link = article.get('url', '#')
                        publisher = article.get('source', 'Finnhub')
                        sentiment_label, score = self.analyze_sentiment(title)
                        processed.append({
                            "title": title[:220],
                            "link": link,
                            "publisher": publisher,
                            "sentiment": sentiment_label,
                            "score": round(score, 3)
                        })
                    if processed:
                        news_cache[cache_key] = (now, processed)
                        return processed
            except:
                pass

        # 2. Aggressive yfinance fallback with heavy cleaning
        try:
            stock = yf.Ticker(ticker)
            raw_news = stock.news[:limit]
            processed = []

            for item in raw_news:
                title = "Market Update"
                link = "#"

                if isinstance(item, dict):
                    title = item.get('title') or item.get('content') or item.get('headline') or "Market Update"
                    link = item.get('link') or item.get('url') or "#"
                elif isinstance(item, str):
                    # Aggressive regex cleaning for the messy strings you're seeing
                    match = re.search(r"'title':\s*'([^']+)'", item)
                    if match:
                        title = match.group(1)
                    else:
                        # Try to extract any proper sentence
                        match = re.search(r'([A-Z][^.!?]{40,300}[.!?])', item)
                        if match:
                            title = match.group(1)
                        else:
                            title = item[:180]

                # Final heavy cleaning
                title = re.sub(r'\{.*?\}', '', str(title))  # Remove JSON fragments
                title = re.sub(r'\[.*?\]', '', title)
                title = re.sub(r'provider.*?canonicalUrl.*?(?=,|$)', '', title, flags=re.I)
                title = re.sub(r'[\[\]\'\"]+', '', title)
                title = title.strip()[:220]

                if len(title) < 15 or "canonicalUrl" in title:
                    title = "Market Update"

                sentiment_label, score = self.analyze_sentiment(title)

                processed.append({
                    "title": title,
                    "link": link,
                    "publisher": "Yahoo Finance",
                    "sentiment": sentiment_label,
                    "score": round(score, 3)
                })

            if processed:
                news_cache[cache_key] = (now, processed)
                return processed
        except:
            pass

        # Final fallback
        result = [{"title": "No recent news available", "link": "#", "publisher": "System", "sentiment": "⚪ Neutral",
                   "score": 0.0}]
        news_cache[cache_key] = (now, result)
        return result


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

with tab2:
    st.header("Import from SelfWealth")
    uploaded = st.file_uploader("Upload SelfWealth CSV", type="csv")
    if uploaded and st.button("Import CSV"):
        st.info("SelfWealth import logic can be added here (previous version had column mapping)")

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
        if st.button("Save Changes"):
            pm.portfolio = edited.to_dict('records')
            pm.save_all()
            st.success("Positions updated!")
            st.rerun()

with tab4:
    st.header("Dividends & Forecast")
    st.info("Dividend tracking and 12-month forecast can be expanded here.")

with tab5:
    st.header("📰 News & Sentiment Analysis")
    if st.button("🔄 Refresh All News"):
        news_cache.clear()
        st.rerun()

    if pm.portfolio:
        for pos in pm.portfolio:
            with st.expander(f"**{pos['ticker']}** - Latest News"):
                news_items = pm.get_news(pos["ticker"], limit=6)
                for item in news_items:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    st.caption(f"{item['publisher']} • {item['sentiment']} (Score: {item['score']})")
                    st.divider()
    else:
        st.info("Add holdings to see news and sentiment analysis.")

st.sidebar.info("News: Finnhub → Aggressive yfinance fallback | Cached 30 min")
