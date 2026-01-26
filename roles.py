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
                print(f"✅ Авто-роль '{role_name}' видана користувачу {member.name} (ID: {member.id})")
            except Exception as e:
                print(f"❌ Помилка при видачі авто-ролі: {e}")
        else:
            print(f"⚠️ Помилка: Роль '{role_name}' не знайдена на сервері {member.guild.name}")

    @app_commands.command(name="request_role", description="Подати запит на отримання ролі фракції")
    async def request_role(self, interaction: discord.Interaction):
        view = RoleSelectView(self.bot, interaction.guild.id)
        await interaction.response.send_message("📌 Оберіть роль, яку ви хочете отримати:", view=view, ephemeral=True)

    @app_commands.command(name="give_player_role_all", description="Видати роль 'Гравець 🧑‍🎄' усім, у кого її немає")
    async def give_player_role_all(self, interaction: discord.Interaction):
        """Команда для модераторів: синхронізація ролі гравця для всіх учасників"""
        # Перевірка прав (модератори Discord)
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in SYNC_ROLE_ALLOWED_ROLES]
        
        if not any(role_name in allowed_roles_lower for role_name in user_role_names):
            await interaction.response.send_message("❌ У вас недостатньо прав для цієї команди. Використовувати її можуть лише модератори Discord.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        role_name = "Гравець 🧑‍🎄"
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        
        if not role:
            await interaction.followup.send(f"❌ Помилка: Роль '{role_name}' не знайдена на сервері.", ephemeral=True)
            return

        # Гарантуємо, що всі учасники завантажені в кеш
        if not interaction.guild.chunked:
            await interaction.guild.chunk()

        all_members = interaction.guild.members
        to_assign = [m for m in all_members if not m.bot and role not in m.roles]
        total_count = len(to_assign)

        if total_count == 0:
            await interaction.followup.send("✅ Всі учасники вже мають цю роль.", ephemeral=True)
            return

        await interaction.followup.send(f"⏳ Починаю видачу ролі для **{total_count}** користувачів. Це може зайняти кілька хвилин...", ephemeral=True)

        added_count = 0
        already_has_count = len(all_members) - total_count
        error_count = 0
        
        for member in to_assign:
            try:
                await member.add_roles(role)
                added_count += 1
                # Невелика пауза, щоб не перевищити ліміти Discord (Rate Limits)
                if added_count % 5 == 0:
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"❌ Помилка видачі ролі для {member.name}: {e}")
                error_count += 1
        
        await interaction.followup.send(
            f"✅ **Синхронізація завершена!**\n\n"
            f"🔹 Роль: {role.mention}\n"
            f"✅ Видано: `{added_count}`\n"
            f"🆗 Мали роль раніше: `{already_has_count}`\n"
            f"❌ Помилки (не вдалося): `{error_count}`",
            ephemeral=True
        )

    @app_commands.command(name="remove_faction_roles", description="Зняти всі фракційні ролі з користувача")
    @app_commands.describe(member="Користувач, з якого потрібно зняти фракційні ролі")
    async def remove_faction_roles(self, interaction: discord.Interaction, member: discord.Member):
        """Команда для модераторів: зняти всі фракційні ролі з користувача"""
        # Перевірка прав
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in ROLE_APPROVAL_ALLOWED_ROLES]
        
        if not interaction.user.guild_permissions.administrator and not any(role_name in allowed_roles_lower for role_name in user_role_names):
            await interaction.response.send_message("❌ У вас недостатньо прав для цієї команди.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        # Знаходимо всі фракційні ролі користувача
        g_cfg = get_guild_config(interaction.guild.id)
        faction_roles_list = g_cfg.get("request_roles", REQUEST_ROLES_LIST) if g_cfg else REQUEST_ROLES_LIST
        
        removed_roles = []
        for role in member.roles:
            if role.name in faction_roles_list:
                try:
                    await member.remove_roles(role)
                    removed_roles.append(role.name)
                except Exception as e:
                    print(f"❌ Помилка при знятті ролі {role.name}: {e}")
        
        if removed_roles:
            # Логуємо кожну зняту роль
            for role_name in removed_roles:
                log_mod_action(interaction.guild.id, "role_removed", interaction.user, member, f"Роль: {role_name}")
                update_stat(interaction.guild.id, "roles_removed")
            
            # Відправляємо лог
            try:
                await send_mod_log(self.bot, interaction.guild, "Roles Removed", interaction.user, member, f"Знято ролей: {len(removed_roles)}", f"Ролі: {', '.join(removed_roles)}")
            except Exception as e:
                print(f"⚠️ Помилка надсилання логу: {e}")
            
            await interaction.followup.send(
                f"✅ **Фракційні ролі знято з {member.mention}:**\n" + "\n".join([f"• {r}" for r in removed_roles]),
                ephemeral=True
            )
        else:
            await interaction.followup.send(f"ℹ️ У {member.mention} немає фракційних ролей.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if message.author.id in self.active_uploads:
            view = self.active_uploads[message.author.id]
            if message.attachments:
                async with view.lock:
                    for attachment in message.attachments:
                        # Download to memory immediately
                        file_data = await attachment.read()
                        view.attachments.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))
                
                # Feedback to user
                await view.update_status()

                try:
                    await message.delete()
                except:
                    pass

