import discord
from discord.ext import commands
from discord import app_commands
import json, os, asyncio, io
from datetime import datetime
from config import REASONS_LIST, get_guild_config, load_all_guilds_config, DEFAULT_ALLOWED_ROLES
from discord.errors import Forbidden
from services.database import get_conn

def get_complaint_data(guild_id):
    """Отримати всі скарги гільдії з БД"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT local_id, status, user_id, author_nick, category, timestamp 
        FROM complaints WHERE guild_id = %s
    """, (guild_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    complaints = {}
    for r in rows:
        db_key = f"{r[4]}_{r[0]}"
        complaints[db_key] = {
            "status": r[1], "author": r[2], "author_nick": r[3],
            "category": r[4], "local_id": r[0], "timestamp": r[5].isoformat() if hasattr(r[5], 'isoformat') else str(r[5])
        }
    return {"complaints": complaints}

def get_next_complaint_id(guild_id, category):
    """Отримати наступний номер скарги для категорії"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO complaint_counters (guild_id, category, count) 
        VALUES (%s, %s, 1)
        ON CONFLICT (guild_id, category) DO UPDATE SET count = complaint_counters.count + 1
        RETURNING count
    """, (guild_id, category))
    count = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return count

def save_complaint(guild_id, data):
    """Зберегти нову скаргу в PostgreSQL"""
    conn = get_conn()
    cur = conn.cursor()
    # timestamp can be datetime object for direct insert
    ts = datetime.fromisoformat(data["timestamp"]) if isinstance(data["timestamp"], str) else data["timestamp"]
    
    cur.execute("""
        INSERT INTO complaints (guild_id, category, local_id, user_id, author_nick, target_name, reason, proof_url, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        guild_id, data["category"], data["local_id"], 
        data["author"], data["author_nick"], data.get("target_name", "Unknown"), 
        data.get("reason", ""), data.get("proof_url", ""),
        data["status"], ts
    ))
    conn.commit()
    cur.close()
    conn.close()

def update_complaint_status(db_key, status):
    """Оновити статус скарги в БД"""
    category, local_id = db_key.split('_')
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = %s WHERE category = %s AND local_id = %s", (status, category, int(local_id)))
    conn.commit()
    cur.close()
    conn.close()

class ComplaintPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Реєстрація контекстних меню
        self.ctx_menu_player = app_commands.ContextMenu(name="⚠️ Скарга на гравця", callback=ctx_report_player)
        self.ctx_menu_leader = app_commands.ContextMenu(name="⭐ Скарга на Лідера", callback=ctx_report_leader)
        self.ctx_menu_gov = app_commands.ContextMenu(name="🏛 Скарга на Держ.", callback=ctx_report_gov)
        self.bot.tree.add_command(self.ctx_menu_player)
        self.bot.tree.add_command(self.ctx_menu_leader)
        self.bot.tree.add_command(self.ctx_menu_gov)

    @commands.Cog.listener()
    async def on_ready(self):
        # Відновлення персистентних кнопок після перезапуску
        self.bot.add_view(ComplaintActions())
        # Додаємо LauncherView для стандартних категорій
        categories = ["players", "leaders", "gov", "family", "admin", "moderation"]
        for cat in categories:
            self.bot.add_view(ComplaintLauncherView(self.bot, cat))
        print("✅ Система скарг (Postgres) активована")

    async def generic_report_handler(self, interaction: discord.Interaction, member: discord.Member, category_key: str):
        guild_id = interaction.guild.id
        g_config = get_guild_config(guild_id)
        if not g_config:
            await interaction.response.send_message("❌ Конфігурація сервера не знайдена.", ephemeral=True)
            return

        category_cfg = g_config.get("complaint_config", {}).get(category_key)
        if not category_cfg:
            await interaction.response.send_message(f"❌ Категорія '{category_key}' не налаштована.", ephemeral=True)
            return

        target_channel_id = category_cfg["channel_id"]
        modal_title = category_cfg.get("modal_title", "Подати скаргу")
        allowed_roles = g_config.get("allowed_roles", DEFAULT_ALLOWED_ROLES)
        target_nick = member.display_name

        if category_key == "players":
            view = ReasonSelectView(self.bot, target_channel_id, modal_title, category_key, allowed_roles, default_nickname=target_nick)
            await interaction.response.send_message(f"📌 Скарга на гравця: {member.mention}\nОберіть причину:", view=view, ephemeral=True)
        else:
            await interaction.response.send_modal(ComplaintModal(self.bot, target_channel_id, modal_title, category_key, allowed_roles, default_nickname=target_nick))

class ComplaintLauncherView(discord.ui.View):
    def __init__(self, bot, category_key):
        super().__init__(timeout=None)
        self.bot = bot
        self.category_key = category_key
        btn = discord.ui.Button(label="📌 Подати скаргу", style=discord.ButtonStyle.secondary, custom_id=f"launch_complaint:{category_key}")
        btn.callback = self.submit_callback
        self.add_item(btn)

    async def submit_callback(self, interaction: discord.Interaction):
        try:
            g_config = get_guild_config(interaction.guild.id)
            if not g_config:
                await interaction.response.send_message("❌ Конфігурація не знайдена.", ephemeral=True)
                return
            
            category_cfg = g_config.get("complaint_config", {}).get(self.category_key)
            if not category_cfg:
                await interaction.response.send_message(f"❌ Категорія '{self.category_key}' не налаштована.", ephemeral=True)
                return
            
            target_channel_id = category_cfg["channel_id"]
            modal_title = category_cfg.get("modal_title", "Подати скаргу")
            allowed_roles = g_config.get("allowed_roles", DEFAULT_ALLOWED_ROLES)

            if self.category_key == "players":
                view = ReasonSelectView(self.bot, target_channel_id, modal_title, self.category_key, allowed_roles)
                await interaction.response.send_message("📌 Спочатку оберіть причину скарги зі списку:", view=view, ephemeral=True)
            else:
                await interaction.response.send_modal(ComplaintModal(self.bot, target_channel_id, modal_title, self.category_key, allowed_roles))
        except Exception as e:
            print(f"❌ Помилка LauncherView: {e}")
            await interaction.response.send_message("❌ Не вдалося відкрити форму.", ephemeral=True)

class ReasonSelectView(discord.ui.View):
    def __init__(self, bot, channel_id, modal_title, category_key, allowed_roles, default_nickname=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
        self.modal_title = modal_title
        self.category_key = category_key
        self.allowed_roles = allowed_roles
        self.default_nickname = default_nickname
        options = [discord.SelectOption(label=r, value=r) for r in REASONS_LIST[:25]]
        self.select = discord.ui.Select(placeholder="Оберіть причину...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ComplaintModal(self.bot, self.channel_id, self.modal_title, self.category_key, self.allowed_roles, selected_reason=self.select.values[0], default_nickname=self.default_nickname))

class ComplaintModal(discord.ui.Modal):
    your_nickname = discord.ui.TextInput(label="Ваш ігровий нікнейм", placeholder="Введіть свій нікнейм...")
    nickname = discord.ui.TextInput(label="Нік порушника", placeholder="Введіть нікнейм...")
    reason = discord.ui.TextInput(label="Опис ситуації", style=discord.TextStyle.long, placeholder="Опишіть ситуацію детально...")
    proof = discord.ui.TextInput(label="Докази", required=False, placeholder="Посилання на відео або скріншоти...")

    def __init__(self, bot, channel_id, title, category, allowed_roles, selected_reason=None, default_nickname=None):
        super().__init__(title=title)
        self.bot = bot
        self.channel_id = channel_id
        self.category = category
        self.allowed_roles = allowed_roles
        self.selected_reason = selected_reason
        if default_nickname: self.nickname.default = default_nickname

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            guild_id = interaction.guild.id
            current_count = get_next_complaint_id(guild_id, self.category)
            db_key = f"{self.category}_{current_count}"

            complaint_entry = {
                "status": "🟡 Відкрита",
                "author": interaction.user.id,
                "author_nick": self.your_nickname.value,
                "category": self.category,
                "local_id": current_count,
                "target_name": self.nickname.value,
                "reason": self.reason.value,
                "proof_url": self.proof.value,
                "timestamp": datetime.now()
            }
            save_complaint(guild_id, complaint_entry)

            embed = build_complaint_embed(current_count, self.nickname.value, self.reason.value, self.proof.value, interaction.user, self.your_nickname.value, db_key)
            await self.send_complaint_direct(interaction, embed, db_key)
        except Exception as e:
            print(f"❌ Помилка Modal Submit: {e}")
            await interaction.followup.send(f"❌ Помилка: {e}", ephemeral=True)

    async def send_complaint_direct(self, interaction: discord.Interaction, embed, db_key):
        try:
            channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            view = ComplaintActions(db_key, self.allowed_roles)
            if isinstance(channel, discord.ForumChannel):
                tag = next((t for t in channel.available_tags if "на розгляді" in t.name.lower()), None)
                await channel.create_thread(name=f"Скарга #{embed.title.split('#')[1].split(':')[0]}: {embed.fields[1].value}", content=f"Нова скарга від {interaction.user.mention}", embed=embed, view=view, applied_tags=[tag] if tag else [])
            else:
                await channel.send(content=f"Нова скарга від {interaction.user.mention}", embed=embed, view=view)
            await interaction.followup.send(f"✅ Вашу скаргу успішно подано.", ephemeral=True)
        except Exception as e:
            print(f"❌ Помилка Direct Send: {e}")
            await interaction.followup.send(f"❌ Помилка: {e}", ephemeral=True)

class ComplaintActions(discord.ui.View):
    def __init__(self, cid=None, allowed_roles=None):
        super().__init__(timeout=None)
        self.cid = cid
        self.allowed_roles = allowed_roles

    async def check_permissions(self, i: discord.Interaction):
        if i.user.guild_permissions.administrator: return True
        roles = self.allowed_roles
        if not roles:
            g_cfg = get_guild_config(i.guild.id)
            roles = g_cfg.get("allowed_roles", DEFAULT_ALLOWED_ROLES) if g_cfg else DEFAULT_ALLOWED_ROLES
        user_roles = [r.name.lower() for r in i.user.roles]
        if any(r.lower() in user_roles for r in roles): return True
        await i.response.send_message("❌ У вас недостатньо прав.", ephemeral=True)
        return False

    @discord.ui.button(label="✅ Прийняти", style=discord.ButtonStyle.success, custom_id="complaint_accept")
    async def accept(self, i: discord.Interaction, _):
        if not await self.check_permissions(i): return
        await self.set_status(i, "🟢 Прийнята")

    @discord.ui.button(label="❌ Відхилити", style=discord.ButtonStyle.danger, custom_id="complaint_reject")
    async def reject(self, i: discord.Interaction, _):
        if not await self.check_permissions(i): return
        await self.set_status(i, "🔴 Відхилена")

    @discord.ui.button(label="🔒 Закрити", style=discord.ButtonStyle.secondary, custom_id="complaint_close")
    async def close(self, i: discord.Interaction, _):
        if not await self.check_permissions(i): return
        try:
            cid = self.cid or i.message.embeds[0].footer.text.split("|")[1].split(":")[1].strip()
            category, lid = cid.split('_')
            conn = get_conn(); cur = conn.cursor()
            cur.execute("SELECT status FROM complaints WHERE category = %s AND local_id = %s", (category, int(lid)))
            row = cur.fetchone(); cur.close(); conn.close()
            if not row or row[0] == "🟡 Відкрита":
                await i.response.send_message("Спочатку розглянь скаргу.", ephemeral=True)
                return
            await i.response.defer(ephemeral=True)
            update_complaint_status(cid, "⚫ Закрита")
            emb = i.message.embeds[0]
            emb.set_field_at(4, name="📌 Статус", value="⚫ Закрита", inline=False)
            await i.message.edit(embed=emb, view=None)
            if isinstance(i.channel, discord.Thread): await i.channel.edit(archived=True, locked=True)
            await i.followup.send("🔒 Закрито", ephemeral=True)
        except Exception as e: await i.followup.send(f"❌ Помилка: {e}", ephemeral=True)

    async def set_status(self, i: discord.Interaction, status):
        await i.response.defer(ephemeral=True)
        cid = self.cid or i.message.embeds[0].footer.text.split("|")[1].split(":")[1].strip()
        update_complaint_status(cid, status)
        emb = i.message.embeds[0]
        emb.set_field_at(4, name="📌 Статус", value=status, inline=False)
        await i.message.edit(embed=emb)
        await i.followup.send(f"Статус: {status}", ephemeral=True)

def build_complaint_embed(cid, nick, reason, proof, author, sub_nick, db_key):
    e = discord.Embed(title=f"🚨 Скарга #{cid}", color=discord.Color.red())
    e.add_field(name="👤 Подав", value=f"{sub_nick} ({author.mention})", inline=False)
    e.add_field(name="👤 Порушник", value=nick, inline=False)
    e.add_field(name="📄 Опис", value=reason, inline=False)
    e.add_field(name="🔗 Докази", value=proof or "Не надано", inline=False)
    e.add_field(name="📌 Статус", value="🟡 Відкрита", inline=False)
    e.set_footer(text=f"ID автора: {author.id} | key:{db_key}")
    e.timestamp = datetime.now()
    return e

async def ctx_report_player(interaction: discord.Interaction, member: discord.Member):
    cog = interaction.client.get_cog("ComplaintPanel")
    if cog:
        await cog.generic_report_handler(interaction, member, "players")
    else:
        await interaction.response.send_message("❌ Система скарг не активна.", ephemeral=True)

async def ctx_report_leader(interaction: discord.Interaction, member: discord.Member):
    cog = interaction.client.get_cog("ComplaintPanel")
    if cog:
        await cog.generic_report_handler(interaction, member, "leaders")
    else:
        await interaction.response.send_message("❌ Система скарг не активна.", ephemeral=True)

async def ctx_report_gov(interaction: discord.Interaction, member: discord.Member):
    cog = interaction.client.get_cog("ComplaintPanel")
    if cog:
        await cog.generic_report_handler(interaction, member, "gov")
    else:
        await interaction.response.send_message("❌ Система скарг не активна.", ephemeral=True)
