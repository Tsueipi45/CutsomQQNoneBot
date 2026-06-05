import asyncio
from collections import defaultdict, deque
from pathlib import Path

from plugins.nb_compat import logging
from plugins.picture_api import (
    encode_image_base64,
    encode_remote_image_base64,
    get_random_picture_path,
    search_picture_candidates,
)

_log = logging.get_logger()
RECENT_KEYWORD_HISTORY_SIZE = 20
_recent_picture_urls_by_keyword = defaultdict(lambda: deque(maxlen=RECENT_KEYWORD_HISTORY_SIZE))


def _normalize_keyword_history_key(keyword: str) -> str:
    return " ".join(keyword.casefold().split())


def _prioritize_unseen_pictures(keyword: str, pictures):
    recent_urls = set(_recent_picture_urls_by_keyword[_normalize_keyword_history_key(keyword)])
    unseen = [picture for picture in pictures if picture.get("url") not in recent_urls]
    seen = [picture for picture in pictures if picture.get("url") in recent_urls]
    return unseen + seen


def _remember_sent_picture(keyword: str, picture) -> None:
    url = picture.get("url")
    if not url:
        return
    _recent_picture_urls_by_keyword[_normalize_keyword_history_key(keyword)].append(url)


async def handle_picture(client, message, arguments=None, is_group=True, msg_seq=1):
    keyword = (arguments or "").strip()
    _log.info(f"[picture_handler] received picture command, keyword={keyword!r}")

    if keyword:
        await send_text_message(
            client,
            message,
            f"天使在帮你搜寻[{keyword}]的图片",
            is_group,
            msg_seq,
        )

        pictures = await asyncio.to_thread(search_picture_candidates, keyword)
        if not pictures:
            await send_text_message(client, message, "找不到相关图片", is_group, msg_seq + 1)
            return

        pictures = _prioritize_unseen_pictures(keyword, pictures)
        file_data = None
        picture = None
        for candidate in pictures[:5]:
            image_url = candidate["url"]
            file_data = await asyncio.to_thread(encode_remote_image_base64, image_url)
            if file_data:
                picture = candidate
                break

        if not file_data:
            await send_text_message(client, message, "图片下载失败", is_group, msg_seq + 1)
            return

        source_name = picture.get("title") or picture["url"]
        send_msg_seq = msg_seq + 1
    else:
        image_path = get_random_picture_path()
        if not image_path:
            await send_text_message(client, message, "找不到图片文件", is_group, msg_seq)
            return

        file_data = encode_image_base64(image_path)
        if not file_data:
            await send_text_message(client, message, "图片编码失败", is_group, msg_seq)
            return

        source_name = Path(image_path).name
        send_msg_seq = msg_seq

    try:
        _log.info(f"[picture_handler] sending picture: {source_name}")
        await send_image_message(client, message, file_data, is_group, send_msg_seq)
        if keyword and picture:
            _remember_sent_picture(keyword, picture)
        _log.info("[picture_handler] picture sent successfully")
    except Exception as e:
        _log.error(f"[picture_handler] failed to send picture: {e}")
        await send_text_message(client, message, "发送图片失败", is_group, msg_seq + 1)


async def send_image_message(client, message, file_data, is_group, msg_seq):
    if is_group:
        upload_result = await message._api.post_group_base64file(
            group_openid=message.group_openid,
            file_type=1,
            file_data=file_data,
        )

        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=7,
            msg_id=message.id,
            msg_seq=msg_seq,
            media=upload_result,
        )
        return

    upload_result = await message._api.post_c2c_base64file(
        openid=message.author.user_openid,
        file_type=1,
        file_data=file_data,
    )

    await message._api.post_c2c_message(
        openid=message.author.user_openid,
        msg_type=7,
        msg_id=message.id,
        msg_seq=msg_seq,
        media=upload_result,
    )


async def send_text_message(client, message, content, is_group, msg_seq):
    try:
        if is_group:
            await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type=0,
                msg_id=message.id,
                msg_seq=msg_seq,
                content=content,
            )
        else:
            await message._api.post_c2c_message(
                openid=message.author.user_openid,
                msg_type=0,
                msg_id=message.id,
                msg_seq=msg_seq,
                content=content,
            )
    except Exception as e:
        _log.error(f"[picture_handler] failed to send text message: {e}")
