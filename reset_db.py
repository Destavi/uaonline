from services.database import get_conn
import sys

def reset():
    print("⚠️ Починаю повне очищення бази даних PostgreSQL...")
    print("Всі дані (скарги, варни, статистика) будуть видалені!")
    
    # Якщо ти запускаєш це вручну і хочеш підтвердження
    # confirm = input("Ви впевнені? (y/n): ")
    # if confirm.lower() != 'y': return

    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Список таблиць для видалення
        tables = [
            "complaints", "complaint_counters", "mod_stats", 
            "mod_actions", "server_stats", "warnings", 
            "temp_bans", "guild_configs"
        ]
        
        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"🗑️ Таблиця {table} видалена.")
            
        conn.commit()
        cur.close()
        conn.close()
        print("\n✅ База даних повністю очищена!")
        print("Тепер просто запустіть бота (python main.py), і він створить нові таблиці.")
        
    except Exception as e:
        print(f"❌ Помилка при очищенні: {e}")

if __name__ == "__main__":
    reset()
