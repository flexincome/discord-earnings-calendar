import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import os

FINNHUB_TOKEN = "paste_your_new_finnhub_key_here"  # ← PUT YOUR CURRENT KEY HERE (in quotes)

def get_finnhub_earnings():
    today = datetime.now().date()
    to_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={to_date}&token={FINNHUB_TOKEN}"
    print(f"Calling Finnhub...")
    response = requests.get(url)
    data = response.json()
   if "earningsCalendar" in data and data["earningsCalendar"]:
    df = pd.DataFrame(data["earningsCalendar"])
    if "hour" in df.columns:
        df = df[df["hour"].isin(["bmo", "amc"])]
    else:
        print("Warning: No 'hour' column found, using all events")
else:
    df = pd.DataFrame()
    print("No earningsCalendar data returned")
    print(f"Finnhub returned {len(df)} confirmed earnings")
    return df[["symbol", "date", "hour", "epsEstimate", "revenueEstimate"]]

def calculate_implied_move(symbol, earnings_date):
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice")
        if not price: return None
        exps = ticker.options
        target_exp = next((exp for exp in exps if datetime.strptime(exp, "%Y-%m-%d").date() >= datetime.strptime(earnings_date, "%Y-%m-%d").date()), None)
        if not target_exp: return None
        opts = ticker.option_chain(target_exp)
        calls = opts.calls
        puts = opts.puts
        atm_strike = round(price / 5) * 5
        call_row = calls[calls["strike"].between(atm_strike-2.5, atm_strike+2.5)]
        put_row = puts[puts["strike"].between(atm_strike-2.5, atm_strike+2.5)]
        if call_row.empty or put_row.empty: return None
        straddle = call_row["lastPrice"].iloc[0] + put_row["lastPrice"].iloc[0]
        implied_pct = round((straddle / price) * 100, 1)
        return {"implied_pct": implied_pct, "price": round(price, 2)}
    except:
        return None

print("Fetching earnings...")
df = get_finnhub_earnings()

results = []
for _, row in df.iterrows():   # no more strict filter — shows all BMO/AMC
    move = calculate_implied_move(row["symbol"], row["date"])
    try:
        company = yf.Ticker(row["symbol"]).info.get("longName", row["symbol"])
    except:
        company = row["symbol"]
    time_of_day = "BMO" if row["hour"] == "bmo" else "AMC"
    results.append({
        "symbol": row["symbol"],
        "company": company,
        "date": row["date"],
        "time": time_of_day,
        "eps_est": round(row["epsEstimate"], 2) if pd.notna(row["epsEstimate"]) else None,
        "rev_est": row["revenueEstimate"],
        "implied_pct": move["implied_pct"] if move else None,
        "price": move["price"] if move else None,
        "implied_dollar": round(move["price"] * (move["implied_pct"]/100), 2) if move else None
    })
    time.sleep(1.2)

with open("earnings.json", "w") as f:
    json.dump({"last_updated": datetime.now().isoformat(), "data": results}, f, indent=2)

print(f"✅ Saved {len(results)} earnings events")
