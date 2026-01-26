import discord
from datetime import datetime
from config import get_guild_config

async def send_mod_log(bot, guild, action_type, admin, target, reason, details=None):
    """
    Sends a moderation log embed to the configured log channel.
    """
    print(f"🔍 [DEBUG] send_mod_log START: Action={action_type}", flush=True)
    g_cfg = get_guild_config(guild.id)
    if not g_cfg:
        print(f"⚠️ [DEBUG] No config found for guild {guild.id}", flush=True)
        return

    # Визначаємо ключ каналу на основі типу дії
    channel_key = "role_log_channel_id" if action_type == "Role Issued" else "mod_log_channel_id"
    print(f"🔍 [DEBUG] Selected channel_key: {channel_key}", flush=True)
    
    if channel_key not in g_cfg:
        print(f"⚠️ [DEBUG] key {channel_key} not in config. Falling back to mod_log_channel_id", flush=True)
        # fallback to general mod log if specific one is missing
        channel_key = "mod_log_channel_id"
        if channel_key not in g_cfg:
            print(f"⚠️ [DEBUG] mod_log_channel_id also missing in config.", flush=True)
            return

    channel_id = g_cfg[channel_key]
    print(f"🔍 [DEBUG] Final channel_id: {channel_id}", flush=True)
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"🔍 [DEBUG] Channel not in cache. Fetching...", flush=True)
        try:
            channel = await bot.fetch_channel(channel_id)
            print(f"✅ [DEBUG] Channel fetched successfully.", flush=True)
        except Exception as e:
            print(f"❌ [DEBUG] Failed to fetch channel {channel_id}: {e}", flush=True)
            return

    print(f"🔍 [DEBUG] Preparing embed for channel #{channel.name}...", flush=True)
    
    colors = {
        "Ban": discord.Color.red(),
        "Unban": discord.Color.green(),
        "Mute": discord.Color.orange(),
        "Unmute": discord.Color.blue(),
        "Warn": discord.Color.yellow(),
        "Unwarn": discord.Color.light_grey(),
        "Role Issued": discord.Color.purple()
    }

    embed = discord.Embed(
        title=f"📝 Модерація: {action_type}",
        color=colors.get(action_type, discord.Color.blue()),
        timestamp=datetime.now()
    )

    embed.add_field(name="👤 Користувач", value=f"{target.mention} ({target.id})", inline=False)
    embed.add_field(name="🛡️ Адміністратор", value=f"{admin.mention}", inline=False)
    embed.add_field(name="📂 Причина", value=reason, inline=False)
    
    if details:
        embed.add_field(name="ℹ️ Деталі", value=details, inline=False)

    embed.set_footer(text=f"ID Користувача: {target.id}")
    
    try:
        await channel.send(embed=embed)
        print(f"✅ [DEBUG] Log successfully sent to Discord!", flush=True)
    except Exception as e:
        print(f"❌ [DEBUG] Failed to send message to log channel: {e}", flush=True)
