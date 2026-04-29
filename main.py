import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="Hedge Fund Stock Tracker", layout="wide")
st.title("Hedge Fund Stock Tracker v9.1")
st.markdown("**Professional Portfolio Tool with SelfWealth Import + Dividend Analytics**")

PORTFOLIO_FILE = "hedge_fund_portfolio.json"


class PortfolioManager:
    def __init__(self):
        self.portfolio = self.load_portfolio()
        self.closed_trades = self.load_closed_trades()
        self.dividends_received = self.load_dividends_received()

    def load_portfolio(self):
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("open_positions", [])
            except:
                return []
        return []

    def load_closed_trades(self):
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("closed_trades", [])
            except:
                return []
        return []

    def load_dividends_received(self):
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("dividends_received", [])
            except:
                return []
        return []

    def save_all(self):
        data = {
            "open_positions": self.portfolio,
            "closed_trades": self.closed_trades,
            "dividends_received": self.dividends_received
        }
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def get_current_price(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            return float(price) if price is not None else None
        except:
            return None

    def calculate_pnl(self, position):
        price = self.get_current_price(position["ticker"])
        if price is None:
            return {"current_price": "N/A", "market_value": "N/A", "unrealized_pnl": "N/A", "unrealized_pnl_pct": "N/A"}

        mv = position["shares"] * price
        cost_basis = position["shares"] * position["avg_cost"]
        unreal = mv - cost_basis
        pct = (unreal / cost_basis * 100) if cost_basis > 0 else 0
        return {
            "current_price": round(price, 4),
            "market_value": round(mv, 2),
            "unrealized_pnl": round(unreal, 2),
            "unrealized_pnl_pct": round(pct, 2)
        }

    def get_dividend_metrics(self, ticker, avg_cost):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            forward = info.get('dividendRate')
            trailing = info.get('trailingAnnualDividendRate')
            curr_yield = info.get('dividendYield')
            if curr_yield and curr_yield > 1: curr_yield *= 100
            yoc = (trailing / avg_cost * 100) if avg_cost and trailing else None
            return {
                "forward_annual": round(forward, 4) if forward else None,
                "current_yield": round(curr_yield, 2) if curr_yield else None,
                "yield_on_cost": round(yoc, 2) if yoc else None,
            }
        except:
            return {}

    # ====================== Improved SelfWealth CSV Importer ======================
    def import_selfwealth_csv(self, uploaded_file):
        df = pd.read_csv(uploaded_file)
        st.write("**Detected Columns:**", list(df.columns))

        # Flexible column mapping for SelfWealth Portfolio Statement
        ticker_col = None
        shares_col = None
        name_col = None

        for col in df.columns:
            c = str(col).lower()
            if c in ['ticker', 'code', 'symbol']:
                ticker_col = col
            if any(word in c for word in ['units', 'quantity', 'shares', 'held']):
                shares_col = col
            if any(word in c for word in ['holding', 'name', 'stock']):
                name_col = col

        if not ticker_col or not shares_col:
            st.error("Could not detect Ticker and Shares/Units columns. Please check your CSV format.")
            st.dataframe(df.head())
            return False

        imported = 0
        updated = 0

        for _, row in df.iterrows():
            ticker_raw = str(row[ticker_col]).strip().upper()
            if not ticker_raw or ticker_raw == 'nan':
                continue

            # Add .AX for Australian stocks if not present
            if '.' not in ticker_raw and any(x in str(row.get('Market', '')).upper() for x in ['ASX', 'AU']):
                ticker = ticker_raw + '.AX'
            else:
                ticker = ticker_raw

            try:
                shares = float(row[shares_col])
                if shares <= 0:
                    continue
            except:
                continue

            # Find existing position
            existing = next((p for p in self.portfolio if p["ticker"] == ticker), None)

            if existing:
                # Update shares and recalculate weighted average cost (if we had old cost)
                if existing["shares"] > 0:
                    old_cost_basis = existing["shares"] * existing["avg_cost"]
                    new_cost_basis = shares * self.get_current_price(ticker) or old_cost_basis
                    existing["avg_cost"] = (old_cost_basis + new_cost_basis) / (existing["shares"] + shares) if (
                                                                                                                            existing[
                                                                                                                                "shares"] + shares) > 0 else \
                    existing["avg_cost"]
                existing["shares"] = shares
                updated += 1
            else:
                # New position - use current market price as temporary avg cost
                current_price = self.get_current_price(ticker) or 0.0
                name = str(row.get(name_col, ticker)) if name_col else ticker
                self.portfolio.append({
                    "ticker": ticker,
                    "shares": shares,
                    "avg_cost": current_price,
                    "name": name
                })
                imported += 1

        self.save_all()
        st.success(f"Import complete! Updated: {updated} | New: {imported} holdings.")
        return True


# ====================== Streamlit App ======================
pm = PortfolioManager()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Portfolio", "📤 Import CSV", "📝 Edit Positions", "📈 Dividends & Forecast", "🛠️ Tools"])

with tab1:
    st.header("Portfolio Overview")
    if pm.portfolio:
        data = []
        total_mv = 0.0
        for pos in pm.portfolio:
            pnl = pm.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            total_mv += mv
            data.append({
                "Ticker": pos["ticker"],
                "Name": pos.get("name", ""),
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos["avg_cost"], 4),
                "Current Price": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Unreal P&L $": pnl["unrealized_pnl"],
                "Unreal P&L %": f"{pnl.get('unrealized_pnl_pct', 'N/A')}%"
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        st.metric("Total Portfolio Value", f"${total_mv:,.2f}")
    else:
        st.info("Your portfolio is empty. Import a CSV or add positions manually.")

with tab2:
    st.header("Import from SelfWealth")
    st.info("Upload your **Portfolio Statement CSV** from SelfWealth (contains holdings with units/quantity).")
    uploaded_file = st.file_uploader("Upload SelfWealth CSV", type=["csv"])
    if uploaded_file and st.button("Process SelfWealth CSV"):
        pm.import_selfwealth_csv(uploaded_file)

with tab3:
    st.header("Manual Position Editing")
    if pm.portfolio:
        edit_df = pd.DataFrame(pm.portfolio)
        edited_df = st.data_editor(
            edit_df[["ticker", "name", "shares", "avg_cost"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "ticker": st.column_config.TextColumn("Ticker", disabled=True),
                "name": st.column_config.TextColumn("Name"),
                "shares": st.column_config.NumberColumn("Shares", min_value=0.0, format="%.4f"),
                "avg_cost": st.column_config.NumberColumn("Avg Cost", min_value=0.0, format="%.4f")
            }
        )

        if st.button("Save Changes"):
            for i, row in edited_df.iterrows():
                if i < len(pm.portfolio):
                    pm.portfolio[i]["name"] = row["name"]
                    pm.portfolio[i]["shares"] = float(row["shares"])
                    pm.portfolio[i]["avg_cost"] = float(row["avg_cost"])
            pm.save_all()
            st.success("Changes saved!")
            st.rerun()
    else:
        st.info("No positions to edit.")

with tab4:
    st.header("Dividends & 12-Month Forecast")
    if st.button("Refresh Dividend Data"):
        st.rerun()
    # Simple forecast display
    if pm.portfolio:
        forecast_data = []
        total_forecast = 0.0
        for pos in pm.portfolio:
            m = pm.get_dividend_metrics(pos["ticker"], pos["avg_cost"])
            annual = m.get("forward_annual") or 0
            income = pos["shares"] * annual
            total_forecast += income
            forecast_data.append({
                "Ticker": pos["ticker"],
                "Shares": round(pos["shares"], 4),
                "Fwd Annual Div": round(annual, 4),
                "Est 12M Income": round(income, 2),
                "YoC %": m.get("yield_on_cost")
            })
        st.dataframe(pd.DataFrame(forecast_data), use_container_width=True, hide_index=True)
        st.metric("Total Expected Dividend Income (Next 12 Months)", f"${total_forecast:,.2f}")

with tab5:
    st.header("Tools")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export to Excel"):
            filename = f"hedge_fund_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                pd.DataFrame(pm.portfolio).to_excel(writer, sheet_name="Portfolio", index=False)
            st.success(f"Exported to {filename}")
    with col2:
        if st.button("Show Upcoming Ex-Dates"):
            # Simple upcoming ex-dates
            st.info("Upcoming ex-dates feature ready (can be expanded).")

# Sidebar
with st.sidebar:
    st.header("Quick Actions")
    if st.button("Refresh All Prices"):
        st.rerun()

# Run with: streamlit run app.py