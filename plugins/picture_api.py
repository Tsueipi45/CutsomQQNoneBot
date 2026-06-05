import base64
import html
import io
import random
import re
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageOps
import requests

from plugins.nb_compat import logging

_log = logging.get_logger()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PICTURE_FOLDER = PROJECT_ROOT / "pictures"
RANDOM_PICTURE_FOLDER = "random_pictures"
LOLICON_API_URL = "https://api.lolicon.app/setu/v2"
SAFEBOORU_API_URL = "https://safebooru.org/index.php"
SEX_PHOTO_API_URL = "https://sex.nyan.run/api/v2/"
API_TIMEOUT_SECONDS = 15
IMAGE_TIMEOUT_SECONDS = 30
MAX_SEND_IMAGE_BYTES = 500 * 1024
MAX_SEND_IMAGE_SIDE = 1280
SEND_IMAGE_JPEG_QUALITY = 82

REQUEST_HEADERS = {
    "User-Agent": "CustomQQNoneBot/1.0",
}

PIXIV_ALIAS_TAGS = {
    "mygo": ["MyGO!!!!!"],
    "mygo!!!!!": ["MyGO!!!!!"],
    "soyo": ["長崎そよ", "Soyo Nagasaki"],
    "nagasaki": ["長崎そよ", "Soyo Nagasaki"],
    "nagasaki_soyo": ["長崎そよ", "Soyo Nagasaki"],
    "anon": ["千早愛音", "Anon Chihaya"],
    "tomori": ["高松燈", "Takamatsu Tomori"],
    "taki": ["椎名立希", "Taki Shiina"],
    "rana": ["要楽奈", "Raana Kaname"],
    "raana": ["要楽奈", "Raana Kaname"],
    "sakiko": ["豊川祥子", "Sakiko Togawa"],
    "mutsumi": ["若葉睦", "Mutsumi Wakaba"],
    "umiri": ["八幡海鈴", "Umiri Yahata"],
    "nyamu": ["祐天寺にゃむ", "Nyamu Yutenji"],
    "uika": ["三角初華", "Uika Misumi"],
    "saki": ["豊川祥子", "Sakiko Togawa"],
    "祥子": ["豊川祥子", "Sakiko Togawa"],
    "sakiko": ["豊川祥子", "Sakiko Togawa"],
}

SAFEBOORU_ALIAS_TAGS = {
    "mygo": ["bang_dream!_it's_mygo!!!!!"],
    "mygo!!!!!": ["bang_dream!_it's_mygo!!!!!"],
    "soyo": ["nagasaki_soyo"],
    "nagasaki": ["nagasaki_soyo"],
    "nagasaki_soyo": ["nagasaki_soyo"],
    "anon": ["chihaya_anon"],
    "tomori": ["takamatsu_tomori"],
    "taki": ["shiina_taki"],
    "rana": ["kaname_raana"],
    "raana": ["kaname_raana"],
    "sakiko": ["togawa_sakiko"],
    "mutsumi": ["wakaba_mutsumi"],
    "umiri": ["yahata_umiri"],
    "nyamu": ["yuutenji_nyamu"],
    "uika": ["misumi_uika"],
    "saki": ["togawa_sakiko"],
    "祥子": ["togawa_sakiko"],
    "sakiko": ["togawa_sakiko"],
}

BLOCKED_IMAGE_TAGS = {
    "r-18",
    "r18",
    "nsfw",
    "nude",
    "naked",
    "sex",
    "panties",
    "underwear",
    "lingerie",
    "bikini",
    "breasts",
    "cleavage",
    "loli",
    "ロリ",
    "萝莉",
    "下着",
    "パンツ",
    "おっぱい",
}


def _find_child_case_insensitive(parent: Path, filename: str) -> Path:
    candidate = parent / filename
    if candidate.exists():
        return candidate

    lowered = filename.casefold()
    try:
        for child in parent.iterdir():
            if child.name.casefold() == lowered:
                return child
    except OSError:
        pass

    return candidate


def _read_picture_list(csv_path: Path) -> list[str]:
    with csv_path.open(newline="", encoding="gbk") as csvfile:
        return [line.strip() for line in csvfile if line.strip()]


def _get_list_csv_paths(folder_path: Path, group_name: Optional[str]) -> list[Path]:
    if group_name:
        csv_filename = f"{group_name}_list.csv"
        return [_find_child_case_insensitive(folder_path, csv_filename)]

    try:
        return sorted(
            child
            for child in folder_path.iterdir()
            if child.is_file() and child.name.casefold().endswith("_list.csv")
        )
    except OSError as e:
        _log.error(f"failed to list picture folder {folder_path}: {e}")
        return []


