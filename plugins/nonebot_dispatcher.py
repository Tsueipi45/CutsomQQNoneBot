from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nonebot import logger, on_message
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent
from nonebot.rule import Rule

from plugins import fortune_handler, help_handler, picture_handler
from plugins import shutdown_handler, weather_handler
from plugins.mai_plugins import b50, bind, info, upload, where
from plugins.nb_compat import CompatMessage

SimpleHandler = Callable[[Bot, CompatMessage, str], Awaitable[Any]]
ExtendedHandler = Callable[[Bot, CompatMessage, str, str], Awaitable[Any]]
SuffixHandler = Callable[[Bot, CompatMessage, str, str], Awaitable[Any]]


simple_handlers: dict[str, SimpleHandler] = {
    "天气": weather_handler.handle_weather,
    "shutdown": shutdown_handler.handle_shutdown,
    "图片": picture_handler.handle_picture,
    "help": help_handler.handle_help,
    "帮助": help_handler.handle_help,
}

extended_handlers: dict[str, ExtendedHandler] = {
    "今日运势": fortune_handler.handle_fortune,
    "b50": b50.b50,
    "绑": bind.bind_qrcode_element,
    "水鱼": bind.bind_divingfish_token,
    "导": upload.upload_scores,
    "在哪mai": where.where_mai,
    "info": info.song_info,
}

suffix_handlers: dict[str, SuffixHandler] = {
    "是什么歌": info.alias_song_info,
}


def normalize_command_text(message: str) -> str:
    return message[1:].lstrip() if message.startswith("/") else message


def match_command(command_text: str, command: str) -> tuple[bool, str]:
    if not command_text.startswith(command):
        return False, ""

    rest = command_text[len(command):]
    if rest and not rest[0].isspace():
        return False, ""

    return True, rest.strip()


def find_command(command_text: str, handlers: dict[str, Any]) -> tuple[str | None, str]:
    for command in handlers:
        matched, args = match_command(command_text, command)
        if matched:
            return command, args
    return None, ""


def find_suffix_command(command_text: str, handlers: dict[str, Any]) -> tuple[str | None, str]:
    for suffix in handlers:
        if command_text.endswith(suffix):
            args = command_text[: -len(suffix)].strip()
            return suffix, args
    return None, ""


async def is_group_message(event: Event) -> bool:
    return isinstance(event, GroupMessageEvent)


dispatcher = on_message(rule=Rule(is_group_message), priority=10, block=False)


@dispatcher.handle()
async def handle_group_at_message(bot: Bot, event: GroupMessageEvent) -> None:
    msg = event.get_plaintext().strip()
    command_text = normalize_command_text(msg)
    message = CompatMessage(bot, event, msg)
    logger.info(f"收到群消息 group={event.group_id} sender_qq={message.sender_id}：{msg}")

    command_key, args = find_command(command_text, simple_handlers)
    if command_key:
        handler = simple_handlers[command_key]
        await handler(bot, message, args)
        logger.info(f"[处理完成] 使用 simple_handler 处理：{msg}")
        return

    command_key, args = find_command(command_text, extended_handlers)
    if command_key:
        handler = extended_handlers[command_key]
        sender = message.sender_id
        await handler(bot, message, args, sender)
        logger.info(f"[处理完成] 使用 extended_handler 处理：{msg}")
        return

    command_key, args = find_suffix_command(command_text, suffix_handlers)
    if command_key:
        handler = suffix_handlers[command_key]
        sender = message.sender_id
        await handler(bot, message, args, sender)
        logger.info(f"[处理完成] 使用 suffix_handler 处理：{msg}")
        return

    logger.info(f"[未匹配指令] 忽略群消息：{msg}")
