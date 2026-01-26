from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Тут додамо команди MUT / BAN / WARN
    @commands.command()
    async def warn(self, ctx, member: commands.MemberConverter, *, reason=None):
        await ctx.send(f"{member} отримав попередження. Причина: {reason}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
