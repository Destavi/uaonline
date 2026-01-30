import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add the project root to path
sys.path.append(os.getcwd())

from services.stats_manager import update_stat, log_mod_action, get_stats, load_logs
from services.database import init_db

class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.display_name = name

def test():
    guild_id = 123456789
    admin = MockUser(987654321, "AdminTest")
    target = MockUser(111222333, "TargetTest")
    
    print("🐘 Initializing PostgreSQL database...")
    try:
        init_db()
        print("✅ Database initialized.")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return

    print("Testing update_stat...")
    update_stat(guild_id, "ban_issued", admin.id)
    update_stat(guild_id, "mute_issued", admin.id)
    
    print("Testing log_mod_action...")
    log_mod_action(guild_id, "ban", admin, target, "Test reason")
    log_mod_action(guild_id, "mute", admin, target, "Test reason")
    
    print("Retrieving stats...")
    stats = get_stats(guild_id)
    logs = load_logs(guild_id)
    
    print(f"Stats: {stats}")
    print(f"Last 2 Logs: {logs[:2]}")
    
    print("\n🏁 Test finished.")

if __name__ == "__main__":
    test()
