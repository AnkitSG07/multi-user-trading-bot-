import gspread
from oauth2client.service_account import ServiceAccountCredentials

def store_token_to_sheet(user_id, token):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Angel token").sheet1
    sheet.append_row([user_id, token])
