"""Donnees du site (web/data/) : le catalogue et les 50 voisins de chaque morceau.

Le site est statique et ne calcule rien : depuis le 2026-10-11, les
recommandations sont calculees ici, une fois pour tout le catalogue, par le
moteur de components/engine/functions.py (_similarity_space). Chaque liste
est ensuite comparee a celle de recommandation_cosine, la fonction que
l'app Dash appelait a chaque clic : au moindre ecart, rien n'est ecrit.

A relancer apres tout changement du catalogue, des vecteurs CLAP ou des
reglages du moteur. embeddings.publish() le fait apres un ajout.

Trois fichiers JSON, indexes par le numero de ligne du catalogue :
- catalog.json : {"genres": [...], "tracks": [[titre, artiste, album,
  genre, pochette, extrait], ...]}. genre est un indice dans genres (null
  pour les 27 morceaux sans genre), album est null pour les morceaux de 2026.
  pochette et extrait sont les identifiants des URL Spotify, sans le
  prefixe : le site choisit la taille de la pochette (64 ou 640 px).
- neighbors.json : [[10 numeros de ligne], ...], du plus proche au moins
  proche : les recommandations affichees, chargees a la premiere visite.
- queue.json : [[voisins 11 a 50], ...] : la suite de la file de lecture
  (depuis le 2026-10-12, la lecture enchaine jusqu'au 50e voisin), chargee
  seulement au premier morceau joue.
- spotify.json : [identifiant Spotify ou null, ...], pour la lecture des
  morceaux entiers (web/spotify.js, sessions invitees seulement). Ecrit si
  data/spotify_ids.csv existe (python -m pipeline spotify-ids), avec les
  seules correspondances acceptees (spotify_ids.ACCEPTED).
"""
import json
import re

import numpy as np
import pandas as pd

from . import REPO_DIR

WEB_DATA_DIR = REPO_DIR / "web" / "data"
SPOTIFY_IDS_CSV = REPO_DIR / "data" / "spotify_ids.csv"
N_NEIGHBORS = 10  # affiches
N_QUEUE = 50      # enchaines a la lecture
COVER_PREFIX = "https://i.scdn.co/image/"
PREVIEW_RE = re.compile(r"^https://p\.scdn\.co/mp3-preview/([0-9a-f]{40})(\?.*)?$")


def neighbors(space):
    """Les N_QUEUE plus proches voisins de chaque ligne, au cosinus.

    Toute la matrice d'un coup (4 724 x 4 724, 180 Mo en local) au lieu
    d'une ligne par morceau : 1 s au lieu de 95.
    """
    unit = space / np.linalg.norm(space, axis=1, keepdims=True)
    similarity = unit @ unit.T
    np.fill_diagonal(similarity, -np.inf)
    return np.argsort(-similarity, axis=1, kind="stable")[:, :N_QUEUE]


def _text(value):
    return None if pd.isna(value) else str(value)


def _cover_id(url):
    if pd.isna(url):
        return None
    if not url.startswith(COVER_PREFIX):
        raise SystemExit(f"Pochette hors du CDN Spotify : {url}")
    return url[len(COVER_PREFIX):]


def _preview_id(url):
    match = PREVIEW_RE.match(url)
    if not match:
        raise SystemExit(f"Extrait hors du CDN Spotify : {url}")
    return match.group(1)


def run(check=True):
    from components.engine import functions
    # Apres un ajout au catalogue ou de nouveaux vecteurs dans le meme processus.
    functions.load_catalog.cache_clear()
    functions._similarity_space.cache_clear()
    df_rec, space = functions._similarity_space()
    top = neighbors(space)

    if check:
        print(f"Controle contre recommandation_cosine, {len(df_rec)} morceaux...", flush=True)
        for row in range(len(df_rec)):
            expected = functions.recommandation_cosine(row, n=N_QUEUE).index.tolist()
            if top[row].tolist() != expected:
                raise SystemExit(f"Ligne {row} ({df_rec['Song'][row]!r}) : {top[row].tolist()} "
                                 f"au lieu de {expected}. Rien n'est ecrit.")
            if row % 1000 == 0:
                print(f"  {row}/{len(df_rec)}", flush=True)
        print("  identiques pour tous les morceaux", flush=True)

    genres = functions.GENRES
    tracks = [
        [r.Song, r.Artist, _text(r.Album),
         genres.index(r.Main_Genre) if r.Main_Genre in genres else None,
         _cover_id(r.Cover), _preview_id(r.Preview)]
        for r in df_rec.itertuples()
    ]
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "catalog.json": {"genres": genres, "tracks": tracks},
        "neighbors.json": top[:, :N_NEIGHBORS].tolist(),
        "queue.json": top[:, N_NEIGHBORS:].tolist(),
    }
    if SPOTIFY_IDS_CSV.exists():
        from .spotify_ids import ACCEPTED
        found = pd.read_csv(SPOTIFY_IDS_CSV)
        found = found[found["match"].isin(ACCEPTED)]
        ids = [None] * len(df_rec)
        for r in found.itertuples():
            ids[r.row] = r.track_id
        files["spotify.json"] = ids
        print(f"Identifiants Spotify : {len(found)} / {len(df_rec)} morceaux")
    for name, content in files.items():
        path = WEB_DATA_DIR / name
        path.write_bytes(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        print(f"{path} : {path.stat().st_size / 1024:.0f} Ko")
