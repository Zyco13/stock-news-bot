import os
import time
from datetime import date, datetime, timedelta, timezone

import requests
from google import genai

# キーは環境変数から読む（コードには絶対に直接書かない）
FINNHUB_KEY = os.environ["FINNHUB_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")  # まだ無くても動く

WATCHLIST = ["XOM", "ADM", "AAPL", "MU", "SNDK", "CRWV", "AMZN"]
NEWS_PER_SYMBOL = 3
JST = timezone(timedelta(hours=9))

client = genai.Client(api_key=GEMINI_API_KEY)


def fetch_news(symbol):
    """Finnhubから直近7日のニュースを取得する"""
    today = date.today()
    params = {
        "symbol": symbol,
        "from": str(today - timedelta(days=7)),
        "to": str(today),
        "token": FINNHUB_KEY,
    }
    res = requests.get("https://finnhub.io/api/v1/company-news", params=params)
    return res.json()


def summarize(symbol, item):
    """関係あるニュースだけ日本語2行で要約する。関係なければ「関係なし」を返す"""
    prompt = f"""以下は{symbol}に関する英語のニュースです。
次のどちらかに当てはまる場合だけ、内容を日本語2行で要約してください。
・{symbol}の会社自身が主役のニュース
・{symbol}の株価に直接影響しそうなニュース（決算、アナリスト評価、業界や貿易の大きな動きなど）
どちらにも当てはまらない場合は「関係なし」とだけ答えてください。
要約以外の説明や前置きは書かないでください。

見出し: {item['headline']}
本文: {item['summary']}"""
    res = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
    return res.text


def send(text):
    """Discordに送る。Webhookが未設定なら画面に表示するだけ"""
    if not DISCORD_WEBHOOK_URL:
        print(text)
        return
    # Discordは1メッセージ2000文字までなので分けて送る
    for i in range(0, len(text), 1900):
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text[i:i + 1900]})
        time.sleep(1)


def main():
    for symbol in WATCHLIST:
        lines = []
        for item in fetch_news(symbol)[:NEWS_PER_SYMBOL]:
            result = summarize(symbol, item)
            time.sleep(5)  # 無料枠の回数制限よけ
            if "関係なし" in result:
                continue
            t = datetime.fromtimestamp(item["datetime"], JST).strftime("%m/%d %H:%M")
            lines.append(f"**{t} {item['headline']}**\n{result}\n<{item['url']}>")
        if lines:
            send(f"## {symbol}\n" + "\n\n".join(lines))


if __name__ == "__main__":
    main()
