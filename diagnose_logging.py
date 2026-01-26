import os
import sys

def check_files():
    files_to_check = [
        "main.py",
        "moderation.py",
        "roles.py",
        "guilds_config.json",
        "services/moderation_logger.py"
    ]
    
    print("--- Diagnostic Report ---")
    for file_path in files_to_check:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✅ FOUND: {file_path} ({size} bytes)")
            # Check for specific strings in files
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if "send_mod_log" in content:
                    print(f"  ✨ contains 'send_mod_log'")
                else:
                    print(f"  ❌ MISSING 'send_mod_log'!")
        else:
            print(f"❌ NOT FOUND: {file_path}")

    print("\n--- Python Path ---")
    print(sys.path)

if __name__ == "__main__":
    check_files()
