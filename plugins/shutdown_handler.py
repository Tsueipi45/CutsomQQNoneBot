from plugins.nb_compat import logging
import sys

_log = logging.get_logger()

async def handle_shutdown(client, message, space=None):
    content = "正在关闭机器人..."
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=0,
        msg_id=message.id,
        content=content
    )
    _log.info(f"已处理消息：{message.content.strip()} → {content}")
    
    sys.exit(0)
