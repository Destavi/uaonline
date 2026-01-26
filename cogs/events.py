from discord.ext import commands
import discord

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role = discord.utils.get(member.guild.roles, name="Гравець 🧑‍🎄")
        if role:
            await member.add_roles(role)

async def setup(bot):
    await bot.add_cog(Events(bot))
