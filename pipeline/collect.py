"""Collecte des morceaux des playlists listees dans pipeline/playlists.csv.

Un meme morceau ne doit avoir qu'un vecteur : on ecarte ceux deja presents
au catalogue (meme extrait, ou meme couple artiste / titre normalise) et les
doublons entre playlists (meme id Spotify, ou meme artiste / titre sous un
autre id : single et version album, par exemple).

Le lot precedent (new_tracks.csv) est archive en new_tracks_<date>.csv avant
d'etre remplace : spotify_ids y lit les identifiants des lots deja ajoutes.
Les titres deja presents au catalogue sous un autre artiste (P!nk / Pink,
reprises...) ne sont pas ecartes : ils vont dans OUT_DIR/doublons_possibles.csv,
a relire avant merge.
"""
import re
import time
import unicodedata

import pandas as pd
import requests

from . import CATALOG_CSV, OUT_DIR, PLAYLISTS_CSV
from . import spotify_embed
from .extract import NEW_TRACKS_CSV, preview_hash


def normalize(text):
    """'Señorita (feat. X) - Remastered 2011' -> 'senorita' ; '湖' -> '湖'.

    Les ecritures non latines sont gardees : jusqu'au 2026-10-12, [^0-9a-z]
    reduisait 129 titres du catalogue (japonais, chinois...) a une chaine
    vide, et tous les titres d'un tel artiste avaient la meme cle.
    """
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)
    text = text.split(" - ")[0]
    return " ".join(re.sub(r"[\W_]+", " ", text).split())


def run():
    playlists = pd.read_csv(PLAYLISTS_CSV)
    catalog = pd.read_csv(CATALOG_CSV)
    known_previews = set(catalog["Preview"].map(preview_hash))
    known_keys = set(zip(catalog["Artist"].map(normalize), catalog["Song"].map(normalize)))

    candidates = {}
    for pl in playlists.itertuples():
        name, tracks = spotify_embed.playlist(spotify_embed.parse_id(pl.url))
        print(f"{pl.label} ({name}) : {len(tracks)} morceaux")
        for t in tracks:
            candidates.setdefault(t["track_id"], {**t, "playlist": pl.label})

    stats = {"sans extrait": 0, "deja au catalogue": 0, "doublon artiste/titre": 0,
             "page embed illisible": 0}
    rows, new_keys = [], set()
    for i, (track_id, cand) in enumerate(candidates.items(), 1):
        if not cand["preview"]:
            stats["sans extrait"] += 1
            continue
        if preview_hash(cand["preview"]) in known_previews:
            stats["deja au catalogue"] += 1
            continue
        try:
            info = spotify_embed.track(track_id)
        except (ValueError, requests.RequestException) as exc:
            print(f"  {track_id} ecarte : {exc}")
            stats["page embed illisible"] += 1
            continue
        artist = info["artists"][0] if info["artists"] else ""
        key = (normalize(artist), normalize(info["title"]))
        if key in known_keys:
            stats["deja au catalogue"] += 1
            continue
        if key in new_keys:
            stats["doublon artiste/titre"] += 1
            continue
        new_keys.add(key)
        rows.append({
            "track_id": track_id,
            "Artist": artist,
            "Album": "",
            "Song": info["title"],
            "Preview": info["preview"] or cand["preview"],
            "Cover": info["cover"] or "",
            "playlist": cand["playlist"],
            "release_date": info["release_date"],
        })
        if i % 50 == 0:
            print(f"  {i}/{len(candidates)} morceaux examines", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if NEW_TRACKS_CSV.exists():
        stamp = time.strftime("%Y-%m-%d", time.localtime(NEW_TRACKS_CSV.stat().st_mtime))
        NEW_TRACKS_CSV.replace(NEW_TRACKS_CSV.with_name(f"new_tracks_{stamp}.csv"))
    new = pd.DataFrame(rows)
    new.to_csv(NEW_TRACKS_CSV, index=False)
    print(f"{len(candidates)} morceaux distincts, {len(rows)} retenus -> {NEW_TRACKS_CSV}")
    for label, count in stats.items():
        print(f"  ecartes, {label} : {count}")

    # Meme titre qu'un morceau du catalogue, artiste ecrit autrement.
    if len(new):
        known = catalog.assign(title=catalog["Song"].map(normalize))[["title", "Artist", "Song"]]
        twins = (new.assign(title=new["Song"].map(normalize))
                 .merge(known, on="title", suffixes=("", "_catalogue")))
        twins.to_csv(OUT_DIR / "doublons_possibles.csv", index=False)
        print(f"  doublons possibles (meme titre, autre artiste) : {twins['track_id'].nunique()} "
              f"-> {OUT_DIR / 'doublons_possibles.csv'}")
