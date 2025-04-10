from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi
import json
import os

app = Flask(__name__)

api = tradeapi.REST(
    key_id=os.environ.get(f"{user_id.upper()}_API_KEY"),
    secret_key=os.environ.get(f"{user_id.upper()}_SECRET_KEY"),
    base_url="https://paper-api.alpaca.markets"
)

# Load user credentials from users.json
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

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

        # Submit order
        order = api.submit_order(
            symbol=symbol,
            qty=quantity,
            side=action.lower(),
            type="market",
            time_in_force="gtc"
        )

        print(f"✅ [{user_id}] Order placed: {symbol} {action.upper()} x{quantity}")
        return jsonify({"status": "success", "order_id": order.id}), 200

    except Exception as e:
        print(f"❌ [{user_id}] Order failed:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
