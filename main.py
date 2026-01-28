import discord
from discord.ext import commands
from panel import ComplaintPanel
from moderation import Moderation
from roles import RoleRequest
from applications_publisher import AppPublisher
from config import TOKEN
from services.database import init_db
import asyncio

# Ініціалізація бази даних
# Тимчасово включаємо повне очищення для "чистого старту"
from reset_db import reset as reset_db
try:
    reset_db()
except Exception as e:
    print(f"⚠️ Reset skip/error: {e}")

init_db()
# Створюємо бота
# Ми НЕ використовуємо Intents.all(), щоб не вимагати Presence Intent (статус онлайн)
intents = discord.Intents.default()
intents.members = True          # Потрібно для видачі ролей
intents.message_content = True  # Потрібно для доказів (фото/відео)
bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# Подія готовності
@bot.event
async def on_ready():
    print("====================================")
    print(f"✅ Бот ЗАПУЩЕНИЙ як {bot.user}")
    print(f"🚀 Версія: 1.0.1 (Stats Fix Applied)")
    print("====================================")
    try:
        await bot.tree.sync()
        print("✅ Slash-команди синхронізовані")
    except Exception as e:
        print(f"❌ Помилка синхронізації slash-команд: {e}")

# -----------------------------
# Підключаємо модулі
async def setup():
    print("🔍 [DEBUG] Loading Cogs...")
    await bot.add_cog(ComplaintPanel(bot))
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(RoleRequest(bot))
    await bot.add_cog(AppPublisher(bot))
    print("✅ [DEBUG] All Cogs loaded.")

# -----------------------------
# Запуск
async def main():
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
