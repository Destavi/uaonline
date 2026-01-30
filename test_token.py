import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

async def test():
    if not TOKEN:
        print("Error: No TOKEN found in .env")
        return
    
    print(f"Testing token beginning with {TOKEN[:10]}...")
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bot {TOKEN}"}
        try:
            async with session.get("https://discord.com/api/v10/users/@me", headers=headers) as r:
                print(f"Status: {r.status}")
                body = await r.text()
                print(f"Body: {body}")
        except Exception as e:
            print(f"Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
