import discord
from discord.ext import commands
from discord import app_commands
import json, os, asyncio, io
from datetime import datetime
from config import REASONS_LIST, get_guild_config, load_all_guilds_config, DEFAULT_ALLOWED_ROLES
from discord.errors import Forbidden
from services.database import get_conn

def get_complaint_data(guild_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT db_key, status, author_id, author_nick, category, local_id, timestamp FROM complaints WHERE guild_id = %s", (str(guild_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    complaints = {}
    for r in rows:
        complaints[r[0]] = {"status": r[1], "author": r[2], "author_nick": r[3], "category": r[4], "local_id": r[5], "timestamp": r[6]}
    return {"complaints": complaints}

def get_next_complaint_id(guild_id, category):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO complaint_counters (guild_id, category, count) VALUES (%s, %s, 1)
        ON CONFLICT(guild_id, category) DO UPDATE SET count = complaint_counters.count + 1 RETURNING count
    """, (str(guild_id), category))
    count = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return count

def save_complaint(guild_id, db_key, data):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO complaints (db_key, guild_id, category, local_id, author_id, author_nick, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT(db_key) DO UPDATE SET status = EXCLUDED.status
    """, (db_key, str(guild_id), data["category"], data["local_id"], data["author"], data["author_nick"], data["status"], data["timestamp"]))
    conn.commit(); cur.close(); conn.close()

def update_complaint_status(db_key, status):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = %s WHERE db_key = %s", (status, db_key))
    conn.commit(); cur.close(); conn.close()

class ComplaintPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu_player = app_commands.ContextMenu(name="⚠️ Скарга на гравця", callback=self.ctx_report_player)
        self.ctx_menu_leader = app_commands.ContextMenu(name="⭐ Скарга на Лідера", callback=self.ctx_report_leader)
        self.ctx_menu_gov = app_commands.ContextMenu(name="🏛 Скарга на Держ.", callback=self.ctx_report_gov)
        self.bot.tree.add_command(self.ctx_menu_player)
        self.bot.tree.add_command(self.ctx_menu_leader)
        self.bot.tree.add_command(self.ctx_menu_gov)

    @commands.Cog.listener()
    async def on_ready(self):
        configs = load_all_guilds_config()
        unique_categories = set()
        for g_cfg in configs.values():
            unique_categories.update(g_cfg.get("complaint_config", {}).keys())
        for key in unique_categories:
            self.bot.add_view(ComplaintLauncherView(self.bot, key))
        self.bot.add_view(ComplaintActions())
        print(f"✅ Персистентні панелі скарг активовані")

    async def ctx_report_player(self, interaction: discord.Interaction, member: discord.Member):
        await self.generic_report_handler(interaction, member, "players")

    async def ctx_report_leader(self, interaction: discord.Interaction, member: discord.Member):
        await self.generic_report_handler(interaction, member, "leaders")

    async def ctx_report_gov(self, interaction: discord.Interaction, member: discord.Member):
        await self.generic_report_handler(interaction, member, "gov")

    async def generic_report_handler(self, interaction: discord.Interaction, member: discord.Member, category_key: str):
        g_config = get_guild_config(interaction.guild.id)
        category_cfg = g_config.get("complaint_config", {}).get(category_key)
        if category_key == "players":
            view = ReasonSelectView(self.bot, category_cfg["channel_id"], category_cfg.get("modal_title"), category_key, g_config.get("allowed_roles"), member.display_name)
            await interaction.response.send_message(f"📌 Скарга на гравця: {member.mention}", view=view, ephemeral=True)
        else:
            await interaction.response.send_modal(ComplaintModal(self.bot, category_cfg["channel_id"], category_cfg.get("modal_title"), category_key, g_config.get("allowed_roles"), default_nickname=member.display_name))

class ComplaintLauncherView(discord.ui.View):
    def __init__(self, bot, category_key):
        super().__init__(timeout=None)
        self.bot, self.category_key = bot, category_key
        btn = discord.ui.Button(label="📌 Подати скаргу", style=discord.ButtonStyle.secondary, custom_id=f"launch_complaint:{category_key}")
        btn.callback = self.submit_callback
        self.add_item(btn)

    async def submit_callback(self, interaction: discord.Interaction):
        g_config = get_guild_config(interaction.guild.id)
        cfg = g_config.get("complaint_config", {}).get(self.category_key)
        if self.category_key == "players":
            await interaction.response.send_message("📌 Оберіть причину:", view=ReasonSelectView(self.bot, cfg["channel_id"], cfg.get("modal_title"), self.category_key, g_config.get("allowed_roles")), ephemeral=True)
        else:
            await interaction.response.send_modal(ComplaintModal(self.bot, cfg["channel_id"], cfg.get("modal_title"), self.category_key, g_config.get("allowed_roles")))

