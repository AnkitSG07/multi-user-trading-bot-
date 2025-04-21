import os
import pyotp
from smartapi import SmartConnect

# Load credentials from environment
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")

# Generate TOTP using pyotp
totp = pyotp.TOTP(TOTP_SECRET).now()

# Create a SmartConnect object
smart_api = SmartConnect(api_key=API_KEY)

try:
    # Generate session (login)
    data = smart_api.generateSession(client_id=CLIENT_ID, password=PASSWORD, totp=totp)
    refresh_token = data['data']['refreshToken']
    access_token = data['data']['accessToken']
    print("✅ Login successful")
    print("Access Token:", access_token)
    print("Refresh Token:", refresh_token)

    # Set access token for future requests
    smart_api.setAccessToken(access_token)

except Exception as e:
    print("❌ Login failed:", e)
