import discord
from discord.ext import commands
from panel import ComplaintPanel
from moderation import Moderation
from roles import RoleRequest
from applications_publisher import AppPublisher
from config import TOKEN
from services.database import init_db
import asyncio
from flask import Flask
from threading import Thread
import os

# --- КЕЕР ALIVE СЕРВЕР ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "✅ Бот UA Online 05 працює!"

def run():
    # Render використовує порт 8080 або динамічний PORT з оточення
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
# ------------------------------------

# Ініціалізація бази даних
init_db()

# Створюємо бота
intents = discord.Intents.default()
intents.members = True          
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("====================================")
    print(f"✅ Бот ЗАПУЩЕНИЙ як {bot.user}")
    print(f"🚀 Версія: 1.1.0 (Render Keep-Alive)")
    print("====================================")
    try:
        await bot.tree.sync()
        print("✅ Slash-команди синхронізовані")
    except Exception as e:
        print(f"❌ Помилка синхронізації slash-команд: {e}")

async def setup():
    print("🔍 [DEBUG] Loading Cogs...")
    await bot.add_cog(ComplaintPanel(bot))
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(RoleRequest(bot))
    await bot.add_cog(AppPublisher(bot))
    print("✅ [DEBUG] All Cogs loaded.")

async def main():
    # Запускаємо веб-сервер, щоб Render не присипляв бота
    keep_alive() 
    
    async with bot:
        await setup()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот зупинений вручну")
    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА: {e}")
