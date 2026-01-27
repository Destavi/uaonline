import psycopg2
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

# Ми змінили назву з get_connection на get_conn
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            target_name TEXT,
            reason TEXT,
            proof_url TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mod_stats (
            moderator_id BIGINT PRIMARY KEY,
            warnings_count INTEGER DEFAULT 0,
            bans_count INTEGER DEFAULT 0,
            reports_handled INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()
    print("🐘 [PostgreSQL] База даних ініціалізована!")
    cur.close()
    conn.close()
    print("🐘 [PostgreSQL] База даних ініціалізована!")

