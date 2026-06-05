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
                return None, None

            arcade_credentials = user_data.get("arcade_credentials")
            divingfish_token = user_data.get("divingfish_update_token")

            return arcade_credentials, divingfish_token
    except Exception as e:
        _log.warning(f"[upload_scores] 加载失败：{e}")
        return None, None


def format_missing_binding_message(arcade_credentials: str | None, divingfish_token: str | None) -> str | None:
    missing = []
    if not arcade_credentials:
        missing.append("二维码：请先发送「绑 SGWCMAID...」")
    if not divingfish_token:
        missing.append("水鱼 token：请先发送「水鱼 <token>」")
    if not missing:
        return None
    return "❌ 上传前还缺少绑定信息：\n" + "\n".join(f"- {item}" for item in missing)


async def upload_scores(client, message, space=None, sender=None):
    if not sender:
        return "[ERROR] 未提供 sender ID，无法上传"
    _log.info(f"[upload_scores] 收到 {sender} 的上传请求")

    start_time = time.perf_counter()  # 开始计时

    arcade_credentials, divingfish_token = load_user_credentials(sender)

    missing_message = format_missing_binding_message(arcade_credentials, divingfish_token)
    if missing_message:
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=missing_message
        )
        return

    _log.info(f"[upload_scores] 绑定信息加载成功")

    try:
        # 拉取成绩
        arcade_id = PlayerIdentifier(credentials=arcade_credentials)
        scores = await maimai.scores(arcade_id, provider=ArcadeProvider())

        # 上传到查分器
        diving_id = PlayerIdentifier(credentials=divingfish_token)
        await maimai.updates(diving_id, scores.scores, provider=divingfish)

        elapsed = time.perf_counter() - start_time  # 计算耗时

        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=f"成绩已成功上传至查分器！共上传 {len(scores.scores)} 条记录\n 耗时：{elapsed:.2f} 秒"
        )

        _log.info(f"[upload_scores] {sender} 成功上传了 {len(scores.scores)} 条成绩，用时 {elapsed:.2f} 秒")

    except Exception as e:
        _log.warning(f"[upload_scores] 上传失败：{e}")
        elapsed = time.perf_counter() - start_time
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=f"❌ 成绩上传失败，请稍后再试\n错误信息：{e}\n耗时：{elapsed:.2f} 秒"
        )
