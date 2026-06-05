import base64
import asyncio
import io
import json
import os
import time
import unicodedata
from pathlib import Path

from maimai_py import ArcadeProvider, PlayerIdentifier, SongType
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import requests

from plugins.nb_compat import logging

from .maimai_client import maimai

_log = logging.get_logger()

USERDATA_PATH = "userdata.json"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COVER_DIR = PROJECT_ROOT / "pictures" / "maimai_bg"
COVER_CACHE_DIR = COVER_DIR / "_cache"
COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
REMOTE_COVER_TIMEOUT = (1.5, 5)
REMOTE_COVER_MISS_TTL = 3600
REMOTE_COVER_FAILURE_LIMIT = 3
REMOTE_COVER_BACKOFF_TTL = 60
REMOTE_COVER_USER_AGENT = "AmatsukaUtoBot/1.0"

CANVAS_WIDTH = 1500
PADDING_X = 44
TOP_HEIGHT = 210
SECTION_HEADER_HEIGHT = 90
CARD_WIDTH = 266
CARD_HEIGHT = 118
CARD_GAP_X = 20
CARD_GAP_Y = 26
GRID_COLUMNS = 5
B35_ROWS = 7
B15_ROWS = 3
BOTTOM_PADDING = 50

RATE_COLORS = {
    "SSS+": "#ff9c24",
    "SSS": "#ffb22d",
    "SS+": "#ffbf33",
    "SS": "#ffcf46",
    "S+": "#ffde55",
    "S": "#ffe66d",
    "AAA": "#f8b34b",
}

DIFF_COLORS = {
    0: "#68c84d",
    1: "#f6a63a",
    2: "#ef5454",
    3: "#9b59d0",
    4: "#d7d7d7",
}

DISPLAY_NAMES = {
    "SSSP": "SSS+",
    "SSP": "SS+",
    "SP": "S+",
    "APP": "AP+",
    "FCP": "FC+",
    "FSDP": "FSD+",
    "FSP": "FS+",
}

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
]


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


def enum_name(value) -> str:
    if not value:
        return ""
    return DISPLAY_NAMES.get(value.name, value.name)


def type_name(song_type: SongType) -> str:
    if song_type == SongType.STANDARD:
        return "SD"
    if song_type == SongType.DX:
        return "DX"
    return "宴"


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = FONT_CANDIDATES[:]
    if bold:
        candidates.insert(0, Path("C:/Windows/Fonts/msyhbd.ttc"))
        candidates.insert(0, Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"))

    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT_TITLE = get_font(54, bold=True)
FONT_SUBTITLE = get_font(30, bold=True)
FONT_CARD_TITLE = get_font(20, bold=True)
FONT_CARD_SMALL = get_font(18, bold=True)
FONT_CARD_RATE = get_font(38, bold=True)
FONT_CARD_RATE_SIZES = [36, 34, 32, 30, 28]
FONT_CARD_BADGE = get_font(17, bold=True)
FONT_FOOTER = get_font(22)
REMOTE_COVER_MISSES: dict[int, float] = {}
REMOTE_COVER_FAILURES = 0
REMOTE_COVER_DISABLED_UNTIL = 0.0


def text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font,
    fill,
) -> None:
    width, height = text_size(draw, text, font)
    x1, y1, x2, y2 = box
    draw.text((x1 + (x2 - x1 - width) / 2, y1 + (y2 - y1 - height) / 2 - 2), text, font=font, fill=fill)


def fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if text_size(draw, text, font)[0] <= max_width:
        return text

    ellipsis = "..."
    result = ""
    for ch in text:
        candidate = result + ch
        if text_size(draw, candidate + ellipsis, font)[0] > max_width:
            return result + ellipsis if result else ellipsis
        result = candidate
    return result


def fit_font(draw: ImageDraw.ImageDraw, text: str, sizes: list[int], max_width: int, bold: bool = False):
    for size in sizes:
        font = get_font(size, bold=bold)
        if text_size(draw, text, font)[0] <= max_width:
            return font
    return get_font(sizes[-1], bold=bold)


