"""Identifiant Spotify de chaque morceau du catalogue, pour la lecture complete.

Le site joue les morceaux en entier pour une session Spotify Premium (Web
Playback SDK) : il lui faut l'identifiant du morceau (22 caracteres), que le
catalogue n'a pas garde.
- Morceaux ajoutes en 2026 : l'identifiant est dans OUT_DIR/new_tracks.csv
  (etape collect), retrouve par le hash de l'extrait.
- Morceaux de 2021 : recherche de l'API Web, une requete par morceau
  (10 resultats au maximum depuis fevrier 2026), puis choix du resultat.

Niveaux de correspondance (colonne match), du plus sur au moins sur :
- playlist : identifiant de la collecte de 2026 ;
Titre compare en entier, en minuscules, sans accents ni ponctuation ; seuls
les invites (feat., with), la remasterisation et « Original Mix » sont
ignores (title_key). L'artiste doit correspondre dans tous les cas.
- pochette : meme titre, meme pochette d'album ;
- album : meme titre, meme nom d'album (la pochette a change depuis 2021) ;
- titre : meme titre, sur un autre album (compilation, reedition) ;
- oeuvre : classique seulement (Main_Genre Classical), la meme oeuvre dans une
  autre interpretation : tous les mots du titre du catalogue, hors parentheses
  et mention d'acte, sont dans le titre Spotify, et pas d'arrangement que le
  catalogue n'annonce pas (decision du 2026-10-22 : l'artiste du catalogue est
  le compositeur, et toute version entiere de l'oeuvre convient) ;
- douteux : meme titre de base, mais une autre version (remix, live, autre
  prise...) ;
- aucun : rien de convenable dans les resultats.
Le site ne garde que les niveaux de ACCEPTED (pipeline/site.py).
L'extrait ne sert pas de preuve : Spotify a regenere ses fichiers d'extrait
depuis 2021, le hash differe meme pour le meme album (essai du 2026-10-12).

Acces : application Spotify en mode developpement, flux Client Credentials.
Les identifiants de l'app sont dans WORK_DIR/spotify_app.json
({"client_id": ..., "client_secret": ...}), hors du depot, qui est public :
ne jamais les ecrire ailleurs.

Les reponses sont mises en cache (SPOTIFY_CACHE_DIR) et les lignes deja
traitees sont sautees. Quota du mode developpement atteint (QUOTA_EXCEEDED) :
la suite se fait avec les seules recherches en cache, les autres morceaux
sont laisses pour une prochaine execution. --max N arrete de meme les
recherches apres N requetes envoyees a Spotify (le cache ne compte pas) : des
lots de quelques centaines par jour, sans atteindre le quota, qui sert aussi a
la lecture des comptes invites. --rematch reapplique la regle aux morceaux
deja cherches (apres un changement de match), depuis le cache.

Sorties :
- data/spotify_ids.csv : row, track_id, match (identifiants publics) ;
- OUT_DIR/revue_spotify.csv : details des correspondances, pour relecture.
"""
import base64
import hashlib
import json
import re
import time
import unicodedata

import pandas as pd
import requests

from . import CATALOG_CSV, OUT_DIR, WORK_DIR
from .extract import NEW_TRACKS_CSV
from .site import PREVIEW_RE, SPOTIFY_IDS_CSV

APP_JSON = WORK_DIR / "spotify_app.json"
SPOTIFY_CACHE_DIR = WORK_DIR / "spotify_cache"
REVIEW_CSV = OUT_DIR / "revue_spotify.csv"
API_URL = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
MARKET = "FR"
MIN_INTERVAL = 0.5  # secondes entre deux requetes a l'API
# Niveaux retenus par le site : fixes par l'utilisateur apres l'essai sur
# 100 morceaux, plus oeuvre pour le classique (2026-10-22).
ACCEPTED = ("playlist", "pochette", "album", "titre", "oeuvre")
# Seules mentions ignorees dans un titre (decision du 2026-10-12) : les
# invites, la remasterisation et « Original Mix ». Tout le reste compte :
# « Sleepyhead - Stripped Down Version » n'est pas « Sleepyhead ».
# Toutes leurs ecritures (2026-10-17) : « Breathe - feat. Sondar » est
# « Breathe (feat. Sondar) », « Che - 2019 - Remaster » est « Che (2019 - Remaster) ».
_FEAT = re.compile(r"\s*[(\[](?:feat\.?|ft\.?|featuring|with)\s[^)\]]*[)\]]"
                   r"|\s+-\s+(?:feat\.?|ft\.?|featuring)\s(?:(?!\s-\s).)*(?=\s-\s|$)", re.I)
