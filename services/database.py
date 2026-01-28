import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    # Скарги (Complaints) - Розширена структура для збереження функціоналу
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            guild_id BIGINT,
            category TEXT,
            local_id INTEGER,
            user_id BIGINT, -- Author ID
            author_nick TEXT,
            target_name TEXT,
            reason TEXT,
            proof_url TEXT,
            status TEXT DEFAULT '🟡 Відкрита',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Статистика модераторів
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mod_stats (
            moderator_id BIGINT PRIMARY KEY,
            warnings_count INTEGER DEFAULT 0,
            bans_count INTEGER DEFAULT 0,
            mutes_count INTEGER DEFAULT 0,
            reports_handled INTEGER DEFAULT 0
        )
    ''')
    
    # Логи модерації (для персональної статистики та аудиту)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mod_actions (
            id SERIAL PRIMARY KEY,
            guild_id BIGINT,
            action_type TEXT,
            admin_id BIGINT,
            admin_name TEXT,
            target_id TEXT,
            target_name TEXT,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Лічильники скарг
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaint_counters (
            guild_id BIGINT,
            category TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, category)
        )
    ''')

    # Глобальна статистика сервера
    cur.execute('''
        CREATE TABLE IF NOT EXISTS server_stats (
            guild_id BIGINT,
            stat_key TEXT,
            value INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, stat_key)
        )
    ''')

    # Попередження (Warnings)
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

    # Тимчасові бани (Temp Bans)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS temp_bans (
            guild_id BIGINT,
            user_id BIGINT,
            unban_time TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')

    # Конфігурація серверів (Guild Configs)
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
    print("🐘 [PostgreSQL] База даних ініціалізована!")
