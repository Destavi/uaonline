import discord
from discord.ext import commands
from panel import ComplaintPanel
from moderation import Moderation
from roles import RoleRequest
from applications_publisher import AppPublisher
from config import TOKEN
from services.database import init_db, get_conn
import asyncio

# --- ТИМЧАСОВИЙ БЛОК ОЧИЩЕННЯ БАЗИ ---
def drop_all_tables():
    print("⚠️ [RESET] Починаю очищення бази...")
    try:
        conn = get_conn()
        cur = conn.cursor()
        tables = [
            "complaints", "complaint_counters", "mod_stats", 
            "mod_actions", "server_stats", "warnings", 
            "temp_bans", "guild_configs"
        ]
        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        conn.commit()
        cur.close(); conn.close()
        print("✅ [RESET] База очищена.")
    except Exception as e:
        print(f"❌ [RESET] Помилка: {e}")

# Запустити очищення (один раз)
drop_all_tables()
# ---------------------------------------

# Ініціалізація бази даних (створення нових таблиць)
init_db()

intents = discord.Intents.default()
intents.members = True          
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("====================================")
    print(f"✅ Бот ЗАПУЩЕНИЙ як {bot.user}")
    print("====================================")
    try:
        await bot.tree.sync()
        print("✅ Slash-команди синхронізовані")
    except Exception as e:
        print(f"❌ Помилка синхронізації slash-команд: {e}")

async def setup():
    await bot.add_cog(ComplaintPanel(bot))
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(RoleRequest(bot))
    await bot.add_cog(AppPublisher(bot))

async def main():
    async with bot:
        await setup()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот зупинений")
    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА: {e}")
