import gspread
import requests
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet(sheet_name="Angel token"):
    # 📥 Fetch the JSON credentials from your GitHub repo
    repo_url = "https://raw.githubusercontent.com/AnkitSG07/multi-user-trading-bot-/main/service_account.json"
    response = requests.get(repo_url)
    if response.status_code != 200:
        raise Exception("Failed to fetch service_account.json from GitHub.")

    # ✅ Write in binary mode to preserve PEM format
    with open("service_account.json", "wb") as f:
        f.write(response.content)

    # ✅ Set up gspread with scopes
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)

    # 📄 Access the sheet
    return client.open(sheet_name).sheet1

def write_token_to_sheet(user_id, token):
    sheet = get_sheet("Angel token")
    sheet.append_row([user_id, token, datetime.now().isoformat()])