def get_random_picture_path(
    group_name: Optional[str] = None,
    subfolder: str = RANDOM_PICTURE_FOLDER,
) -> Optional[str]:
    folder_path = PICTURE_FOLDER / subfolder
    candidates: list[Path] = []

    for csv_path in _get_list_csv_paths(folder_path, group_name):
        try:
            filenames = _read_picture_list(csv_path)
        except Exception as e:
            _log.error(f"failed to read picture list {csv_path}: {e}")
            continue

        if not filenames:
            _log.warning(f"{csv_path} has no picture filenames")
            continue

        for filename in filenames:
            if filename.casefold().endswith(".csv"):
                continue

            image_path = _find_child_case_insensitive(folder_path, filename)
            if image_path.exists():
                candidates.append(image_path)
            else:
                _log.warning(f"picture file does not exist: {image_path}")

    if not candidates:
        return None

    return str(random.choice(candidates))


def encode_image_base64(image_path: str) -> Optional[str]:
    try:
        with open(image_path, "rb") as f:
            return encode_image_bytes_base64(f.read())
    except Exception as e:
        _log.error(f"failed to encode picture as base64: {e}")
        return None


def encode_image_bytes_base64(image_bytes: bytes) -> Optional[str]:
    try:
        return base64.b64encode(_prepare_image_bytes_for_send(image_bytes)).decode("utf-8")
    except Exception as e:
        _log.error(f"failed to encode image bytes as base64: {e}")
        return None


def _prepare_image_bytes_for_send(image_bytes: bytes) -> bytes:
    if len(image_bytes) <= MAX_SEND_IMAGE_BYTES:
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_SEND_IMAGE_SIDE, MAX_SEND_IMAGE_SIDE), Image.Resampling.LANCZOS)

            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            output = io.BytesIO()
            image.save(output, format="JPEG", quality=SEND_IMAGE_JPEG_QUALITY, optimize=True)
            compressed = output.getvalue()

            if len(compressed) < len(image_bytes):
                _log.info(
                    f"compressed image for send: {len(image_bytes)} bytes -> {len(compressed)} bytes"
                )
                return compressed
    except Exception as e:
        _log.warning(f"failed to compress image before send: {e}")

    return image_bytes


def _split_keyword(keyword: str) -> list[str]:
    return [part for part in re.split(r"[\s,，、|/]+", keyword.strip()) if part]


def _unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _normalize_tag(tag: str) -> str:
    return re.sub(r"[\s_]+", " ", tag.casefold()).strip()


def _normalize_alias_value(value: str) -> str:
    return _normalize_tag(value).replace("!", "")


def _has_blocked_tags(tags: Any) -> bool:
    if isinstance(tags, str):
        tag_values = re.split(r"\s+", tags)
    elif isinstance(tags, list):
        tag_values = [str(tag) for tag in tags]
    else:
        return False

    normalized_tags = {_normalize_tag(tag) for tag in tag_values}
    normalized_blocked = {_normalize_tag(tag) for tag in BLOCKED_IMAGE_TAGS}
    return bool(normalized_tags & normalized_blocked)


def _tag_values(tags: Any) -> set[str]:
    if isinstance(tags, str):
        tag_values = re.split(r"\s+", tags)
    elif isinstance(tags, list):
        tag_values = [str(tag) for tag in tags]
    else:
        tag_values = []

    normalized_values = set()
    for tag in tag_values:
        normalized = _normalize_alias_value(tag)
        if normalized:
            normalized_values.add(normalized)
    return normalized_values


def _required_pixiv_alias_groups(keyword: str) -> list[set[str]]:
    groups = []
    for token in _split_keyword(keyword):
        aliases = PIXIV_ALIAS_TAGS.get(token.casefold(), [token])
        groups.append({_normalize_alias_value(alias) for alias in aliases})
    return groups


def _required_safebooru_alias_groups(keyword: str) -> list[set[str]]:
    groups = []
    for token in _split_keyword(keyword):
        aliases = SAFEBOORU_ALIAS_TAGS.get(token.casefold())
        if aliases:
            groups.append({_normalize_alias_value(alias) for alias in aliases})
        elif token.isascii():
            groups.append({_normalize_alias_value(token)})
    return groups


def _tags_match_all_groups(tags: Any, required_groups: list[set[str]]) -> bool:
    if not required_groups:
        return True

    values = _tag_values(tags)
    if not values:
        return False

    return all(group & values for group in required_groups)


def _pixiv_tag_groups(keyword: str) -> list[str]:
    groups: list[str] = []
    for token in _split_keyword(keyword):
        aliases = PIXIV_ALIAS_TAGS.get(token.casefold(), [token])
        groups.append("|".join(_unique(aliases)))
    return groups or [keyword]


