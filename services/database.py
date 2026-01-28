import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Скарги (Complaints)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            guild_id BIGINT,
            category TEXT,
            local_id INTEGER,
            user_id BIGINT,
            author_nick TEXT,
            target_name TEXT,
            reason TEXT,
            proof_url TEXT,
            status TEXT DEFAULT '🟡 Відкрита',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Лічильники скарг
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaint_counters (
            guild_id BIGINT,
            category TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, category)
        )
    ''')

    # 3. Статистика модераторів
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mod_stats (
            guild_id BIGINT,
            user_id BIGINT,
            action_type TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, action_type)
        )
    ''')

    # 4. Логи дій модераторів
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mod_actions (
            id SERIAL PRIMARY KEY,
            guild_id BIGINT,
            admin_id BIGINT,
            admin_name TEXT,
            target_id BIGINT,
            target_name TEXT,
            action_type TEXT,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Статистика сервера (Global)
    # Перевіряємо чи стара структура таблиці (без stat_key)
    cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='server_stats' AND column_name='stat_key'")
    if cur.fetchone()[0] == 0:
        cur.execute("DROP TABLE IF EXISTS server_stats")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS server_stats (
            guild_id BIGINT,
            stat_key TEXT,
            value INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, stat_key)
        )
    ''')

    # 6. Варни (Warnings)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            id SERIAL PRIMARY KEY,
            guild_id BIGINT,
            user_id BIGINT,
            local_id INTEGER,
            reason TEXT,
            admin_name TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Тимчасові бани (Temp Bans)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS temp_bans (
            guild_id BIGINT,
            user_id BIGINT,
            unban_time TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')

    # 8. Налаштування серверів (Guild Configs)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS guild_configs (
            guild_id BIGINT PRIMARY KEY,
            config JSONB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    cur.close()
    conn.close()
    print("🐘 [PostgreSQL] База даних успішно ініціалізована!")
