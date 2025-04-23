import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("google/credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name).sheet1  # opens the first sheet
