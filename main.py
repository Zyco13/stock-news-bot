import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from google import genai

FINNHUB_KEY = os.environ["FINNHUB_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Aktierna du vill bevaka (USA-tickers)
WATCHLIST = ["AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "META", "TSLA", "AMD", "PLTR", "AVGO"]
NEWS_PER_SYMBOL = 2
TZ = ZoneInfo("Europe/Stockholm")
SKIP = "IRRELEVANT"

client = genai.Client(api_key=GEMINI_API_KEY)


def fetch_news(symbol):
    """Hämtar gårdagens och dagens nyheter från Finnhub"""
    today = date.today()
    params = {
        "symbol": symbol,
        "from": str(today - timedelta(days=1)),
        "to": str(today),
        "token": FINNHUB_KEY,
    }
    res = requests.get("https://finnhub.io/api/v1/company-news", params=params, timeout=30)
    return res.json() if res.ok else []


def summarize(symbol, item):
    """Sammanfattar på svenska om nyheten är relevant, annars SKIP"""
    prompt = f"""Här är en engelsk nyhet om {symbol}.
Sammanfatta den på svenska i max 2 korta meningar, men BARA om något av detta stämmer:
- Nyheten handlar främst om bolaget {symbol}
- Nyheten kan påverka {symbol}s aktiekurs direkt (rapport, analytikerbetyg, stora bransch- eller handelshändelser)
Om inget stämmer, svara exakt: {SKIP}
Skriv ingen inledning eller förklaring, bara sammanfattningen.

Rubrik: {item['headline']}
Text: {item['summary']}"""
    for attempt in range(3):
        try:
            res = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
            return (res.text or SKIP).strip()
        except Exception as e:
            print(f"{symbol}: sammanfattning misslyckades (försök {attempt + 1}): {e}")
            time.sleep(30)
    return "(Kunde inte sammanfatta just nu)"


def send(text):
    """Skickar till Discord, eller skriver ut om webhook saknas"""
    if not DISCORD_WEBHOOK_URL:
        print(text)
        return
    for i in range(0, len(text), 1900):
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text[i:i + 1900]}, timeout=30)
        time.sleep(1)


def main():
    for symbol in WATCHLIST:
        lines = []
        for item in fetch_news(symbol)[:NEWS_PER_SYMBOL]:
            result = summarize(symbol, item)
            time.sleep(5)  # håller oss inom gratisgränsen
            if SKIP in result:
                continue
            t = datetime.fromtimestamp(item["datetime"], TZ).strftime("%d/%m %H:%M")
            lines.append(f"**{t} {item['headline']}**\n{result}\n<{item['url']}>")
        if lines:
            send(f"## {symbol}\n" + "\n\n".join(lines))


if __name__ == "__main__":
    main()