def normalize_filename_stem(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


def build_cover_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not COVER_DIR.exists():
        return index

    for path in COVER_DIR.iterdir():
        if not path.is_file() or path.suffix.casefold() not in COVER_EXTENSIONS:
            continue
        stem = normalize_filename_stem(path.stem)
        index.setdefault(stem, path)
    return index


COVER_INDEX = build_cover_index()


def score_cover_id(score) -> int | None:
    try:
        song_id = int(score.id)
    except (TypeError, ValueError):
        return None

    if song_id <= 0:
        return None
    return song_id % 10000 if song_id > 10000 else song_id


def local_cover_ids(score) -> list[int]:
    ids: list[int] = []

    def add(song_id: int | None) -> None:
        if song_id and song_id > 0 and song_id not in ids:
            ids.append(song_id)

    try:
        raw_id = int(score.id)
    except (TypeError, ValueError):
        raw_id = None

    add(raw_id)
    base_id = score_cover_id(score)
    add(base_id)
    if base_id and score.type == SongType.DX:
        add(base_id + 10000)
    return ids


def cover_keys(score) -> list[str]:
    title = score.title or str(score.id)
    keys = []
    if score.type == SongType.DX:
        keys.append(f"{title} [DX]")
    keys.append(title)
    for song_id in local_cover_ids(score):
        keys.extend(
            [
                str(song_id),
                f"{song_id:05d}",
                f"{song_id}_{title}",
                f"{song_id:05d}_{title}",
            ]
        )
    return [normalize_filename_stem(key) for key in keys]


def cached_cover_path(song_id: int) -> Path:
    return COVER_CACHE_DIR / f"{song_id:05d}.png"


def remote_cover_urls(song_id: int) -> list[str]:
    return [
        f"https://www.diving-fish.com/covers/{song_id:05d}.png",
        f"https://assets2.lxns.net/maimai/jacket/{song_id}.png",
    ]


def validate_image_bytes(content: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        return True
    except Exception:
        return False


def mark_remote_cover_network_failure() -> None:
    global REMOTE_COVER_FAILURES, REMOTE_COVER_DISABLED_UNTIL
    REMOTE_COVER_FAILURES += 1
    if REMOTE_COVER_FAILURES >= REMOTE_COVER_FAILURE_LIMIT:
        REMOTE_COVER_DISABLED_UNTIL = time.monotonic() + REMOTE_COVER_BACKOFF_TTL
        _log.warning(f"[b50] 远程封面源连续失败，暂停 {REMOTE_COVER_BACKOFF_TTL} 秒")


def mark_remote_cover_success() -> None:
    global REMOTE_COVER_FAILURES, REMOTE_COVER_DISABLED_UNTIL
    REMOTE_COVER_FAILURES = 0
    REMOTE_COVER_DISABLED_UNTIL = 0.0


def download_cover(score) -> Path | None:
    song_id = score_cover_id(score)
    if not song_id:
        return None

    cache_path = cached_cover_path(song_id)
    if cache_path.exists():
        return cache_path

    now = time.monotonic()
    if now < REMOTE_COVER_DISABLED_UNTIL:
        return None

    missed_at = REMOTE_COVER_MISSES.get(song_id)
    if missed_at and now - missed_at < REMOTE_COVER_MISS_TTL:
        return None

    headers = {"User-Agent": REMOTE_COVER_USER_AGENT}
    for url in remote_cover_urls(song_id):
        try:
            response = requests.get(url, headers=headers, timeout=REMOTE_COVER_TIMEOUT)
        except requests.RequestException as e:
            _log.warning(f"[b50] 远程封面请求失败 {url}: {e}")
            mark_remote_cover_network_failure()
            continue

        content_type = response.headers.get("Content-Type", "")
        if response.status_code != 200 or not content_type.startswith("image/"):
            continue

        if not validate_image_bytes(response.content):
            _log.warning(f"[b50] 远程封面内容无法识别 {url}")
            continue

        try:
            COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
            tmp_path.write_bytes(response.content)
            tmp_path.replace(cache_path)
        except OSError as e:
            _log.warning(f"[b50] 远程封面缓存失败 {cache_path}: {e}")
            return None

        mark_remote_cover_success()
        REMOTE_COVER_MISSES.pop(song_id, None)
        _log.info(f"[b50] 已缓存远程封面 {song_id}: {url}")
        return cache_path

    REMOTE_COVER_MISSES[song_id] = now
    return None


def find_cover(score) -> Path | None:
    for key in cover_keys(score):
        if key in COVER_INDEX:
            return COVER_INDEX[key]
    song_id = score_cover_id(score)
    if song_id:
        cache_path = cached_cover_path(song_id)
        if cache_path.exists():
            return cache_path
    return download_cover(score)


def load_cover(score, size: tuple[int, int]) -> Image.Image | None:
    cover_path = find_cover(score)
    if not cover_path:
        return None

    try:
        image = Image.open(cover_path).convert("RGB")
    except Exception as e:
        _log.warning(f"[b50] 封面读取失败 {cover_path}: {e}")
        return None

    image.thumbnail(size, Image.Resampling.LANCZOS)
    result = Image.new("RGB", size, (235, 242, 248))
    result.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return result


def card_missing_name(score) -> str:
    suffix = " [DX]" if score.type == SongType.DX else ""
    return f"{score.title}{suffix}"


def gradient_background(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.55:
            p = t / 0.55
            top = (46, 184, 225)
            bottom = (149, 225, 239)
        else:
            p = (t - 0.55) / 0.45
            top = (149, 225, 239)
            bottom = (222, 245, 232)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * p) for i in range(3))
        for x in range(width):
            pixels[x, y] = color
    return image


def draw_soft_shapes(image: Image.Image) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((-150, -120, 420, 260), fill=(255, 241, 91, 90))
    draw.ellipse((1100, 40, 1670, 500), fill=(255, 116, 151, 78))
    draw.ellipse((-180, 1300, 460, 1950), fill=(255, 255, 255, 72))
    draw.ellipse((980, 1700, 1680, 2380), fill=(160, 235, 170, 95))
    draw.line((40, 470, 1460, 280), fill=(255, 255, 255, 70), width=9)
    draw.line((100, 1480, 1420, 1650), fill=(255, 255, 255, 65), width=7)
    image.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(4)))


