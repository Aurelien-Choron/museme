"""Lecture des pages embed publiques de Spotify (open.spotify.com/embed/...).

Acces sans compte : chaque page embarque un JSON (__NEXT_DATA__) qui decrit
le morceau ou la playlist, avec l'URL p.scdn.co de l'extrait de 30 s.
Ce n'est pas une API : le format peut changer ou disparaitre sans preavis,
et cet usage n'est pas couvert par les conditions developpeur de Spotify.

Les reponses sont mises en cache dans EMBED_CACHE_DIR : une collecte
interrompue reprend sans refaire les requetes. Supprimer le cache d'une
playlist pour en relire la version du jour.
"""
import json
import re
import time

import requests

from . import EMBED_CACHE_DIR

EMBED_URL = "https://open.spotify.com/embed/{kind}/{id}"
MIN_INTERVAL = 1.0  # secondes entre deux requetes

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
_ID = re.compile(r"(?:open\.spotify\.com/(?:embed/)?\w+/|spotify:\w+:)?([0-9A-Za-z]{22})")

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"
_last_request = 0.0


def parse_id(url_or_uri):
    """URL open.spotify.com, URI spotify:xxx:ID ou ID nu -> ID."""
    match = _ID.search(url_or_uri)
    if not match:
        raise ValueError(f"identifiant Spotify introuvable dans {url_or_uri!r}")
    return match.group(1)


def _get(url, retries=4):
    global _last_request
    for attempt in range(retries):
        wait = _last_request + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            resp = _session.get(url, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(5 * 2 ** attempt)


def entity(kind, spotify_id, retries=4):
    """JSON decrivant le morceau ('track') ou la playlist ('playlist').

    Spotify sert parfois une page degradee (HTTP 200 sans donnees) : on
    reessaie avant de conclure a un identifiant invalide.
    """
    cache = EMBED_CACHE_DIR / f"{kind}_{spotify_id}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    for attempt in range(retries):
        match = _NEXT_DATA.search(_get(EMBED_URL.format(kind=kind, id=spotify_id)))
        try:
            data = json.loads(match.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
            break
        except (AttributeError, KeyError) as exc:
            if attempt == retries - 1:
                raise ValueError(f"page embed {kind}/{spotify_id} sans donnees") from exc
            time.sleep(10 * 2 ** attempt)
    EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def playlist(playlist_id):
    """(nom, [{track_id, title, preview}]) ; embed limite a 100 morceaux."""
    data = entity("playlist", playlist_id)
    tracks = [
        {
            "track_id": t["uri"].rsplit(":", 1)[-1],
            "title": t["title"],
            "preview": (t.get("audioPreview") or {}).get("url"),
        }
        for t in data.get("trackList", [])
    ]
    return data.get("name"), tracks


def track(track_id):
    """Artistes, titre, extrait, pochette 640 px et date de sortie d'un morceau."""
    data = entity("track", track_id)
    images = (data.get("visualIdentity") or {}).get("image") or []
    cover = None
    if images:
        largest = max(images, key=lambda img: img.get("maxWidth") or 0)
        # Meme forme que les pochettes du catalogue : i.scdn.co/image/<id>
        cover = "https://i.scdn.co/image/" + largest["url"].rsplit("/", 1)[-1]
    return {
        "artists": [a["name"] for a in data.get("artists", [])],
        "title": data.get("title") or data.get("name"),
        "preview": (data.get("audioPreview") or {}).get("url"),
        "cover": cover,
        "release_date": ((data.get("releaseDate") or {}).get("isoString") or "")[:10],
    }
