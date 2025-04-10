from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi
import json
import os
from datetime import datetime

app = Flask(__name__)

# Load user credentials from users.json
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

# Log trade to logs/<user_id>.json
def log_trade(user_id, log_data):
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/{user_id}.json"

    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            logs = json.load(f)

    logs.insert(0, log_data)  # newest on top
    logs = logs[:20]  # keep only last 20

    with open(log_file, "w") as f:
        json.dump(logs, f, indent=2)

@app.route("/")
def home():
    return "🚀 Trading Platform API is running."

@app.route("/webhook/<user_id>", methods=["POST"])
def webhook(user_id):
    users = load_users()
    
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404
    
    user = users[user_id]
    data = request.get_json()

    print(f"📩 [{user_id}] Webhook received:", data)

    symbol = data.get("symbol")
    action = data.get("action")
    quantity = int(data.get("quantity", 1))

    if not symbol or not action:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    try:
        # Initialize Alpaca API
        api = tradeapi.REST(
            key_id=user["api_key"],
            secret_key=user["secret_key"],
            base_url="https://paper-api.alpaca.markets"
        )

        order = api.submit_order(
            symbol=symbol,
            qty=quantity,
            side=action.lower(),
            type="market",
            time_in_force="gtc"
        )

        print(f"✅ [{user_id}] Order placed: {symbol} {action.upper()} x{quantity}")

        log_trade(user_id, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action.capitalize(),
            "quantity": quantity,
            "status": "✅"
        })

        return jsonify({"status": "success", "order_id": order.id}), 200

    except Exception as e:
        print(f"❌ [{user_id}] Order failed:", str(e))
        log_trade(user_id, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action.capitalize(),
            "quantity": quantity,
            "status": "❌"
        })
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/logs/<user_id>", methods=["GET"])
def get_logs(user_id):
    log_file = f"logs/{user_id}.json"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return jsonify(json.load(f))
    return jsonify([])

import requests

@app.route("/suggested/<user_id>", methods=["GET"])
def suggested_symbols(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    # TwelveData API key (you can hardcode or store in .env if needed)
    TD_API_KEY = "732be95d470647be80419085887d2606"
    watchlist = ["AAPL", "TSLA", "MSFT", "AMZN", "GOOG"]
    suggestions = []

    for symbol in watchlist:
        try:
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=2&apikey={TD_API_KEY}"
            response = requests.get(url)
            data = response.json()

            if "values" not in data or len(data["values"]) < 2:
                print(f"⚠️ Not enough data for {symbol}")
                continue

            today = float(data["values"][0]["close"])
            yesterday = float(data["values"][1]["close"])
            change = round(((today - yesterday) / yesterday) * 100, 2)
            suggestion = "Buy" if change < -2 else "Sell" if change > 2 else "Hold"

            suggestions.append({
                "symbol": symbol,
                "current_price": today,
                "change_percent": change,
                "suggestion": suggestion
            })

        except Exception as e:
            print(f"❌ Error fetching data for {symbol}: {e}")
            continue

    return jsonify(suggestions), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
