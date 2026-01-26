import sys
import os

# Add the project root and services directory to path
sys.path.append(os.getcwd())

from services.stats_manager import update_stat, log_mod_action, load_stats, load_logs

class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.display_name = name

def test():
    guild_id = 123456789
    admin = MockUser(987654321, "AdminTest")
    target = MockUser(111222333, "TargetTest")
    
    print(f"Current working directory: {os.getcwd()}")
    
    print("Testing update_stat...")
    update_stat(guild_id, "ban_issued")
    update_stat(guild_id, "mute_issued")
    
    print("Testing log_mod_action...")
    log_mod_action(guild_id, "ban", admin, target, "Test reason")
    log_mod_action(guild_id, "mute", admin, target, "Test reason")
    
    stats = load_stats()
    logs = load_logs(guild_id)
    
    print(f"Stats: {stats}")
    print(f"Logs: {logs}")
    
    if os.path.exists("stats.json"):
        print("✅ stats.json exists")
    else:
        print("❌ stats.json NOT found")
        
    if os.path.exists("mod_logs.json"):
        print("✅ mod_logs.json exists")
    else:
        print("❌ mod_logs.json NOT found")

if __name__ == "__main__":
    test()
