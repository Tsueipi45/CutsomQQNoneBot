from plugins.nb_compat import logging

_log = logging.get_logger()

async def handle_help(client, message, space=None):

    user_input = message.content.strip()
    _log.info(f"[handle_help] 收到訊息：{user_input}")

    result = (
    "🎯 可用指令一览：\n\n"
    "📌 常用功能：\n"
    "👉 天气 [城市] —— 获取当前天气状况\n"
    "👉 图片 —— 随机获取一张本地图片\n"
    "👉 图片 关键词 —— 搜索图片，例：图片 mygo soyo\n"
    "👉 help 或 帮助 —— 显示本帮助菜单\n\n"
    "📊 成绩功能：\n"
    "👉 绑 二维码解析内容 —— 绑定查分器账号（Arcade）\n"
    "👉 水鱼 token —— 绑定水鱼查分器 token（DivingFish）\n"
    "👉 导 —— 上传已绑定账号的成绩至查分器\n"
    "👉 b50 —— 查询你的 B50 分数列表(还在做)\n"
    "👉 info 歌曲名/歌曲别名 —— 查询该曲在水鱼查分器中的单曲成绩\n"
    "👉 在哪mai —— 查询舞萌dx足迹\n\n"
    "🔮 其他趣味功能：\n"
    "👉 今日运势 —— 获取你的今日运势签文\n\n"
    "📎 小提示：\n"
    "命令和参数之间需要空格，例如：`图片 mygo soyo`、`绑 SGW...`\n"
    "绑定一次后即可使用 导 上传成绩。"
)

    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=0,
        msg_id=message.id,
        content=result
    )
