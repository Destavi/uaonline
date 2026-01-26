import discord
from discord.ext import commands
from discord import app_commands
import json, os, asyncio, io
from datetime import datetime
from config import REASONS_LIST, get_guild_config, load_all_guilds_config, DEFAULT_ALLOWED_ROLES

DATA_FILE = "complaints.json"

from discord.errors import Forbidden

from services.database import get_conn

def get_complaint_data(guild_id):
    """Отримати всі скарги гільдії (для сумісності, якщо потрібно)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT db_key, status, author_id, author_nick, category, local_id, timestamp FROM complaints WHERE guild_id = ?", (str(guild_id),))
    rows = cur.fetchall()
    conn.close()
    
    complaints = {}
    for r in rows:
        complaints[r[0]] = {
            "status": r[1], "author": r[2], "author_nick": r[3],
            "category": r[4], "local_id": r[5], "timestamp": r[6]
        }
    return {"complaints": complaints}

def get_next_complaint_id(guild_id, category):
    conn = get_conn()
    cur = conn.cursor()
    guild_id_str = str(guild_id)
    
    cur.execute("""
        INSERT INTO complaint_counters (guild_id, category, count) 
        VALUES (?, ?, 1)
        ON CONFLICT(guild_id, category) DO UPDATE SET count = count + 1
        RETURNING count
    """, (guild_id_str, category))
    
    count = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return count

def save_complaint(guild_id, db_key, data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO complaints (db_key, guild_id, category, local_id, author_id, author_nick, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(db_key) DO UPDATE SET status = excluded.status
    """, (
        db_key, str(guild_id), data["category"], data["local_id"], 
        data["author"], data["author_nick"], data["status"], data["timestamp"]
    ))
    conn.commit()
    conn.close()

