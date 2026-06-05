from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment


class CompatLogging:
    @staticmethod
    def get_logger():
        return logger


logging = CompatLogging()


@dataclass
class CompatAuthor:
    member_openid: str
    user_openid: str


class CompatApi:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def post_group_message(
        self,
        group_openid: str,
        msg_type: int = 0,
        content: str | None = None,
        media: Any | None = None,
        **_: Any,
    ) -> None:
        message = self._build_message(msg_type=msg_type, content=content, media=media)
        await self.bot.send_group_msg(group_id=int(group_openid), message=message)

    async def post_c2c_message(
        self,
        openid: str,
        msg_type: int = 0,
        content: str | None = None,
        media: Any | None = None,
        **_: Any,
    ) -> None:
        message = self._build_message(msg_type=msg_type, content=content, media=media)
        await self.bot.send_private_msg(user_id=int(openid), message=message)

    async def post_group_base64file(
        self,
        group_openid: str,
        file_data: str,
        **_: Any,
    ) -> MessageSegment:
        return self._image_from_base64(file_data)

    async def post_c2c_base64file(
        self,
        openid: str,
        file_data: str,
        **_: Any,
    ) -> MessageSegment:
        return self._image_from_base64(file_data)

    @staticmethod
    def _image_from_base64(file_data: str) -> MessageSegment:
        image_bytes = base64.b64decode(file_data)
        return MessageSegment.image(image_bytes)

    @staticmethod
    def _build_message(
        msg_type: int,
        content: str | None,
        media: Any | None,
    ) -> Message | MessageSegment | str:
        if media is not None:
            return media
        if msg_type == 7 and media is None:
            return ""
        return content or ""


class CompatMessage:
    def __init__(self, bot: Bot, event: GroupMessageEvent, content: str):
        self._bot = bot
        self._event = event
        self._api = CompatApi(bot)
        self.sender_id = str(event.user_id)
        self.content = content
        self.id = event.message_id
        self.group_openid = str(event.group_id)
        self.author = CompatAuthor(
            member_openid=self.sender_id,
            user_openid=self.sender_id,
        )

    async def reply(self, content: str) -> None:
        await self._api.post_group_message(
            group_openid=self.group_openid,
            msg_type=0,
            content=content,
        )
