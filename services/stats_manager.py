from services.database import get_conn
from datetime import datetime

print(f"📊 [StatsManager] Initialized with SQLite backend")

def update_stat(guild_id, action_type):
    conn = get_conn()
    cur = conn.cursor()
    guild_id_str = str(guild_id)
    
    cur.execute("""
        INSERT INTO mod_stats (guild_id, stat_key, value) 
        VALUES (?, ?, 1)
        ON CONFLICT(guild_id, stat_key) DO UPDATE SET value = value + 1
    """, (guild_id_str, action_type))
    
    conn.commit()
    conn.close()
    print(f"📈 [StatsManager] Updated {action_type} for guild {guild_id_str}")

def get_stats(guild_id):
    conn = get_conn()
    cur = conn.cursor()
    guild_id_str = str(guild_id)
    
    cur.execute("SELECT stat_key, value FROM mod_stats WHERE guild_id = ?", (guild_id_str,))
    rows = cur.fetchall()
    conn.close()
    
    stats = {
        "mute_issued": 0, "mute_removed": 0,
        "ban_issued": 0, "ban_removed": 0,
        "warn_issued": 0, "warn_removed": 0,
        "roles_issued": 0, "roles_removed": 0
    }
    for key, val in rows:
        if key in stats:
            stats[key] = val
    return stats

def load_logs(guild_id):
    conn = get_conn()
    cur = conn.cursor()
    guild_id_str = str(guild_id)
    
    cur.execute("""
        SELECT action_type, admin_id, admin_name, target_id, target_name, reason, timestamp 
        FROM mod_actions WHERE guild_id = ?
    """, (guild_id_str,))
    rows = cur.fetchall()
    conn.close()
    
    logs = []
    for r in rows:
        logs.append({
            "type": r[0],
            "admin_id": r[1],
            "admin_name": r[2],
            "target_id": r[3],
            "target_name": r[4],
            "reason": r[5],
            "timestamp": r[6]
        })
    return logs

def log_mod_action(guild_id, action_type, admin, target, reason):
    conn = get_conn()
    cur = conn.cursor()
    guild_id_str = str(guild_id)
    
    timestamp = datetime.now().isoformat()
    target_id = str(target.id) if hasattr(target, 'id') else str(target)
    target_name = target.display_name if hasattr(target, 'display_name') else str(target)
    
    cur.execute("""
        INSERT INTO mod_actions (guild_id, action_type, admin_id, admin_name, target_id, target_name, reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (guild_id_str, action_type, admin.id, admin.display_name, target_id, target_name, reason, timestamp))
    
    conn.commit()
    conn.close()
    print(f"📝 [StatsManager] Logged {action_type} for guild {guild_id_str}")
