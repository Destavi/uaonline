import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

class GoogleSheetsService:
    def __init__(self, sheet_id, credentials_path):
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.client = self._authenticate()

    def _authenticate(self):
        try:
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=self.scope)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"❌ Помилка авторизації Google Sheets: {e}")
            return None

    def append_complaint(self, cid, reason, link):
        if not self.client: return

        try:
            sheet = self.client.open_by_key(self.sheet_id).sheet1
            
            # Columns: 
            # 1: Номер скарги
            # 2: Вердикт
            # 3: Суть скарги
            # 4: Час подачі скарги
            # 5: Час закриття скарги
            # 6: Час розгляду
            # 7: Адмін розглядавший скаргу
            # 8: Посилання на скаргу
            
            row = [
                f"#{cid}",          # 1
                "Не обрано",        # 2
                reason,             # 3
                datetime.now().strftime("%d.%m.%Y %H:%M"), # 4
                "",                 # 5 (Час закриття)
                "",                 # 6 (Час розгляду)
                "",                 # 7 (Адмін)
                link                # 8
            ]
            
            sheet.append_row(row)
            print(f"✅ Скарга #{cid} ініціалізована в Google Таблиці.")
        except Exception as e:
            print(f"❌ Помилка при додаванні рядка в Google Таблицю: {e}")

    def update_verdict(self, cid, discord_status, admin_name):
        if not self.client: return
        
        # Map Discord status to Sheet verdict
        verdict_map = {
            "🟢 Прийнята": "Схвалено",
            "🔴 Відхилена": "Відмовлено"
        }
        verdict = verdict_map.get(discord_status, "Не обрано")

        try:
            sheet = self.client.open_by_key(self.sheet_id).sheet1
            cell = sheet.find(f"#{cid}")
            if cell:
                # Update Verdict (col 2), Decision Time (col 6), Admin (col 7)
                updates = [
                    {'range': f'B{cell.row}', 'values': [[verdict]]},
                    {'range': f'F{cell.row}', 'values': [[datetime.now().strftime("%d.%m.%Y %H:%M")]]},
                    {'range': f'G{cell.row}', 'values': [[admin_name]]}
                ]
                sheet.batch_update(updates)
                print(f"✅ Вердикт для #{cid} оновлено в таблиці.")
        except Exception as e:
            print(f"❌ Помилка при оновленні вердикту в Google Таблиці: {e}")

    def update_closing(self, cid):
        if not self.client: return
        try:
            sheet = self.client.open_by_key(self.sheet_id).sheet1
            cell = sheet.find(f"#{cid}")
            if cell:
                # Update Closing Time (col 5)
                sheet.update_acell(f'E{cell.row}', datetime.now().strftime("%d.%m.%Y %H:%M"))
                print(f"✅ Час закриття для #{cid} оновлено в таблиці.")
        except Exception as e:
            print(f"❌ Помилка при оновленні закриття в Google Таблиці: {e}")
