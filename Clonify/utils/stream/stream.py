import os
from random import randint
from typing import Union
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from Clonify import Carbon, YouTube, app
from Clonify.core.call import PRO
from Clonify.misc import db
from Clonify.utils.database import add_active_video_chat, is_active_chat
from Clonify.utils.exceptions import AssistantErr
from Clonify.utils.inline import aq_markup, close_markup, stream_markup
from Clonify.utils.stream.queue import put_queue, put_queue_index
from Clonify.utils.pastebin import PROBin
from Clonify.utils.thumbnails import get_thumb

# --- DATABASE SETUP (Mongo Se Connect Karne Ke Liye) ---
try:
    from Clonify.core.mongo import mongodb as mongo_db
except ImportError:
    from Clonify.utils.database import mongodb as mongo_db

stream_db = mongo_db.stream_config 

# ================================
#      SETSTREAM COMMAND (Admin Only)
# ================================
# Ye command sirf aap (ID: 7553434931) use kar payenge
@app.on_message(filters.command("setstream") & filters.user(7553434931))
async def set_stream_template(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ **Usage:** `/setstream [Your Text]`\n\n"
            "**Variables:**\n"
            "• `{link}` - Track Info Link\n"
            "• `{title}` - Song Title\n"
            "• `{duration}` - Time Duration\n"
            "• `{user}` - Requested By"
        )
    
    # Formatting preserve karne ke liye html split kiya hai
    try:
        new_msg = message.text.html.split(None, 1)[1]
    except IndexError:
        return await message.reply_text("❌ Kuch text likhein.")

    await stream_db.update_one(
        {"_id": "stream_caption"}, 
        {"$set": {"message": new_msg}}, 
        upsert=True
    )
    await message.reply_text("✅ **Stream Now Playing Caption Updated in MongoDB!**")

# Helper function to get caption
async def get_stream_caption(_, link, title, duration, user):
    data = await stream_db.find_one({"_id": "stream_caption"})
    if data and "message" in data:
        text = data["message"]
        # Replace Placeholders
        final_text = text.replace("{link}", str(link)) \
                         .replace("{title}", str(title)) \
                         .replace("{duration}", str(duration)) \
                         .replace("{user}", str(user))
        return final_text
    
    # Default message agar DB empty ho
    return _["stream_1"].format(link, title, duration, user)


