from flask import Flask, request, jsonify
from flask_cors import CORS
import alpaca_trade_api as tradeapi
import json
import os
import sys, os
import requests
import hashlib
from datetime import datetime
from cryptography.fernet import Fernet
import google.generativeai as genai
from google.generativeai import GenerativeModel
from smartapi.smartConnect import SmartConnect

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

fernet = Fernet(os.environ["FERNET_KEY"])
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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

def log_trade(userId, log_data):
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/{userId}.json"
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

@app.route("/safe-bot/<userId>", methods=["POST"])
def safe_bot(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        api_key = fernet.decrypt(users[userId]["api_key"].encode()).decode()
        secret_key = fernet.decrypt(users[userId]["secret_key"].encode()).decode()
    except:
        return jsonify({"status": "error", "message": "Decryption failed"}), 500

    api = tradeapi.REST(api_key, secret_key, base_url="https://paper-api.alpaca.markets")
    strategy = users[userId].get("strategy", "balanced")
    symbols = users[userId].get("watchlist", []) or ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]

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
                log_trade(userId, {
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
                        log_trade(userId, {
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

@app.route("/logs/<userId>", methods=["GET"])
def get_logs(userId):
    log_file = f"logs/{userId}.json"
    if not os.path.exists(log_file):
        return jsonify([])
    try:
        with open(log_file, "r") as f:
            return jsonify(json.load(f))
    except:
        return jsonify([])

@app.route('/angel-trade', methods=['POST'])
def place_angel_trade():
    data = request.json
    symbol = data['symbol']
    side = data['action'].upper()
    quantity = int(data['quantity'])

    try:
        from smartapi.smartConnect import SmartConnect  # Corrected import
        import os

        api_key = os.getenv('ANGEL_API_KEY')
        clientId = os.getenv('ANGEL_CLIENT_ID')
        password = os.getenv('ANGEL_PASSWORD')
        totp = os.getenv('ANGEL_TOTP')

        smartapi = SmartConnect(api_key)
        session = smartapi.generateSession(clientId, password, totp)

        symbol_map = {"RELIANCE": "2885", "INFY": "1594"}  # Extend this
        token = symbol_map.get(symbol.upper())
        if not token:
            return jsonify({"status": "error", "message": "Symbol not found"}), 400

        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol.upper(),
            "symboltoken": token,
            "transactiontype": side,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": quantity
        }

        orderId = smartapi.placeOrder(orderparams)
        return jsonify({"status": "success", "orderId": orderId})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/connect-broker", methods=["POST"])
def connect_broker():
    data = request.json
    broker = data.get("broker")
    userId = data.get("userId")

    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    # ✅ Set current broker
    users[userId]["current_broker"] = broker

    if broker == "alpaca":
        api_key = data.get("apiKey")
        secret_key = data.get("secretKey")

        if not api_key or not secret_key:
            return jsonify({"message": "❌ Missing Alpaca keys"}), 400

        try:
            enc_api_key = fernet.encrypt(api_key.encode()).decode()
            enc_secret_key = fernet.encrypt(secret_key.encode()).decode()
            users[userId]["alpaca"] = {
                "api_key": enc_api_key,
                "secret_key": enc_secret_key
            }
            save_users(users)
            return jsonify({"message": "✅ Alpaca connected."})
        except Exception as e:
            return jsonify({"message": "❌ Encryption failed", "error": str(e)}), 500

    elif broker == "angelone":
        try:
            from angelone_autologin import login_to_angelone
            auth = login_to_angelone()
            users[userId]["angelone"] = {
                "auth_token": auth["authToken"]
            }
            save_users(users)
            return jsonify({"message": "✅ Angel One connected."})
        except Exception as e:
            return jsonify({"message": "❌ Angel One login failed", "error": str(e)}), 500

    return jsonify({"message": "❌ Unknown broker"}), 400



@app.route("/recommend-ai", methods=["POST"])
def recommend_ai():
    model = GenerativeModel("gemini-1.5-flash")

    userId = request.args.get("userId", "")
    data = request.get_json()
    prompt = data.get("prompt", "")

    users = load_users()
    if userId not in users:
        return jsonify({"suggestion": "User not found."}), 404

    user = users[userId]
    strategy = user.get("strategy", "balanced")
    watchlist = user.get("watchlist", []) or ["AAPL", "MSFT", "TSLA"]

    # Get portfolio info
    try:
        api_key = fernet.decrypt(user["api_key"].encode()).decode()
        secret_key = fernet.decrypt(user["secret_key"].encode()).decode()
        api = tradeapi.REST(api_key, secret_key, base_url="https://paper-api.alpaca.markets")
        account = api.get_account()
        positions = api.list_positions()
        cash = round(float(account.cash), 2)
        equity = round(float(account.equity), 2)
        market_value = round(sum([float(p.market_value) for p in positions]), 2)
        pnl = round(equity - cash, 2)
    except:
        cash = equity = market_value = pnl = "N/A"

    # 🧠 Add live prices to prompt
    price_lines = ""
    for symbol in watchlist:
        try:
            r = requests.get(f"https://api.twelvedata.com/price?symbol={symbol}&apikey=732be95d470647be80419085887d2606")
            price = r.json().get("price", "N/A")
            price_lines += f"- {symbol}: ${price}\n"
        except:
            continue

    # 🧠 AI Prompt context
    context = f"""
You are a professional AI stock trading assistant.

Strategy: {strategy}

Portfolio:
- 💰 Cash: ${cash}
- 📈 Market Value: ${market_value}
- 💵 Total Equity: ${equity}
- 📊 P&L: ${pnl}

Watchlist with latest prices:
{price_lines}

✅ Give direct BUY / SELL / HOLD suggestions only.
✅ Be brief, actionable, and avoid over-explaining.
✅ Use bullet points when possible.
"""

    try:
        response = model.generate_content(context + "\n\nUser: " + prompt)
        return jsonify({"suggestion": response.text})
    except Exception as e:
        return jsonify({"suggestion": "❌ Gemini error: " + str(e)}), 500

@app.route("/connect-angel", methods=["POST"])
def connect_angel():
    data = request.get_json()
    userId = data.get("userId")
    clientId = data.get("clientId")
    password = data.get("password")
    totp = data.get("totp")

    if not all([userId, clientId, password, totp]):
        return jsonify({"status": "error", "message": "Missing credentials"}), 400

    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        from smartapi.smartConnect import SmartConnect  # Corrected import
        smartApi = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        session = smartApi.generateSession(clientId, password, totp)

        users[userId]["auth_token"] = session["data"]["jwtToken"]
        users[userId]["broker"] = "angelone"
        save_users(users)

        return jsonify({"status": "success", "message": "✅ Angel One connected successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    userId = data.get("userId", "").strip()
    password = data.get("password", "").strip()

    if not userId or not password:
        return jsonify({"status": "error", "message": "User ID and password are required"}), 400

    users = load_users()
    if userId in users:
        return jsonify({"status": "error", "message": "User ID already exists"}), 409

    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    users[userId] = {
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
    userId = data.get("userId", "").strip()
    password = data.get("password", "").strip()

    if not userId or not password:
        return jsonify({"status": "error", "message": "User ID and Password are required."}), 400

    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "User not found."}), 404

    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    if users[userId].get("password") != hashed_pw:
        return jsonify({"status": "error", "message": "Incorrect password."}), 401

    return jsonify({"status": "success", "message": "Login successful."}), 200

@app.route("/connect-alpaca", methods=["POST"])
def connect_alpaca():
    data = request.get_json()
    userId = data.get("userId", "").strip()
    api_key = data.get("api_key", "").strip()
    secret_key = data.get("secret_key", "").strip()

    if not userId or not api_key or not secret_key:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    try:
        # Encrypt using Fernet here on backend
        enc_api_key = fernet.encrypt(api_key.encode()).decode()
        enc_secret_key = fernet.encrypt(secret_key.encode()).decode()
    except Exception as e:
        return jsonify({"status": "error", "message": "Encryption failed: " + str(e)}), 500

    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    users[userId]["api_key"] = enc_api_key
    users[userId]["secret_key"] = enc_secret_key
    save_users(users)

    return jsonify({"status": "success", "message": "API keys saved securely"}), 200

@app.route("/webhook/<userId>", methods=["POST"])
def webhook(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    user = users[userId]
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
        log_trade(userId, {
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
        log_trade(userId, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action.capitalize(),
            "quantity": quantity,
            "status": "❌",
            "error": error_message
        })
        return jsonify({"status": "error", "message": f"❌ {error_message}"}), 500

@app.route("/webhook-angelone/<userId>", methods=["POST"])
def webhook_angelone(userId):
    users = load_users()
    if userId not in users or "angelone" not in users[userId]:
        return jsonify({"status": "error", "message": "User or Angel One credentials not found"}), 404

    user = users[userId]
    data = request.get_json()
    symbol = data.get("symbol")
    action = data.get("action", "").upper()
    quantity = int(data.get("quantity", 1))

    if not symbol or not action:
        return jsonify({"status": "error", "message": "Missing symbol or action"}), 400

    try:
        from smartapi.smartConnect import SmartConnect  # Corrected import
        smartApi = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        # TODO: Implement token refresh here.  This is CRUCIAL for long-term use.
        smartApi.setAccessToken(user["angelone"]["auth_token"])  # This token will expire!

        symbol_map = {
            "RELIANCE": "2885", "INFY": "1594", "TCS": "11536", "HDFCBANK": "1333", "ICICIBANK": "4963",
            "SBIN": "3045", "ITC": "1660", "KOTAKBANK": "1922", "HINDUNILVR": "1394", "LT": "11483",
            "BHARTIARTL": "10604", "AXISBANK": "5900", "MARUTI": "509", "BAJFINANCE": "317", "ASIANPAINT": "604"
        }

        token = symbol_map.get(symbol.upper())
        if not token:
            return jsonify({"status": "error", "message": f"Symbol '{symbol}' not supported"}), 400

        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol.upper(),
            "symboltoken": token,
            "transactiontype": action,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": quantity
        }

        order_id = smartApi.placeOrder(orderparams)

        log_trade(userId, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "broker": "angelone",
            "status": "✅",
            "order_id": order_id
        })

        return jsonify({"status": "success", "orderId": order_id, "broker": "angelone"}), 200

    except Exception as e:
        log_trade(userId, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "broker": "angelone",
            "status": "❌",
            "error": str(e)
        })
        return jsonify({"status": "error", "message": f"❌ {str(e)}"}), 500



@app.route("/portfolio/<userId>", methods=["GET"])
def get_portfolio(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404
    user = users[userId]
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

@app.route("/strategy/<userId>", methods=["GET", "POST"])
def strategy_handler(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404
    if request.method == "GET":
        return jsonify({"strategy": users[userId].get("strategy", "balanced")})
    data = request.get_json()
    users[userId]["strategy"] = data.get("strategy", "balanced")
    save_users(users)
    return jsonify({"status": "success", "message": "Strategy updated"})

@app.route("/watchlist/<userId>", methods=["GET", "POST"])
def watchlist_handler(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404
    user = users[userId]
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

@app.route("/suggested/<userId>", methods=["GET"])
def suggested_symbols(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "Invalid user"}), 404

    TD_API_KEY = "732be95d470647be80419085887d2606"
    strategy = users[userId].get("strategy", "balanced")
    symbols = users[userId].get("watchlist", []) or ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]

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

@app.route("/pnl/<userId>", methods=["GET"])
def get_pnl_chart(userId):
    log_file = f"logs/{userId}.json"
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

@app.route("/live-logs/<userId>", methods=["GET"])
def live_logs(userId):
    log_file = f"logs/{userId}.json"
    if not os.path.exists(log_file):
        return jsonify({"logs": [], "message": "No logs found."})

    try:
        with open(log_file, "r") as f:
            logs = json.load(f)
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"logs": [], "error": str(e)})

@app.route("/user-info/<userId>", methods=["GET"])
def user_info(userId):
    users = load_users()
    if userId not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404

    broker = users[userId].get("broker", "angelone")
    strategy = users[userId].get("strategy", "balanced")

    render_base = "https://multi-user-trading-bot.onrender.com"
    webhook_url = f"{render_base}/webhook-angelone/{userId}" if broker == "angelone" else f"{render_base}/webhook/{userId}"

    return jsonify({
        "broker": broker,
        "strategy": strategy,
        "webhook_url": webhook_url
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