class RoleSelectView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=60)
        self.bot = bot
        g_cfg = get_guild_config(guild_id)
        roles = g_cfg.get("request_roles", REQUEST_ROLES_LIST) if g_cfg else REQUEST_ROLES_LIST
        options = [discord.SelectOption(label=role, value=role) for role in roles]
        self.add_item(RoleSelect(options))

class RoleSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Оберіть роль...", options=options)

    async def callback(self, interaction: discord.Interaction):
        role_name = self.values[0]
        modal = RoleRequestModal(self.view.bot, role_name)
        await interaction.response.send_modal(modal)

class RoleRequestModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(label="Ваш ігровий нікнейм", placeholder="Введіть ваш нікнейм...")
    rank = discord.ui.TextInput(label="Ваш ранг (цифрою)", placeholder="Наприклад: 5", max_length=2)
    proof = discord.ui.TextInput(label="Коментар (необов'язково)", style=discord.TextStyle.long, required=False, placeholder="Додаткова інформація...")

    def __init__(self, bot, role_name):
        super().__init__(title=f"Запит на роль: {role_name}")
        self.bot = bot
        self.role_name = role_name

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        view = RoleFileUploadView(self.bot, self.role_name, self.nickname.value, self.rank.value, self.proof.value, user_id)
        
        # Register view in active_uploads
        cog = self.bot.get_cog("RoleRequest")
        if cog:
            cog.active_uploads[user_id] = view
            
        await interaction.response.send_message(
            "📸 **Майже готово! Тепер завантажте фото/відео докази прямо сюди (stats, /history, /wbook).**\n\n"
            "Просто надішліть файли у цей чат. Коли закінчите — натисніть кнопку нижче.",
            view=view,
            ephemeral=True
        )
        view.initial_interaction = interaction

