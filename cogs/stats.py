from discord.ext import commands

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Тут можна буде додати статистику модераторів
    @commands.command()
    async def weekly_stats(self, ctx):
        await ctx.send("Тут буде статистика за тиждень")

async def setup(bot):
    await bot.add_cog(Stats(bot))
