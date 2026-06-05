import json
import os
import time

from maimai_py import DivingFishProvider, PlayerIdentifier, Song, SongType

from plugins.nb_compat import logging

from .maimai_client import maimai

_log = logging.get_logger()

SETTINGS_PATH = "settings.json"

LEVEL_NAMES = {
    0: "BASIC",
    1: "ADVANCED",
    2: "EXPERT",
    3: "MASTER",
    4: "Re:MASTER",
}

TYPE_ORDER = {
    SongType.STANDARD: 0,
    SongType.DX: 1,
    SongType.UTAGE: 2,
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


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_PATH):
        raise FileNotFoundError("找不到 settings.json")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


settings = load_settings()
DIVINGFISH_TOKEN = settings.get("diving_fish_dev")
divingfish = DivingFishProvider(developer_token=DIVINGFISH_TOKEN)


async def post_text(message, content: str) -> None:
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=0,
        msg_id=message.id,
        content=content,
    )


async def find_song(query: str) -> Song | None:
    songs = await maimai.songs(provider=divingfish, curve_provider=divingfish)

    if query.isdecimal():
        song = await songs.by_id(int(query))
        if song:
            return song

    song = await songs.by_alias(query)
    if song:
        return song

    song = await songs.by_title(query)
    if song:
        return song

    matches = await songs.by_keywords(query)
    return matches[0] if matches else None


def enum_name(value) -> str:
    if not value:
        return "-"
    return DISPLAY_NAMES.get(value.name, value.name)


def type_name(song_type: SongType) -> str:
    if song_type == SongType.STANDARD:
        return "SD"
    if song_type == SongType.DX:
        return "DX"
    return "UTAGE"


def level_name(level_index) -> str:
    return LEVEL_NAMES.get(level_index.value, level_index.name)


def format_dx_score(dx_score: int | None, level_dx_score: int | None) -> str:
    if dx_score is None:
        return "-"
    if not level_dx_score:
        return str(dx_score)
    return f"{dx_score}/{level_dx_score}"


def format_score_line(score) -> str:
    achievement = "-" if score.achievements is None else f"{score.achievements:.4f}%"
    dx_score = format_dx_score(score.dx_score, score.level_dx_score)
    dx_star = "-" if score.dx_star is None else f"{score.dx_star}★"
    dx_rating = "-" if score.dx_rating is None else str(score.dx_rating)
    play_count = "-" if score.play_count is None else str(score.play_count)

    parts = [
        f"{type_name(score.type)} {level_name(score.level_index)} {score.level}({score.level_value:.1f})",
        f"达成率 {achievement}",
        f"评级 {enum_name(score.rate)}",
        f"DX {dx_score}",
        f"星数 {dx_star}",
        f"Rating {dx_rating}",
        f"FC {enum_name(score.fc)}",
        f"FS {enum_name(score.fs)}",
        f"游玩 {play_count} 次",
    ]
    return " - " + " | ".join(parts)


def format_song_summary(song: Song) -> list[str]:
    aliases = "、".join(song.aliases[:5]) if song.aliases else "-"
    return [
        f"🎵 {song.title} (ID: {song.id})",
        f"艺术家：{song.artist}",
        f"分类：{song.genre.value} / BPM：{song.bpm}",
        f"别名：{aliases}",
    ]


def format_info_result(player_song, elapsed: float) -> str:
    lines = format_song_summary(player_song.song)

    if not player_song.scores:
        lines.extend(
            [
                "",
                "未查询到这首歌的成绩。",
                f"⏱️ 查询耗时：{elapsed:.2f} 秒",
            ]
        )
        return "\n".join(lines)

    scores = sorted(
        player_song.scores,
        key=lambda s: (TYPE_ORDER.get(s.type, 99), s.level_index.value),
    )

    lines.append("")
    lines.append("📊 单曲成绩：")
    lines.extend(format_score_line(score) for score in scores)
    lines.append(f"\n⏱️ 查询耗时：{elapsed:.2f} 秒")
    return "\n".join(lines)


async def song_info(client, message, content, sender=None):
    query = content.strip()
    if not query:
        await post_text(message, "用法：info [歌曲名/歌曲别名/歌曲ID]")
        return

    if not sender:
        return "[ERROR] 未提供 sender ID，无法查询"

    _log.info(f"[info] 收到 {sender} 对于 {query} 的单曲成绩查询请求")
    start_time = time.perf_counter()

    try:
        song = await find_song(query)
        if song is None:
            await post_text(message, f"❌ 未找到相关歌曲：{query}")
            return

        identifier = PlayerIdentifier(qq=int(sender))
        player_song = await maimai.minfo(song, identifier, provider=divingfish)
        elapsed = time.perf_counter() - start_time

        if player_song is None:
            await post_text(message, f"❌ 未找到相关歌曲：{query}")
            return

        await post_text(message, format_info_result(player_song, elapsed))
        _log.info(f"[info] {sender} 查询 {song.title} 完成，用时 {elapsed:.2f} 秒")

    except Exception as e:
        _log.warning(f"[info] 查询失败：{e}")
        elapsed = time.perf_counter() - start_time
        await post_text(
            message,
            f"❌ 单曲成绩查询失败，请稍后再试\n错误信息：{e}\n耗时：{elapsed:.2f} 秒",
        )