def draw_header(draw: ImageDraw.ImageDraw, scores, elapsed: float, sender: str) -> None:
    total = scores.rating
    b35 = scores.rating_b35
    b15 = scores.rating_b15
    draw.rounded_rectangle((PADDING_X, 34, CANVAS_WIDTH - PADDING_X, 175), radius=26, fill=(255, 255, 255, 222))
    draw.text((PADDING_X + 34, 58), "maimai DX Best 50", font=FONT_TITLE, fill=(24, 73, 126))
    draw.text((PADDING_X + 40, 126), f"QQ {sender}", font=FONT_SUBTITLE, fill=(58, 96, 132))

    rating_box = (CANVAS_WIDTH - PADDING_X - 470, 58, CANVAS_WIDTH - PADDING_X - 34, 150)
    draw.rounded_rectangle(rating_box, radius=18, fill=(27, 93, 190, 235))
    draw.text((rating_box[0] + 26, rating_box[1] + 15), "RATING", font=FONT_SUBTITLE, fill=(210, 236, 255))
    draw.text((rating_box[0] + 162, rating_box[1] + 3), str(total), font=FONT_TITLE, fill=(255, 243, 91))
    draw.text(
        (rating_box[0] + 26, rating_box[1] + 61),
        f"旧曲 {b35}  +  新曲 {b15}    {elapsed:.2f}s",
        font=FONT_FOOTER,
        fill=(236, 249, 255),
    )


def draw_section_header(draw: ImageDraw.ImageDraw, y: int, title: str) -> None:
    box_width = 520
    x = (CANVAS_WIDTH - box_width) // 2
    draw.rounded_rectangle((x, y + 12, x + box_width, y + 68), radius=18, fill=(255, 255, 255, 235))
    draw.rounded_rectangle((x + 12, y + 22, x + box_width - 12, y + 58), radius=12, outline=(65, 188, 226), width=4)
    draw_centered_text(draw, (x, y + 8, x + box_width, y + 68), title, FONT_SUBTITLE, (20, 45, 70))


