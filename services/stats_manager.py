from services.database import get_conn
from datetime import datetime

print(f"📊 [StatsManager] Initialized with PostgreSQL backend")

def update_stat_v2(guild_id, action_type, moderator_id=None):
    print(f"DEBUG: update_stat called with ({guild_id}, {action_type}, {moderator_id})")
    """
    Updates both global server stats and per-moderator stats.
    action_type: e.g. 'ban_issued', 'mute_issued', 'warn_issued', etc.
    """
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # 1. Update Global Server Stats
        cur.execute("""
            INSERT INTO server_stats (guild_id, stat_key, value) 
            VALUES (%s, %s, 1)
            ON CONFLICT(guild_id, stat_key) DO UPDATE SET value = server_stats.value + 1
        """, (guild_id, action_type))
        
        # 2. Update Moderator Personal Stats
        if moderator_id:
            # Map specific issued/removed actions to generalized stats if needed, 
            # but here we use the action_type as provided to match the mod_stats schema.
            cur.execute("""
                INSERT INTO mod_stats (guild_id, user_id, action_type, count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT(guild_id, user_id, action_type) 
                DO UPDATE SET count = mod_stats.count + 1
            """, (guild_id, moderator_id, action_type))
        
        conn.commit()
        print(f"📈 [StatsManager] Updated '{action_type}' for guild {guild_id}")
    except Exception as e:
        conn.rollback()
        print(f"❌ [StatsManager ERROR] Failed to update stat: {e}")
    finally:
        cur.close()
        conn.close()

def get_stats(guild_id):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT stat_key, value FROM server_stats WHERE guild_id = %s", (guild_id,))
    rows = cur.fetchall()
    cur.close()
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
    
    cur.execute("""
        SELECT action_type, admin_id, admin_name, target_id, target_name, reason, timestamp 
        FROM mod_actions WHERE guild_id = %s
        ORDER BY timestamp DESC
    """, (guild_id,))
    rows = cur.fetchall()
    cur.close()
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
            "timestamp": r[6].isoformat() if hasattr(r[6], 'isoformat') else str(r[6])
        })
    return logs

def log_mod_action(guild_id, action_type, admin, target, reason):
    conn = get_conn()
    cur = conn.cursor()
    
    timestamp = datetime.now()
    target_id = str(target.id) if hasattr(target, 'id') else str(target)
    target_name = target.display_name if hasattr(target, 'display_name') else str(target)
    
    try:
        cur.execute("""
            INSERT INTO mod_actions (guild_id, action_type, admin_id, admin_name, target_id, target_name, reason, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (guild_id, action_type, admin.id, admin.display_name, target_id, target_name, reason, timestamp))
        
        conn.commit()
        print(f"📝 [StatsManager] Logged {action_type} for guild {guild_id}")
    except Exception as e:
        conn.rollback()
        print(f"❌ [StatsManager ERROR] Failed to log mod action: {e}")
    finally:
        cur.close()
        conn.close()
