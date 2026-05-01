import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import requests
from datetime import datetime

# VADER Sentiment
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

# Plotly
try:
    import plotly.express as px

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide", page_icon="📈")

st.title("Hedge Fund Stock Tracker")
st.markdown("**Professional Multi-Asset Portfolio Intelligence Platform**")

PORTFOLIO_FILE = "hedge_fund_portfolio.json"
NEWS_API_KEY = "523c8e0c5905413ea50dce4eef9948ec"


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

    # ====================== NEWSAPI + SENTIMENT ======================
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
        try:
            url = f"https://newsapi.org/v2/everything?q={ticker}&apiKey={NEWS_API_KEY}&sortBy=publishedAt&pageSize={limit}"
            response = requests.get(url)
            if response.status_code != 200:
                return [{"title": "Unable to fetch news", "link": "#", "publisher": "System", "sentiment": "⚪ Neutral",
                         "score": 0.0}]

            articles = response.json().get('articles', [])
            processed = []

            for article in articles:
                title = article.get('title', 'Market Update')
                link = article.get('url', '#')
                publisher = article.get('source', {}).get('name', 'Unknown')

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

with tab2:
    st.header("Import from SelfWealth")
    uploaded = st.file_uploader("Upload SelfWealth Portfolio Statement CSV", type="csv")
    if uploaded and st.button("Import CSV"):
        st.info("Import function ready (add your improved importer if needed)")

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
    st.header("Dividends & 12-Month Forecast")
    if pm.portfolio:
        forecast_data = []
        total_forecast = 0.0
        for pos in pm.portfolio:
            annual = 0.0  # Expand with full dividend logic later
            income = pos["shares"] * annual
            total_forecast += income
            forecast_data.append({
                "Ticker": pos["ticker"],
                "Shares": round(pos["shares"], 4),
                "Est 12M Income": round(income, 2)
            })
        st.dataframe(pd.DataFrame(forecast_data), use_container_width=True, hide_index=True)
        st.metric("Total Expected Dividend Income (Next 12 Months)", f"${total_forecast:,.2f}")
    else:
        st.info("No holdings yet.")

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

st.sidebar.info("News powered by NewsAPI.org | Data synced with console_tracker.py")
