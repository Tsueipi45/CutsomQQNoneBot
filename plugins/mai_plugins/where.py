import json
import os
from plugins.nb_compat import logging
import time

from maimai_py import PlayerIdentifier, ArcadeProvider, DivingFishProvider
from .maimai_client import maimai

_log = logging.get_logger()

USERDATA_PATH = "userdata.json"
SETTINGS_PATH = "settings.json"

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        raise FileNotFoundError("找不到 settings.json")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
    
settings = load_settings()
DIVINGFISH_TOKEN = settings.get("diving_fish_dev")
divingfish = DivingFishProvider(developer_token=DIVINGFISH_TOKEN)

def load_user_credentials(sender_id: str):
    try:
        with open(USERDATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            user_data = data.get(sender_id)
            if not user_data:
                raise ValueError("未找到用户绑定数据")

            arcade_credentials = user_data.get("arcade_credentials")

            if not arcade_credentials:
                raise ValueError("绑定信息不完整")

            return arcade_credentials
    except Exception as e:
        _log.warning(f"[b50] 加载失败：{e}")
        return None


async def where_mai(client, message, space=None, sender=None):
    if not sender:
        return "[ERROR] 未提供 sender ID，无法查询"
    _log.info(f"[region] 收到 {sender} 的地区查询请求")

    start_time = time.perf_counter()  # 开始计时

    arcade_credentials = load_user_credentials(sender)

    if not arcade_credentials:
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content="❌ 请先完成 绑 \"qrcode解析内容\""
        )
        return

    _log.info("[region] 绑定信息加载成功")

    try:
        # 查询地区游玩信息
        identifier = PlayerIdentifier(credentials=arcade_credentials)
        regions = await maimai.regions(identifier, provider=ArcadeProvider())

        if not regions:
            msg = "⚠️ 没有查询到任何地区游玩记录。"
        else:
            msg = "📍 你近期的游玩地区如下：\n"
            msg += "\n".join(f"{region.region_name}：{region.play_count} 次" for region in regions)

        elapsed = time.perf_counter() - start_time  # 计算耗时
        msg += f"\n\n⏱️ 查询耗时：{elapsed:.2f} 秒"

        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=msg
        )

        _log.info(f"[region] {sender} 查询地区完成，用时 {elapsed:.2f} 秒")

    except Exception as e:
        _log.warning(f"[region] 查询失败：{e}")
        elapsed = time.perf_counter() - start_time
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=f"❌ 查询失败，请稍后再试\n错误信息：{e}\n耗时：{elapsed:.2f} 秒"
        )
