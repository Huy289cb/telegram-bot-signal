import os
from dotenv import load_dotenv
import requests
import json
import time
from datetime import datetime
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not GROQ_API_KEY:
    raise Exception("Missing GROQ_API_KEY environment variable")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise Exception("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variable")

client = Groq(api_key=GROQ_API_KEY)

BINANCE_SYMBOL = 'BTCUSDT'
INTERVAL = '15m'
LIMIT = 100
INTERVAL_SECONDS = 15 * 60  # 15 phút


def get_binance_candles(symbol, interval, limit):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        candles = []
        for item in data:
            candles.append({
                "t": item[0],
                "o": float(item[1]),
                "h": float(item[2]),
                "l": float(item[3]),
                "c": float(item[4]),
                "v": float(item[5])
            })
        return candles
    else:
        raise Exception(f"Binance API error: {resp.text}")


def analyze_with_llama4_maverick(candles):
    candle_json = json.dumps(candles)
    prompt = f"""
    Bạn là chuyên gia trading chuyên phân tích BTCUSDT có 20 năm kinh nghiệm.
    Dưới đây là dữ liệu {LIMIT} cây nến gần nhất trên khung {INTERVAL}:
    {candle_json}

    Hãy trả lời dưới dạng JSON gồm:
    {{"action": "long"|"short", "et": số, "sl": số, "tp1": số, "tp2": số, "tp3": số, "prob": %}}
    Chỉ đề xuất nếu probability > 60%. Nếu không đủ tỉ lệ thì không cần đưa ra quyết định json.
    """

    response = client.chat.completions.create(
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    result = response.choices[0].message.content
    return result


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    resp = requests.post(url, data=payload)
    if resp.status_code != 200:
        print(f"[ERROR] Telegram send failed: {resp.text}")


def auto_trading_decision():
    candles = get_binance_candles(BINANCE_SYMBOL, INTERVAL, LIMIT)
    print(f"[INFO] Fetched {len(candles)} candles {BINANCE_SYMBOL} {INTERVAL}")

    analysis = analyze_with_llama4_maverick(candles)
    print("[LLAMA-4 MAVERICK RESULT]", analysis)

    message = f"*Auto Trading Result*\n\n{analysis}"
    send_telegram_message(message)


if __name__ == "__main__":
    while True:
        try:
            auto_trading_decision()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(INTERVAL_SECONDS)
