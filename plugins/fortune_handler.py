from plugins.fortune_api import get_daily_fortune
from plugins.nb_compat import logging

_log = logging.get_logger()

async def handle_fortune(client, message, args=None, sender=None):
    user_input = message.content.strip()
    _log.info(f"[fortune_handler] 收到訊息：{user_input}")

    user_name = args if args else "你"

    result = await get_daily_fortune(user_name)
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=0,
        msg_id=message.id,
        content=result
    )
    _log.info(f"[fortune_handler] 已处理消息：{user_input} → {result}")

