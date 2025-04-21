import os
import pyotp
from smartapi import SmartConnect

# Reusable login function
def login_to_angelone():
    client = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
    totp = pyotp.TOTP(os.environ["ANGEL_TOTP_SECRET"]).now()

    try:
        session = client.generateSession(
            os.environ["ANGEL_CLIENT_ID"],
            os.environ["ANGEL_PASSWORD"],
            totp
        )
        client.set_session_token(session["data"]["jwtToken"])
        return {
            "client": client,
            "authToken": session["data"]["jwtToken"],
            "feedToken": client.getfeedToken()
        }
    except Exception as e:
        raise Exception(f"Angel One login failed: {str(e)}")

# Reusable order function
def place_order_angelone(symbol, side, quantity):
    login_data = login_to_angelone()
    client = login_data["client"]

    # 📝 Replace this with actual token fetched from Angel One's instrument list
    symboltoken = "3045"  # Dummy NSE symboltoken, update this dynamically later

    orderparams = {
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": symboltoken,
        "transactiontype": side.upper(),  # "BUY" or "SELL"
        "exchange": "NSE",
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": quantity
    }

    try:
        order_id = client.placeOrder(orderparams)
        return order_id
    except Exception as e:
        raise Exception(f"Angel One order failed: {str(e)}")
