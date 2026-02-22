import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import os

FINNHUB_TOKEN = os.getenv("FINNHUB_TOKEN")  # put your key in GitHub Secrets

def get_finnhub_earnings():
    today = datetime.now().date()
    to_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")  # next 2 weeks
    url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={to_date}&token={FINNHUB_TOKEN}"
    data = requests.get(url).json()
    df = pd.DataFrame(data["earningsCalendar"])
    df = df[df["hour"].isin(["bmo", "amc"])]  # only confirmed times
    return df[["symbol", "date", "hour", "epsEstimate", "revenueEstimate"]]

def calculate_implied_move(symbol, earnings_date):
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice")
        if not price:
            return None
        
        # Get options expirations after earnings date
        exps = ticker.options
        target_exp = next((exp for exp in exps if datetime.strptime(exp, "%Y-%m-%d").date() >= datetime.strptime(earnings_date, "%Y-%m-%d").date()), None)
        if not target_exp:
            return None
            
        opts = ticker.option_chain(target_exp)
        calls = opts.calls
        puts = opts.puts
        
        # ATM strike
        atm_strike = round(price / 5) * 5
        call = calls[calls["strike"].between(atm_strike-2.5, atm_strike+2.5)]["lastPrice"].iloc[0]
        put = puts[puts["strike"].between(atm_strike-2.5, atm_strike+2.5)]["lastPrice"].iloc[0]
        
        straddle = call + put
        implied_pct = round((straddle / price) * 100, 1)
        return {"implied_pct": implied_pct, "price": round(price, 2)}
    except:
        return None

# Main
print("Fetching earnings...")
df = get_finnhub_earnings()

results = []
for _, row in df.iterrows():
    print(f"Processing {row['symbol']}...")
    move = calculate_implied_move(row["symbol"], row["date"])
    
    # Get company name
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
    time.sleep(0.3)  # be nice to Yahoo

# Save
with open("earnings.json", "w") as f:
    json.dump({"last_updated": datetime.now().isoformat(), "data": results}, f, indent=2)

print(f"✅ Saved {len(results)} earnings events")
