import discord
from discord.ext import commands
from discord import app_commands
from config import get_guild_config

class AppPublisher(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.default_target_channel_id = 1390025739688214578
        self.default_leader_channel_id = 1388960880758358158
        self.required_role_name = "Developer UA Online"

    ORG_CHOICES = [
        app_commands.Choice(name="СБУ К", value="СБУ К"),
        app_commands.Choice(name="СБУ Д", value="СБУ Д"),
        app_commands.Choice(name="СБУ Л", value="СБУ Л"),
        app_commands.Choice(name="МОЗ Л", value="МОЗ Л"),
        app_commands.Choice(name="МОЗ Д", value="МОЗ Д"),
        app_commands.Choice(name="МОЗ К", value="МОЗ К"),
        app_commands.Choice(name="ВРУ", value="ВРУ"),
        app_commands.Choice(name="ТСН", value="ТСН"),
        app_commands.Choice(name="ТЦК", value="ТЦК"),
        app_commands.Choice(name="ЗСУ", value="ЗСУ"),
        app_commands.Choice(name="НПУ К", value="НПУ К"),
        app_commands.Choice(name="НПУ Д", value="НПУ Д"),
        app_commands.Choice(name="НПУ Л", value="НПУ Л")
    ]

    @app_commands.command(name="publish_apps", description="Публікація шаблонів заявок на старший склад")
    @app_commands.describe(organization="Оберіть організацію для публікації заявки")
    @app_commands.choices(organization=ORG_CHOICES)
    async def publish_apps(self, interaction: discord.Interaction, organization: app_commands.Choice[str]):
        # Перевірка наявності ролі "Куратор Держ."
        has_role = any(role.name == self.required_role_name for role in interaction.user.roles)
        
        if not has_role:
            await interaction.response.send_message(f"У вас немає ролі **{self.required_role_name}** для цієї дії.", ephemeral=True)
            return

        # Отримуємо ID каналу з конфігурації
        guild_id = interaction.guild.id
        g_cfg = get_guild_config(guild_id)
        target_channel_id = self.default_target_channel_id
        
        if g_cfg and "applications_channel_id" in g_cfg:
            target_channel_id = g_cfg["applications_channel_id"]

        try:
            channel = await self.bot.fetch_channel(target_channel_id)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ **Помилка доступу (403 Forbidden)!**\n\n"
                f"Бот не має прав доступу до каналу з ID: `{target_channel_id}`.\n"
                f"**Виправлення:**\n"
                f"1. Переконайтеся, що бот знаходиться на сервері, де створено цей канал.\n"
                f"2. Надайте боту права **'Перегляд каналу' (View Channel)** та **'Надсилати повідомлення' (Send Messages)** у цьому каналі.\n"
                f"3. Якщо канал є форумом, додайте право **'Створювати публічні гілки' (Create Public Threads)**.",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"Помилка при пошуку каналу {target_channel_id}: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Починаю публікацію заявки для {organization.name}...", ephemeral=True)

        title = f"Заявки на Старший Склад (7-8-9) | {organization.name}"
        description = f"""**ЗАЯВКА на старший склад / заступника**
**Базові дані**
1. Нікнейм та id ігрового акаунту: ??? | ???
2. Ранг і фракція на яку подаєте: 
3. Реальний вік: ?? повних років
4. Рівень у грі: 
5. Середній добовий онлайн (/time): ? год
6. Які були серйозні покарання в грі (бан, варн) (надати відеозапис із гри /history 1, 5, 18, 19):
7. Які маєте твінк-акаунти (перелічити нікнейми та надати скріншот персонажів до входу в гру):
8. Місто, де насправді проживаєте:
9. Які обіймали ранги старшого складу та яких фракцій (скріншоти /wbook): 
10. Чи знімався з посади 7-8/9/лідерства (якщо так, то причини): 
11. Вказати фракції, де призначалися на пост лідера/заступника та тривалість кожного свого строку на посаді у календарних днях:
12. Тег Discord: @
**Питання до кандидатів:**
13. Чи готові отримати покарання за передбачасне залишення посади чи інші порушення?:
14. Опишіть себе (дайте собі характеристику):
15. Чому саме Ви повинні обійняти посаду, на яку претендуєте?: 
16. Які ідеї маєте для покращення фракції?: 
**Дата подання:**

У заявці заповнюєте поля із ?? та порожні поля.
**Обов'язково надати:**
- скріншот із входу в гру, де видно ID акаунта та нікнейми персонажів;
- статистика персонажа (два скріншота);
- скріншоти /wbook де видно посади на лідерку/заступника/7-8 ранги. Якщо вас знімали із цих посад, то повідомте;
- відеозапис /history де видно бан, варн.

**Хостинг**
Відео https://gofile.io/home
Фото https://postimages.org/"""

        try:
            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.green()
            )
            
            if isinstance(channel, discord.ForumChannel):
                # Пошук тегу для форуму
                applied_tags = []
                if channel.available_tags:
                    # Шукаємо тег "Відкрита" або просто беремо перший доступний
                    tag = next((t for t in channel.available_tags if "відкрита" in t.name.lower()), channel.available_tags[0])
                    applied_tags = [tag]
                
                await channel.create_thread(name=title, embed=embed, applied_tags=applied_tags)
            else:
                await channel.send(embed=embed)
            
            await interaction.followup.send(f"Заявку для **{organization.name}** успішно опубліковано!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ **Помилка доступу (403 Forbidden) при відправці!**\n\n"
                f"Бот знайшов канал, але не зміг надіслати в нього повідомлення.\n"
                f"Перевірте права бота у каналі <#{target_channel_id}>.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Критична помилка при відправці: {e}", ephemeral=True)

    @app_commands.command(name="publish_leader_apps", description="Публікація шаблонів заявок на Лідера")
    @app_commands.describe(organization="Оберіть організацію для публікації заявки на лідера")
    @app_commands.choices(organization=ORG_CHOICES)
    async def publish_leader_apps(self, interaction: discord.Interaction, organization: app_commands.Choice[str]):
        # Перевірка наявності ролі "Куратор Держ."
        has_role = any(role.name == self.required_role_name for role in interaction.user.roles)
        
        if not has_role:
            await interaction.response.send_message(f"У вас немає ролі **{self.required_role_name}** для цієї дії.", ephemeral=True)
            return

        # Отримуємо ID каналу з конфігурації
        guild_id = interaction.guild.id
        g_cfg = get_guild_config(guild_id)
        target_channel_id = self.default_leader_channel_id
        
        if g_cfg and "leader_applications_channel_id" in g_cfg:
            target_channel_id = g_cfg["leader_applications_channel_id"]

        try:
            channel = await self.bot.fetch_channel(target_channel_id)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ **Помилка доступу (403 Forbidden)!**\n\n"
                f"Бот не має прав доступу до каналу з ID: `{target_channel_id}`.\n"
                f"Перевірте права бота у каналі або на сервері.",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"Помилка при пошуку каналу {target_channel_id}: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Починаю публікацію заявки на лідера для {organization.name}...", ephemeral=True)

        title = f"Заявка на посаду лідера | {organization.name}"
        description = f"""**ЗАЯВКА на Лідера**
**Базові дані**
1. Нікнейм та id ігрового акаунту: ??? | ???
2. Ранг і фракція на яку подаєте: 
3. Реальний вік: ?? повних років
4. Рівень у грі: 
5. Середній добовий онлайн (/time): ? год
6. Які були серйозні покарання в грі (бан, варн) (надати відеозапис із гри /history 1, 5, 18, 19):
7. Які маєте твінк-акаунти (перелічити нікнейми та надати скріншот персонажів до входу в гру):
8. Місто, де насправді проживаєте:
9. Які обіймали ранги старшого складу та яких фракцій (скріншоти /wbook): 
10. Чи знімався з посади 7-8/9/лідерства (якщо так, то причини): 
11. Вказати фракції, де призначалися на пост лідера/заступника та тривалість кожного свого строку на посаді у календарних днях:
12. Тег Discord: @
**Питання до кандидатів:**
13. Чи готові отримати покарання за передбачасне залишення посади чи інші порушення?:
14. Опишіть себе (дайте собі характеристику):
15. Чому саме Ви повинні обійняти посаду, на яку претендуєте?: 
16. Які ідеї маєте для покращення фракції?: 
**Дата подання:**"""

        try:
            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.gold()
            )
            
            if isinstance(channel, discord.ForumChannel):
                # Пошук тегу для форуму
                applied_tags = []
                if channel.available_tags:
                    # Шукаємо тег "Лідер" або просто беремо перший доступний
                    tag = next((t for t in channel.available_tags if "лідер" in t.name.lower()), channel.available_tags[0])
                    applied_tags = [tag]
                
                await channel.create_thread(name=title, embed=embed, applied_tags=applied_tags)
            else:
                await channel.send(embed=embed)
            
            await interaction.followup.send(f"Заявку на лідера для **{organization.name}** успішно опубліковано!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ **Помилка доступу (403 Forbidden) при відправці!**\n\n"
                f"Бот знайшов канал, але не зміг надіслати в нього повідомлення.\n"
                f"Перевірте права бота у каналі <#{target_channel_id}>.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Критична помилка при відправці: {e}", ephemeral=True)

    @app_commands.command(name="publish_complaints", description="Публікація панелей для подання скарг")
    @app_commands.describe(category="Оберіть категорію скарги для публікації")
    @app_commands.choices(category=[
        app_commands.Choice(name="Гравці", value="players"),
        app_commands.Choice(name="Лідери", value="leaders"),
        app_commands.Choice(name="Держ. службовці", value="gov"),
        app_commands.Choice(name="Учасники сімей", value="family"),
        app_commands.Choice(name="Адміністрація", value="admin"),
        app_commands.Choice(name="Модерація", value="moderation")
    ])
    async def publish_complaints(self, interaction: discord.Interaction, category: app_commands.Choice[str]):
        # Перевірка наявності ролі "Куратор Держ."
        has_role = any(role.name == self.required_role_name for role in interaction.user.roles)
        
        if not has_role:
            await interaction.response.send_message(f"У вас немає ролі **{self.required_role_name}** для цієї дії.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        g_cfg = get_guild_config(guild_id)
        
        if not g_cfg:
            await interaction.response.send_message("❌ Конфігурація для цього сервера не знайдена в guilds_config.json", ephemeral=True)
            return

        complaint_config = g_cfg.get("complaint_config", {})
        category_cfg = complaint_config.get(category.value)
        
        if not category_cfg:
            await interaction.response.send_message(f"❌ Категорія '{category.value}' не налаштована для цього сервера.", ephemeral=True)
            return

        rules_text = g_cfg.get("rules", "")
        target_channel_id = category_cfg["channel_id"]

        try:
            channel = await self.bot.fetch_channel(target_channel_id)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ **Помилка доступу (403 Forbidden)!**\n\n"
                f"Бот не має прав доступу до каналу з ID: `{target_channel_id}`.\n"
                f"**Виправлення:**\n"
                f"1. Переконайтеся, що бот знаходиться на сервері, де створено цей канал.\n"
                f"2. Надайте боту права **'Перегляд каналу' (View Channel)** та **'Надсилати повідомлення' (Send Messages)** у цьому каналі.\n"
                f"3. Якщо канал є форумом, додайте право **'Створювати публічні гілки' (Create Public Threads)**.",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"Помилка при пошуку каналу {target_channel_id}: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Починаю публікацію панелі скарг для категорії **{category.name}**...", ephemeral=True)

        # Build embed
        description = f"{rules_text}\n\n{category_cfg['description']}" if rules_text else category_cfg["description"]
        embed = discord.Embed(
            title=f"{category_cfg['emoji']} {category_cfg['title']}",
            description=description,
            color=category_cfg["color"]
        )
        from datetime import datetime
        footer_text = f"Дякуємо за допомогу в покращенні нашого серверу! | {datetime.now().strftime('%d.%m.%Y, %H:%M')}"
        embed.set_footer(text=footer_text)

        # Import ComplaintLauncherView
        from panel import ComplaintLauncherView
        view = ComplaintLauncherView(self.bot, category.value)

        try:
            if isinstance(channel, discord.ForumChannel):
                # Пошук тегу для форуму
                applied_tags = []
                if channel.available_tags:
                    # Шукаємо перший доступний тег
                    applied_tags = [channel.available_tags[0]]
                
                await channel.create_thread(
                    name=f"📌 {category_cfg['title']}", 
                    embed=embed, 
                    view=view,
                    applied_tags=applied_tags
                )
            else:
                await channel.send(embed=embed, view=view)
            
            await interaction.followup.send(f"✅ Панель скарг для категорії **{category.name}** успішно опубліковано!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ **Помилка доступу (403 Forbidden) при відправці!**\n\n"
                f"Бот знайшов канал, але не зміг надіслати в нього повідомлення.\n"
                f"Перевірте права бота у каналі <#{target_channel_id}>.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Критична помилка при відправці: {e}", ephemeral=True)
