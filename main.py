import logging
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import PlainTextResponse

from config import API_KEY, DEBUG
from browser import browser
from resolver import resolve_query
from torznab import caps_xml, search_xml, torznab_cats_to_ygg
from torrent_cache import (
    is_cache_available, get_from_cache, put_to_cache,
    make_cache_key, inject_passkey, strip_passkey, filename_from_url,
)

logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

DUMMY_RESULTS = [
    {
        "title": "YGGTorznab Test Movie",
        "link": "https://www.yggtorrent.org",
        "torrent_id": "0",
        "size": 0,
        "seeders": 0,
        "leechers": 0,
        "subcat": "2183",
    },
    {
        "title": "YGGTorznab Test TV",
        "link": "https://www.yggtorrent.org/tv",
        "torrent_id": "0",
        "size": 0,
        "seeders": 0,
        "leechers": 0,
        "subcat": "2184",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Logging in to YGG…")
    try:
        browser.login()
    except Exception as e:
        log.error("Initial login failed: %s — will retry on first request", e)
    yield
    log.info("Shutting down browser…")
    browser.close()


app = FastAPI(title="YGGTorznab", lifespan=lifespan)


@app.get("/api")
def torznab_api(
    request: Request,
    t: str = Query(""),
    q: str = Query(""),
    cat: str = Query(""),
    imdbid: str = Query(""),
    tmdbid: str = Query(""),
    tvdbid: str = Query(""),
    season: str = Query(""),
    ep: str = Query(""),
    apikey: str = Query(""),
    offset: str = Query("0"),
    limit: str = Query("100"),
    extended: str = Query(""),
):
    if apikey != API_KEY:
        return PlainTextResponse("Unauthorized", status_code=401)

    if t == "caps":
        return Response(content=caps_xml(), media_type="application/xml")

    if t in ("search", "tvsearch", "movie"):
        media = "tv" if t == "tvsearch" else "movie"
        log.debug("Search request: t=%s, q=%r, imdbid=%r, tmdbid=%r, tvdbid=%r, cat=%r",
                  t, q, imdbid, tmdbid, tvdbid, cat)
        search_q = resolve_query(
            q=q, imdbid=imdbid, tmdbid=tmdbid, tvdbid=tvdbid,
            media=media, season=season, ep=ep,
        )

        if not search_q:
            log.debug("No search query resolved, returning dummy results")
            download_base = str(request.base_url).rstrip("/")
            return Response(
                content=search_xml(DUMMY_RESULTS, download_base=download_base, apikey=apikey),
                media_type="application/xml",
            )

        log.debug("Resolved search query: %r", search_q)
        ygg_cats = torznab_cats_to_ygg(cat)
        log.debug("YGG categories: %s", ygg_cats)

        if ygg_cats:
            results = []
            seen = set()
            for ygg_cat, ygg_subcat in ygg_cats:
                for r in browser.search(search_q, category=ygg_cat, sub_category=ygg_subcat):
                    if r["link"] not in seen:
                        seen.add(r["link"])
                        results.append(r)
        else:
            results = browser.search(search_q)

        log.debug("Search returned %d results", len(results))
        download_base = str(request.base_url).rstrip("/")
        return Response(
            content=search_xml(results, download_base=download_base, apikey=apikey),
            media_type="application/xml",
        )

    return PlainTextResponse(f"Unknown t={t}", status_code=400)


@app.get("/download")
def download_torrent(
    url: str = Query(""),
    apikey: str = Query(""),
):
    if apikey != API_KEY:
        return PlainTextResponse("Unauthorized", status_code=401)

    if not url:
        return PlainTextResponse("Missing url", status_code=400)

    url = quote(url, safe=':/?#[]@!$&\'()*+,;=-._~%')

    try:
        if browser.passkey and is_cache_available():
            cache_key = make_cache_key(url)
            cached = get_from_cache(cache_key)

            if cached is not None:
                cached_data, cached_filename = cached
                log.info("Cache HIT for %s", url)
                torrent_data = inject_passkey(cached_data, browser.passkey)
                fname = cached_filename or filename_from_url(url)
                return Response(
                    content=torrent_data,
                    media_type="application/x-bittorrent",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'},
                )

            log.info("Cache MISS for %s", url)
            torrent_data, filename = browser.download(url)
            if not torrent_data:
                return PlainTextResponse("Download failed", status_code=500)

            try:
                stripped = strip_passkey(torrent_data)
                put_to_cache(cache_key, stripped, filename=filename)
                log.info("Cached torrent for %s", url)
            except Exception as e:
                log.warning("Failed to cache torrent: %s", e)

            return Response(
                content=torrent_data,
                media_type="application/x-bittorrent",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
    except Exception as e:
        log.warning("Cache logic error, falling back to direct download: %s", e)

    torrent_data, filename = browser.download(url)
    if not torrent_data:
        return PlainTextResponse("Download failed", status_code=500)

    return Response(
        content=torrent_data,
        media_type="application/x-bittorrent",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7474)
