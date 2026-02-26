import json
import logging
import urllib.request
from config import TMDB_API_KEY

log = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"


def _tmdb_get(path: str) -> dict | None:
    if not TMDB_API_KEY:
        return None
    url = f"{TMDB_BASE}{path}"
    sep = "&" if "?" in path else "?"
    url += f"{sep}api_key={TMDB_API_KEY}&language=fr-FR"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.warning("TMDb request failed: %s", e)
        return None


def resolve_imdbid(imdbid: str) -> str | None:
    data = _tmdb_get(f"/find/{imdbid}?external_source=imdb_id")
    if not data:
        return None
    for key in ("movie_results", "tv_results"):
        if data.get(key):
            return data[key][0].get("title") or data[key][0].get("name")
    return None


def resolve_tmdbid(tmdbid: str, media: str = "movie") -> str | None:
    data = _tmdb_get(f"/{media}/{tmdbid}")
    if not data:
        return None
    return data.get("title") or data.get("name")


def resolve_tvdbid(tvdbid: str) -> str | None:
    data = _tmdb_get(f"/find/{tvdbid}?external_source=tvdb_id")
    if not data:
        return None
    for key in ("tv_results", "movie_results"):
        if data.get(key):
            return data[key][0].get("name") or data[key][0].get("title")
    return None


def resolve_query(q: str = "", imdbid: str = "", tmdbid: str = "", tvdbid: str = "",
                  media: str = "movie", season: str = "", ep: str = "") -> str | None:
    if q:
        return q

    title = None
    if imdbid:
        title = resolve_imdbid(imdbid)
    elif tmdbid:
        title = resolve_tmdbid(tmdbid, media)
    elif tvdbid:
        title = resolve_tvdbid(tvdbid)

    if not title:
        return None

    # Append season/episode for TV searches
    if season:
        title += f" S{int(season):02d}"
        if ep:
            title += f"E{int(ep):02d}"

    log.info("Resolved ID to: %s", title)
    return title
