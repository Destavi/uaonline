import gspread
from google.oauth2.service_account import Credentials
import os

from config import GOOGLE_SHEET_ID, GOOGLE_CREDS_PATH

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def test_connection():
    try:
        if not os.path.exists(GOOGLE_CREDS_PATH):
            print(f"❌ Файл {GOOGLE_CREDS_PATH} не знайдено!")
            return

        creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        print("✅ Успішно підключено до таблиці!")
        print(f"Назва таблиці: {client.open_by_key(GOOGLE_SHEET_ID).title}")
        
    except Exception as e:
        print(f"❌ Помилка підключення: {e}")

if __name__ == "__main__":
    test_connection()
