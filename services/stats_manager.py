from services.database import get_conn
from datetime import datetime

print(f"🐘 [StatsManager] Ініціалізовано з бекендом PostgreSQL")

def update_stat(guild_id, action_type):
    conn = get_conn()
    cur = conn.cursor()
    
    # Використовуємо %s замість ? та виправляємо структуру під PostgreSQL
    cur.execute("""
        INSERT INTO mod_stats (moderator_id, reports_handled) 
        VALUES (%s, 1) 
        ON CONFLICT (moderator_id) 
        DO UPDATE SET reports_handled = mod_stats.reports_handled + 1
    """, (guild_id,)) # Тут ми адаптуємо під твою структуру таблиці
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"📈 [StatsManager] Оновлено {action_type} для PostgreSQL")

def get_stats(guild_id):
    conn = get_conn()
    cur = conn.cursor()
    
    # Використовуємо %s
    cur.execute("SELECT warnings_count, bans_count, reports_handled FROM mod_stats WHERE moderator_id = %s", (guild_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        return {"mute_issued": 0, "ban_issued": 0, "warn_issued": 0, "roles_issued": 0}
        
    return {
        "warn_issued": row[0],
        "ban_issued": row[1],
        "mute_issued": row[2],
        "roles_issued": 0
    }

def log_mod_action(guild_id, action_type, admin, target, reason):
    conn = get_conn()
    cur = conn.cursor()
    
    timestamp = datetime.now()
    target_id = target.id if hasattr(target, 'id') else None
    target_name = target.display_name if hasattr(target, 'display_name') else str(target)
    
    # Створюємо таблицю логів, якщо її немає (специфіка Postgres)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mod_actions (
            id SERIAL PRIMARY KEY,
            guild_id TEXT,
            action_type TEXT,
            admin_id BIGINT,
            admin_name TEXT,
            target_id BIGINT,
            target_name TEXT,
            reason TEXT,
            timestamp TIMESTAMP
        )
    """)

    # Замінюємо ? на %s (це виправляє помилку)
    cur.execute("""
        INSERT INTO mod_actions (guild_id, action_type, admin_id, admin_name, target_id, target_name, reason, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (str(guild_id), action_type, admin.id, admin.display_name, target_id, target_name, reason, timestamp))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"📝 [StatsManager] Лог {action_type} записано в PostgreSQL")

def load_logs(guild_id):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT action_type, admin_id, admin_name, target_id, target_name, reason, timestamp 
        FROM mod_actions WHERE guild_id = %s ORDER BY timestamp DESC LIMIT 100
    """, (str(guild_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    logs = []
    for r in rows:
        logs.append({
            "type": r[0], "admin_id": r[1], "admin_name": r[2],
            "target_id": r[3], "target_name": r[4], "reason": r[5],
            "timestamp": r[6].isoformat() if r[6] else None
        })
    return logs
    conn.commit()
    conn.close()
    print(f"📝 [StatsManager] Logged {action_type} for guild {guild_id_str}")