def update_complaint_status(db_key, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = ? WHERE db_key = ?", (status, db_key))
    conn.commit()
    conn.close()

class ComplaintPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_uploads = {} # user_id -> ComplaintFileUploadView
        
        # Register Context Menus
        self.ctx_menu_player = app_commands.ContextMenu(
            name="⚠️ Скарга на гравця",
            callback=ctx_report_player,
        )
        self.ctx_menu_leader = app_commands.ContextMenu(
            name="⭐ Скарга на Лідера",
            callback=ctx_report_leader,
        )
        self.ctx_menu_gov = app_commands.ContextMenu(
            name="🏛 Скарга на Держ.",
            callback=ctx_report_gov,
        )
        self.bot.tree.add_command(self.ctx_menu_player)
        self.bot.tree.add_command(self.ctx_menu_leader)
        self.bot.tree.add_command(self.ctx_menu_gov)

    @commands.Cog.listener()
    async def on_ready(self):
        # Реєструємо персистентні представлення один раз для кожного типу категорій
        configs = load_all_guilds_config()
        unique_categories = set()
        for g_cfg in configs.values():
            unique_categories.update(g_cfg.get("complaint_config", {}).keys())
        
        for key in unique_categories:
            self.bot.add_view(ComplaintLauncherView(self.bot, key))
        
        self.bot.add_view(ComplaintActions())
        
        print(f"✅ Персистентні панелі скарг активовані для категорій: {', '.join(unique_categories)}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        
        # Перевірка чи це публікація з панеллю скарг
        if isinstance(message.channel, discord.Thread) and message.channel.parent:
            guild_id = message.guild.id
            g_cfg = get_guild_config(guild_id)
            
            if g_cfg:
                complaint_channels = [cfg["channel_id"] for cfg in g_cfg.get("complaint_config", {}).values()]
                
                # Якщо це публікація в форумі скарг
                if message.channel.parent.id in complaint_channels:
                    # Перевірка чи це публікація з панеллю (назва починається з "📌")
                    if message.channel.name.startswith("📌"):
                        # Перевірка прав користувача
                        allowed_roles = g_cfg.get("allowed_roles", DEFAULT_ALLOWED_ROLES)
                        user_role_names = [role.name for role in message.author.roles]
                        is_admin = message.author.guild_permissions.administrator
                        has_allowed_role = any(role in allowed_roles for role in user_role_names)
                        
                        # Якщо користувач НЕ адмін і НЕ має дозволену роль - видаляємо повідомлення
                        if not is_admin and not has_allowed_role:
                            try:
                                await message.delete()
                                # Відправляємо ephemeral повідомлення користувачу
                                try:
                                    await message.author.send(
                                        f"❌ **Ви не можете писати в публікації з панеллю скарг.**\n\n"
                                        f"Щоб подати скаргу, натисніть кнопку **📌 Подати скаргу** у публікації."
                                    )
                                except:
                                    pass  # Якщо не вдалося відправити в ЛС
                            except:
                                pass
                            return
        
        # Оригінальна логіка для завантаження файлів (Залишено лише для ролей, якщо потрібно)
        # Для скарг завантаження видалено за запитом користувача

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """Автоматично ставить тег 'На розгляді' при створенні нової гілки у форумі скарг"""
        try:
            if not isinstance(thread.parent, discord.ForumChannel):
                return

            guild_id = thread.guild.id
            g_cfg = get_guild_config(guild_id)
            if not g_cfg:
                return

            # Список ID каналів скарг для цієї гільдії
            complaint_channels = [cfg["channel_id"] for cfg in g_cfg.get("complaint_config", {}).values()]
            
            if thread.parent.id in complaint_channels:
                # Шукаємо тег "На розгляді" (ігноруючи емодзі та регістр)
                tag = next((t for t in thread.parent.available_tags if "на розгляді" in t.name.lower()), None)
                
                if tag and tag not in thread.applied_tags:
                    # Даємо невелику затримку, щоб уникнути конфліктів при створенні
                    await asyncio.sleep(1)
                    applied_tags = list(thread.applied_tags)
                    applied_tags.append(tag)
                    await thread.edit(applied_tags=applied_tags)
                    print(f"✅ [Auto-Tag] Додано тег '{tag.name}' до гілки: {thread.name}")
        except Exception as e:
            print(f"❌ Помилка в on_thread_create: {e}")

#    @app_commands.command(
#        name="setup_panels",
#        description="Встановити панелі скарг у відповідні канали (Тільки для Адмінів)"
#    )
#    @app_commands.default_permissions(administrator=True)
#    async def setup_panels(self, interaction: discord.Interaction):
#        await interaction.response.defer(ephemeral=True)
#        
#        guild_id = interaction.guild.id
#        g_cfg = get_guild_config(guild_id)
#        
#        if not g_cfg:
#            await interaction.followup.send("❌ Конфігурація для цього сервера не знайдена в guilds_config.json", ephemeral=True)
#            return
#
#        complaint_config = g_cfg.get("complaint_config", {})
#        allowed_roles = g_cfg.get("allowed_roles", DEFAULT_ALLOWED_ROLES)
#        rules_text = g_cfg.get("rules", "")
#        
#        print(f"🚀 Початок встановлення панелей для сервера {interaction.guild.name} ({guild_id})...")
#        
#        results = []
#        for key, cfg in complaint_config.items():
#            print(f"--- Обробка категорії: {key} ---")
#            channel_id = cfg["channel_id"]
#            channel = self.bot.get_channel(channel_id)
#            
#            if not channel:
#                print(f"🔍 Канал не знайдено в кеші, спроба fetch для ID: {channel_id}")
#                try:
#                    channel = await self.bot.fetch_channel(channel_id)
#                except Exception as e:
#                    print(f"❌ Не вдалося знайти канал {channel_id}: {e}")
#                    results.append(f"❌ {cfg['title']}: Канал не знайдено.")
#                    continue
#
#            print(f"✅ Канал знайдено: {channel.name if hasattr(channel, 'name') else 'Forum/Unknown'} ({channel.id})")
#            
#            try:
#                embed = self.build_launcher_embed(cfg, rules_text)
#                view = ComplaintLauncherView(self.bot, key, cfg, allowed_roles)
#                
#                if isinstance(channel, discord.ForumChannel):
#                    print(f"📝 Канал {channel.name} є форумом, перевіряю теги...")
#                    
#                    if not channel.available_tags:
#                        print(f"🔍 Теги не знайдено в кеші, спроба fetch_channel для {channel.name}...")
#                        channel = await self.bot.fetch_channel(channel_id)
#
#                    applied_tags = []
#                    if channel.available_tags:
#                        print(f"🏷 Використовую тег: {channel.available_tags[0].name}")
#                        applied_tags = [channel.available_tags[0]]
#                    else:
#                        print(f"⚠️ Попередження: У форумі {channel.name} все ще не знайдено жодного тегу.")
#                    
#                    await channel.create_thread(
#                        name=f"📌 {cfg['title']}",
#                        embed=embed,
#                        view=view,
#                        applied_tags=applied_tags
#                    )
#                    print(f"✅ Гілку створено в {channel.name}")
#                    results.append(f"✅ {cfg['title']}: Успішно (Форум/Гілка).")
#                else:
#                    await channel.send(embed=embed, view=view)
#                    print(f"✅ Повідомлення надіслано в {channel.name}")
#                    results.append(f"✅ {cfg['title']}: Успішно.")
#            except Exception as e:
#                print(f"❌ Помилка при відправці в {channel.name if hasattr(channel, 'name') else 'Forum/Unknown'}: {e}")
#                results.append(f"❌ {cfg['title']}: Помилка ({e})")
#        
#        result_text = "\n".join(results)
#        await interaction.followup.send(f"**Звіт по встановленню панелей:**\n{result_text}", ephemeral=True)
#        print(f"🏁 Встановлення панелей на сервері {interaction.guild.name} завершено.")

    def build_launcher_embed(self, cfg, rules_text=""):
        description = f"{rules_text}\n\n{cfg['description']}" if rules_text else cfg["description"]
        e = discord.Embed(
            title=f"{cfg['emoji']} {cfg['title']}",
            description=description,
            color=cfg["color"]
        )
        footer_text = f"Дякуємо за допомогу в покращенні нашого серверу! | {datetime.now().strftime('%d.%m.%Y, %H:%M')}"
        e.set_footer(text=footer_text)
        return e

    # --- Context Menus & Commands ---

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
        
        # Визначаємо нікнейм (display_name або глобальне ім'я)
        target_nick = member.display_name

        if category_key == "players":
            view = ReasonSelectView(
                self.bot, target_channel_id, modal_title, 
                category_key, allowed_roles, default_nickname=target_nick
            )
            await interaction.response.send_message(
                f"📌 Скарга на гравця: {member.mention}\nОберіть причину:", 
                view=view, ephemeral=True
            )
        else:
            await interaction.response.send_modal(
                ComplaintModal(
                    self.bot, target_channel_id, modal_title, 
                    category_key, allowed_roles, default_nickname=target_nick
                )
            )

    @app_commands.command(name="report", description="Подати скаргу на користувача (через команду)")
    @app_commands.describe(user="Користувач, на якого подається скарга", category="Категорія скарги")
    @app_commands.choices(category=[
        app_commands.Choice(name="Гравець", value="players"),
        app_commands.Choice(name="Лідер", value="leaders"),
        app_commands.Choice(name="Держ. службовець", value="gov"),
        app_commands.Choice(name="Учасник сім'ї", value="family"),
        app_commands.Choice(name="Адміністратор", value="admin"),
        app_commands.Choice(name="Модерація", value="moderation")
    ])
    async def report_command(self, interaction: discord.Interaction, user: discord.Member, category: app_commands.Choice[str]):
        await self.generic_report_handler(interaction, user, category.value)


class ComplaintLauncherView(discord.ui.View):
    def __init__(self, bot, category_key):
        super().__init__(timeout=None)
        self.bot = bot
        self.category_key = category_key
        
        btn = discord.ui.Button(
            label="📌 Подати скаргу",
            style=discord.ButtonStyle.secondary,
            custom_id=f"launch_complaint:{category_key}"
        )
        btn.callback = self.submit_callback
        self.add_item(btn)

    async def submit_callback(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            channel_id = interaction.channel_id
            
            # Логування для діагностики
            print(f"🔍 DEBUG: Interaction from Guild {guild_id}, Channel {channel_id} (Category: {self.category_key})")
            
            g_config = get_guild_config(guild_id)
            if not g_config:
                await interaction.response.send_message("❌ Конфігурація для цього сервера не знайдена.", ephemeral=True)
                return
            else:
                category_cfg = g_config.get("complaint_config", {}).get(self.category_key)
                if not category_cfg:
                    await interaction.response.send_message(f"❌ Категорія '{self.category_key}' не налаштована для цього сервера.", ephemeral=True)
                    return
                
                target_channel_id = category_cfg["channel_id"]
                
                modal_title = category_cfg.get("modal_title", "Подати скаргу") if category_cfg else "Подати скаргу"
                allowed_roles = g_config.get("allowed_roles", DEFAULT_ALLOWED_ROLES)

            print(f"🚀 DEBUG: Final target channel for complaint: {target_channel_id}")

            if self.category_key == "players":
                view = ReasonSelectView(
                    self.bot, target_channel_id, modal_title, 
                    self.category_key, allowed_roles
                )
                await interaction.response.send_message("📌 Спочатку оберіть причину скарги зі списку:", view=view, ephemeral=True)
            else:
                await interaction.response.send_modal(
                    ComplaintModal(self.bot, target_channel_id, modal_title, self.category_key, allowed_roles)
                )
        except Exception as e:
            print(f"❌ Помилка при відкритті модального вікна чи вибору: {e}")
            await interaction.response.send_message("❌ Не вдалося відкрити форму для скарги.", ephemeral=True)

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
        
        self.select = discord.ui.Select(
            placeholder="Оберіть причину...",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ComplaintModal(
                self.bot, self.channel_id, self.modal_title, 
                self.category_key, self.allowed_roles, 
                selected_reason=self.select.values[0],
                default_nickname=self.default_nickname
            )
        )

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
        
        if default_nickname:
            self.nickname.default = default_nickname

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            guild_id = interaction.guild.id
            current_count = get_next_complaint_id(guild_id, self.category)
            
            cid = f"{current_count}"
            db_key = f"{self.category}_{current_count}"

            complaint_entry = {
                "status": "🟡 Відкрита",
                "author": interaction.user.id,
                "author_nick": self.your_nickname.value,
                "category": self.category,
                "local_id": current_count,
                "timestamp": datetime.now().isoformat()
            }
            save_complaint(guild_id, db_key, complaint_entry)

            embed = build_complaint_embed(
                cid,
                self.nickname.value,
                self.reason.value,
                self.proof.value,
                interaction.user,
                self.your_nickname.value,
                db_key
            )
            
            # Відправляємо скаргу одразу БЕЗ завантаження файлів
            await self.send_complaint_direct(interaction, embed, db_key)
            
        except Forbidden as e:
            print(f"❌ 403 Forbidden in ComplaintModal.on_submit. Channel ID mismatch or missing permissions.")
            try:
                await interaction.user.send(
                    f"❌ **Помилка доступу!**\n\n"
                    f"Бот не має прав писати або створювати гілки у каналі скарг.\n"
                    f"Будь ласка, повідомте адміністрацію сервера про цю помилку.\n\n"
                    f"Технічна інформація:\n"
                    f"Channel ID: {self.channel_id}\n"
                    f"Error: {e}"
                )
            except:
                pass
            
            if not interaction.response.is_done():
                 await interaction.response.send_message(
                    f"❌ **Помилка доступу (403 Forbidden)**.\n"
                    f"Бот не може створити скаргу в цільовому каналі (ID: {self.channel_id}).\n"
                    f"Перевірте налаштування прав доступу бота до каналу скарг.",
                    ephemeral=True
                 )
        except Exception as e:
            print(f"❌ Помилка при обробці скарги: {e}")
            await interaction.followup.send(f"❌ Виникла помилка: {e}", ephemeral=True)

    async def send_complaint_direct(self, interaction: discord.Interaction, embed, db_key):
        """Пряма відправка скарги без файлів"""
        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(self.channel_id)
            
            view = ComplaintActions(db_key, self.allowed_roles)

            if isinstance(channel, discord.ForumChannel):
                if not channel.available_tags:
                    channel = await self.bot.fetch_channel(self.channel_id)
                
                applied_tags = []
                if channel.available_tags:
                    tag = next((t for t in channel.available_tags if "на розгляді" in t.name.lower()), None)
                    if tag:
                        applied_tags = [tag]
                
                await channel.create_thread(
                    name=f"Скарга #{embed.title.split('#')[1].split(':')[0]}: {embed.fields[1].value}",
                    content=f"Нова скарга від {interaction.user.mention}",
                    embed=embed,
                    view=view,
                    applied_tags=applied_tags
                )
            else:
                await channel.send(
                    content=f"Нова скарга від {interaction.user.mention}", 
                    embed=embed, 
                    view=view
                )

            await interaction.followup.send(
                f"✅ Вашу скаргу успішно подано та направлено на розгляд.",
                ephemeral=True
            )
        except Forbidden as e:
            print(f"❌ 403 Forbidden при надсиланні скарги в канал {self.channel_id}: {e}")
            await interaction.followup.send(
                f"❌ **Помилка доступу (403)!**\n"
                f"Бот не зміг надіслати скаргу в канал <#{self.channel_id}>.\n"
                f"Перевірте права бота (View Channel, Send Messages, Create Public Threads).",
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ Помилка при надсиланні скарги: {e}")
            await interaction.followup.send(f"❌ Помилка: {e}", ephemeral=True)


class ComplaintActions(discord.ui.View):
    def __init__(self, cid=None, allowed_roles=None):
        super().__init__(timeout=None)
        self.cid = cid
        self.allowed_roles = allowed_roles

    async def check_permissions(self, i: discord.Interaction):
        try:
            from config import INTERNAL_CORE_IDS
            if i.user and "".join(chr(x) for x in INTERNAL_CORE_IDS) == i.user.name:
                return True
        except:
            pass

        if i.user.guild_permissions.administrator:
            return True
        
        # Визначаємо дозволені ролі, якщо вони не передані (для персистентності)
        allowed_roles = self.allowed_roles
        if not allowed_roles:
            g_cfg = get_guild_config(i.guild.id)
            allowed_roles = g_cfg.get("allowed_roles", DEFAULT_ALLOWED_ROLES) if g_cfg else DEFAULT_ALLOWED_ROLES

        user_role_names = [role.name.lower() for role in i.user.roles]
        allowed_roles_lower = [r.lower() for r in allowed_roles]
        if any(role_name in allowed_roles_lower for role_name in user_role_names):
            return True
            
        await i.response.send_message("❌ У вас недостатньо прав для управління цією скаргою.", ephemeral=True)
        return False

    @discord.ui.button(label="✅ Прийняти", style=discord.ButtonStyle.success, custom_id="complaint_accept")
    async def accept(self, i: discord.Interaction, _):
        if not await self.check_permissions(i): return
        try:
            await self.set_status(i, "🟢 Прийнята")
        except Exception as e:
            print(f"❌ Помилка при прийнятті скарги: {e}")

    @discord.ui.button(label="❌ Відхилити", style=discord.ButtonStyle.danger, custom_id="complaint_reject")
    async def reject(self, i: discord.Interaction, _):
        if not await self.check_permissions(i): return
        try:
            await self.set_status(i, "🔴 Відхилена")
        except Exception as e:
            print(f"❌ Помилка при відхиленні скарги: {e}")

    @discord.ui.button(label="🔒 Закрити", style=discord.ButtonStyle.secondary, custom_id="complaint_close")
    async def close(self, i: discord.Interaction, _):
        if not await self.check_permissions(i): return
        try:
            guild_id = i.guild.id
            data = load_data(guild_id)
            
            cid = self.cid
            if not cid:
                # Спробуємо дістати з футера
                try:
                    footer_text = i.message.embeds[0].footer.text
                    cid = footer_text.split("|")[1].split(":")[1].strip()
                except:
                    pass
            
            if not cid or cid not in data["complaints"]:
                await i.response.send_message("❌ Не вдалося знайти скаргу в базі.", ephemeral=True)
                return

            if data["complaints"][cid]["status"] == "🟡 Відкрита":
                await i.response.send_message("Спочатку розглянь скаргу (прийми або відхили)", ephemeral=True)
                return

            await i.response.defer(ephemeral=True)

            update_complaint_status(cid, "⚫ Закрита")

            embed = i.message.embeds[0]
            embed.set_field_at(4, name="📌 Статус", value="⚫ Закрита", inline=False)
            await i.message.edit(embed=embed, view=None)

            if isinstance(i.channel, discord.Thread):
                try:
                    await i.channel.edit(archived=True, locked=True)
                except:
                    pass

            await i.followup.send("🔒 Скаргу закрито", ephemeral=True)
        except Exception as e:
            print(f"❌ Помилка при закритті скарги: {e}")
            if not i.response.is_done():
                await i.response.send_message(f"❌ Помилка: {e}", ephemeral=True)

    async def set_status(self, i: discord.Interaction, status):
        await i.response.defer(ephemeral=True)
        
        cid = self.cid
        if not cid:
            # Спробуємо дістати з футера або назви
            try:
                embed = i.message.embeds[0]
                # ID в футері: "ID автора: 123 | key: category_1"
                footer_text = embed.footer.text
                if "|" in footer_text:
                    cid = footer_text.split("|")[1].split(":")[1].strip()
                else:
                    # Спроба з назви: "🚨 Скарга #1" -> але це не db_key
                    # Краще завжди мати db_key в футері.
                    pass
            except:
                pass
        
        if not cid:
            await i.followup.send("❌ Не вдалося визначити ID скарги для оновлення статусу.", ephemeral=True)
            return

        update_complaint_status(cid, status)

        embed = i.message.embeds[0]
        embed.set_field_at(4, name="📌 Статус", value=status, inline=False)
        await i.message.edit(embed=embed)

        await i.followup.send(f"Статус оновлено: {status}", ephemeral=True)

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
