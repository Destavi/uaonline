import json
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from services.database import init_db, get_conn

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
MOD_LOGS_FILE = os.path.join(BASE_DIR, "mod_logs.json")
COMPLAINTS_FILE = os.path.join(BASE_DIR, "complaints.json")
WARNINGS_FILE = os.path.join(BASE_DIR, "warnings.json")
TEMP_BANS_FILE = os.path.join(BASE_DIR, "temp_bans.json")
GUILDS_CONFIG_FILE = os.path.join(BASE_DIR, "guilds_config.json")

def migrate():
    print("🚀 Starting migration to PostgreSQL...")
    # Обов'язково створюємо таблиці перед міграцією
    init_db()
    
    conn = get_conn()
    cur = conn.cursor()

    # 1. Migrate Stats
    if os.path.exists(STATS_FILE):
        print("📊 Migrating stats.json to server_stats...")
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats_data = json.load(f)
            for guild_id, guild_stats in stats_data.items():
                for key, val in guild_stats.items():
                    cur.execute("""
                        INSERT INTO server_stats (guild_id, stat_key, value)
                        VALUES (%s, %s, %s)
                        ON CONFLICT(guild_id, stat_key) DO UPDATE SET value = server_stats.value + EXCLUDED.value
                    """, (int(guild_id), key, val))
        print("✅ Stats migrated.")

    # 2. Migrate Mod Logs
    if os.path.exists(MOD_LOGS_FILE):
        print("📝 Migrating mod_logs.json to mod_actions...")
        with open(MOD_LOGS_FILE, "r", encoding="utf-8") as f:
            logs_data = json.load(f)
            for guild_id, logs in logs_data.items():
                for l in logs:
                    timestamp = datetime.fromisoformat(l["timestamp"]) if "timestamp" in l else datetime.now()
                    cur.execute("""
                        INSERT INTO mod_actions (guild_id, action_type, admin_id, admin_name, target_id, target_name, reason, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        int(guild_id), l["type"], l["admin_id"], l["admin_name"],
                        str(l["target_id"]), l["target_name"], l["reason"], timestamp
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
                        VALUES (%s, %s, %s)
                        ON CONFLICT(guild_id, category) DO UPDATE SET count = GREATEST(complaint_counters.count, EXCLUDED.count)
                    """, (int(guild_id), category, count))
                
                # Migration complaints
                complaints = g_data.get("complaints", {})
                for db_key, c in complaints.items():
                    try:
                        category, local_id = db_key.split('_')
                    except:
                        category = "unknown"
                        local_id = 0
                        
                    timestamp = datetime.fromisoformat(c["timestamp"]) if "timestamp" in c else datetime.now()
                    
                    cur.execute("""
                        INSERT INTO complaints (guild_id, category, local_id, user_id, target_name, reason, proof_url, author_nick, status, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        int(guild_id), category, int(local_id),
                        c.get("author", 0), c.get("target_name", "Unknown"),
                        c.get("reason", ""), c.get("proof_url", ""),
                        c.get("author_nick", "Unknown"),
                        c.get("status", "Відкрита"), timestamp
                    ))
        print("✅ Complaints migrated.")
    
    # 4. Migrate Warnings
    if os.path.exists(WARNINGS_FILE):
        print("⚠️ Migrating warnings.json...")
        with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
            warnings_data = json.load(f)
            for guild_id, g_warnings in warnings_data.items():
                for user_id, user_warns in g_warnings.items():
                    for w in user_warns:
                        timestamp = datetime.fromisoformat(w["timestamp"]) if "timestamp" in w else datetime.now()
                        cur.execute("""
                            INSERT INTO warnings (guild_id, user_id, local_id, reason, admin_name, timestamp)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (int(guild_id), int(user_id), w["id"], w["reason"], w["admin"], timestamp))
        print("✅ Warnings migrated.")

    # 5. Migrate Temp Bans
    if os.path.exists(TEMP_BANS_FILE):
        print("⏳ Migrating temp_bans.json...")
        with open(TEMP_BANS_FILE, "r", encoding="utf-8") as f:
            temp_bans_data = json.load(f)
            for guild_id, users in temp_bans_data.items():
                for user_id, unban_time_str in users.items():
                    unban_time = datetime.fromisoformat(unban_time_str)
                    cur.execute("""
                        INSERT INTO temp_bans (guild_id, user_id, unban_time)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (guild_id, user_id) DO UPDATE SET unban_time = EXCLUDED.unban_time
                    """, (int(guild_id), int(user_id), unban_time))
        print("✅ Temp bans migrated.")

    # 6. Migrate Guild Configs
    if os.path.exists(GUILDS_CONFIG_FILE):
        print("⚙️ Migrating guilds_config.json...")
        with open(GUILDS_CONFIG_FILE, "r", encoding="utf-8") as f:
            guilds_data = json.load(f)
            for guild_id, config in guilds_data.items():
                cur.execute("""
                    INSERT INTO guild_configs (guild_id, config, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (guild_id) DO UPDATE SET config = EXCLUDED.config, updated_at = CURRENT_TIMESTAMP
                """, (int(guild_id), json.dumps(config)))
        print("✅ Guild configs migrated.")

    conn.commit()
    cur.close()
    conn.close()
    print("🏁 Migration finished successfully!")

if __name__ == "__main__":
    migrate()
