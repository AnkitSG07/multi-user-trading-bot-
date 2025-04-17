from flask import Flask, request, jsonify
from flask_cors import CORS
import alpaca_trade_api as tradeapi
import json
import os
import requests
import hashlib
from datetime import datetime
from cryptography.fernet import Fernet
import openai

fernet = Fernet(os.environ["FERNET_KEY"])

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def load_users():
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=2)

def log_trade(user_id, log_data):
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/{user_id}.json"
    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            try:
                logs = json.load(f)
            except:
                logs = []
    logs.append(log_data)
    with open(log_file, "w") as f:
        json.dump(logs, f, indent=2)

@app.route("/safe-bot/<user_id>", methods=["POST"])
def safe_bot(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        api_key = fernet.decrypt(users[user_id]["api_key"].encode()).decode()
        secret_key = fernet.decrypt(users[user_id]["secret_key"].encode()).decode()
    except:
        return jsonify({"status": "error", "message": "Decryption failed"}), 500

    api = tradeapi.REST(api_key, secret_key, base_url="https://paper-api.alpaca.markets")
    strategy = users[user_id].get("strategy", "balanced")
    symbols = users[user_id].get("watchlist", []) or ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]

    TD_API_KEY = "732be95d470647be80419085887d2606"
    actions = []

    for symbol in symbols:
        try:
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=2&apikey={TD_API_KEY}"
            res = requests.get(url).json()
            if "values" not in res or len(res["values"]) < 2:
                continue

            today = float(res["values"][0]["close"])
            yesterday = float(res["values"][1]["close"])
            change = round(((today - yesterday) / yesterday) * 100, 2)

            # ✅ Safe Buy
            if change < -2:
                api.submit_order(symbol=symbol, qty=1, side="buy", type="market", time_in_force="gtc")
                log_trade(user_id, {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": symbol,
                    "action": "Buy",
                    "quantity": 1,
                    "status": "✅",
                    "price": today
                })
                actions.append(f"✅ Bought 1 {symbol} at ${today}")

            # ✅ Safe Sell
            elif change > 2:
                try:
                    position = api.get_position(symbol)
                    qty = int(float(position.qty_available))
                    if qty > 0:
                        api.submit_order(symbol=symbol, qty=1, side="sell", type="market", time_in_force="gtc")
                        log_trade(user_id, {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "symbol": symbol,
                            "action": "Sell",
                            "quantity": 1,
                            "status": "✅",
                            "price": today
                        })
                        actions.append(f"✅ Sold 1 {symbol} at ${today}")
                except:
                    pass  # No position to sell

        except Exception as e:
            actions.append(f"❌ {symbol}: {str(e)}")

    return jsonify({"status": "done", "actions": actions})


@app.route("/")
def home():
    return '<script>window.location.href="/login.html";</script>'

@app.route("/recommend-ai", methods=["POST"])
def recommend_ai():
    data = request.get_json()
    user_id = data.get("user_id", "")

    prompt = f"Give a 1-line smart trading suggestion for user '{user_id}' based on current market trends. Be precise and clear."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{ "role": "user", "content": prompt }],
            max_tokens=60
        )
        suggestion = response.choices[0].message['content'].strip()
        return jsonify({ "suggestion": suggestion })
    except Exception as e:
        return jsonify({ "error": str(e) }), 500

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    user_id = data.get("user_id", "").strip()
    password = data.get("password", "").strip()

    if not user_id or not password:
        return jsonify({"status": "error", "message": "User ID and password are required"}), 400

    users = load_users()
    if user_id in users:
        return jsonify({"status": "error", "message": "User ID already exists"}), 409

    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    users[user_id] = {
        "password": hashed_pw,
        "api_key": "",
        "secret_key": "",
        "strategy": "balanced",
        "watchlist": []
    }
    save_users(users)
    return jsonify({"status": "success", "message": "Signup successful"}), 200

@app.route("/login", methods=["POST"])
def login_user():
    data = request.get_json()
    user_id = data.get("user_id", "").strip()
    password = data.get("password", "").strip()

    if not user_id or not password:
        return jsonify({"status": "error", "message": "User ID and Password are required."}), 400

    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "User not found."}), 404

    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    if users[user_id].get("password") != hashed_pw:
        return jsonify({"status": "error", "message": "Incorrect password."}), 401

    return jsonify({"status": "success", "message": "Login successful."}), 200

