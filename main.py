import discord
from discord.ext import commands
from panel import ComplaintPanel
from moderation import Moderation
from roles import RoleRequest
from applications_publisher import AppPublisher
from config import TOKEN
from services.database import init_db
import asyncio
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Ініціалізація бази даних
init_db()

intents = discord.Intents.default()
intents.members = True          
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

# Простий HTTP-сервер для Health Check (потрібно для Render)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return # Вимикаємо зайве логування запитів

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"📡 Health Check сервер запущений на порту {port}")
    server.serve_forever()

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
    # Запускаємо health check в окремому потоці
    threading.Thread(target=run_health_check, daemon=True).start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот зупинений")
    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА: {e}")

