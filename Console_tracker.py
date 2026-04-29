import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from tabulate import tabulate
from colorama import init, Fore, Style

init(autoreset=True)

PORTFOLIO_FILE = "hedge_fund_portfolio.json"


class StockTracker:
    def __init__(self):
        self.portfolio = self.load_portfolio()
        self.closed_trades = self.load_closed_trades()
        self.dividends_received = self.load_dividends_received()

    # ====================== LOAD & SAVE ======================
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
        print(f"{Fore.GREEN}Portfolio saved successfully.")

    # ====================== HELPERS ======================
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

        market_value = position["shares"] * price
        cost_basis = position["shares"] * position["avg_cost"]
        unrealized = market_value - cost_basis
        pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0

        return {
            "current_price": round(price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "unrealized_pnl_pct": round(pct, 2)
        }

    def get_dividend_metrics(self, ticker, avg_cost):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            forward = info.get('dividendRate')
            trailing = info.get('trailingAnnualDividendRate')
            curr_yield = info.get('dividendYield')
            if curr_yield and curr_yield > 1:
                curr_yield *= 100
            yoc = (trailing / avg_cost * 100) if avg_cost and trailing else None

            return {
                "forward_annual": round(forward, 4) if forward else None,
                "current_yield": round(curr_yield, 2) if curr_yield else None,
                "yield_on_cost": round(yoc, 2) if yoc else None,
            }
        except:
            return {}

    def remove_invalid_tickers(self):
        to_remove = [pos for pos in self.portfolio if self.get_current_price(pos["ticker"]) is None]
        for pos in to_remove:
            print(f"{Fore.RED}Removing invalid ticker: {pos['ticker']}")
            self.portfolio.remove(pos)
        if to_remove:
            self.save_all()
            print(f"{Fore.GREEN}Cleaned {len(to_remove)} invalid ticker(s).")

    # ====================== CORE FUNCTIONS ======================
    def add_position(self):
        print(f"\n{Fore.CYAN}=== Add / Increase Position ===")
        ticker = input("Enter Ticker (e.g. AAPL, BHP.AX): ").strip().upper()
        try:
            shares = float(input("Number of shares: "))
            avg_cost = float(input("Average cost per share: "))
        except ValueError:
            print(f"{Fore.RED}Invalid input.")
            return

        for pos in self.portfolio:
            if pos["ticker"] == ticker:
                total_cost = (pos["shares"] * pos["avg_cost"]) + (shares * avg_cost)
                pos["shares"] += shares
                pos["avg_cost"] = total_cost / pos["shares"]
                print(f"{Fore.GREEN}Position updated. New avg cost: ${pos['avg_cost']:.4f}")
                self.save_all()
                return

        name = yf.Ticker(ticker).info.get('shortName', ticker)
        self.portfolio.append({"ticker": ticker, "shares": shares, "avg_cost": avg_cost, "name": name})
        print(f"{Fore.GREEN}New position added: {ticker}")
        self.save_all()

    def sell_position(self):
        if not self.portfolio:
            print(f"{Fore.YELLOW}No open positions.")
            return

        print("\nCurrent Positions:")
        for i, pos in enumerate(self.portfolio, 1):
            print(f"{i}. {pos['ticker']} - {pos['shares']} shares @ ${pos['avg_cost']:.4f}")

        try:
            idx = int(input("\nSelect position to sell: ")) - 1
            pos = self.portfolio[idx]
            sell_shares = float(input(f"How many shares to sell? (max {pos['shares']}): "))
            if sell_shares <= 0 or sell_shares > pos['shares']:
                print(f"{Fore.RED}Invalid amount.")
                return
            sell_price = float(input("Sell price per share: "))
        except:
            print(f"{Fore.RED}Invalid input.")
            return

        cost_basis = sell_shares * pos["avg_cost"]
        proceeds = sell_shares * sell_price
        realized_pnl = proceeds - cost_basis

        self.closed_trades.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ticker": pos["ticker"],
            "shares_sold": round(sell_shares, 4),
            "sell_price": round(sell_price, 4),
            "realized_pnl": round(realized_pnl, 2)
        })

        if sell_shares >= pos["shares"]:
            self.portfolio.pop(idx)
            print(f"{Fore.GREEN}Fully closed {pos['ticker']}")
        else:
            pos["shares"] -= sell_shares

        color = Fore.GREEN if realized_pnl >= 0 else Fore.RED
        print(f"{color}Realized P&L: ${realized_pnl:,.2f}")
        self.save_all()

    def record_dividend(self):
        print(f"\n{Fore.CYAN}=== Record Dividend Received ===")
        ticker = input("Ticker: ").strip().upper()
        try:
            shares = float(input("Shares eligible: "))
            amount_per_share = float(input("Amount per share: "))
            date_str = input("Ex-div date (YYYY-MM-DD) or Enter for today: ").strip()
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
        except ValueError:
            print(f"{Fore.RED}Invalid input.")
            return

        total = round(shares * amount_per_share, 2)
        self.dividends_received.append({
            "date": date_str,
            "ticker": ticker,
            "shares": shares,
            "amount_per_share": round(amount_per_share, 4),
            "total_received": total
        })
        print(f"{Fore.GREEN}Recorded ${total:,.2f} for {ticker}")
        self.save_all()

    def delete_position(self):
        if not self.portfolio:
            print(f"{Fore.YELLOW}Portfolio is empty.")
            return

        print("\nCurrent Positions:")
        for i, pos in enumerate(self.portfolio, 1):
            print(f"{i}. {pos['ticker']} - {pos['shares']} shares")

        try:
            idx = int(input("\nEnter number to delete: ")) - 1
            pos = self.portfolio[idx]
            confirm = input(f"Delete {pos['ticker']} permanently? (y/n): ").lower()
            if confirm == 'y':
                self.portfolio.pop(idx)
                print(f"{Fore.GREEN}Deleted {pos['ticker']}")
                self.save_all()
            else:
                print("Deletion cancelled.")
        except:
            print(f"{Fore.RED}Invalid selection.")

    def show_upcoming_ex_dates(self, days_ahead=90):
        print(f"\n{Fore.CYAN}=== UPCOMING EX-DIVIDEND DATES (Next {days_ahead} Days) ===")
        today = datetime.now().date()
        upcoming = []
        alerts = []

        for pos in self.portfolio:
            try:
                stock = yf.Ticker(pos["ticker"])
                info = stock.info
                ex_ts = info.get('exDividendDate')
                if not ex_ts: continue
                ex_date = datetime.fromtimestamp(ex_ts).date()
                days_away = (ex_date - today).days

                if 0 <= days_away <= days_ahead:
                    amount = info.get('dividendRate') or info.get('trailingAnnualDividendRate')
                    est_amount = round((amount or 0) / 4, 4)

                    upcoming.append({
                        "Ticker": pos["ticker"],
                        "Ex-Date": ex_date.strftime("%Y-%m-%d"),
                        "Days Away": days_away,
                        "Est. Amount": est_amount,
                        "YoC %": self.get_dividend_metrics(pos["ticker"], pos["avg_cost"]).get("yield_on_cost")
                    })

                    if days_away <= 7:
                        alerts.append(f"{Fore.RED}URGENT: {pos['ticker']} ex-div in {days_away} days")
                    elif days_away <= 30:
                        alerts.append(f"{Fore.YELLOW}ALERT: {pos['ticker']} ex-div in {days_away} days")
            except:
                continue

        if upcoming:
            df = pd.DataFrame(upcoming).sort_values("Days Away")
            print(tabulate(df, headers='keys', tablefmt='pretty', showindex=False))
        else:
            print(f"{Fore.YELLOW}No upcoming ex-dates found.")

        if alerts:
            print(f"\n{Fore.MAGENTA}=== DIVIDEND ALERTS ===")
            for alert in alerts:
                print(alert)

    def refresh_all_data(self):
        print(f"{Fore.CYAN}Refreshing all prices and dividend data...")
        for pos in self.portfolio:
            try:
                self.get_current_price(pos["ticker"])
            except:
                pass
        print(f"{Fore.GREEN}Refresh completed!")
        self.show_portfolio()

    def show_portfolio(self):
        if not self.portfolio:
            print(f"{Fore.YELLOW}Portfolio is empty.")
            return

        print(f"\n{Fore.MAGENTA}=== PORTFOLIO SUMMARY === {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        data = []
        total_mv = 0.0
        total_unreal = 0.0

        for pos in self.portfolio:
            pnl = self.calculate_pnl(pos)
            mv = pnl["market_value"] if isinstance(pnl["market_value"], (int, float)) else 0
            unreal = pnl["unrealized_pnl"] if isinstance(pnl["unrealized_pnl"], (int, float)) else 0
            total_mv += mv
            total_unreal += unreal

            data.append({
                "Ticker": pos["ticker"],
                "Shares": round(pos["shares"], 4),
                "Avg Cost": round(pos["avg_cost"], 4),
                "Current": pnl["current_price"],
                "Market Value": pnl["market_value"],
                "Unreal P&L $": pnl["unrealized_pnl"],
                "Unreal P&L %": f"{pnl.get('unrealized_pnl_pct', 'N/A')}%"
            })

        print(tabulate(pd.DataFrame(data), headers='keys', tablefmt='pretty', showindex=False))
        print(f"\nTotal Market Value : ${total_mv:,.2f}")
        print(f"Total Unrealized P&L: ${total_unreal:,.2f}")

    def show_dividend_forecast(self):
        print(f"\n{Fore.CYAN}=== 12-MONTH DIVIDEND FORECAST ===")
        total = 0.0
        data = []
        for pos in self.portfolio:
            m = self.get_dividend_metrics(pos["ticker"], pos["avg_cost"])
            annual = m.get("forward_annual") or 0
            income = pos["shares"] * annual
            total += income
            data.append({
                "Ticker": pos["ticker"],
                "Shares": round(pos["shares"], 4),
                "Fwd Annual Div": round(annual, 4),
                "Est 12M Income": round(income, 2),
                "YoC %": m.get("yield_on_cost")
            })
        print(tabulate(pd.DataFrame(data), headers='keys', tablefmt='pretty', showindex=False))
        print(f"\n{Fore.GREEN}Total Expected Dividend Income (Next 12 Months): ${total:,.2f}")

    # ====================== MENU ======================
    def menu(self):
        self.remove_invalid_tickers()

        while True:
            print(f"\n{Fore.MAGENTA}=== Hedge Fund Stock Tracker - Console Version ===")
            print("1.  Show Portfolio")
            print("2.  Add / Increase Position")
            print("3.  Sell Position")
            print("4.  Record Dividend Received")
            print("5.  Dividends Dashboard & Forecast")
            print("6.  Upcoming Ex-Dividend Dates + Alerts")
            print("7.  Delete Position")
            print("8.  Refresh All Data")
            print("9.  Exit")

            choice = input("\nSelect option (1-9): ").strip()

            if choice == '1':
                self.show_portfolio()
            elif choice == '2':
                self.add_position()
            elif choice == '3':
                self.sell_position()
            elif choice == '4':
                self.record_dividend()
            elif choice == '5':
                self.show_portfolio()
                self.show_dividend_forecast()
            elif choice == '6':
                self.show_upcoming_ex_dates()
            elif choice == '7':
                self.delete_position()
            elif choice == '8':
                self.refresh_all_data()
            elif choice == '9':
                print(f"{Fore.GREEN}Goodbye! Data saved.")
                break
            else:
                print(f"{Fore.RED}Invalid option.")


if __name__ == "__main__":
    print(f"{Fore.YELLOW}Hedge Fund Stock Tracker - Console Version")
    print("Supports ASX, NYSE, and major global markets.\n")
    tracker = StockTracker()
    tracker.menu()