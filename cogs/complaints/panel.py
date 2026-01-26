import discord
from discord.ext import commands
from services.database import get_conn  # твоя функція для роботи з БД

class ComplaintPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="panel_players")
    async def panel_players(self, ctx):
        """Відкриває панель для подачі скарг на гравців"""
        embed = discord.Embed(
            title="Скарги на гравців",
            description=(
                "📌 **Правила подачі скарг:**\n"
                "• Обґрунтована причина\n"
                "• Без фейків\n"
                "• Один гравець — одна скарга\n\n"
                "Натисніть кнопку нижче для подачі скарги"
            ),
            color=0xff0000
        )

        view = ComplaintButtonView()
        await ctx.send(embed=embed, view=view)

class ComplaintButtonView(discord.ui.View):
    @discord.ui.button(label="Подати скаргу", style=discord.ButtonStyle.danger)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ComplaintModal())

class ComplaintModal(discord.ui.Modal, title="Скарга на гравця"):
    target = discord.ui.TextInput(label="Нік порушника", required=True)
    reason = discord.ui.TextInput(label="Суть порушення", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Додавання скарги в базу даних
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO complaints (type, author_id, author_name, target, reason) VALUES (?, ?, ?, ?, ?)",
            ("player", interaction.user.id, str(interaction.user), self.target.value, self.reason.value)
        )
        complaint_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Підтвердження автору
        await interaction.response.send_message(
            "✅ Скаргу подано успішно!",
            ephemeral=True
        )

        # Надсилання скарги в канал
        embed = discord.Embed(
            title=f"Скарга №{complaint_id}",
            description=(
                f"👤 **Автор:** {interaction.user.mention}\n"
                f"🎯 **Порушник:** {self.target.value}\n"
                f"📄 **Опис:** {self.reason.value}\n"
                f"📌 **Статус:** Відкрита"
            ),
            color=0xff9900
        )

        channel = interaction.channel  # можеш вказати конкретний канал через bot.get_channel(ID)
        await channel.send(embed=embed)

# Функція setup для завантаження Cog
async def setup(bot):
    await bot.add_cog(ComplaintPanel(bot))
