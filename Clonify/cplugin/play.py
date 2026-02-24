import os
import random
import string
import asyncio
import urllib.parse
import aiohttp
from time import time

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
from pytgcalls.exceptions import NoActiveGroupCall

import config
from config import BANNED_USERS, lyrical

from Clonify import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, app
from Clonify.core.call import PRO
from Clonify.misc import SUDOERS
from Clonify.utils.inline import panel_markup_clone
from Clonify.utils import seconds_to_min, time_to_seconds
from Clonify.utils.channelplay import get_channeplayCB
from Clonify.utils.decorators.language import languageCB
from Clonify.utils.decorators.play import CPlayWrapper
from Clonify.utils.formatters import formats
from Clonify.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from Clonify.utils.database import (
    add_served_chat_clone,
    add_served_user_clone,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from Clonify.utils.logger import play_logs, clone_bot_logs
from Clonify.cplugin.setinfo import get_logging_status, get_log_channel
from Clonify.utils.extraction import extract_user
from Clonify.utils.stream.stream import stream


# ========================================================
# 🚀 JIOSAAVN CONFIG & CACHE
# ========================================================

JIOSAAVN_CACHE = {}
JIOSAAVN_API = "https://jiosavan-lilac.vercel.app/api/search/songs?query="


async def jiosaavn_play_logic(query):
    cache_key = query.lower().strip()
    if cache_key in JIOSAAVN_CACHE:
        return JIOSAAVN_CACHE[cache_key]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                JIOSAAVN_API + urllib.parse.quote(query), timeout=6
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    songs = data.get("data", {}).get("results", []) or data.get("results", [])
                    if songs:
                        song = songs[0]
                        stream_url = song["downloadUrl"][-1]["url"]
                        title = song["name"].replace("&quot;", '"').replace("&#039;", "'")
                        thumb = song["image"][-1]["url"]
                        duration_sec = int(song.get("duration", 0))
                        mins = duration_sec // 60
                        secs = duration_sec % 60
                        duration_str = f"{mins}:{secs:02d}"

                        result_tuple = (stream_url, title, thumb, duration_str)
                        JIOSAAVN_CACHE[cache_key] = result_tuple
                        return result_tuple
    except Exception:
        pass

    return None, None, None, None


# ========================================================
# SPAM PROTECTION
# ========================================================

user_last_message_time = {}
user_command_count = {}

SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5


@Client.on_message(
    filters.command(
        [
            "play", "vplay", "cplay", "cvplay",
            "playforce", "vplayforce", "cplayforce", "cvplayforce",
        ],
        prefixes=["/", "!", "%", ".", "@", "#"],
    )
    & filters.group
    & ~BANNED_USERS
)
@CPlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):

    cuser = await client.get_me()
    bot_id = cuser.id
    user_id = message.from_user.id

    # ====================================================
    # SAFE LOGGING FIX (CHANNEL_INVALID FIXED)
    # ====================================================

    try:
        C_LOG_STATUS = get_logging_status(bot_id)
        C_LOGGER_ID = get_log_channel(bot_id)
    except Exception:
        C_LOG_STATUS = False
        C_LOGGER_ID = None

    if not C_LOGGER_ID or not str(C_LOGGER_ID).startswith("-100"):
        C_LOG_STATUS = False
        clone_logger_id = None
    else:
        clone_logger_id = C_LOGGER_ID

    # ====================================================
    # SPAM CONTROL
    # ====================================================

    now = time()
    last = user_last_message_time.get(user_id, 0)

    if now - last < SPAM_WINDOW_SECONDS:
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            hu = await message.reply_text(
                f"{message.from_user.mention} please don't spam. Try again after 5 sec."
            )
            await asyncio.sleep(3)
            await hu.delete()
            return
    else:
        user_command_count[user_id] = 1

    user_last_message_time[user_id] = now

    await add_served_user_clone(message.chat.id, bot_id)

    mystic = await message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_name = message.from_user.first_name

    # ====================================================
    # TEXT QUERY MODE
    # ====================================================

    if not url:

        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["play_18"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        query = message.text.split(None, 1)[1].replace("-v", "")

        # ===============================
        # JioSaavn Direct Mode
        # ===============================

        if str(playmode) == "Direct" and not video:
            stream_url, js_title, js_thumb, js_dur = await jiosaavn_play_logic(query)

            if stream_url:
                details = {
                    "title": js_title,
                    "link": stream_url,
                    "path": stream_url,
                    "dur": js_dur,
                }
                try:
                    await stream(
                        client,
                        _,
                        mystic,
                        user_id,
                        details,
                        chat_id,
                        user_name,
                        message.chat.id,
                        video=video,
                        streamtype="telegram",
                        forceplay=fplay,
                    )
                    await mystic.delete()

                    if C_LOG_STATUS and clone_logger_id:
                        await clone_bot_logs(
                            client,
                            message,
                            cuser.mention,
                            clone_logger_id,
                            "JioSaavn",
                        )

                    return await play_logs(message, streamtype="JioSaavn")

                except Exception:
                    pass

        # ===============================
        # YouTube Fallback
        # ===============================

        try:
            details, track_id = await YouTube.track(query)
        except Exception as e:
            return await mystic.edit_text(f"YouTube Error:\n{e}")

        streamtype = "youtube"
        slider = True

    # ====================================================
    # URL MODE (Safe)
    # ====================================================

    else:
        try:
            await stream(
                client,
                _,
                mystic,
                user_id,
                url,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype="index",
                forceplay=fplay,
            )
        except Exception as e:
            return await mystic.edit_text(str(e))

        await mystic.delete()

        if C_LOG_STATUS and clone_logger_id:
            await clone_bot_logs(
                client,
                message,
                cuser.mention,
                clone_logger_id,
                "URL",
            )

        return await play_logs(message, streamtype="URL")

    # ====================================================
    # FINAL EXECUTION (SAME LOGIC)
    # ====================================================

    if str(playmode) == "Direct":

        if details.get("duration_min"):
            if time_to_seconds(details["duration_min"]) > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(config.DURATION_LIMIT_MIN, cuser.mention)
                )

        try:
            await stream(
                client,
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
        except Exception as e:
            return await mystic.edit_text(str(e))

        await mystic.delete()

        if C_LOG_STATUS and clone_logger_id:
            await clone_bot_logs(
                client,
                message,
                cuser.mention,
                clone_logger_id,
                streamtype=streamtype,
            )

        return await play_logs(message, streamtype=streamtype)

    else:

        if slider:
            buttons = slider_markup(
                _,
                track_id,
                user_id,
                query,
                0,
                "c" if channel else "g",
                "f" if fplay else "d",
            )

            await mystic.delete()

            await message.reply_photo(
                photo=details["thumb"],
                caption=_["play_10"].format(
                    details["title"].title(),
                    details["duration_min"],
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
            )

            if C_LOG_STATUS and clone_logger_id:
                await clone_bot_logs(
                    client,
                    message,
                    cuser.mention,
                    clone_logger_id,
                    "Searched on Youtube",
                )

            return await play_logs(message, streamtype="Searched on Youtube")
                        
# Zeo
@Client.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_music(client: Client, CallbackQuery, _):
    cuser = await client.get_me()
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    try:
        details, track_id = await YouTube.track(vidid, True)
    except:

        os.system(f"kill -9 {os.getpid()} && bash start")
    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, cuser.mention)
            )
    else:
        buttons = livestream_markup(
            _,
            track_id,
            CallbackQuery.from_user.id,
            mode,
            "c" if cplay == "c" else "g",
            "f" if fplay else "d",
        )
        return await mystic.edit_text(
            _["play_13"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    try:
        await stream(
            client,
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        print(e)
        return await mystic.edit_text(e)
    return await mystic.delete()


@Client.on_callback_query(filters.regex("ZEOmousAdmin") & ~BANNED_USERS)
async def ZEOmous_check(client: Client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\nᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except:
        pass


@Client.on_callback_query(filters.regex("ZEOPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client: Client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        videoid,
        user_id,
        ptype,
        mode,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except:

            os.system(f"kill -9 {os.getpid()} && bash start")
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:

            os.system(f"kill -9 {os.getpid()} && bash start")
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:

            os.system(f"kill -9 {os.getpid()} && bash start")
    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:

            os.system(f"kill -9 {os.getpid()} && bash start")
    if ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except:

            os.system(f"kill -9 {os.getpid()} && bash start")
    try:
        await stream(
            client,
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        print(e)
        return await mystic.edit_text(e)
    return await mystic.delete()


@Client.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client: Client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        what,
        rtype,
        query,
        user_id,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    what = str(what)
    rtype = int(rtype)
    if what == "F":
        if rtype == 9:
            query_type = 0
        else:
            query_type = int(rtype + 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )


# -----------------------------------------------------STREAM----------------------------------------#

import os
from random import randint
from typing import Union
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup

import config
from Clonify import Carbon, YouTube
from Clonify.core.call import PRO
from Clonify.misc import db
from Clonify.utils.database import add_active_video_chat, is_active_chat
from Clonify.utils.exceptions import AssistantErr
from Clonify.utils.inline import (
    aq_markup,
    queuemarkup,
    close_markup,
    stream_markup,
    stream_markup2,
    panel_markup_4,
)
from Clonify.utils.pastebin import PROBin
from Clonify.utils.stream.queue import put_queue, put_queue_index
from youtubesearchpython.__future__ import VideosSearch
from Clonify.utils.database.clonedb import get_owner_id_from_db, get_cloned_support_chat, get_cloned_support_channel


async def stream(
    client,
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
    
    a = await client.get_me()
    C_BOT_OWNER_ID = get_owner_id_from_db(a.id)

    #Cloned Bot Support Chat and channel
    C_BOT_SUPPORT_CHAT = await get_cloned_support_chat(a.id)
    C_SUPPORT_CHAT = f"https://t.me/{C_BOT_SUPPORT_CHAT}"
    C_BOT_SUPPORT_CHANNEL = await get_cloned_support_channel(a.id)
    C_SUPPORT_CHANNEL = f"https://t.me/{C_BOT_SUPPORT_CHANNEL}"

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
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = await YouTube.details(search, False if spotify else True)
            except:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                status = True if video else None
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=status, videoid=True
                    )
                except:

                    os.system(f"kill -9 {os.getpid()} && bash start")
                await PRO.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=status,
                    image=thumbnail,
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                img = await get_thumb(vidid)
                i = await client.get_me()
                button = panel_markup_clone(_, vidid, chat_id)
                run = await client.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{i.username}?start=info_{vidid}",
                        title[:18],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )

                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        if count == 0:
            return
        else:
            link = await PROBin(msg)
            lines = msg.count("\n")
            if lines >= 17:
                car = os.linesep.join(msg.split(os.linesep)[:17])
            else:
                car = msg
            carbon = await Carbon.generate(car, randint(100, 10000000))
            upl = close_markup(_)
            return await client.send_photo(
                original_chat_id,
                photo=carbon,
                caption=_["play_21"].format(position, link),
                reply_markup=upl,
            )
    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        status = True if video else None
        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, videoid=True, video=status
            )
        except:

            os.system(f"kill -9 {os.getpid()} && bash start")
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            img = await get_thumb(vidid)
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await client.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:18], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await PRO.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await get_thumb(vidid)
            i = await client.get_me()
            button = panel_markup_clone(_, vidid, chat_id)
            run = await client.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{i.username}?start=info_{vidid}",
                    title[:18],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )

            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await client.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:18], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await PRO.join_call(chat_id, original_chat_id, file_path, video=None)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            button = stream_markup2(_, chat_id)
            run = await client.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    C_SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await client.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:18], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await PRO.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            if video:
                await add_active_video_chat(chat_id)
            button = stream_markup2(_, chat_id)
            run = await client.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                caption=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "Live Track"
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await client.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:18], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            await PRO.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail if thumbnail else None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await get_thumb(vidid)
            i = await client.get_me()
            button = stream_markup2(_, chat_id)
            run = await client.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{i.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"
        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text("**❀≽ 𝐀ɗɗɘɗ 𝐓σ 𝐐ʋɘʋɘ ✭ Ʌʈ**")

        else:
            if not forceplay:
                db[chat_id] = []
            await PRO.join_call(
                chat_id,
                original_chat_id,
                link,
                video=True if video else None,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            button = stream_markup2(_, chat_id)
            run = await client.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()


async def get_thumb(videoid):
    try:
        # Search for the video using video ID
        query = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail
    except Exception as e:
        return config.YOUTUBE_IMG_URL
