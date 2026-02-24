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
            
        


@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_music(client, CallbackQuery, _):
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
        return await mystic.edit_text(_["play_3"])
    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
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
        if ex_type == "AssistantErr":
            err = e 
        else:
            err = _["general_2"].format(ex_type)
            LOGGER(__name__).error(ex_type, exc_info=True)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("ZEOmousAdmin") & ~BANNED_USERS)
async def SHUKLAmous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\nᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except:
        pass


@app.on_callback_query(filters.regex("ZEOPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
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
            return await mystic.edit_text(_["play_3"])
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except:
            return await mystic.edit_text(_["play_3"])
    try:
        await stream(
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
        if ex_type == "AssistantErr":
            err = e
        else:
            err = _["general_2"].format(ex_type)
            LOGGER(__name__).error(ex_type, exc_info=True)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client, CallbackQuery, _):
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
        query_type = 0 if rtype == 9 else int(rtype + 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
            
        title, duration_min, _, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        
        # Create a text message instead of an image
        med = InputMediaText(
            message=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    if what == "B":
        query_type = 9 if rtype == 0 else int(rtype - 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
            
        title, duration_min, _, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        
        # Create a text message instead of an image
        med = InputMediaText(
            message=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )
