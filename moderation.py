import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import re
from datetime import datetime, timedelta
from config import get_guild_config, DEFAULT_ALLOWED_ROLES, MUTE_ROLES, BAN_ROLES, UNBAN_ROLES
from services.database import get_conn # Використовуємо наше підключення
from services.moderation_logger import send_mod_log

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_mod_permissions(self, interaction: discord.Interaction, allowed_roles):
        if interaction.user.guild_permissions.administrator:
            return True
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in allowed_roles]
        if any(role_name in allowed_roles_lower for role_name in user_role_names):
            return True
        await interaction.response.send_message("❌ У вас недостатньо прав.", ephemeral=True)
        return False

    def parse_duration(self, duration_str: str):
        units = {'м': 'minutes', 'г': 'hours', 'д': 'days', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
        match = re.match(r"(\d+)([мгдmhd])", duration_str.lower())
        if not match: return None
        amount, unit = match.groups()
        return timedelta(**{units[unit]: int(amount)})

    @app_commands.command(name="mute", description="Видати таймаут (мут) користувачу")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Не вказана"):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        
        if any(role.name == "Куратор Держ." for role in member.roles):
            return await interaction.response.send_message("❌ Неможливо замутити Куратора Держ.", ephemeral=True)

        delta = self.parse_duration(duration)
        if not delta:
            return await interaction.response.send_message("❌ Невірний формат часу.", ephemeral=True)

        await interaction.response.defer()
        try:
            await member.timeout(delta, reason=f"{reason} | Адмін: {interaction.user.display_name}")
            
            # ЗАПИС У POSTGRESQL (Виправлений синтаксис %s)
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO mod_stats (moderator_id, reports_handled) 
                VALUES (%s, 1) 
                ON CONFLICT (moderator_id) 
                DO UPDATE SET reports_handled = mod_stats.reports_handled + 1
            """, (interaction.user.id,))
            conn.commit()
            cur.close()
            conn.close()

            embed = discord.Embed(title="🔇 Таймаут (Мут)", color=discord.Color.orange())
            embed.add_field(name="Користувач", value=member.mention)
            embed.add_field(name="Тривалість", value=duration)
            embed.add_field(name="Причина", value=reason)
            embed.add_field(name="Адміністратор", value=interaction.user.mention)
            embed.timestamp = datetime.now()
            
            await interaction.followup.send(embed=embed)
            await send_mod_log(self.bot, interaction.guild, "Mute", interaction.user, member, reason, f"Тривалість: {duration}")

        except Exception as e:
            await interaction.followup.send(f"❌ Помилка: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Забанити користувача")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, duration: str = None, reason: str = "Не вказана"):
        if not await self.check_mod_permissions(interaction, BAN_ROLES): return
        
        if any(role.name == "Куратор Держ." for role in member.roles):
            return await interaction.response.send_message("❌ Неможливо забанити Куратора Держ.", ephemeral=True)

        await interaction.response.defer()
        try:
            ban_reason = f"{reason} | Адмін: {interaction.user.display_name}"
            await member.ban(reason=ban_reason)
            
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO mod_stats (moderator_id, bans_count) 
                VALUES (%s, 1) 
                ON CONFLICT (moderator_id) 
                DO UPDATE SET bans_count = mod_stats.bans_count + 1
            """, (interaction.user.id,))
            conn.commit()
            cur.close()
            conn.close()

            embed = discord.Embed(title="🔨 Бан", color=discord.Color.red())
            embed.add_field(name="Користувач", value=f"{member.mention}")
            embed.add_field(name="Причина", value=reason)
            embed.timestamp = datetime.now()
            
            await interaction.followup.send(embed=embed)
            await send_mod_log(self.bot, interaction.guild, "Ban", interaction.user, member, reason)
        except Exception as e:
            await interaction.followup.send(f"❌ Помилка: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