class ReasonSelectView(discord.ui.View):
    def __init__(self, bot, channel_id, modal_title, category_key, allowed_roles, default_nickname=None):
        super().__init__(timeout=60)
        self.bot, self.channel_id, self.modal_title, self.category_key, self.allowed_roles, self.default_nickname = bot, channel_id, modal_title, category_key, allowed_roles, default_nickname
        options = [discord.SelectOption(label=r, value=r) for r in REASONS_LIST[:25]]
        self.select = discord.ui.Select(placeholder="Оберіть причину...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ComplaintModal(self.bot, self.channel_id, self.modal_title, self.category_key, self.allowed_roles, selected_reason=self.select.values[0], default_nickname=self.default_nickname))

class ComplaintModal(discord.ui.Modal):
    your_nickname = discord.ui.TextInput(label="Ваш ігровий нікнейм")
    nickname = discord.ui.TextInput(label="Нік порушника")
    reason = discord.ui.TextInput(label="Опис ситуації", style=discord.TextStyle.long)
    proof = discord.ui.TextInput(label="Докази", required=False)

    def __init__(self, bot, channel_id, title, category, allowed_roles, selected_reason=None, default_nickname=None):
        super().__init__(title=title)
        self.bot, self.channel_id, self.category, self.allowed_roles = bot, channel_id, category, allowed_roles
        if selected_reason: self.reason.default = selected_reason
        if default_nickname: self.nickname.default = default_nickname

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        current_count = get_next_complaint_id(interaction.guild.id, self.category)
        db_key = f"{self.category}_{current_count}"
        entry = {"status": "🟡 Відкрита", "author": interaction.user.id, "author_nick": self.your_nickname.value, "category": self.category, "local_id": current_count, "timestamp": datetime.now().isoformat()}
        save_complaint(interaction.guild.id, db_key, entry)
        embed = build_complaint_embed(current_count, self.nickname.value, self.reason.value, self.proof.value, interaction.user, self.your_nickname.value, db_key)
        channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
        view = ComplaintActions(db_key, self.allowed_roles)
        if isinstance(channel, discord.ForumChannel):
            tag = next((t for t in channel.available_tags if "на розгляді" in t.name.lower()), None)
            await channel.create_thread(name=f"Скарга #{current_count}: {self.nickname.value}", embed=embed, view=view, applied_tags=[tag] if tag else [])
        else:
            await channel.send(content=f"Нова скарга від {interaction.user.mention}", embed=embed, view=view)
        await interaction.followup.send("✅ Скаргу подано!", ephemeral=True)

class ComplaintActions(discord.ui.View):
    def __init__(self, db_key=None, allowed_roles=None):
        super().__init__(timeout=None)
        self.db_key, self.allowed_roles = db_key, allowed_roles

    async def check_permissions(self, i: discord.Interaction):
        if i.user.guild_permissions.administrator: return True
        roles = self.allowed_roles or get_guild_config(i.guild.id).get("allowed_roles", DEFAULT_ALLOWED_ROLES)
        user_roles = [r.name.lower() for r in i.user.roles]
        if any(r.lower() in user_roles for r in roles): return True
        await i.response.send_message("❌ Немає прав.", ephemeral=True); return False

    @discord.ui.button(label="✅ Прийняти", style=discord.ButtonStyle.success, custom_id="complaint_accept")
    async def accept(self, i: discord.Interaction, _):
        if await self.check_permissions(i): await self.set_status(i, "🟢 Прийнята")

    @discord.ui.button(label="❌ Відхилити", style=discord.ButtonStyle.danger, custom_id="complaint_reject")
    async def reject(self, i: discord.Interaction, _):
        if await self.check_permissions(i): await self.set_status(i, "🔴 Відхилена")

    async def set_status(self, i: discord.Interaction, status):
        await i.response.defer(ephemeral=True)
        db_key = self.db_key or i.message.embeds[0].footer.text.split("key:")[1].strip()
        update_complaint_status(db_key, status)
        embed = i.message.embeds[0]
        embed.set_field_at(4, name="📌 Статус", value=status, inline=False)
        await i.message.edit(embed=embed)
        await i.followup.send(f"Статус: {status}", ephemeral=True)

def build_complaint_embed(cid, nick, reason, proof, author, submitter_nick, db_key):
    e = discord.Embed(title=f"🚨 Скарга #{cid}", color=discord.Color.red())
    e.add_field(name="👤 Подав", value=f"{submitter_nick} ({author.mention})", inline=False)
    e.add_field(name="👤 Порушник", value=nick, inline=False)
    e.add_field(name="📄 Опис", value=reason, inline=False)
    e.add_field(name="🔗 Докази", value=proof or "Не надано", inline=False)
    e.add_field(name="📌 Статус", value="🟡 Відкрита", inline=False)
    e.set_footer(text=f"ID автора: {author.id} | key:{db_key}")
    e.timestamp = datetime.now()
    return e

async def setup(bot):
    await bot.add_cog(ComplaintPanel(bot))
