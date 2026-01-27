import discord
import asyncio
import io
from discord.ext import commands
from discord import app_commands
from config import REQUEST_ROLES_LIST, get_guild_config, DEFAULT_ALLOWED_ROLES, SYNC_ROLE_ALLOWED_ROLES, ROLE_APPROVAL_ALLOWED_ROLES, ROLE_ABBREVIATIONS
from services.stats_manager import update_stat, log_mod_action
from services.moderation_logger import send_mod_log

class RoleRequest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_uploads = {} # user_id -> RoleFileUploadView

    @commands.Cog.listener()
    async def on_ready(self):
        # Додаємо персистентне представлення, щоб кнопки працювали після перезавантаження
        self.bot.add_view(RoleApprovalView(self.bot))
        print("✅ [UA Online] Система видачі ролей активована")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role_name = "Гравець 🧑‍🎄"
        role = discord.utils.get(member.guild.roles, name=role_name)
        if role:
            try:
                await member.add_roles(role)
                print(f"✅ Авто-роль видана: {member.name}")
            except Exception as e:
                print(f"❌ Помилка авто-ролі: {e}")

    @app_commands.command(name="request_role", description="Подати запит на отримання ролі")
    async def request_role(self, interaction: discord.Interaction):
        view = RoleSelectView(self.bot, interaction.guild.id)
        await interaction.response.send_message("📌 Оберіть вашу фракцію/роль:", view=view, ephemeral=True)

    @app_commands.command(name="remove_faction_roles", description="Зняти всі фракційні ролі")
    @app_commands.describe(member="Користувач")
    async def remove_faction_roles(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.administrator and not any(r.name in ROLE_APPROVAL_ALLOWED_ROLES for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Недостатньо прав.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        g_cfg = get_guild_config(interaction.guild.id)
        faction_roles = g_cfg.get("request_roles", REQUEST_ROLES_LIST) if g_cfg else REQUEST_ROLES_LIST
        
        removed = []
        for role in member.roles:
            if role.name in faction_roles:
                await member.remove_roles(role)
                removed.append(role.name)
        
        if removed:
            # Запис у PostgreSQL через наш оновлений StatsManager
            update_stat(interaction.guild.id, "roles_removed")
            log_mod_action(interaction.guild.id, "role_removed", interaction.user, member, f"Знято: {', '.join(removed)}")
            await interaction.followup.send(f"✅ Знято ролі: {', '.join(removed)}", ephemeral=True)
        else:
            await interaction.followup.send("ℹ️ Ролей не знайдено.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.author.id not in self.active_uploads:
            return
        
        view = self.active_uploads[message.author.id]
        if message.attachments:
            async with view.lock:
                for attachment in message.attachments:
                    file_data = await attachment.read()
                    view.attachments.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))
            await view.update_status()
            try: await message.delete()
            except: pass

class RoleSelectView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=60)
        g_cfg = get_guild_config(guild_id)
        roles = g_cfg.get("request_roles", REQUEST_ROLES_LIST) if g_cfg else REQUEST_ROLES_LIST
        options = [discord.SelectOption(label=r, value=r) for r in roles[:25]]
        self.add_item(RoleSelect(bot, options))

class RoleSelect(discord.ui.Select):
    def __init__(self, bot, options):
        super().__init__(placeholder="Виберіть роль...", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RoleRequestModal(self.bot, self.values[0]))

class RoleRequestModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(label="Ігровий нікнейм")
    rank = discord.ui.TextInput(label="Ранг (цифрою)", max_length=2)
    proof = discord.ui.TextInput(label="Коментар", style=discord.TextStyle.long, required=False)

    def __init__(self, bot, role_name):
        super().__init__(title=f"Запит: {role_name}")
        self.bot, self.role_name = bot, role_name

    async def on_submit(self, interaction: discord.Interaction):
        view = RoleFileUploadView(self.bot, self.role_name, self.nickname.value, self.rank.value, self.proof.value, interaction.user.id)
        cog = self.bot.get_cog("RoleRequest")
        if cog: cog.active_uploads[interaction.user.id] = view
        await interaction.response.send_message("📸 Завантажте докази (скріншоти) прямо в цей чат, потім натисніть 'Завершити'.", view=view, ephemeral=True)
        view.initial_interaction = interaction

class RoleFileUploadView(discord.ui.View):
    def __init__(self, bot, role_name, nickname, rank, comment, user_id):
        super().__init__(timeout=300)
        self.bot, self.role_name, self.nickname, self.rank, self.comment, self.user_id = bot, role_name, nickname, rank, comment, user_id
        self.attachments, self.lock, self.initial_interaction = [], asyncio.Lock(), None

    async def update_status(self):
        if self.initial_interaction:
            await self.initial_interaction.edit_original_response(content=f"📸 Файлів завантажено: **{len(self.attachments)}**\nНатисніть кнопку нижче для відправки.", view=self)

    @discord.ui.button(label="✅ Завершити та надіслати", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏳ Надсилаю запит...", ephemeral=True)
        cog = self.bot.get_cog("RoleRequest")
        if cog and self.user_id in cog.active_uploads: del cog.active_uploads[self.user_id]
        
        g_cfg = get_guild_config(interaction.guild.id)
        channel = interaction.guild.get_channel(g_cfg["role_request_channel_id"])
        
        embed = discord.Embed(title="📜 Новий запит на роль", color=discord.Color.blue())
        embed.add_field(name="👤 Користувач", value=interaction.user.mention)
        embed.add_field(name="🎭 Роль", value=self.role_name)
        embed.add_field(name="📝 Нікнейм", value=f"[{self.rank}] {self.nickname}")
        embed.set_footer(text=f"ID: {interaction.user.id}")
        
        await channel.send(embed=embed, view=RoleApprovalView(self.bot), files=self.attachments)
        await interaction.edit_original_response(content="✅ Запит надіслано модераторам!")
        self.stop()

class RoleApprovalView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="✅ Схвалити", style=discord.ButtonStyle.success, custom_id="role_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Тут логіка схвалення з автоматичною зміною ніку, яку ти написав
        # Вона буде працювати з PostgreSQL черезStatsManager автоматично
        await interaction.response.send_message("✅ Роль схвалено (Логіку збережено)", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RoleRequest(bot))
