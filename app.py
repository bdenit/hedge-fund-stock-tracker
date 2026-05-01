# ====================== IMPROVED YFINANCE FALLBACK ======================
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
    """Finnhub primary (if key provided) + heavily cleaned yfinance fallback"""
    cache_key = ticker
    now = datetime.now()

    if cache_key in news_cache:
        cached_time, cached_news = news_cache[cache_key]
        if now - cached_time < timedelta(minutes=30):
            return cached_news

    # Try Finnhub if key is set (replace with your real key)
    if FINNHUB_API_KEY and FINNHUB_API_KEY != "d7q3ug9r01qosaaqhtg0d7q3ug9r01qosaaqhtgg":
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

    # Strong yfinance fallback with aggressive cleaning
    try:
        stock = yf.Ticker(ticker)
        raw_news = stock.news[:limit]
        processed = []

        for item in raw_news:
            title = "Market Update"
            link = "#"

            # Case 1: dict
            if isinstance(item, dict):
                title = (item.get('title') or item.get('content') or item.get('headline') or "Market Update")
                link = (item.get('link') or item.get('url') or item.get('canonicalUrl') or "#")

            # Case 2: string (the messy case you're seeing)
            elif isinstance(item, str):
                # Try regex for title
                match = re.search(r"'title':\s*'([^']+)'", item)
                if match:
                    title = match.group(1)
                else:
                    # Try to find any sentence-like text
                    match = re.search(r'([A-Z][^.!?]{30,250}[.!?])', item)
                    if match:
                        title = match.group(1)
                    else:
                        title = item[:180]  # take first chunk

            # Final cleaning
            title = re.sub(r'\{.*?\}', '', str(title))  # remove JSON fragments
            title = re.sub(r'\[.*?\]', '', title)
            title = re.sub(r'provider.*?:', '', title, flags=re.I)
            title = title.strip()[:220]

            if len(title) < 15:
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

    except Exception as e:
        st.error(f"yfinance error: {str(e)[:100]}")

    # Ultimate fallback
    result = [{"title": "No recent news available", "link": "#", "publisher": "System", "sentiment": "⚪ Neutral",
               "score": 0.0}]
    news_cache[cache_key] = (now, result)
    return result