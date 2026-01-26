import json
import os
import sqlite3
from datetime import datetime

from services.database import init_db

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "discordua05.db")
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
MOD_LOGS_FILE = os.path.join(BASE_DIR, "mod_logs.json")
COMPLAINTS_FILE = os.path.join(BASE_DIR, "complaints.json")

def migrate():
    print("🚀 Starting migration...")
    # Обов'язково створюємо таблиці перед міграцією
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Migrate Stats
    if os.path.exists(STATS_FILE):
        print("📊 Migrating stats.json...")
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats_data = json.load(f)
            for guild_id, guild_stats in stats_data.items():
                for key, val in guild_stats.items():
                    cur.execute("""
                        INSERT INTO mod_stats (guild_id, stat_key, value)
                        VALUES (?, ?, ?)
                        ON CONFLICT(guild_id, stat_key) DO UPDATE SET value = value + excluded.value
                    """, (guild_id, key, val))
        print("✅ Stats migrated.")

    # 2. Migrate Mod Logs
    if os.path.exists(MOD_LOGS_FILE):
        print("📝 Migrating mod_logs.json...")
        with open(MOD_LOGS_FILE, "r", encoding="utf-8") as f:
            logs_data = json.load(f)
            for guild_id, logs in logs_data.items():
                for l in logs:
                    cur.execute("""
                        INSERT INTO mod_actions (guild_id, action_type, admin_id, admin_name, target_id, target_name, reason, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        guild_id, l["type"], l["admin_id"], l["admin_name"],
                        str(l["target_id"]), l["target_name"], l["reason"], l["timestamp"]
                    ))
        print("✅ Mod logs migrated.")

    # 3. Migrate Complaints
    if os.path.exists(COMPLAINTS_FILE):
        print("📂 Migrating complaints.json...")
        with open(COMPLAINTS_FILE, "r", encoding="utf-8") as f:
            complaints_data = json.load(f)
            for guild_id, g_data in complaints_data.items():
                # Migration counters
                counters = g_data.get("counters", {})
                for category, count in counters.items():
                    cur.execute("""
                        INSERT INTO complaint_counters (guild_id, category, count)
                        VALUES (?, ?, ?)
                        ON CONFLICT(guild_id, category) DO UPDATE SET count = MAX(count, excluded.count)
                    """, (guild_id, category, count))
                
                # Migration complaints
                complaints = g_data.get("complaints", {})
                for db_key, c in complaints.items():
                    cur.execute("""
                        INSERT INTO complaints (db_key, guild_id, category, local_id, author_id, author_nick, status, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(db_key) DO UPDATE SET status = excluded.status
                    """, (
                        db_key, guild_id, c.get("category", "unknown"), c.get("local_id", 0),
                        c.get("author", 0), c.get("author_nick", "Unknown"),
                        c.get("status", "Відкрита"), c.get("timestamp", datetime.now().isoformat())
                    ))
        print("✅ Complaints migrated.")

    conn.commit()
    conn.close()
    print("🏁 Migration finished successfully!")

if __name__ == "__main__":
    migrate()