# ================================
#        MAIN STREAM FUNCTION
# ================================
async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return
    if forceplay:
        await PRO.force_stop_stream(chat_id)
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                (title, duration_min, duration_sec, thumbnail, vidid) = await YouTube.details(search, False if spotify else True)
            except:
                continue
            if str(duration_min) == "None" or duration_sec > config.DURATION_LIMIT:
                continue

            if await is_active_chat(chat_id):
                await put_queue(chat_id, original_chat_id, f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio")
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                status = True if video else None
                try:
                    file_path, direct = await YouTube.download(vidid, mystic, video=status, videoid=True)
                except:
                    raise AssistantErr(_["play_14"])
                await PRO.join_call(chat_id, original_chat_id, file_path, video=status, image=thumbnail)
                await put_queue(chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio", forceplay=forceplay)
                
                img = await get_thumb(vidid)
                button = stream_markup(_, chat_id)
                
                # --- CUSTOM CAPTION ---
                track_link = f"https://t.me/{app.username}?start=info_{vidid}"
                cap = await get_stream_caption(_, track_link, title[:23], duration_min, user_name)

                run = await app.send_photo(original_chat_id, photo=img, caption=cap, reply_markup=InlineKeyboardMarkup(button))
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        
        if count == 0: return
        else:
            link = await PROBin(msg)
            car = os.linesep.join(msg.split(os.linesep)[:17]) if msg.count("\n") >= 17 else msg
            carbon = await Carbon.generate(car, randint(100, 10000000))
            return await app.send_photo(original_chat_id, photo=carbon, caption=_["play_21"].format(position, link), reply_markup=close_markup(_))

    elif streamtype == "youtube":
        vidid = result["vidid"]
        title, duration_min, thumbnail = (result["title"]).title(), result["duration_min"], result["thumb"]
        status = True if video else None
        try:
            file_path, direct = await YouTube.download(vidid, mystic, videoid=True, video=status)
        except:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio")
            position = len(db.get(chat_id)) - 1
            await app.send_message(chat_id=original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay: db[chat_id] = []
            await PRO.join_call(chat_id, original_chat_id, file_path, video=status, image=thumbnail)
            await put_queue(chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio", forceplay=forceplay)
            
            img = await get_thumb(vidid)
            button = stream_markup(_, chat_id)
            
            # --- CUSTOM CAPTION ---
            track_link = f"https://t.me/{app.username}?start=info_{vidid}"
            cap = await get_stream_caption(_, track_link, title[:23], duration_min, user_name)

            run = await app.send_photo(original_chat_id, photo=img, caption=cap, reply_markup=InlineKeyboardMarkup(button))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

    elif streamtype == "soundcloud":
        file_path, title, duration_min = result["filepath"], result["title"], result["duration_min"]
        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "audio")
            position = len(db.get(chat_id)) - 1
            await app.send_message(chat_id=original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay: db[chat_id] = []
            await PRO.join_call(chat_id, original_chat_id, file_path, video=None)
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "audio", forceplay=forceplay)
            
            button = stream_markup(_, chat_id)
            # --- CUSTOM CAPTION ---
            cap = await get_stream_caption(_, config.SUPPORT_CHAT, title[:23], duration_min, user_name)

            run = await app.send_photo(original_chat_id, photo=config.SOUNCLOUD_IMG_URL, caption=cap, reply_markup=InlineKeyboardMarkup(button))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "telegram":
        file_path, link, title, duration_min = result["path"], result["link"], (result["title"]).title(), result["dur"]
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "video" if video else "audio")
            position = len(db.get(chat_id)) - 1
            await app.send_message(chat_id=original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay: db[chat_id] = []
            await PRO.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "video" if video else "audio", forceplay=forceplay)
            if video: await add_active_video_chat(chat_id)
            
            button = stream_markup(_, chat_id)
            # --- CUSTOM CAPTION ---
            cap = await get_stream_caption(_, link, title[:23], duration_min, user_name)

            run = await app.send_photo(original_chat_id, photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL, caption=cap, reply_markup=InlineKeyboardMarkup(button))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "live":
        link, vidid, title, thumbnail = result["link"], result["vidid"], (result["title"]).title(), result["thumb"]
        duration_min = "Live Track"
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, f"live_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio")
            position = len(db.get(chat_id)) - 1
            await app.send_message(chat_id=original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay: db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0: raise AssistantErr(_["str_3"])
            await PRO.join_call(chat_id, original_chat_id, file_path, video=status, image=thumbnail if thumbnail else None)
            await put_queue(chat_id, original_chat_id, f"live_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio", forceplay=forceplay)
            
            img = await get_thumb(vidid)
            button = stream_markup(_, chat_id)
            # --- CUSTOM CAPTION ---
            track_link = f"https://t.me/{app.username}?start=info_{vidid}"
            cap = await get_stream_caption(_, track_link, title[:23], duration_min, user_name)

            run = await app.send_photo(original_chat_id, photo=img, caption=cap, reply_markup=InlineKeyboardMarkup(button))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        link, title, duration_min = result, "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ", "00:00"
        if await is_active_chat(chat_id):
            await put_queue_index(chat_id, original_chat_id, "index_url", title, duration_min, user_name, link, "video" if video else "audio")
            position = len(db.get(chat_id)) - 1
            await mystic.edit_text(text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay: db[chat_id] = []
            await PRO.join_call(chat_id, original_chat_id, link, video=True if video else None)
            await put_queue_index(chat_id, original_chat_id, "index_url", title, duration_min, user_name, link, "video" if video else "audio", forceplay=forceplay)
            
            button = stream_markup(_, chat_id)
            run = await app.send_photo(original_chat_id, photo=config.STREAM_IMG_URL, caption=_["stream_2"].format(user_name), reply_markup=InlineKeyboardMarkup(button))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
        
