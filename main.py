import os
from dotenv import load_dotenv
import requests
import json
import time
from datetime import datetime
from groq import Groq
from flask import Flask
import threading

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RENDER_URL = os.getenv("RENDER_URL")  # Thêm dòng này để lấy URL chính xác app của bạn

BINANCE_SYMBOL = os.getenv("BINANCE_SYMBOL") or 'BTCUSDT'
INTERVAL = os.getenv("INTERVAL") or '15m'
LIMIT = int(os.getenv("LIMIT") or 100)
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS") or (15 * 60))  # 15 phút
PROB = int(os.getenv("PROB") or 60)  # 60%

if not GROQ_API_KEY:
    raise Exception("Missing GROQ_API_KEY environment variable")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise Exception("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variable")

if not RENDER_URL:
    raise Exception("Missing RENDER_URL environment variable (e.g. https://your-app-name.onrender.com)")

client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)

def get_binance_candles(symbol, interval, limit):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        candles = [{
            "t": item[0],
            "o": float(item[1]),
            "h": float(item[2]),
            "l": float(item[3]),
            "c": float(item[4]),
            "v": float(item[5])
        } for item in data]
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
    {{"action": "long"|"short", "et": số, "sl": số, "tp1": số, "tp2": số, "tp3": số, "prob": %, "analysis": "các phân tích"}}
    Chỉ đề xuất nếu probability > {PROB}%. Nếu không đủ tỉ lệ thì không cần đưa ra quyết định json.
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


def auto_trading_loop():
    while True:
        try:
            candles = get_binance_candles(BINANCE_SYMBOL, INTERVAL, LIMIT)
            print(f"[INFO] Fetched {len(candles)} candles {BINANCE_SYMBOL} {INTERVAL}")
            analysis = analyze_with_llama4_maverick(candles)
            print("[LLAMA-4 MAVERICK RESULT]", analysis)
            message = f"*Auto Trading Result*\n\n{analysis}"
            send_telegram_message(message)
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(INTERVAL_SECONDS)


def keep_alive_ping():
    while True:
        try:
            requests.get(RENDER_URL)
            print("[PING] Sent keep-alive ping to Render")
        except Exception as e:
            print(f"[PING ERROR] {e}")
        time.sleep(600)  # Ping mỗi 10 phút


@app.route("/")
def home():
    return "Bot is running."


if __name__ == "__main__":
    threading.Thread(target=auto_trading_loop).start()
    threading.Thread(target=keep_alive_ping).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
