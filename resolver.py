import json
import logging
import urllib.request
from config import TMDB_API_KEY

log = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"


def _tmdb_get(path: str) -> dict | None:
    if not TMDB_API_KEY:
        log.debug("TMDB_API_KEY is not set, skipping TMDb lookup")
        return None
    url = f"{TMDB_BASE}{path}"
    sep = "&" if "?" in path else "?"
    url += f"{sep}api_key={TMDB_API_KEY}&language=fr-FR"
    log.debug("TMDb GET %s", url.replace(TMDB_API_KEY, "***"))
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            log.debug("TMDb response keys: %s", list(data.keys()) if data else None)
            return data
    except Exception as e:
        log.warning("TMDb request failed: %s", e)
        return None


def resolve_imdbid(imdbid: str) -> str | None:
    if not imdbid.startswith("tt"):
        imdbid = f"tt{imdbid}"
    log.debug("Resolving IMDb ID: %s", imdbid)
    data = _tmdb_get(f"/find/{imdbid}?external_source=imdb_id")
    if not data:
        log.debug("No data returned for IMDb ID %s", imdbid)
        return None
    for key in ("movie_results", "tv_results"):
        if data.get(key):
            title = data[key][0].get("title") or data[key][0].get("name")
            log.debug("IMDb %s -> %s (from %s)", imdbid, title, key)
            return title
    log.debug("IMDb %s: no results in movie_results or tv_results", imdbid)
    return None


def resolve_tmdbid(tmdbid: str, media: str = "movie") -> str | None:
    log.debug("Resolving TMDb ID: %s (media=%s)", tmdbid, media)
    data = _tmdb_get(f"/{media}/{tmdbid}")
    if not data:
        log.debug("No data returned for TMDb ID %s", tmdbid)
        return None
    title = data.get("title") or data.get("name")
    log.debug("TMDb %s -> %s", tmdbid, title)
    return title


def resolve_tvdbid(tvdbid: str) -> str | None:
    log.debug("Resolving TVDb ID: %s", tvdbid)
    data = _tmdb_get(f"/find/{tvdbid}?external_source=tvdb_id")
    if not data:
        log.debug("No data returned for TVDb ID %s", tvdbid)
        return None
    for key in ("tv_results", "movie_results"):
        if data.get(key):
            title = data[key][0].get("name") or data[key][0].get("title")
            log.debug("TVDb %s -> %s (from %s)", tvdbid, title, key)
            return title
    log.debug("TVDb %s: no results in tv_results or movie_results", tvdbid)
    return None


def resolve_query(q: str = "", imdbid: str = "", tmdbid: str = "", tvdbid: str = "",
                  media: str = "movie", season: str = "", ep: str = "") -> str | None:
    log.debug("resolve_query(q=%r, imdbid=%r, tmdbid=%r, tvdbid=%r, media=%r, season=%r, ep=%r)",
              q, imdbid, tmdbid, tvdbid, media, season, ep)
    if q:
        log.debug("Using direct query: %s", q)
        return q

    title = None
    if imdbid:
        title = resolve_imdbid(imdbid)
    elif tmdbid:
        title = resolve_tmdbid(tmdbid, media)
    elif tvdbid:
        title = resolve_tvdbid(tvdbid)

    if not title:
        log.debug("Could not resolve any ID to a title, returning None")
        return None

    # Append season/episode for TV searches
    if season:
        title += f" S{int(season):02d}"
        if ep:
            title += f"E{int(ep):02d}"

    log.info("Resolved ID to: %s", title)
    return title