def draw_badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fill: tuple[int, int, int] | str,
    text_fill: tuple[int, int, int] | str = "white",
    min_width: int = 42,
) -> int:
    width = max(min_width, text_size(draw, text, FONT_CARD_BADGE)[0] + 16)
    draw.rounded_rectangle((x, y, x + width, y + 22), radius=10, fill=fill)
    draw_centered_text(draw, (x, y - 1, x + width, y + 21), text, FONT_CARD_BADGE, text_fill)
    return width


def draw_card(draw: ImageDraw.ImageDraw, base: Image.Image, score, rank: int, x: int, y: int) -> str | None:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((x + 4, y + 5, x + CARD_WIDTH + 4, y + CARD_HEIGHT + 5), radius=13, fill=(0, 0, 0, 65))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)))

    draw.rounded_rectangle((x, y, x + CARD_WIDTH, y + CARD_HEIGHT), radius=13, fill=(255, 255, 255, 235))

    cover_size = (102, CARD_HEIGHT)
    cover = load_cover(score, cover_size)
    missing = None
    if cover:
        mask = Image.new("L", cover_size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, cover_size[0] + 14, cover_size[1]), radius=13, fill=255)
        base.paste(cover.convert("RGBA"), (x, y), mask)
    else:
        missing = card_missing_name(score)
        draw.rounded_rectangle((x, y, x + cover_size[0], y + cover_size[1]), radius=13, fill=(226, 235, 241))
        draw_centered_text(draw, (x + 8, y + 38, x + cover_size[0] - 8, y + 78), "NO IMAGE", FONT_CARD_SMALL, (129, 149, 164))

    info_x = x + 112
    draw.text((info_x, y + 8), f"#{rank:02d}", font=FONT_CARD_BADGE, fill=(75, 95, 115))

    diff_color = DIFF_COLORS.get(score.level_index.value, "#777777")
    type_label = type_name(score.type)
    badge_x = info_x + 42
    used = draw_badge(draw, badge_x, y + 5, type_label, diff_color, min_width=38)
    level_text = f"{score.level_value:.1f}"
    used += draw_badge(draw, badge_x + used + 5, y + 5, level_text, "#7d4fe0", min_width=48) + 5
    draw_badge(draw, badge_x + used, y + 5, str(int(score.dx_rating or 0)), "#ff7a22", min_width=46)

    title = fit_text(draw, score.title, FONT_CARD_TITLE, CARD_WIDTH - 126)
    draw.text((info_x, y + 32), title, font=FONT_CARD_TITLE, fill=(28, 39, 54))

    achievement = "-" if score.achievements is None else f"{score.achievements:.4f}%"
    rate_font = fit_font(draw, achievement, FONT_CARD_RATE_SIZES, CARD_WIDTH - 124, bold=True)
    draw.text((info_x, y + 56), achievement, font=rate_font, fill=(25, 31, 42))

    rate = enum_name(score.rate)
    draw.text((info_x, y + 91), rate, font=FONT_CARD_TITLE, fill=RATE_COLORS.get(rate, "#f5a623"))

    marker_x = min(info_x + 76, x + CARD_WIDTH - 92)
    fc = enum_name(score.fc)
    fs = enum_name(score.fs)
    if fc:
        marker_x += draw_badge(draw, marker_x, y + 90, fc, "#3abf5a", min_width=34) + 4
    if fs:
        draw_badge(draw, min(marker_x, x + CARD_WIDTH - 43), y + 90, fs, "#47bde8", min_width=39)

    return missing


def draw_scores_grid(
    draw: ImageDraw.ImageDraw,
    base: Image.Image,
    scores: list,
    start_y: int,
) -> list[str]:
    missing: list[str] = []
    grid_x = PADDING_X
    for idx, score in enumerate(scores):
        col = idx % GRID_COLUMNS
        row = idx // GRID_COLUMNS
        x = grid_x + col * (CARD_WIDTH + CARD_GAP_X)
        y = start_y + row * (CARD_HEIGHT + CARD_GAP_Y)
        missed = draw_card(draw, base, score, idx + 1, x, y)
        if missed:
            missing.append(missed)
    return missing


