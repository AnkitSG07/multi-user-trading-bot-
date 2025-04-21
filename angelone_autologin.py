import os
from smartapi import SmartConnect
import pyotp

# Load credentials from environment variables
ANGEL_API_KEY = os.getenv("ANGEL_API_KEY")
ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")

# Generate TOTP
totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()

# Initialize SmartAPI client
smart_api = SmartConnect(api_key=ANGEL_API_KEY)

try:
    # Attempt login
    data = smart_api.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
    authToken = data["data"]["jwtToken"]
    refreshToken = data["data"]["refreshToken"]
    feedToken = smart_api.getfeedToken()

    print("✅ Login successful!")
    print("Auth Token:", authToken)
    print("Feed Token:", feedToken)

    # You can return these tokens from a function if needed

except Exception as e:
    print("❌ Login failed:", e)