_REMASTER = re.compile(r"\s*[(\[][^)\]]*remaster[^)\]]*[)\]]|\s+-\s+[^-]*remaster[^-]*$"
                       r"|\s+-\s+\d{4}\s+-\s+[^-]*remaster[^-]*$", re.I)
_ORIGINAL_MIX = re.compile(r"\s*[(\[]original mix[)\]]|\s+-\s+original mix$", re.I)
# Album : sans la mention d'edition (« (Deluxe Edition) », « [2020 Remaster] »).
_EDITION = re.compile(r"\s*[(\[][^)\]]*(?:edition|deluxe|expanded|anniversary|bonus|version)[^)\]]*[)\]]", re.I)
# Classique : mention d'acte, ecrite de bien des facons d'un disque a l'autre
# (« Act 1 », « Act I », « ACT1 », « 1. Akt ») ; arrangement (« Arr. Lewin for
# Guitar », « Orchestral Version ») : une autre oeuvre pour l'oreille.
_ACT = re.compile(r"\b(?:act|acte|akt|atto)\s*\.?\s*(?:[ivx]+|\d+)\b|\b\d+\.\s*(?:akt|act)\b", re.I)
_ARRANGEMENT = re.compile(r"\b(?:arr|arranged|arrangement|transcr\w*|orch|orchestrated"
                          r"|orchestral version|version for)\b", re.I)

_session = requests.Session()
_token = {"value": None, "expires": 0.0}
_last_request = 0.0
_quota = {"exceeded": False, "max": None, "requests": 0}


class QuotaExceeded(Exception):
    """Quota du mode developpement atteint : reprendre plus tard."""


def _app():
    if not APP_JSON.exists():
        raise SystemExit(f"{APP_JSON} introuvable : y ecrire client_id et client_secret de l'app Spotify.")
    app = json.loads(APP_JSON.read_text(encoding="utf-8-sig"))
    return app["client_id"], app["client_secret"]


def _access_token():
    if _token["value"] and time.monotonic() < _token["expires"] - 60:
        return _token["value"]
    client_id, secret = _app()
    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    resp = _session.post(TOKEN_URL, data={"grant_type": "client_credentials"},
                         headers={"Authorization": f"Basic {basic}"}, timeout=20)
    if resp.status_code != 200:
        # Jamais le corps de la requete (secret) : seulement la reponse.
        raise SystemExit(f"Jeton Spotify refuse ({resp.status_code}) : {resp.text[:200]}")
    data = resp.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.monotonic() + data["expires_in"]
    return _token["value"]


def _get(path, params, retries=5):
    global _last_request
    for attempt in range(retries):
        wait = _last_request + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            resp = _session.get(f"{API_URL}/{path}", params=params, timeout=20,
                                headers={"Authorization": f"Bearer {_access_token()}"})
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(5 * 2 ** attempt)
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            if "QUOTA_EXCEEDED" in resp.text:
                raise QuotaExceeded(resp.text[:200])
            time.sleep(int(resp.headers.get("Retry-After", 5)) + 1)
            continue
        if resp.status_code == 401:
            _token["value"] = None
            continue
        if resp.status_code >= 500:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{path} {params} : {resp.status_code} {resp.text[:200]}")
    raise RuntimeError(f"{path} {params} : echec apres {retries} essais")


def search(query):
    """Resultats (10 au maximum) de la recherche de morceaux, avec cache."""
    key = hashlib.md5(f"{MARKET}|{query}".encode("utf-8")).hexdigest()
    return _search(SPOTIFY_CACHE_DIR / f"search_{key}.json", query, "track")


def search_artist(name):
    """Resultats (10 au maximum) de la recherche d'artistes, avec cache.

    Compte dans le meme quota que la recherche de morceaux (--max)."""
    key = hashlib.md5(f"{MARKET}|{name}".encode("utf-8")).hexdigest()
    return _search(SPOTIFY_CACHE_DIR / f"artist_{key}.json", name, "artist")


