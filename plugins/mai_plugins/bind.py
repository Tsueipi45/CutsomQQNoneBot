import json
import os
from plugins.nb_compat import logging
from maimai_py import PlayerIdentifier
from .maimai_client import maimai

_log = logging.get_logger()
USERDATA_PATH = "userdata.json"


def load_userdata():
    if not os.path.exists(USERDATA_PATH):
        return {}
    with open(USERDATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_userdata(data):
    with open(USERDATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# 绑定街机 credentials
async def bind_arcade_credentials(client, message, content, sender=None):
    cred = content.strip()
    _log.info(f"[bind_arcade] 收到 {sender} 的街机凭证")

    if not sender:
        return "[ERROR] 未提供 sender ID，无法绑定"

    udata = load_userdata()
    udata.setdefault(sender, {})["arcade_credentials"] = cred
    save_userdata(udata)

    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_id=message.id,
        msg_type=0,
        content="✅ 街机凭证已绑定成功"
    )


# 绑定查分器 token
async def bind_divingfish_token(client, message, content, sender=None):
    token = content.strip()
    _log.info(f"[bind_dftoken] 收到 {sender} 的查分器 token")

    if not sender:
        return "[ERROR] 未提供 sender ID，无法绑定"

    udata = load_userdata()
    udata.setdefault(sender, {})["divingfish_update_token"] = token
    save_userdata(udata)

    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_id=message.id,
        msg_type=0,
        content="✅ 查分器 token 绑定成功"
    )

# 绑定二维码内容，并自动解析街机凭证
async def bind_qrcode_element(client, message, content, sender=None):
    qrcode = content.strip()
    _log.info(f"[bind_qrcode] 收到 {sender} 的二维码内容")

    if not sender:
        return "[ERROR] 未提供 sender ID，无法绑定"

    udata = load_userdata()
    udata.setdefault(sender, {})["qrcode_element"] = qrcode

    try:
        identifier: PlayerIdentifier = await maimai.qrcode(qrcode)
        arcade_credentials = identifier.credentials
        udata[sender]["arcade_credentials"] = arcade_credentials
        _log.info(f"[bind_qrcode] 自动设置 arcade_credentials：{arcade_credentials}")
    except Exception as e:
        _log.warning(f"[bind_qrcode] 解析二维码失败：{e}")
        save_userdata(udata)
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_id=message.id,
            msg_type=0,
            content="⚠️ 二维码绑定成功，但解析 arcade credentials 失败，请手动绑定。"
        )
        return

    save_userdata(udata)

    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_id=message.id,
        msg_type=0,
        content="✅ 二维码绑定成功，已自动解析并绑定街机凭证"
    )
