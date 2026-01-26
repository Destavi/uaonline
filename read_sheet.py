import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, GOOGLE_CREDS_PATH

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def read_sheet():
    try:
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        records = sheet.get_all_records()
        print(f"Знайдено записів: {len(records)}")
        if records:
            print("Перший запис:", records[0])
    except Exception as e:
        print(f"❌ Помилка: {e}")

if __name__ == "__main__":
    read_sheet()