def encode_image_to_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=92, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def render_b50_image(scores, sender: str, elapsed: float) -> tuple[str, list[str]]:
    total_height = (
        TOP_HEIGHT
        + SECTION_HEADER_HEIGHT
        + B35_ROWS * CARD_HEIGHT
        + (B35_ROWS - 1) * CARD_GAP_Y
        + SECTION_HEADER_HEIGHT
        + B15_ROWS * CARD_HEIGHT
        + (B15_ROWS - 1) * CARD_GAP_Y
        + BOTTOM_PADDING
    )
    image = gradient_background(CANVAS_WIDTH, total_height).convert("RGBA")
    draw_soft_shapes(image)
    draw = ImageDraw.Draw(image)

    draw_header(draw, scores, elapsed, sender)

    b35_header_y = TOP_HEIGHT
    draw_section_header(draw, b35_header_y, "非当前版本最好成绩 B35")
    b35_grid_y = b35_header_y + SECTION_HEADER_HEIGHT
    missing = draw_scores_grid(draw, image, scores.scores_b35, b35_grid_y)

    b15_header_y = b35_grid_y + B35_ROWS * CARD_HEIGHT + (B35_ROWS - 1) * CARD_GAP_Y + 20
    draw_section_header(draw, b15_header_y, "当前版本最好成绩 B15")
    b15_grid_y = b15_header_y + SECTION_HEADER_HEIGHT
    missing.extend(draw_scores_grid(draw, image, scores.scores_b15, b15_grid_y))

    draw.text(
        (PADDING_X, total_height - 34),
        "generated by AmatsukaUtoBot",
        font=FONT_FOOTER,
        fill=(58, 102, 130),
    )

    return encode_image_to_base64(image), sorted(set(missing))


async def post_text(message, content: str, msg_seq: int = 1) -> None:
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=0,
        msg_id=message.id,
        msg_seq=msg_seq,
        content=content,
    )


async def post_image(message, file_data: str, msg_seq: int = 1) -> None:
    upload_result = await message._api.post_group_base64file(
        group_openid=message.group_openid,
        file_type=1,
        file_data=file_data,
    )
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=7,
        msg_id=message.id,
        msg_seq=msg_seq,
        media=upload_result,
    )


def format_missing_covers(missing: list[str]) -> str:
    listed = "\n".join(f"- {name}" for name in missing[:30])
    extra = "" if len(missing) <= 30 else f"\n... 另有 {len(missing) - 30} 张未列出"
    return f"⚠️ 以下歌曲封面缺失，已在 B50 图中留空：\n{listed}{extra}"


async def b50(client, message, space=None, sender=None):
    if not sender:
        return "[ERROR] 未提供 sender ID，无法查询"
    _log.info(f"[b50] 收到 {sender} 的请求")

    start_time = time.perf_counter()
    arcade_credentials = load_user_credentials(sender)

    if not arcade_credentials:
        await post_text(message, "❌ 请先完成 /绑 \"qrcode解析内容\"")
        return

    _log.info("[b50] 绑定信息加载成功")

    try:
        await post_text(message, "天使手绘中请稍后~", msg_seq=1)

        identifier = PlayerIdentifier(credentials=arcade_credentials)
        scores = await maimai.scores(identifier, provider=ArcadeProvider())
        elapsed = time.perf_counter() - start_time

        file_data, missing_covers = await asyncio.to_thread(render_b50_image, scores, sender, elapsed)
        await post_image(message, file_data, msg_seq=2)

        if missing_covers:
            await post_text(message, format_missing_covers(missing_covers), msg_seq=3)

        _log.info(
            f"[b50] {sender} 成功生成 B50 图片，b35={len(scores.scores_b35)} "
            f"b15={len(scores.scores_b15)} missing={len(missing_covers)} 用时 {elapsed:.2f} 秒"
        )

    except Exception as e:
        _log.warning(f"[b50] 查询或制图失败：{e}")
        elapsed = time.perf_counter() - start_time
        await post_text(
            message,
            f"❌ B50 查询失败，请稍后再试\n错误信息：{e}\n耗时：{elapsed:.2f} 秒",
        )
