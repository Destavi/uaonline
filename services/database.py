import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "discordua05.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Перевірка чи таблиця complaints має стару структуру (без db_key)
    cur.execute("PRAGMA table_info(complaints)")
    columns = [col[1] for col in cur.fetchall()]
    if columns and "db_key" not in columns:
        print("⚠️ [Database] Old 'complaints' table detected. Recreating to match new schema...")
        cur.execute("DROP TABLE complaints")

    # Скарги
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        db_key TEXT PRIMARY KEY,
        guild_id TEXT,
        category TEXT,
        local_id INTEGER,
        author_id INTEGER,
        author_nick TEXT,
        status TEXT,
        timestamp TEXT
    )
    """)

    # Лічильники скарг
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaint_counters (
        guild_id TEXT,
        category TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, category)
    )
    """)

    # Глобальна статистика модерації
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mod_stats (
        guild_id TEXT,
        stat_key TEXT,
        value INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, stat_key)
    )
    """)

    # Логи модерації (для персональної статистики та аудиту)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mod_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        action_type TEXT,
        admin_id INTEGER,
        admin_name TEXT,
        target_id TEXT,
        target_name TEXT,
        reason TEXT,
        timestamp TEXT
    )
    """)

    conn.commit()
    conn.close()
