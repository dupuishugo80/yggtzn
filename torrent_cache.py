import hashlib
import logging
import re
from io import BytesIO
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests

log = logging.getLogger(__name__)

CACHE_API_URL = "http://89.168.52.228"


# --- Bencode codec ---

def _bdecode(data: bytes):
    stream = BytesIO(data)
    return _bdecode_next(stream)


def _bdecode_next(stream: BytesIO):
    ch = stream.read(1)
    if not ch:
        raise ValueError("Unexpected end of data")

    if ch == b"i":
        num = b""
        while True:
            c = stream.read(1)
            if c == b"e":
                break
            num += c
        return int(num)

    if ch == b"l":
        result = []
        while stream.read(1) != b"e":
            stream.seek(stream.tell() - 1)
            result.append(_bdecode_next(stream))
        return result

    if ch == b"d":
        result = {}
        while stream.read(1) != b"e":
            stream.seek(stream.tell() - 1)
            key = _bdecode_next(stream)
            val = _bdecode_next(stream)
            result[key] = val
        return result

    if ch.isdigit():
        length = ch
        while True:
            c = stream.read(1)
            if c == b":":
                break
            length += c
        return stream.read(int(length))

    raise ValueError(f"Invalid bencode character: {ch}")


def _bencode(obj) -> bytes:
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, str):
        encoded = obj.encode()
        return str(len(encoded)).encode() + b":" + encoded
    if isinstance(obj, list):
        return b"l" + b"".join(_bencode(item) for item in obj) + b"e"
    if isinstance(obj, dict):
        items = sorted(obj.items(), key=lambda kv: kv[0] if isinstance(kv[0], bytes) else kv[0].encode())
        return b"d" + b"".join(_bencode(k) + _bencode(v) for k, v in items) + b"e"
    raise TypeError(f"Cannot bencode type {type(obj)}")


# --- Passkey manipulation ---

_PLACEHOLDER = "{PASSKEY}"
_PATH_PASSKEY_RE = re.compile(r"/([a-zA-Z0-9]{20,})/announce")


def _strip_passkey_from_url(url_bytes: bytes) -> bytes:
    url_str = url_bytes.decode("utf-8", errors="replace")
    parsed = urlparse(url_str)

    params = parse_qs(parsed.query, keep_blank_values=True)
    if "passkey" in params:
        params["passkey"] = [_PLACEHOLDER]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query)).encode("utf-8")

    new_path = _PATH_PASSKEY_RE.sub(f"/{_PLACEHOLDER}/announce", parsed.path)
    if new_path != parsed.path:
        return urlunparse(parsed._replace(path=new_path)).encode("utf-8")

    return url_bytes


def _inject_passkey_into_url(url_bytes: bytes, passkey: str) -> bytes:
    url_str = url_bytes.decode("utf-8", errors="replace")
    if _PLACEHOLDER not in url_str:
        raise ValueError(f"No {_PLACEHOLDER} found in announce URL: {url_str}")
    return url_str.replace(_PLACEHOLDER, passkey).encode("utf-8")


def strip_passkey(torrent_data: bytes) -> bytes:
    meta = _bdecode(torrent_data)

    if b"announce" in meta and isinstance(meta[b"announce"], bytes):
        meta[b"announce"] = _strip_passkey_from_url(meta[b"announce"])

    if b"announce-list" in meta and isinstance(meta[b"announce-list"], list):
        new_list = []
        for tier in meta[b"announce-list"]:
            if isinstance(tier, list):
                new_list.append([_strip_passkey_from_url(u) for u in tier if isinstance(u, bytes)])
            elif isinstance(tier, bytes):
                new_list.append([_strip_passkey_from_url(tier)])
        meta[b"announce-list"] = new_list

    return _bencode(meta)


def inject_passkey(torrent_data: bytes, passkey: str) -> bytes:
    meta = _bdecode(torrent_data)

    if b"announce" in meta and isinstance(meta[b"announce"], bytes):
        meta[b"announce"] = _inject_passkey_into_url(meta[b"announce"], passkey)

    if b"announce-list" in meta and isinstance(meta[b"announce-list"], list):
        new_list = []
        for tier in meta[b"announce-list"]:
            if isinstance(tier, list):
                new_list.append([_inject_passkey_into_url(u, passkey) for u in tier if isinstance(u, bytes)])
            elif isinstance(tier, bytes):
                new_list.append([_inject_passkey_into_url(tier, passkey)])
        meta[b"announce-list"] = new_list

    return _bencode(meta)


# --- Cache key & filename ---

def make_cache_key(url: str) -> str:
    match = re.search(r"/(\d+)-", url)
    if match:
        return match.group(1)
    return hashlib.sha256(url.encode()).hexdigest()


def filename_from_url(url: str) -> str:
    match = re.search(r"/(\d+-[^/?]+\.torrent)", url)
    if match:
        return match.group(1)
    match = re.search(r"/(\d+-[^/?]+)", url)
    if match:
        return match.group(1) + ".torrent"
    return "download.torrent"


# --- HTTP cache calls ---

def is_cache_available() -> bool:
    try:
        resp = requests.get(f"{CACHE_API_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def get_from_cache(key: str) -> tuple[bytes, str] | None:
    try:
        resp = requests.get(f"{CACHE_API_URL}/cache/{key}", timeout=10)
        if resp.status_code == 200:
            filename = None
            cd = resp.headers.get("Content-Disposition", "")
            match = re.search(r'filename="(.+?)"', cd)
            if match:
                filename = match.group(1)
            return resp.content, filename
        return None
    except Exception:
        return None


def put_to_cache(key: str, data: bytes, filename: str = None):
    try:
        headers = {}
        if filename:
            headers["X-Filename"] = filename
        resp = requests.put(f"{CACHE_API_URL}/cache/{key}", data=data, headers=headers, timeout=10)
        if resp.status_code != 200:
            log.warning("Cache PUT returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        log.warning("Failed to PUT to cache: %s", e)