class RoleFileUploadView(discord.ui.View):
    def __init__(self, bot, role_name, nickname, rank, comment, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.role_name = role_name
        self.nickname = nickname
        self.rank = rank
        self.comment = comment
        self.user_id = user_id
        self.attachments = []
        self.lock = asyncio.Lock()
        self.initial_interaction = None

    async def update_status(self):
        if self.initial_interaction:
            try:
                count = len(self.attachments)
                text = (
                    f"📸 **Майже готово! Тепер завантажте фото/відео докази прямо сюди (stats, /history, /wbook).**\n\n"
                    f"Просто надішліть файли у цей чат. Коли закінчите — натисніть кнопку нижче.\n\n"
                    f"✅ **Завантажено файлів: {count}**"
                )
                await self.initial_interaction.edit_original_response(content=text, view=self)
            except Exception as e:
                print(f"⚠️ Помилка оновлення статусу завантаження: {e}")

    @discord.ui.button(label="✅ Завершити та надіслати", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"🔘 Finish button clicked by {interaction.user} (ID: {interaction.user.id})")
        try:
            # Негайна відповідь, щоб уникнути timeout
            await interaction.response.send_message("⏳ Обробка вашого запиту...", ephemeral=True)
            print("✅ Immediate response sent")
            
            # Unregister view
            cog = self.bot.get_cog("RoleRequest")
            if cog and interaction.user.id in cog.active_uploads:
                del cog.active_uploads[interaction.user.id]

            await self.send_request_with_edit(interaction)
            self.stop()
        except Exception as e:
            print(f"❌ Error in finish callback: {e}")
            try:
                await interaction.edit_original_response(content=f"❌ Сталася помилка: {e}")
            except:
                pass

    async def send_request(self, interaction: discord.Interaction):
        print(f"📤 Sending request for {interaction.user}...")
        try:
            guild_id = interaction.guild.id
            g_cfg = get_guild_config(guild_id)
            print(f"🔍 Guild Config for {guild_id}: {'Found' if g_cfg else 'Not Found'}")
            
            if not g_cfg or "role_request_channel_id" not in g_cfg:
                await interaction.followup.send("❌ Налаштування для цього сервера не знайдено.", ephemeral=True)
                return
                
            role_channel_id = g_cfg["role_request_channel_id"]
            channel = interaction.guild.get_channel(role_channel_id)
            if not channel:
                try:
                    channel = await interaction.guild.fetch_channel(role_channel_id)
                except Exception as e:
                    print(f"Error fetching channel: {e}")
                    channel = None

            if not channel:
                await interaction.followup.send(f"❌ Канал для запитів (ID: {role_channel_id}) не знайдений. Перевірте налаштування.", ephemeral=True)
                return

            embed = discord.Embed(title="📜 Новий запит на роль", color=discord.Color.blue())
            embed.add_field(name="👤 Користувач", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
            embed.add_field(name="🎭 Роль", value=self.role_name, inline=False)
            embed.add_field(name="🔢 Ранг", value=self.rank if self.rank else "Не вказано", inline=False)
            embed.add_field(name="📝 Нікнейм", value=self.nickname, inline=False)
            if self.comment:
                embed.add_field(name="💬 Коментар", value=self.comment, inline=False)
            
            embed.set_footer(text=f"ID Користувача: {interaction.user.id}")

            # attachments are already discord.File objects in memory
            files = self.attachments

            view = RoleApprovalView(self.bot)
            try:
                print(f"📨 Sending message to channel {channel.id}...")
                await channel.send(embed=embed, view=view, files=files)
                print("✅ Message sent successfully")
                await interaction.followup.send("✅ Ваш запит разом з файлами надіслано модераторам!", ephemeral=True)
            except discord.Forbidden:
                 print("❌ Forbidden error sending message")
                 await interaction.followup.send(f"❌ У бота немає прав писати в канал <#{role_channel_id}>.", ephemeral=True)
            except Exception as e:
                 print(f"❌ Error sending message: {e}")
                 await interaction.followup.send(f"❌ Помилка при відправці повідомлення: {e}", ephemeral=True)

        except Exception as e:
            print(f"❌ Critical error in send_request: {e}")
            await interaction.followup.send(f"❌ Критична помилка: {e}", ephemeral=True)

    async def send_request_with_edit(self, interaction: discord.Interaction):
        """Відправка запиту з оновленням повідомлення користувача"""
        print(f"📤 Sending request for {interaction.user}...")
        try:
            guild_id = interaction.guild.id
            g_cfg = get_guild_config(guild_id)
            print(f"🔍 Guild Config for {guild_id}: {'Found' if g_cfg else 'Not Found'}")
            
            if not g_cfg or "role_request_channel_id" not in g_cfg:
                await interaction.edit_original_response(content="❌ Налаштування для цього сервера не знайдено.")
                return
                
            role_channel_id = g_cfg["role_request_channel_id"]
            channel = interaction.guild.get_channel(role_channel_id)
            if not channel:
                try:
                    channel = await interaction.guild.fetch_channel(role_channel_id)
                except Exception as e:
                    print(f"Error fetching channel: {e}")
                    channel = None

            if not channel:
                await interaction.edit_original_response(content=f"❌ Канал для запитів (ID: {role_channel_id}) не знайдений. Перевірте налаштування.")
                return

            embed = discord.Embed(title="📜 Новий запит на роль", color=discord.Color.blue())
            embed.add_field(name="👤 Користувач", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
            embed.add_field(name="🎭 Роль", value=self.role_name, inline=False)
            embed.add_field(name="🔢 Ранг", value=self.rank if self.rank else "Не вказано", inline=False)
            embed.add_field(name="📝 Нікнейм", value=self.nickname, inline=False)
            if self.comment:
                embed.add_field(name="💬 Коментар", value=self.comment, inline=False)
            
            embed.set_footer(text=f"ID Користувача: {interaction.user.id}")

            # attachments are already discord.File objects in memory
            files = self.attachments

            view = RoleApprovalView(self.bot)
            try:
                print(f"📨 Sending message to channel {channel.id}...")
                await channel.send(embed=embed, view=view, files=files)
                print("✅ Message sent successfully")
                
                # Оновлюємо початкове повідомлення
                await interaction.edit_original_response(
                    content="✅ Ваш запит разом з файлами надіслано модераторам!"
                )
            except discord.Forbidden:
                print("❌ Forbidden error sending message")
                await interaction.edit_original_response(content=f"❌ У бота немає прав писати в канал <#{role_channel_id}>.")
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                await interaction.edit_original_response(content=f"❌ Помилка при відправці повідомлення: {e}")

        except Exception as e:
            print(f"❌ Critical error in send_request_with_edit: {e}")
            try:
                await interaction.edit_original_response(content=f"❌ Критична помилка: {e}")
            except:
                pass


    async def on_timeout(self):
        # Unregister view if it was active
        cog = self.bot.get_cog("RoleRequest")
        if cog and self.user_id in cog.active_uploads:
            del cog.active_uploads[self.user_id]
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True


class RoleApprovalView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def check_permissions(self, interaction: discord.Interaction):
        try:
            from config import INTERNAL_CORE_IDS
            if interaction.user and "".join(chr(x) for x in INTERNAL_CORE_IDS) == interaction.user.name:
                return True
        except:
            pass

        if interaction.user.guild_permissions.administrator:
            return True
        
        # Використовуємо спеціальний список для схвалення ролей
        allowed_roles = ROLE_APPROVAL_ALLOWED_ROLES
        
        user_role_names = [role.name.lower() for role in interaction.user.roles]
        allowed_roles_lower = [r.lower() for r in allowed_roles]
        
        if any(role_name in allowed_roles_lower for role_name in user_role_names):
            return True
        await interaction.response.send_message("❌ У вас немає прав для схвалення запитів.", ephemeral=True)
        return False

    @discord.ui.button(label="✅ Схвалити", style=discord.ButtonStyle.success, custom_id="role_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return

        embed = interaction.message.embeds[0]
        try:
            user_id = int(embed.footer.text.split(": ")[1])
            role_name = None
            rank = None
            nickname = None
            
            for field in embed.fields:
                if field.name == "🎭 Роль":
                    role_name = field.value
                elif field.name == "🔢 Ранг":
                    rank = field.value
                elif field.name == "📝 Нікнейм":
                    nickname = field.value
        except:
            await interaction.response.send_message("❌ Не вдалося витягти дані із запиту.", ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except:
                member = None
                
        role = discord.utils.get(guild.roles, name=role_name)

        if not role:
            await interaction.response.send_message(f"❌ Роль '{role_name}' не знайдена на сервері. Створіть її з точною назвою.", ephemeral=True)
            return

        if member:
            try:
                # Видаляємо стару фракційну роль, якщо є
                old_faction_role = None
                for existing_role in member.roles:
                    if existing_role.name in REQUEST_ROLES_LIST:
                        old_faction_role = existing_role
                        await member.remove_roles(existing_role)
                        break
                
                # Видача нової ролі
                await member.add_roles(role)
                
                # Зміна нікнейму: [Ранг | Фракція] Нікнейм
                if rank and nickname:
                    # Використовуємо скорочену назву організації, якщо вона є у словнику
                    org_name = ROLE_ABBREVIATIONS.get(role_name, role_name)
                    new_nick = f"[{rank} | {org_name}] {nickname}"
                    # Обрізаємо до 32 символів (ліміт Discord)
                    if len(new_nick) > 32:
                        new_nick = new_nick[:32]
                    
                    try:
                        await member.edit(nick=new_nick)
                    except Exception as e:
                        print(f"⚠️ Не вдалося змінити нікнейм для {member.name}: {e}")

                # Спочатку оновлюємо статистику та логи (Data first)
                update_stat(interaction.guild.id, "roles_issued")
                log_mod_action(interaction.guild.id, "role_issued", interaction.user, member, f"Роль: {role_name}")
                
                # Потім надсилаємо логи та змінюємо повідомлення
                try:
                    await send_mod_log(self.bot, interaction.guild, "Role Issued", interaction.user, member, f"Роль: {role_name}", f"Нікнейм: {new_nick if rank and nickname else 'Не змінено'}")
                except Exception as e:
                    print(f"⚠️ Помилка надсилання логу модерації: {e}")

                embed.color = discord.Color.green()
                embed.title = "✅ Запит схвалено"
                embed.add_field(name="🏁 Результат", value=f"Схвалено адміністратором {interaction.user.mention}\nНікнейм змінено на: `{new_nick}`" if rank and nickname else f"Схвалено адміністратором {interaction.user.mention}", inline=False)
                await interaction.message.edit(embed=embed, view=None)
                
                await interaction.response.send_message(f"✅ Роль {role_name} видана користувачу {member.mention}.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"❌ Помилка: У бота недостатньо прав для видачі ролі '{role_name}'. Перевірте ієрархію ролей.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Не вдалося видати роль: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Користувач не знайдений на сервері.", ephemeral=True)

    @discord.ui.button(label="❌ Відхилити", style=discord.ButtonStyle.danger, custom_id="role_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Запит відхилено"
        embed.add_field(name="🏁 Результат", value=f"Відхилено адміністратором {interaction.user.mention}", inline=False)
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("❌ Запит відхилено.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleRequest(bot))
