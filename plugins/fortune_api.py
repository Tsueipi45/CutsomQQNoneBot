import json
import random

from openai import OpenAI

with open("settings.json", "r", encoding="utf-8") as f:
    config = json.load(f)

client = OpenAI(
    api_key=config["deepseek_apikey"],
    base_url=config.get("deepseek_base_url", "https://api.deepseek.com"),
)

DEEPSEEK_MODEL = config.get("deepseek_model", "deepseek-v4-flash")
luck = ["财产", "爱情", "事业", "健康", "学业", "人际关系"]


async def get_daily_fortune(user_name):
    try:
        topic = random.choice(luck)
        completion = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {'role': 'system', 'content': '你是一个风水大师，以幽默风趣的方式每日提供一句运势建议'},
                {'role': 'user', 'content': f"请为{user_name}生成一句关于{topic}的今日运势，要求简短幽默。格式为：的今日运势：<内容>。请确保内容不超过30个字，且不要包含任何敏感或不当内容。"}
            ],
        )
        content = completion.choices[0].message.content
        if content:
            return f"{user_name}{content.strip()}"
        return "运势生成失败，请稍后再试。"
    except Exception as e:
        return f"❌ 运势生成失败，请稍后再试。错误信息：{e}"
