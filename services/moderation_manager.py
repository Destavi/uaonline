from services.database import get_conn
from datetime import datetime

def add_warning(guild_id, user_id, reason, admin_name):
    conn = get_conn()
    cur = conn.cursor()
    
    # Get the next local_id for this user in this guild
    cur.execute("SELECT COALESCE(MAX(local_id), 0) FROM warnings WHERE guild_id = %s AND user_id = %s", (guild_id, user_id))
    max_id = cur.fetchone()[0]
    next_id = max_id + 1
    
    cur.execute("""
        INSERT INTO warnings (guild_id, user_id, local_id, reason, admin_name, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING local_id
    """, (guild_id, user_id, next_id, reason, admin_name, datetime.now()))
    
    conn.commit()
    cur.close()
    conn.close()
    return next_id

def get_warnings(guild_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT local_id, reason, admin_name, timestamp 
        FROM warnings 
        WHERE guild_id = %s AND user_id = %s
        ORDER BY local_id ASC
    """, (guild_id, user_id))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    warnings = []
    for r in rows:
        warnings.append({
            "id": r[0],
            "reason": r[1],
            "admin": r[2],
            "timestamp": r[3].isoformat() if hasattr(r[3], 'isoformat') else str(r[3])
        })
    return warnings

def delete_warning(guild_id, user_id, local_id):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM warnings 
        WHERE guild_id = %s AND user_id = %s AND local_id = %s
    """, (guild_id, user_id, local_id))
    
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted

def add_temp_ban(guild_id, user_id, unban_time):
    conn = get_conn()
    cur = conn.cursor()
    
    # unban_time is expected to be a datetime object or isoformat string
    if isinstance(unban_time, str):
        unban_time = datetime.fromisoformat(unban_time)
        
    cur.execute("""
        INSERT INTO temp_bans (guild_id, user_id, unban_time)
        VALUES (%s, %s, %s)
        ON CONFLICT (guild_id, user_id) DO UPDATE SET unban_time = EXCLUDED.unban_time
    """, (guild_id, user_id, unban_time))
    
    conn.commit()
    cur.close()
    conn.close()

def remove_temp_ban(guild_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM temp_bans WHERE guild_id = %s AND user_id = %s", (guild_id, user_id))
    
    conn.commit()
    cur.close()
    conn.close()

def get_expired_temp_bans():
    conn = get_conn()
    cur = conn.cursor()
    
    now = datetime.now()
    cur.execute("SELECT guild_id, user_id FROM temp_bans WHERE unban_time <= %s", (now,))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
