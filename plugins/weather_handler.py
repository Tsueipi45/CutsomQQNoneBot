from plugins.weather_api import format_weather
from plugins.nb_compat import logging

_log = logging.get_logger()

async def handle_weather(client, message, city_name=None):

    user_input = message.content.strip()
    _log.info(f"[weather_handler] 收到訊息：{user_input}")

    if city_name:
        city_name = city_name.strip()
        _log.info(f"[weather_handler] 查询天气的城市：{city_name}")
    else:
        # 如果没有提供城市名，则使用默认城市
        city_name = "大连"
        _log.info(f"[weather_handler] 用户未指定,查询天气的城市：{city_name}")

    result = format_weather(city_name)
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=0,
        msg_id=message.id,
        content=result
    )
