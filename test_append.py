import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, GOOGLE_CREDS_PATH
from datetime import datetime

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def test_append():
    try:
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        
        row = ["#TEST", "🟢 Тест", "Результат тесту", datetime.now().strftime("%d.%m.%Y %H:%M"), "", "", "Bot Test", "http://test.com"]
        sheet.append_row(row)
        print("✅ Тестовий рядок додано!")
    except Exception as e:
        print(f"❌ Помилка: {e}")

if __name__ == "__main__":
    test_append()
