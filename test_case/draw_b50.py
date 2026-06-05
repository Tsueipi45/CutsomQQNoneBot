import json
import os
import time
import asyncio
from maimai_py import MaimaiClient, PlayerIdentifier, DivingFishProvider

from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
import re

USERDATA_PATH = "userdata.json"
SETTINGS_PATH = "settings.json"

maimai = MaimaiClient()

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
            username = user_data.get("nickname")
            if not username:
                raise ValueError("绑定信息不完整")
            return username
    except Exception as e:
        print(f"[b50] 加载失败：{e}")
        return None

# 图像绘制参数和函数
font_path = font_manager.findfont("Microsoft YaHei")  # 使用微软雅黑字体

# 加载中文（英文字体）和日文字体
font_path_default = font_manager.findfont("Microsoft YaHei")  # 使用微软雅黑字体")
font_path_jp = "C:/Windows/Fonts/YuGothM.ttc"

font_title = ImageFont.truetype(font_path_default, 28)
font_small = ImageFont.truetype(font_path_default, 22)
font_jp = ImageFont.truetype(font_path_jp, 28)

font_title = ImageFont.truetype(font_path, 28)
font_small = ImageFont.truetype(font_path, 22)

columns = 5
box_width = 460
box_height = 170
padding = 20
gap_between_sections = 60
rows_b35 = 7
rows_b15 = 3
canvas_width = columns * box_width
canvas_height = (rows_b35 + rows_b15) * box_height + padding * 2 + gap_between_sections
start_b35_y = padding + 40
start_b15_y = start_b35_y + rows_b35 * box_height + gap_between_sections

level_color_map = {
    "ReMASTER": (255, 255, 255),
    "MASTER": (144, 101, 255),
    "EXPERT": (255, 85, 85),
    "ADVANCED": (255, 202, 40),
    "BASIC": (100, 221, 100),
}

def extract_level_index_from_raw(raw_text):
    entries = re.findall(r"ScoreExtend\((.*?)\)", raw_text, re.DOTALL)
    level_indices = []
    for entry in entries:
        m = re.search(r"level_index=<LevelIndex\.([A-Za-z]+)", entry)
        if m:
            level_indices.append(m.group(1))
        else:
            level_indices.append("UNKNOWN")
    return level_indices

def draw_scores_block_with_color(draw, scores, start_y, title):
    draw.text((padding, start_y - 40), title, font=font_title, fill="black")
    for i, score in enumerate(scores):
        row = i // columns
        col = i % columns
        x = col * box_width + padding
        y = start_y + row * box_height

        level_index = score.get("level_index", "UNKNOWN").upper()
        color = level_color_map.get(level_index, (200, 200, 200))

        draw.rectangle([x, y, x + box_width - padding * 2, y + box_height - padding],
                       fill=(255, 255, 255), outline="cornflowerblue", width=3)
        draw.rectangle([x, y, x + 15, y + box_height - padding], fill=color)

        draw_multiline_text_with_font_split(draw, score['title'], font_title, font_jp, x + 25, y + 10, max_width=box_width - 50, line_height=30)
        draw.text((x + 25, y + 60), f"成绩: {score['achievements']}%", font=font_small, fill="black")
        draw.text((x + 25, y + 90), f"等级: {score['level']}", font=font_small, fill="black")
        draw.text((x + 260, y + 60), f"DX Rating: {score['dx_rating']}", font=font_small, fill="black")
        draw.text((x + 260, y + 90), f"Score: {score['dx_score']}", font=font_small, fill="black")

import unicodedata

def is_japanese_or_chinese(char):
    name = unicodedata.name(char, "")
    return "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name

def draw_multiline_text_with_font_split(draw, text, default_font, jp_font, x, y, max_width, line_height):
    line = ""
    lines = []

    for char in text:
        test_line = line + char
        font = jp_font if is_japanese_or_chinese(char) else default_font
        width = font.getbbox(test_line)[2] - font.getbbox(test_line)[0]
        if width <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = char
    if line:
        lines.append(line)

    for i, line in enumerate(lines):
        # 计算总宽度
        total_width = sum(
            (jp_font if is_japanese_or_chinese(c) else default_font).getbbox(c)[2] -
            (jp_font if is_japanese_or_chinese(c) else default_font).getbbox(c)[0] - 2  # -2 是间距微调
            for c in line
        )

        # 居中对齐：以x为中心点
        cursor_x = x

        for char in line:
            font = jp_font if is_japanese_or_chinese(char) else default_font
            bbox = font.getbbox(char)
            w = bbox[2] - bbox[0]
            draw.text((cursor_x, y + i * line_height), char, font=font, fill="black")
            cursor_x += w - 2  # 字间距微调



def generate_b50_image(score_data, raw_repr_text, output_path="b50_result.jpg"):
    level_indices = extract_level_index_from_raw(raw_repr_text)
    for i in range(len(score_data)):
        score_data[i]["level_index"] = level_indices[i]

    b35_scores = score_data[:35]
    b15_scores = score_data[35:]

    canvas = Image.new("RGB", (canvas_width, canvas_height), (245, 250, 255))
    draw = ImageDraw.Draw(canvas)

    draw_scores_block_with_color(draw, b35_scores, start_b35_y, "B35")
    draw_scores_block_with_color(draw, b15_scores, start_b15_y, "B15")

    canvas.save(output_path)
    return output_path

# ---------- 主函数 ----------
async def b50_runner(sender: str):
    if not sender:
        print("[ERROR] 未提供 sender ID")
        return

    print(f"[b50] 收到 {sender} 的请求")
    start_time = time.perf_counter()

    df_username = load_user_credentials(sender)
    if not df_username:
        print("❌ 请先完成 /昵称 \"水鱼用户名\"")
        return

    print("[b50] 绑定信息加载成功")

    try:
        id = PlayerIdentifier(username=df_username)
        scores = await maimai.scores(id, provider=divingfish)

        b35 = scores.scores_b35
        b15 = scores.scores_b15

        score_data_b35 = [{
            "title": s.title,
            "achievements": s.achievements,
            "dx_score": s.dx_score,
            "dx_rating": s.dx_rating,
            "level": s.level
        } for s in b35]

        score_data_b15 = [{
            "title": s.title,
            "achievements": s.achievements,
            "dx_score": s.dx_score,
            "dx_rating": s.dx_rating,
            "level": s.level
        } for s in b15]

        score_data = score_data_b35 + score_data_b15
        raw_repr = str(b35 + b15)

        elapsed = time.perf_counter() - start_time
        print(f"✅ 成绩已成功查询！共查询到 {len(scores.scores)} 条记录")
        print(f"耗时：{elapsed:.2f} 秒")

        img_path = generate_b50_image(score_data, raw_repr)
        print(f"🎉 成绩图像已保存为：{img_path}")

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"❌ 成绩下载失败：{e}")
        print(f"耗时：{elapsed:.2f} 秒")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("用法: python b50_runner_with_image_fixed.py <sender_id>")
    else:
        asyncio.run(b50_runner(sys.argv[1]))
