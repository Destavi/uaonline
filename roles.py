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
        self.bot.add_view(RoleApprovalView(self.bot))
        print("✅ Система видачі ролей активована")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Автоматична видача ролі при вході на сервер"""
        role_name = "Гравець 🧑‍🎄"
        role = discord.utils.get(member.guild.roles, name=role_name)
        if role:
            try:
                await member.add_roles(role)
                print(f"✅ Авто-роль '{role_name}' видана користувачу {member.name}")
            except Exception as e:
                print(f"❌ Помилка при видачі авто-ролі: {e}")

    @app_commands.command(name="request_role", description="Подати запит на отримання ролі фракції")
    async def request_role(self, interaction: discord.Interaction):
        view = RoleSelectView(self.bot, interaction.guild.id)
        await interaction.response.send_message("📌 Оберіть роль, яку ви хочете отримати:", view=view, ephemeral=True)

    @app_commands.command(name="give_player_role_all", description="Видати роль 'Гравець 🧑‍🎄' усім, у кого її немає")
    async def give_player_role_all(self, interaction: discord.Interaction):
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in SYNC_ROLE_ALLOWED_ROLES]
        if not any(role_name in allowed_roles_lower for role_name in user_role_names):
            return await interaction.response.send_message("❌ У вас недостатньо прав.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        role = discord.utils.get(interaction.guild.roles, name="Гравець 🧑‍🎄")
        if not role: return await interaction.followup.send("❌ Роль не знайдена.", ephemeral=True)

        if not interaction.guild.chunked: await interaction.guild.chunk()
        to_assign = [m for m in interaction.guild.members if not m.bot and role not in m.roles]
        
        if not to_assign: return await interaction.followup.send("✅ Всі вже мають цю роль.", ephemeral=True)

        await interaction.followup.send(f"⏳ Починаю видачу для **{len(to_assign)}** користувачів...", ephemeral=True)
        added = 0
        for member in to_assign:
            try:
                await member.add_roles(role)
                added += 1
                await asyncio.sleep(0.2)
            except: pass
        
        await interaction.followup.send(f"✅ Синхронізація завершена! Видано: `{added}`", ephemeral=True)

    @app_commands.command(name="remove_faction_roles", description="Зняти всі фракційні ролі з користувача")
    async def remove_faction_roles(self, interaction: discord.Interaction, member: discord.Member):
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in ROLE_APPROVAL_ALLOWED_ROLES]
        if not interaction.user.guild_permissions.administrator and not any(role_name in allowed_roles_lower for role_name in user_role_names):
            return await interaction.response.send_message("❌ Недостатньо прав.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        g_cfg = get_guild_config(interaction.guild.id)
        faction_roles_list = g_cfg.get("request_roles", REQUEST_ROLES_LIST) if g_cfg else REQUEST_ROLES_LIST
        
        removed_roles = []
        for role in member.roles:
            if role.name in faction_roles_list:
                try:
                    await member.remove_roles(role)
                    removed_roles.append(role.name)
                except: pass
        
        if removed_roles:
            for r_name in removed_roles:
                log_mod_action(interaction.guild.id, "role_removed", interaction.user, member, f"Роль: {r_name}")
                update_stat(interaction.guild.id, "roles_removed")
            await interaction.followup.send(f"✅ Ролі знято: {', '.join(removed_roles)}", ephemeral=True)
        else:
            await interaction.followup.send("ℹ️ Ролей не знайдено.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if message.author.id in self.active_uploads:
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
        self.bot = bot
        g_cfg = get_guild_config(guild_id)
        roles = g_cfg.get("request_roles", REQUEST_ROLES_LIST) if g_cfg else REQUEST_ROLES_LIST
        options = [discord.SelectOption(label=role, value=role) for role in roles[:25]]
        self.add_item(RoleSelect(options, bot))

class RoleSelect(discord.ui.Select):
    def __init__(self, options, bot):
        super().__init__(placeholder="Оберіть роль...", options=options)
        self.bot = bot
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RoleRequestModal(self.bot, self.values[0]))

class RoleRequestModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(label="Ваш ігровий нікнейм")
    rank = discord.ui.TextInput(label="Ваш ранг (цифрою)", max_length=2)
    proof = discord.ui.TextInput(label="Коментар (необов'язково)", style=discord.TextStyle.long, required=False)

    def __init__(self, bot, role_name):
        super().__init__(title=f"Запит на роль: {role_name}")
        self.bot, self.role_name = bot, role_name

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        view = RoleFileUploadView(self.bot, self.role_name, self.nickname.value, self.rank.value, self.proof.value, user_id)
        cog = self.bot.get_cog("RoleRequest")
        if cog: cog.active_uploads[user_id] = view
        await interaction.response.send_message("📸 Завантажте фото докази прямо сюди. Натисніть кнопку нижче, коли закінчите.", view=view, ephemeral=True)
        view.initial_interaction = interaction

class RoleFileUploadView(discord.ui.View):
    def __init__(self, bot, role_name, nickname, rank, comment, user_id):
        super().__init__(timeout=300)
        self.bot, self.role_name, self.nickname, self.rank, self.comment, self.user_id = bot, role_name, nickname, rank, comment, user_id
        self.attachments, self.lock, self.initial_interaction = [], asyncio.Lock(), None

    async def update_status(self):
        if self.initial_interaction:
            try:
                await self.initial_interaction.edit_original_response(content=f"📸 **Завантажено файлів: {len(self.attachments)}**\nНатисніть кнопку нижче для відправки.", view=self)
            except: pass

    @discord.ui.button(label="✅ Завершити та надіслати", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cog = self.bot.get_cog("RoleRequest")
        if cog and self.user_id in cog.active_uploads: del cog.active_uploads[self.user_id]
        
        g_cfg = get_guild_config(interaction.guild.id)
        channel = self.bot.get_channel(g_cfg["role_request_channel_id"]) or await self.bot.fetch_channel(g_cfg["role_request_channel_id"])
        
        embed = discord.Embed(title="📜 Новий запит на роль", color=discord.Color.blue())
        embed.add_field(name="👤 Користувач", value=interaction.user.mention, inline=False)
        embed.add_field(name="🎭 Роль", value=self.role_name, inline=False)
        embed.add_field(name="🔢 Ранг", value=self.rank, inline=False)
        embed.add_field(name="📝 Нікнейм", value=self.nickname, inline=False)
        if self.comment: embed.add_field(name="💬 Коментар", value=self.comment, inline=False)
        embed.set_footer(text=f"ID Користувача: {interaction.user.id}")

        await channel.send(embed=embed, view=RoleApprovalView(self.bot), files=self.attachments)
        await interaction.followup.send("✅ Ваш запит надіслано!", ephemeral=True)
        self.stop()

class RoleApprovalView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def check_permissions(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator: return True
        user_roles = [r.name.lower() for r in interaction.user.roles]
        if any(r.lower() in user_roles for r in ROLE_APPROVAL_ALLOWED_ROLES): return True
        await interaction.response.send_message("❌ Немає прав.", ephemeral=True); return False

    @discord.ui.button(label="✅ Схвалити", style=discord.ButtonStyle.success, custom_id="role_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        embed = interaction.message.embeds[0]
        user_id = int(embed.footer.text.split(": ")[1])
        role_name, rank, nickname = None, None, None
        for f in embed.fields:
            if f.name == "🎭 Роль": role_name = f.value
            elif f.name == "🔢 Ранг": rank = f.value
            elif f.name == "📝 Нікнейм": nickname = f.value

        guild = interaction.guild
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        role = discord.utils.get(guild.roles, name=role_name)

        if member and role:
            # Видалення старої ролі
            for r in member.roles:
                if r.name in REQUEST_ROLES_LIST: await member.remove_roles(r)
            
            await member.add_roles(role)
            org_name = ROLE_ABBREVIATIONS.get(role_name, role_name)
            new_nick = f"[{rank} | {org_name}] {nickname}"[:32]
            try: await member.edit(nick=new_nick)
            except: pass

            update_stat(interaction.guild.id, "roles_issued")
            log_mod_action(interaction.guild.id, "role_issued", interaction.user, member, f"Роль: {role_name}")
            
            embed.color = discord.Color.green()
            embed.title = "✅ Запит схвалено"
            await interaction.message.edit(embed=embed, view=None)
            await interaction.response.send_message(f"✅ Роль {role_name} видана.", ephemeral=True)

    @discord.ui.button(label="❌ Відхилити", style=discord.ButtonStyle.danger, custom_id="role_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Запит відхилено"
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("❌ Відхилено.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleRequest(bot))
async def setup(bot):
    await bot.add_cog(RoleRequest(bot))