def _search(cache, query, kind):
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if _quota["exceeded"]:
        raise QuotaExceeded("quota deja atteint")
    if _quota["max"] is not None and _quota["requests"] >= _quota["max"]:
        _quota["exceeded"] = True
        raise QuotaExceeded(f"limite --max {_quota['max']} atteinte")
    _quota["requests"] += 1
    try:
        data = _get("search", {"q": query, "type": kind, "market": MARKET, "limit": 10})
    except QuotaExceeded:
        _quota["exceeded"] = True
        raise
    items = [t for t in data.get(f"{kind}s", {}).get("items", []) if t]
    SPOTIFY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


def _quoted(text):
    return str(text).replace('"', " ")


def _image_id(url):
    return url.rsplit("/", 1)[-1] if url else None


def _first_artist(artist):
    """'Calvin Harris, Rihanna' ou 'A feat. B' -> 'Calvin Harris'"""
    return re.split(r",| feat\.? | ft\.? | & ", str(artist), maxsplit=1, flags=re.I)[0].strip()


def _key(text):
    """Minuscules, sans accents ni ponctuation. Garde les ecritures non latines
    (collect.normalize reduit un titre japonais a une chaine vide)."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[\W_]+", " ", text.casefold()).split())


def title_key(title):
    """'Dead Price (feat. Sean Price)' -> 'dead price' ;
    'The Gurner - Tanner Ross Remix' -> 'the gurner tanner ross remix'"""
    title = str(title)
    for pattern in (_FEAT, _REMASTER, _ORIGINAL_MIX):
        title = pattern.sub(" ", title)
    return _key(title)


def base_key(title):
    """Titre sans parentheses ni suite apres ' - ' : meme morceau, version
    peut-etre differente."""
    return _key(re.sub(r"\(.*?\)|\[.*?\]", " ", str(title)).split(" - ")[0])


def album_key(album):
    return title_key(_EDITION.sub(" ", str(album)))


def _classical(track):
    return getattr(track, "Main_Genre", None) == "Classical"


def work_title(title):
    """'Tosca, Act 1: Recondita armonia (Live)' -> 'Tosca, : Recondita armonia'"""
    return " ".join(_ACT.sub(" ", re.sub(r"\(.*?\)|\[.*?\]", " ", str(title))).split())


def same_work(song, spotify_title, composer=""):
    """Meme oeuvre classique : tous les mots du titre du catalogue (hors
    parentheses, acte et nom du compositeur, deja verifie par l'artiste) sont
    dans le titre Spotify, sans arrangement que le catalogue n'annonce pas."""
    words = set(_key(work_title(song)).split()) - set(_key(composer).split())
    if not words or not words <= set(_key(_ACT.sub(" ", str(spotify_title))).split()):
        return False
    return not _ARRANGEMENT.search(str(spotify_title)) or bool(_ARRANGEMENT.search(str(song)))


def candidates(track):
    """Resultats de recherche pour un morceau : requete precise, puis libre.

    Classique : sans la pochette ni l'album de 2021, le titre est cherche dans
    cet album (meme enregistrement : « Lacrimosa » de l'album « Classic » est
    l'arrangement pour violoncelle de HAUSER, pas un choeur) ; si rien ne
    convient encore, une requete libre avec le titre entier (« The Four
    Seasons - Autumn... » n'est pas « The Four Seasons »)."""
    artist = _first_artist(track.Artist)
    title = re.sub(r"\(.*?\)|\[.*?\]", " ", str(track.Song)).split(" - ")[0].strip() or str(track.Song)
    items = search(f'track:"{_quoted(title)}" artist:"{_quoted(artist)}"')
    if not items:
        items = search(f"{title} {artist}")
    if _classical(track):
        level = match(track, items)[0]
        if level not in ("pochette", "album") and isinstance(track.Album, str):
            items = items + search(f'track:"{_quoted(title)}" album:"{_quoted(track.Album)}"')
            level = match(track, items)[0]
        if level not in ACCEPTED:
            items = items + search(f"{work_title(track.Song)} {artist}")
    return items


def match(track, items):
    """(niveau, resultat retenu ou None) pour un morceau de 2021."""
    title, base = title_key(track.Song), base_key(track.Song)
    artist = _key(_first_artist(track.Artist))
    cover = _image_id(track.Cover) if isinstance(track.Cover, str) else None
    album = album_key(track.Album) if isinstance(track.Album, str) else None
    classical = _classical(track)
    best = {}
    for item in items:
        artists = [_key(a["name"]) for a in item.get("artists", [])]
        if not artist or not any(a and (a == artist or a in artist or artist in a) for a in artists):
            continue
        if title_key(item["name"]) != title:
            if classical and same_work(track.Song, item["name"], artist):
                best.setdefault("oeuvre", item)
            elif base and base_key(item["name"]) == base:
                best.setdefault("douteux", item)
            continue
        images = {_image_id(img.get("url")) for img in item.get("album", {}).get("images", [])}
        if cover and cover in images:
            best.setdefault("pochette", item)
        elif album and album_key(item.get("album", {}).get("name", "")) == album:
            best.setdefault("album", item)
        else:
            best.setdefault("titre", item)
    for level in ("pochette", "album", "titre", "oeuvre", "douteux"):
        if level in best:
            return level, best[level]
    return "aucun", None


def _preview_hash(url):
    found = PREVIEW_RE.match(str(url))
    return found.group(1) if found else None


def from_collect(catalog):
    """Identifiants connus par les collectes, par hash de l'extrait.

    Tous les lots : new_tracks.csv et les lots precedents archives a cote
    (new_tracks_<date>.csv). Sans eux, --rematch rechercherait leurs morceaux
    par l'API.
    """
    files = sorted(NEW_TRACKS_CSV.parent.glob("new_tracks*.csv"))
    if not files:
        return {}
    new = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    by_hash = dict(zip(new["Preview"].map(_preview_hash), new["track_id"]))
    return {row: by_hash[h] for row, h in catalog["Preview"].map(_preview_hash).items() if h in by_hash}


def run(sample=None, rematch=False, seed=0, max_requests=None):
    _quota["max"] = max_requests
    catalog = pd.read_csv(CATALOG_CSV)
    done = pd.read_csv(REVIEW_CSV) if REVIEW_CSV.exists() else pd.DataFrame(columns=["row"])
    done_rows = set(done["row"])
    records = []

    known = from_collect(catalog)
    for row, track_id in known.items():
        if rematch or row not in done_rows:
            records.append({"row": row, "track_id": track_id, "match": "playlist"})
    todo = [r for r in catalog.index if r not in known and (rematch or r not in done_rows)]
    if sample:
        rest = [r for r in catalog.index if r not in known]
        todo = [r for r in pd.Series(rest).sample(min(sample, len(rest)), random_state=seed) if r not in done_rows]
    print(f"{len(known)} identifiants par la collecte, {len(todo)} morceaux a chercher "
          f"({len(done_rows)} deja traites)", flush=True)

    skipped = 0
    try:
        for i, row in enumerate(todo, 1):
            track = next(catalog.loc[[row]].itertuples())
            try:
                items = candidates(track)
            except QuotaExceeded as exc:
                if not skipped:
                    reason = ("Limite --max atteinte" if _quota["requests"] == _quota["max"]
                              else f"Quota du mode developpement atteint ({exc})")
                    print(f"{reason} : suite avec les seules recherches en cache", flush=True)
                skipped += 1
                continue
            level, item = match(track, items)
            records.append({
                "row": row, "track_id": item["id"] if item else "", "match": level,
                "Artist": track.Artist, "Song": track.Song, "Album": track.Album,
                "spotify_artist": ", ".join(a["name"] for a in item["artists"]) if item else "",
                "spotify_title": item["name"] if item else "",
                "spotify_album": item["album"]["name"] if item else "",
                "n_results": len(items),
            })
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    finally:
        _write(done, records)
        print(f"{_quota['requests']} recherches envoyees a Spotify")
        if skipped:
            print(f"{skipped} morceaux non cherches (quota ou --max) : relancer plus tard la meme commande.")


def _write(done, records):
    if not records:
        return
    review = pd.concat([done, pd.DataFrame(records)], ignore_index=True)
    review = review.drop_duplicates("row", keep="last").sort_values("row")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    review.to_csv(REVIEW_CSV, index=False)
    ids = review[review["track_id"].fillna("").ne("")][["row", "track_id", "match"]]
    SPOTIFY_IDS_CSV.write_bytes(ids.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    counts = review["match"].value_counts()
    print("Correspondances : " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"-> {SPOTIFY_IDS_CSV} ({len(ids)} identifiants), details : {REVIEW_CSV}")
