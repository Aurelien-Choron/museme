"""Genres Deezer des morceaux du catalogue, pour etiqueter le classifieur.

Le catalogue de 2021 n'a aucun morceau de rap, et les morceaux ajoutes n'ont
pas de genre. Deezer n'a pas de genre par morceau : on prend celui de
l'album du premier resultat de recherche « artiste titre » dont l'artiste
correspond. API publique, sans compte, limitee a 50 requetes par 5 secondes.

Resultat : OUT_DIR/deezer_genres.csv, une ligne par ligne du catalogue
(`row` = index de pd.read_csv). Les reponses sont mises en cache dans
DEEZER_CACHE_DIR : une execution interrompue reprend sans refaire les
requetes.
"""
import hashlib
import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from . import CATALOG_CSV, OUT_DIR, WORK_DIR

DEEZER_CACHE_DIR = WORK_DIR / "deezer_cache"
DEEZER_GENRES_CSV = OUT_DIR / "deezer_genres.csv"
API_URL = "https://api.deezer.com"
MIN_INTERVAL = 0.15  # secondes entre deux requetes (limite : 0,1 s)

_session = requests.Session()
_last_request = 0.0
_lock = threading.Lock()


def _get(path, params=None, retries=5):
    """JSON d'une requete a l'API, en respectant la limite de debit."""
    global _last_request
    for attempt in range(retries):
        # Les requetes partent en parallele (la latence domine), mais espacees
        # d'au moins MIN_INTERVAL toutes ensemble.
        with _lock:
            wait = _last_request + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last_request = time.monotonic()
        try:
            resp = _session.get(f"{API_URL}/{path}", params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            # Quota depasse : HTTP 200 avec {"error": {"code": 4, ...}}
            if data.get("error", {}).get("code") != 4:
                return data
        except requests.RequestException:
            if attempt == retries - 1:
                raise
        time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"quota Deezer toujours depasse sur {path}")


def _cached(name, path, params=None):
    cache = DEEZER_CACHE_DIR / f"{name}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    data = _get(path, params)
    DEEZER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def clean_title(song):
    """'Señorita (feat. X) - Remastered 2011' -> 'Señorita'"""
    title = re.sub(r"\(.*?\)|\[.*?\]", " ", str(song)).split(" - ")[0].strip()
    return title or str(song)


def same_name(a, b):
    """Noms d'artiste equivalents aux accents, a la casse et a la ponctuation pres.

    Garde les ecritures non latines (j-pop, cantopop), contrairement a
    collect.normalize.
    """
    a, b = (unicodedata.normalize("NFKD", str(x)).casefold() for x in (a, b))
    a, b = (re.sub(r"\W+", "", "".join(c for c in x if not unicodedata.combining(c)))
            for x in (a, b))
    return bool(a and b) and (a in b or b in a)


def search(artist, song):
    """Premier resultat dont l'artiste correspond, sinon None."""
    query = f"{artist} {clean_title(song)}"
    key = hashlib.md5(query.encode("utf-8")).hexdigest()
    hits = _cached(f"search_{key}", "search", {"q": query, "limit": 5}).get("data", [])
    return next((h for h in hits if same_name(artist, h["artist"]["name"])), None)


def album_genres(album_id):
    data = _cached(f"album_{album_id}", f"album/{album_id}")
    return [g["name"] for g in data.get("genres", {}).get("data", [])]


def tag(track):
    hit = search(track.Artist, track.Song)
    return {
        "row": track.Index,
        "Artist": track.Artist,
        "Song": track.Song,
        "deezer_artist": hit["artist"]["name"] if hit else "",
        "deezer_title": hit["title"] if hit else "",
        "deezer_album_id": hit["album"]["id"] if hit else "",
        "deezer_genres": "|".join(album_genres(hit["album"]["id"])) if hit else "",
    }


def run(workers=6):
    catalog = pd.read_csv(CATALOG_CSV)
    rows = []
    with ThreadPoolExecutor(workers) as pool:
        for i, row in enumerate(pool.map(tag, catalog.itertuples()), 1):
            rows.append(row)
            if i % 200 == 0:
                print(f"  {i}/{len(catalog)} morceaux", flush=True)

    out = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(DEEZER_GENRES_CSV, index=False)
    found = out["deezer_artist"].ne("")
    print(f"{found.sum()} morceaux trouves sur {len(out)}, "
          f"{out['deezer_genres'].ne('').sum()} avec un genre -> {DEEZER_GENRES_CSV}")
