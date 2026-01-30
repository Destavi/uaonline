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
import math

import random

# Ініціалізація бази даних
init_db()

# Пряме підключення без проксі
current_proxy = None

# Функція для отримання публічної IP
async def get_public_ip():
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipify.org?format=json', timeout=5) as resp:
                data = await resp.json()
                return data.get('ip', 'Unknown')
    except:
        return 'Unknown'

current_public_ip = "Визначається..."
last_error = None

intents = discord.Intents.default()
intents.members = True          
intents.message_content = True  

# Функція для створення екземпляра бота
def create_bot():
    return commands.Bot(command_prefix="!", intents=intents)

bot = create_bot()

# Простий HTTP-сервер для Health Check
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        status_color = "#3ba55c" if bot.is_ready() else "#faa61a"
        status_text = "ОНЛАЙН" if bot.is_ready() else "ПІДКЛЮЧЕННЯ..."
        bot_name = str(bot.user) if bot.user else "Discord Bot"
        
        # Перевірка на NaN для latency
        raw_latency = bot.latency
        if raw_latency is None or math.isnan(raw_latency):
            latency = 0
        else:
            latency = round(raw_latency * 1000)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>UA ONLINE | Status</title>
            <style>
                body {{
                    background-color: #0f172a;
                    color: white;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    overflow: hidden;
                }}
                .card {{
                    background: rgba(30, 41, 59, 0.7);
                    backdrop-filter: blur(10px);
                    padding: 40px;
                    border-radius: 20px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                    text-align: center;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    width: 380px;
                }}
                .status-dot {{
                    height: 12px;
                    width: 12px;
                    background-color: {status_color};
                    border-radius: 50%;
                    display: inline-block;
                    margin-right: 8px;
                    box-shadow: 0 0 10px {status_color};
                }}
                h1 {{ font-size: 24px; margin-bottom: 5px; color: #f8fafc; }}
                p {{ color: #94a3b8; margin-top: 5px; font-size: 14px; }}
                .badge {{
                    background: {status_color}22;
                    color: {status_color};
                    padding: 5px 15px;
                    border-radius: 50px;
                    font-size: 14px;
                    font-weight: bold;
                    border: 1px solid {status_color}44;
                }}
                .stats {{
                    margin-top: 25px;
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 10px;
                }}
                .stat-item {{
                    background: rgba(15, 23, 42, 0.5);
                    padding: 10px;
                    border-radius: 10px;
                    font-size: 13px;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                }}
                .proxy-info {{
                    color: #64748b;
                    font-size: 11px;
                    margin-top: 15px;
                    word-break: break-all;
                }}
                .error-box {{
                    margin-top: 15px;
                    color: #f87171;
                    font-size: 11px;
                    background: rgba(239, 68, 68, 0.1);
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid rgba(239, 68, 68, 0.2);
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>{bot_name}</h1>
                <p>UA ONLINE Monitoring System</p>
                <div style="margin-top: 20px;">
                    <span class="badge">
                        <span class="status-dot"></span>
                        {status_text}
                    </span>
                </div>
                <div class="stats">
                    <div class="stat-item">
                        Затримка: <span style="color: #60a5fa;">{latency}ms</span>
                    </div>
                    <div class="stat-item">
                        Ваша IP: <span style="color: #fbbf24;">{current_public_ip}</span>
                    </div>
                    <div class="stat-item">
                        Мережа: <span style="color: #818cf8;">{"Proxy Active" if current_proxy else "Direct Connect"}</span>
                    </div>
                </div>
                {f'<div class="error-box">Помилка: {last_error}</div>' if last_error else ''}
                <div class="proxy-info">
                    {f"Proxy: {current_proxy}" if current_proxy else "Запущено без проксі"}
                </div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        return # Вимикаємо зайве логування

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"📡 Health Check сервер запущений на порту {port}")
    server.serve_forever()

@bot.event
async def on_ready():
    print("====================================")
    print(f"✅ Бот ЗАПУЩЕНИЙ як {bot.user}")
    print(f"📡 ID: {bot.user.id}")
    print(f"🌐 Proxy: {current_proxy if current_proxy else 'Direct'}")
    print("====================================")

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Синхронізація slash-команд (тільки для власника)"""
    try:
        fmt = await bot.tree.sync()
        await ctx.send(f"✅ Синхронізовано {len(fmt)} команд.")
    except Exception as e:
        await ctx.send(f"❌ Помилка: {e}")

async def setup():
    # Очищення існуючих когів перед додаванням (для уникнення дублікатів при рестарті)
    cogs_to_remove = list(bot.cogs.keys())
    for cog_name in cogs_to_remove:
        await bot.remove_cog(cog_name)
    
    await bot.add_cog(ComplaintPanel(bot))
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(RoleRequest(bot))
    await bot.add_cog(AppPublisher(bot))

async def main():
    global current_public_ip, last_error
    current_public_ip = await get_public_ip()
    try:
        async with bot:
            await setup()
            await bot.start(TOKEN)
    except discord.errors.HTTPException as e:
        last_error = f"HTTP {e.status}: {e.text}"
        if e.status == 429:
            print(f"❌ КРИТИЧНА ПОМИЛКА: Rate Limited (429). Очікування 60 секунд...")
            await asyncio.sleep(60)
            raise e 
        else:
            raise e
    except Exception as e:
        last_error = str(e)
        raise e

if __name__ == "__main__":
    # Запускаємо health check в окремому потоці
    threading.Thread(target=run_health_check, daemon=True).start()
    
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("🛑 Бот зупинений користувачем")
            break
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print("❌ Rate Limited (429) при прямому підключенні. Очікування 5 хвилин...")
                import time
                time.sleep(300) 
                continue
            else:
                print(f"❌ Помилка HTTP: {e}")
                import time
                time.sleep(10)
        except Exception as e:
            last_error = str(e)
            print(f"❌ КРИТИЧНА ПОМИЛКА: {e}")
            import time
            time.sleep(5)

