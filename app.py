from flask import Flask, request, jsonify
from flask_cors import CORS
import alpaca_trade_api as tradeapi
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Load user credentials
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

# Save updated user data
def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=2)

# Log trade history
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
        api = tradeapi.REST(
            key_id=user["api_key"],
            secret_key=user["secret_key"],
            base_url="https://paper-api.alpaca.markets"
        )

        if action.lower() == "sell":
            try:
                position = api.get_position(symbol)
                held_qty = int(float(position.qty_available))
            except:
                held_qty = 0
            if held_qty < quantity:
                msg = f"❌ Not enough quantity to sell: You have {held_qty}, trying to sell {quantity}."
                print(f"[{user_id}] {msg}")
                return jsonify({"status": "error", "message": msg}), 400

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

@app.route("/portfolio/<user_id>", methods=["GET"])
def get_portfolio(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    user = users[user_id]
    try:
        api = tradeapi.REST(
            key_id=user["api_key"],
            secret_key=user["secret_key"],
            base_url="https://paper-api.alpaca.markets"
        )

        account = api.get_account()
        positions = api.list_positions()

        cash = float(account.cash)
        equity = float(account.equity)
        market_value = sum([float(p.market_value) for p in positions])
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
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    if request.method == "GET":
        return jsonify({"strategy": users[user_id].get("strategy", "balanced")})

    if request.method == "POST":
        data = request.get_json()
        new_strategy = data.get("strategy", "balanced")
        users[user_id]["strategy"] = new_strategy
        save_users(users)
        return jsonify({"status": "success", "message": f"Strategy updated to {new_strategy}"})

@app.route("/watchlist/<user_id>", methods=["GET", "POST"])
def watchlist_handler(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    user = users[user_id]
    user.setdefault("watchlist", [])

    if request.method == "GET":
        return jsonify({"symbols": user["watchlist"]})

    data = request.get_json()
    action = data.get("action")
    symbol = data.get("symbol", "").upper()

    if action == "add" and symbol not in user["watchlist"]:
        user["watchlist"].append(symbol)
    elif action == "remove" and symbol in user["watchlist"]:
        user["watchlist"].remove(symbol)

    save_users(users)
    return jsonify({"symbols": user["watchlist"]})

@app.route("/suggested/<user_id>", methods=["GET"])
def suggested_symbols(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    TD_API_KEY = "732be95d470647be80419085887d2606"
    user = users[user_id]
    strategy = user.get("strategy", "balanced")
    symbols = user.get("watchlist", []) or ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]

    suggestions = []
    for symbol in symbols[:50]:
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
                if change < -1.5:
                    suggestion = "Buy"
                elif change > 1.5:
                    suggestion = "Sell"
            elif strategy == "momentum":
                suggestion = "Buy" if change > 0 else "Sell"
            elif strategy == "reversal":
                if change < -2:
                    suggestion = "Buy"
                elif change > 2:
                    suggestion = "Sell"
            elif strategy == "volume_spike":
                suggestion = "Hold"  # Future volume API

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
    return jsonify(top5), 200

@app.route("/pnl/<user_id>", methods=["GET"])
def get_pnl_chart(user_id):
    log_file = f"logs/{user_id}.json"
    if not os.path.exists(log_file):
        return jsonify({"labels": [], "data": []})

    with open(log_file, "r") as f:
        logs = json.load(f)

    pnl_by_day = {}
    for log in logs:
        date = log["timestamp"].split()[0]
        pnl_by_day[date] = pnl_by_day.get(date, 0) + (1 if log["action"].lower() == "buy" else -1)

    labels = sorted(pnl_by_day.keys())
    data = [pnl_by_day[day] for day in labels]
    return jsonify({"labels": labels, "data": data})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
