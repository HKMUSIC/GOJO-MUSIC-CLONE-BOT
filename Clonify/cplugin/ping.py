import time
import psutil
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from config import SUPPORT_CHAT, PING_IMG_URL
from .utils import StartTime
from Clonify.utils import get_readable_time
from Clonify.utils.database.clonedb import get_owner_id_from_db, get_cloned_support_chat, get_cloned_support_channel

# --- DATABASE SETUP ---
try:
    from Clonify.core.mongo import mongodb as db
except ImportError:
    from Clonify.utils.database import mongodb as db

ping_db = db.ping_config 

# ================================
#      SET PING MSG COMMAND
# ================================
# Ye command sirf aap (ID: 7553434931) use kar payenge
@Client.on_message(filters.command("setping") & filters.user(7553434931))
async def set_ping_msg(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ **Usage:** `/setping [Your Message]`\n\n"
            "**Available Placeholders:**\n"
            "• `{ping}` - Bot Speed\n"
            "• `{uptime}` - Online Time\n"
            "• `{ram}` - RAM usage\n"
            "• `{cpu}` - CPU usage\n"
            "• `{disk}` - Disk usage\n"
            "• `{mention}` - Bot Mention"
        )
    
    try:
        # Bold/Italic formatting preserve karne ke liye html use kiya hai
        new_msg = message.text.html.split(None, 1)[1]
    except IndexError:
        return await message.reply_text("❌ Kuch text likhein command ke baad.")

    await ping_db.update_one(
        {"_id": "ping_msg"}, 
        {"$set": {"message": new_msg}}, 
        upsert=True
    )
    await message.reply_text("✅ **Custom Ping message set ho gaya hai!**")


# ================================
#         PING COMMAND
# ================================
@Client.on_message(filters.command("ping"))
async def ping_clone(client: Client, message: Message):
    start_time = datetime.now()
    bot = await client.get_me()

    # Cloned Bot Support Info
    C_BOT_SUPPORT_CHAT = await get_cloned_support_chat(bot.id)
    C_SUPPORT_CHAT = f"https://t.me/{C_BOT_SUPPORT_CHAT}"

    # Initial Loading Message
    hmm = await message.reply_photo(
        photo=PING_IMG_URL, 
        caption=f"{bot.mention} ɪs ᴘɪɴɢɪɴɢ..."
    )

    # System Stats Calculate Karna
    upt = int(time.time() - StartTime)
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    uptime = get_readable_time(upt)
    
    # Speed calculate karna (ms)
    resp = (datetime.now() - start_time).microseconds / 1000

    # Database se Custom Message uthana
    data = await ping_db.find_one({"_id": "ping_msg"})
    
    if data and "message" in data:
        custom_text = data["message"]
        # Placeholders ko asli data se replace karna
        final_caption = custom_text.replace("{ping}", f"{resp}ms") \
                                   .replace("{uptime}", str(uptime)) \
                                   .replace("{ram}", f"{mem}%") \
                                   .replace("{cpu}", f"{cpu}%") \
                                   .replace("{disk}", f"{disk}%") \
                                   .replace("{mention}", bot.mention)
    else:
        # Default message agar database mein kuch set nahi hai
        final_caption = (
            f"➻ ᴩᴏɴɢ : `{resp}ᴍs` \n\n"
            f"<b><u>{bot.mention} sʏsᴛᴇᴍ sᴛᴀᴛs :</u></b>\n\n"
            f"๏ **ᴜᴩᴛɪᴍᴇ :** {uptime}\n"
            f"๏ **ʀᴀᴍ :** {mem}%\n"
            f"๏ **ᴄᴩᴜ :** {cpu}%\n"
            f"๏ **ᴅɪsᴋ :** {disk}%"
        )

    await hmm.edit_text(
        final_caption,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url=C_SUPPORT_CHAT)],
            ]
        ),
    )
    
