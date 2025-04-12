from flask import Flask, request, jsonify
from flask_cors import CORS
import alpaca_trade_api as tradeapi
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def log_trade(user_id, log_data):
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/{user_id}.json"
    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            logs = json.load(f)
    logs.insert(0, log_data)
    logs = logs[:20]
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
        api = tradeapi.REST(user["api_key"], user["secret_key"], base_url="https://paper-api.alpaca.markets")

        if action.lower() == "sell":
            try:
                position = api.get_position(symbol)
                held_qty = int(float(position.qty_available))
            except:
                held_qty = 0
            if held_qty < quantity:
                return jsonify({"status": "error", "message": f"Not enough qty to sell: {held_qty}"}), 400

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

@app.route("/logs/<user_id>")
def get_logs(user_id):
    log_file = f"logs/{user_id}.json"
    return jsonify(json.load(open(log_file))) if os.path.exists(log_file) else jsonify([])

@app.route("/portfolio/<user_id>")
def get_portfolio(user_id):
    users = load_users()
    if user_id not in users: return jsonify({"status": "error", "message": "Invalid user"}), 404
    user = users[user_id]
    try:
        api = tradeapi.REST(user["api_key"], user["secret_key"], base_url="https://paper-api.alpaca.markets")
        account = api.get_account()
        positions = api.list_positions()
        cash = float(account.cash)
        equity = float(account.equity)
        market_value = sum(float(p.market_value) for p in positions)
        pnl = equity - cash
        return jsonify({
            "cash": round(cash, 2),
            "equity": round(equity, 2),
            "market_value": round(market_value, 2),
            "pnl": round(pnl, 2),
            "status": "success"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/strategy/<user_id>", methods=["GET", "POST"])
def strategy_handler(user_id):
    users = load_users()
    if user_id not in users: return jsonify({"status": "error", "message": "Invalid user"}), 404
    if request.method == "GET":
        return jsonify({"strategy": users[user_id].get("strategy", "balanced")})
    data = request.get_json()
    users[user_id]["strategy"] = data.get("strategy", "balanced")
    with open("users.json", "w") as f: json.dump(users, f, indent=2)
    return jsonify({"status": "success", "message": "Strategy updated"})

@app.route("/watchlist/<user_id>", methods=["GET", "POST"])
def watchlist_handler(user_id):
    users = load_users()
    if user_id not in users: return jsonify({"status": "error", "message": "Invalid user"}), 404
    if request.method == "GET":
        return jsonify({"watchlist": users[user_id].get("watchlist", ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"])})
    data = request.get_json()
    users[user_id]["watchlist"] = data.get("watchlist", [])
    with open("users.json", "w") as f: json.dump(users, f, indent=2)
    return jsonify({"status": "success", "message": "Watchlist updated"})

@app.route("/suggested/<user_id>")
def suggested_symbols(user_id):
    users = load_users()
    if user_id not in users: return jsonify({"status": "error", "message": "Invalid user"}), 404
    user = users[user_id]
    strategy = user.get("strategy", "balanced")
    symbols = user.get("watchlist", ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"])
    TD_API_KEY = "732be95d470647be80419085887d2606"

    suggestions = []
    for symbol in symbols:
        try:
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=2&apikey={TD_API_KEY}"
            res = requests.get(url)
            data = res.json()
            if "values" not in data or len(data["values"]) < 2:
                continue
            today = float(data["values"][0]["close"])
            yesterday = float(data["values"][1]["close"])
            change = round(((today - yesterday) / yesterday) * 100, 2)

            suggestion = "Hold"
            if strategy == "balanced":
                if change < -1.5: suggestion = "Buy"
                elif change > 1.5: suggestion = "Sell"
            elif strategy == "momentum":
                suggestion = "Buy" if change > 0 else "Sell"
            elif strategy == "reversal":
                if change < -2: suggestion = "Buy"
                elif change > 2: suggestion = "Sell"
            elif strategy == "volume_spike":
                suggestion = "Hold"

            suggestions.append({
                "symbol": symbol,
                "current_price": today,
                "change_percent": change,
                "suggestion": suggestion
            })
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
            continue

    top5 = sorted(suggestions, key=lambda x: abs(x["change_percent"]), reverse=True)[:5]
    return jsonify(top5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
