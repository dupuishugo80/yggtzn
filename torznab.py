import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
ET.register_namespace("torznab", TORZNAB_NS)

# YGG sub_category → Torznab category
YGG_TO_TORZNAB = {
    "2183": 2000,   # Films → Movies
    "2178": 2010,   # Animation → Movies/Foreign (animation films)
    "2184": 5000,   # Séries TV → TV
    "2179": 5070,   # Séries animées → TV/Anime
}

# Torznab category → YGG (category, sub_category)
TORZNAB_TO_YGG = {
    2000: (2145, 2183),   # Movies → Films
    2010: (2145, 2178),   # Movies/Foreign → Animation
    2020: (2145, 2183),   # Movies/Other → Films
    2030: (2145, 2183),   # Movies/SD → Films
    2040: (2145, 2183),   # Movies/HD → Films
    2045: (2145, 2183),   # Movies/UHD → Films
    2050: (2145, 2183),   # Movies/BluRay → Films
    2060: (2145, 2178),   # Movies/3D → Animation
    2070: (2145, 2183),   # Movies/DVD → Films
    2080: (2145, 2183),   # Movies/WEB-DL → Films
    5000: (2145, 2184),   # TV → Séries TV
    5010: (2145, 2184),   # TV/WEB-DL → Séries TV
    5020: (2145, 2184),   # TV/Foreign → Séries TV
    5030: (2145, 2184),   # TV/SD → Séries TV
    5040: (2145, 2184),   # TV/HD → Séries TV
    5045: (2145, 2184),   # TV/UHD → Séries TV
    5050: (2145, 2184),   # TV/Other → Séries TV
    5060: (2145, 2184),   # TV/Sport → Séries TV
    5070: (2145, 2179),   # TV/Anime → Séries animées
    5080: (2145, 2184),   # TV/Documentary → Séries TV
}


def torznab_cats_to_ygg(cat_str: str) -> list[tuple[int, int]]:
    if not cat_str:
        return []
    seen = set()
    result = []
    for c in cat_str.split(","):
        try:
            ygg = TORZNAB_TO_YGG.get(int(c.strip()))
        except ValueError:
            continue
        if ygg and ygg not in seen:
            seen.add(ygg)
            result.append(ygg)
    return result


def ygg_subcat_to_torznab(subcat: str) -> int:
    return YGG_TO_TORZNAB.get(subcat, 2000)


def caps_xml() -> str:
    caps = ET.Element("caps")
    ET.SubElement(caps, "server", version="1.0", title="YGGTorznab")
    ET.SubElement(caps, "limits", max="100", default="50")

    searching = ET.SubElement(caps, "searching")
    ET.SubElement(searching, "search", available="yes", supportedParams="q,cat")
    ET.SubElement(searching, "tv-search", available="yes", supportedParams="q,season,ep,cat,imdbid,tvdbid,tmdbid")
    ET.SubElement(searching, "movie-search", available="yes", supportedParams="q,cat,imdbid,tmdbid")

    categories = ET.SubElement(caps, "categories")

    movies = ET.SubElement(categories, "category", id="2000", name="Movies")
    ET.SubElement(movies, "subcat", id="2010", name="Movies/Foreign")
    ET.SubElement(movies, "subcat", id="2020", name="Movies/Other")
    ET.SubElement(movies, "subcat", id="2030", name="Movies/SD")
    ET.SubElement(movies, "subcat", id="2040", name="Movies/HD")
    ET.SubElement(movies, "subcat", id="2045", name="Movies/UHD")
    ET.SubElement(movies, "subcat", id="2050", name="Movies/BluRay")
    ET.SubElement(movies, "subcat", id="2060", name="Movies/3D")
    ET.SubElement(movies, "subcat", id="2070", name="Movies/DVD")
    ET.SubElement(movies, "subcat", id="2080", name="Movies/WEB-DL")

    tv = ET.SubElement(categories, "category", id="5000", name="TV")
    ET.SubElement(tv, "subcat", id="5010", name="TV/WEB-DL")
    ET.SubElement(tv, "subcat", id="5020", name="TV/Foreign")
    ET.SubElement(tv, "subcat", id="5030", name="TV/SD")
    ET.SubElement(tv, "subcat", id="5040", name="TV/HD")
    ET.SubElement(tv, "subcat", id="5045", name="TV/UHD")
    ET.SubElement(tv, "subcat", id="5050", name="TV/Other")
    ET.SubElement(tv, "subcat", id="5060", name="TV/Sport")
    ET.SubElement(tv, "subcat", id="5070", name="TV/Anime")
    ET.SubElement(tv, "subcat", id="5080", name="TV/Documentary")

    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(caps, encoding="unicode")


def search_xml(results: list[dict], download_base: str = "", apikey: str = "") -> str:
    rss = ET.Element("rss", version="2.0")

    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "YGGTorznab"

    for r in results:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = r.get("title", "")
        ET.SubElement(item, "link").text = r.get("link", "")
        ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )

        link = r.get("link", "")
        if download_base and link:
            dl_url = f"{download_base}/download?url={link}&apikey={apikey}"
        else:
            dl_url = link

        ET.SubElement(item, "enclosure",
                      url=dl_url,
                      length=str(r.get("size", 0)),
                      type="application/x-bittorrent")

        torznab_cat = ygg_subcat_to_torznab(r.get("subcat", ""))

        def attr(name, value):
            el = ET.SubElement(item, f"{{{TORZNAB_NS}}}attr")
            el.set("name", name)
            el.set("value", str(value))

        attr("category", torznab_cat)
        attr("size", r.get("size", 0))
        attr("seeders", r.get("seeders", 0))
        attr("leechers", r.get("leechers", 0))
        attr("downloadvolumefactor", "1")
        attr("uploadvolumefactor", "1")

    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(rss, encoding="unicode")
