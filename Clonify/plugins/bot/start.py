import time
import random
import asyncio
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython.__future__ import VideosSearch

import config
from Clonify import app
from Clonify.misc import _boot_
from Clonify.plugins.sudo.sudoers import sudoers_list
from Clonify.utils.database import get_served_chats, get_served_users, get_sudoers
from Clonify.utils import bot_sys_stats
from Clonify.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from Clonify.utils.decorators.language import LanguageStart
from Clonify.utils.formatters import get_readable_time
from Clonify.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS, STREAMI_PICS, GREET
from strings import get_string

# --- DATABASE SETUP ---
try:
    from Clonify.core.mongo import mongodb as db
except ImportError:
    from Clonify.utils.database import mongodb as db

welcome_db = db.welcome_config 

# ================================
#      SET WELCOME COMMANDS
# ================================
# Ye commands sirf aap (ID: 7553434931) use kar payenge
@app.on_message(filters.command(["setwelcome_dm", "setwelcome_grp"]) & filters.user(7553434931))
async def set_welcome_msg(client, message):
    cmd = message.command[0].lower()
    msg_type = "welcome_dm" if "dm" in cmd else "welcome_group"

    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text(
            f"❌ <b>Usage:</b>\n<code>/{cmd} [Your HTML Message]</code>\n\n"
            "<b>Variables:</b>\n"
            "<code>{name}</code> - First Name\n"
            "<code>{mention}</code> - User Link\n"
            "<code>{username}</code> - @Username\n"
            "<code>{bot_name}</code> - Bot Name\n"
            "<code>{chat_name}</code> - Chat Name (Group only)"
        )
        return

    try:
        if message.reply_to_message:
            new_msg = message.reply_to_message.text.html or message.reply_to_message.caption.html
        else:
            new_msg = message.text.html.split(None, 1)[1]
    except (IndexError, AttributeError):
         return await message.reply_text("❌ Text extract nahi kar paya. Dobara try karein.")

    await welcome_db.update_one(
        {"_id": msg_type},
        {"$set": {"message": new_msg}},
        upsert=True
    )
    await message.reply_text(f"✅ <b>{msg_type.replace('_', ' ').upper()} message has been set!</b>")

# Helper to get custom or default caption
async def get_welcome_caption(msg_type, default_text, user, bot, chat=None):
    data = await welcome_db.find_one({"_id": msg_type})
    if data and "message" in data:
        text = data["message"]
        text = text.replace("{name}", user.first_name)
        text = text.replace("{mention}", user.mention)
        text = text.replace("{username}", f"@{user.username}" if user.username else "No Username")
        text = text.replace("{bot_name}", bot.first_name)
        if chat:
            text = text.replace("{chat_name}", chat.title)
        return text
    return default_text

# ================================
#        START COMMAND (DM)
# ================================
@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):

    loading_1 = await message.reply_text(random.choice(GREET))
    await add_served_user(message.from_user.id)
    
    # --- ANIMATION ---
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ᴅɪηɢ ᴅᴏηɢ.❤️‍🔥</b>")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ᴅɪηɢ ᴅᴏηɢ..❤️‍🔥</b>")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>sᴛᴧʀᴛɪηɢ...❤️‍🔥</b>")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ʜєʏ ʙᴧʙʏ! 💞</b>")
    await asyncio.sleep(0.1)
    await loading_1.delete()

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_video(
                random.choice(STREAMI_PICS),
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            return
        if name[0:3] == "inf":
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            results = VideosSearch(query, limit=1)
            for result in (await results.next())["result"]:
                title = result["title"]
                duration = result["duration"]
                views = result["viewCount"]["short"]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                channellink = result["channel"]["link"]
                channel = result["channel"]["name"]
                link = result["link"]
                published = result["publishedTime"]
            searched_text = _["start_6"].format(title, duration, views, published, channellink, channel, app.mention)
            key = InlineKeyboardMarkup([[InlineKeyboardButton(text=_["S_B_8"], url=link), InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_CHAT)]])
            await m.delete()
            return await message.reply_photo(photo=thumbnail, caption=searched_text, reply_markup=key)
    else:
        out = private_panel(_)
        # Check Custom DM Caption
        default_caption = _["start_2"].format(message.from_user.mention, app.mention)
        final_caption = await get_welcome_caption("welcome_dm", default_caption, message.from_user, await client.get_me())

        await message.reply_video(
            random.choice(STREAMI_PICS),
            caption=final_caption,
            reply_markup=InlineKeyboardMarkup(out),
        )
        if await is_on_off(2):
            await app.send_message(
                chat_id=config.LOGGER_ID,
                text=f"✦ {message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n✦ <b>ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n✦ <b>ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}",
            )

# ================================
#        START COMMAND (GROUP)
# ================================
@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    
    # Check Custom Group Caption
    default_caption = _["start_1"].format(app.mention, get_readable_time(uptime))
    final_caption = await get_welcome_caption("welcome_group", default_caption, message.from_user, await client.get_me(), message.chat)

    await message.reply_video(
        random.choice(STREAMI_PICS),
        caption=final_caption,
        reply_markup=InlineKeyboardMarkup(out),
    )
    return await add_served_chat(message.chat.id)

# ================================
#        NEW MEMBER WELCOME
# ================================
@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if await is_banned_user(member.id):
                try: await message.chat.ban_member(member.id)
                except: pass
            
            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)
                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(_["start_5"].format(app.mention, f"https://t.me/{app.username}?start=sudolist", config.SUPPORT_CHAT), disable_web_page_preview=True)
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                
                # Check Custom Welcome Message
                default_caption = _["start_3"].format(message.from_user.mention, app.mention, message.chat.title, app.mention)
                final_caption = await get_welcome_caption("welcome_group", default_caption, member, await client.get_me(), message.chat)

                await message.reply_text(
                    text=final_caption,
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()
        except Exception as ex:
            print(ex)
                    