def _safebooru_tags(keyword: str) -> str:
    tags: list[str] = []
    for token in _split_keyword(keyword):
        aliases = SAFEBOORU_ALIAS_TAGS.get(token.casefold())
        if aliases:
            tags.extend(aliases)
        elif token.isascii():
            tags.append(token.casefold().replace(" ", "_"))

    return " ".join(_unique(tags))


def _pick_random(items: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return random.choice(items) if items else None


def _search_lolicon_pictures(keyword: str) -> list[dict[str, Any]]:
    required_groups = _required_pixiv_alias_groups(keyword)
    params: list[tuple[str, Any]] = [
        ("r18", 0),
        ("num", 8),
        ("size", "regular"),
    ]
    params.extend(("tag", group) for group in _pixiv_tag_groups(keyword))

    try:
        response = requests.get(
            LOLICON_API_URL,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        _log.error(f"failed to search lolicon api by keyword {keyword!r}: {e}")
        return []

    if payload.get("error"):
        _log.warning(f"lolicon api returned error for {keyword!r}: {payload.get('error')}")
        return []

    data = payload.get("data")
    if not isinstance(data, list):
        return []

    valid = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = (item.get("urls") or {}).get("regular") or (item.get("urls") or {}).get("original")
        tags = item.get("tags")
        if (
            not url
            or item.get("r18")
            or _has_blocked_tags(tags)
            or not _tags_match_all_groups(tags, required_groups)
        ):
            continue
        valid.append(
            {
                "title": item.get("title") or f"Pixiv {item.get('pid')}",
                "url": url,
                "source": "lolicon",
                "pid": item.get("pid"),
                "author": item.get("author"),
                "tags": tags,
            }
        )

    random.shuffle(valid)
    return valid


def _search_safebooru_pictures(keyword: str) -> list[dict[str, Any]]:
    required_groups = _required_safebooru_alias_groups(keyword)
    tags = _safebooru_tags(keyword)
    if not tags:
        return []

    try:
        response = requests.get(
            SAFEBOORU_API_URL,
            params={
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "tags": tags,
                "limit": 20,
            },
            headers=REQUEST_HEADERS,
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        _log.error(f"failed to search safebooru by keyword {keyword!r}: {e}")
        return []

    if not isinstance(payload, list):
        return []

    valid = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rating = str(item.get("rating") or "").casefold()
        if rating not in {"general", "safe", "g", "s"}:
            continue
        url = item.get("sample_url") or item.get("file_url")
        tags = html.unescape(item.get("tags") or "")
        if not url or _has_blocked_tags(tags) or not _tags_match_all_groups(tags, required_groups):
            continue
        valid.append(
            {
                "title": f"Safebooru #{item.get('id')}",
                "url": html.unescape(url),
                "source": "safebooru",
                "id": item.get("id"),
                "tags": tags,
            }
        )

    random.shuffle(valid)
    return valid


def _search_sex_nyan_pictures(keyword: str) -> list[dict[str, Any]]:
    keyword = keyword.strip()
    if not keyword:
        return []

    try:
        response = requests.get(
            SEX_PHOTO_API_URL,
            params={"keyword": keyword, "num": 1, "r18": "false"},
            headers=REQUEST_HEADERS,
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        _log.error(f"failed to search picture by keyword {keyword!r}: {e}")
        return []

    if not payload.get("success"):
        _log.warning(f"picture api returned failure for {keyword!r}: {payload}")
        return []

    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return []

    valid = []
    for item in data:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        valid.append(
            {
                "title": item.get("title") or item.get("url"),
                "url": item["url"],
                "source": "sex.nyan",
            }
        )

    random.shuffle(valid)
    return valid


def search_picture_candidates(keyword: str) -> list[dict[str, Any]]:
    keyword = keyword.strip()
    if not keyword:
        return []

    candidates: list[dict[str, Any]] = []
    for searcher in (
        _search_lolicon_pictures,
        _search_safebooru_pictures,
        _search_sex_nyan_pictures,
    ):
        candidates.extend(searcher(keyword))
        if candidates:
            return candidates

    return []


def search_picture(keyword: str) -> Optional[dict[str, Any]]:
    return _pick_random(search_picture_candidates(keyword))


def encode_remote_image_base64(url: str) -> Optional[str]:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=IMAGE_TIMEOUT_SECONDS)
        response.raise_for_status()
        return encode_image_bytes_base64(response.content)
    except Exception as e:
        _log.error(f"failed to download or encode remote picture {url}: {e}")
        return None