@app.route("/connect-alpaca", methods=["POST"])
def connect_alpaca():
    data = request.get_json()
    user_id = data.get("user_id", "").strip()
    api_key = data.get("api_key", "").strip()
    secret_key = data.get("secret_key", "").strip()

    if not user_id or not api_key or not secret_key:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    try:
        # Encrypt using Fernet here on backend
        enc_api_key = fernet.encrypt(api_key.encode()).decode()
        enc_secret_key = fernet.encrypt(secret_key.encode()).decode()
    except Exception as e:
        return jsonify({"status": "error", "message": "Encryption failed: " + str(e)}), 500

    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    users[user_id]["api_key"] = enc_api_key
    users[user_id]["secret_key"] = enc_secret_key
    save_users(users)

    return jsonify({"status": "success", "message": "API keys saved securely"}), 200

@app.route("/webhook/<user_id>", methods=["POST"])
def webhook(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    user = users[user_id]
    data = request.get_json()
    symbol = data.get("symbol")
    action = data.get("action")
    quantity = int(data.get("quantity", 1))

    if not symbol or not action:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    try:
        api_key = fernet.decrypt(user["api_key"].encode()).decode()
        secret_key = fernet.decrypt(user["secret_key"].encode()).decode()

        api = tradeapi.REST(
            key_id=api_key,
            secret_key=secret_key,
            base_url="https://paper-api.alpaca.markets"
        )

        # 🔁 New fallback logic to get position
        held_qty = 0
        if action.lower() == "sell":
            try:
                positions = api.list_positions()
                position = next((p for p in positions if p.symbol == symbol), None)
                if position:
                    held_qty = int(float(position.qty_available))
            except Exception as e:
                error_message = f"Failed to fetch position: {str(e)}"
                return jsonify({"status": "error", "message": error_message}), 500

            if held_qty < quantity:
                return jsonify({"status": "error", "message": f"Not enough quantity to sell: You have {held_qty}"}), 400

        order = api.submit_order(
            symbol=symbol,
            qty=quantity,
            side=action.lower(),
            type="market",
            time_in_force="gtc"
        )

        price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
        log_trade(user_id, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action.capitalize(),
            "quantity": quantity,
            "status": "✅",
            "price": price
        })
        return jsonify({"status": "success", "order_id": order.id}), 200

    except Exception as e:
        error_message = str(e)
        log_trade(user_id, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action.capitalize(),
            "quantity": quantity,
            "status": "❌",
            "error": error_message
        })
        return jsonify({"status": "error", "message": f"❌ {error_message}"}), 500




@app.route("/portfolio/<user_id>", methods=["GET"])
def get_portfolio(user_id):
    users = load_users()
    if user_id not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404
    user = users[user_id]
    try:
        api_key = fernet.decrypt(user["api_key"].encode()).decode()
        secret_key = fernet.decrypt(user["secret_key"].encode()).decode()

        api = tradeapi.REST(
            key_id=api_key,
            secret_key=secret_key,
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
    data = request.get_json()
    users[user_id]["strategy"] = data.get("strategy", "balanced")
    save_users(users)
    return jsonify({"status": "success", "message": "Strategy updated"})

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
    strategy = users[user_id].get("strategy", "balanced")
    symbols = users[user_id].get("watchlist", []) or ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]

    suggestions = []
    for symbol in symbols:
        try:
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=2&apikey={TD_API_KEY}"
            res = requests.get(url).json()
            if "values" not in res or len(res["values"]) < 2:
                continue
            today = float(res["values"][0]["close"])
            yesterday = float(res["values"][1]["close"])
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

            suggestions.append({
                "symbol": symbol,
                "current_price": today,
                "change_percent": change,
                "suggestion": suggestion
            })
        except:
            continue

    top5 = sorted(suggestions, key=lambda x: abs(x["change_percent"]), reverse=True)[:5]
    return jsonify(top5), 200

@app.route("/pnl/<user_id>", methods=["GET"])
def get_pnl_chart(user_id):
    log_file = f"logs/{user_id}.json"
    if not os.path.exists(log_file):
        return jsonify({"labels": [], "data": []})
    try:
        with open(log_file, "r") as f:
            logs = json.load(f)

        pnl_by_day = {}
        for log in logs:
            if log.get("status") != "✅":
                continue
            date = log["timestamp"].split()[0]
            qty = int(log.get("quantity", 1))
            price = float(log.get("price", 0.0))
            pnl = price * qty
            if log.get("action", "").lower() == "buy":
                pnl *= -1
            pnl_by_day[date] = pnl_by_day.get(date, 0) + pnl

        labels = sorted(pnl_by_day.keys())
        data = [round(pnl_by_day[d], 2) for d in labels]
        return jsonify({"labels": labels, "data": data})
    except Exception as e:
        return jsonify({"labels": [], "data": [], "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
