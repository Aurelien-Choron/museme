"""Telechargement des extraits et calcul des descripteurs, en parallele.

Les MP3 sont gardes dans AUDIO_DIR (hors OneDrive), nommes par le hachage de
leur URL p.scdn.co : un meme extrait n'est telecharge et calcule qu'une fois.
"""
import concurrent.futures as cf
import time
import warnings

import numpy as np
import pandas as pd
import requests

from . import AUDIO_DIR, OUT_DIR
from . import features_legacy

NEW_TRACKS_CSV = OUT_DIR / "new_tracks.csv"
NEW_FEATURES_CSV = OUT_DIR / "new_features.csv"


def preview_hash(url):
    """https://p.scdn.co/mp3-preview/<hash>?cid=... -> <hash>"""
    return url.split("/mp3-preview/")[1].split("?")[0]


def download(url, retries=4):
    path = AUDIO_DIR / f"{preview_hash(url)}.mp3"
    if path.exists():
        return path
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            tmp = path.with_suffix(".part")
            tmp.write_bytes(resp.content)
            tmp.replace(path)
            return path
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def features_for(url):
    """Descripteurs d'un extrait. Leve une erreur si l'audio est inexploitable."""
    warnings.filterwarnings("ignore")
    feats = features_legacy.extract(features_legacy.load_legacy(download(url)))
    values = np.array(list(feats.values()))
    if not np.isfinite(values).all() or feats["rms_mean"] == 0:
        raise ValueError("audio silencieux ou descripteurs non finis")
    return feats


def extract_many(urls, workers=4, on_result=None):
    """{url: descripteurs} pour chaque URL ; les echecs sont signales, pas leves."""
    results = {}
    with cf.ProcessPoolExecutor(workers) as pool:
        futures = {pool.submit(features_for, url): url for url in urls}
        for i, fut in enumerate(cf.as_completed(futures), 1):
            url = futures[fut]
            try:
                results[url] = fut.result()
                status = "ok"
            except Exception as exc:
                status = f"ECHEC {type(exc).__name__}: {exc}"
            print(f"[{i}/{len(futures)}] {preview_hash(url)} {status}", flush=True)
            if on_result and url in results:
                on_result(url, results[url])
    return results


def run(workers=4):
    """Calcule les descripteurs des morceaux collectes, avec reprise."""
    tracks = pd.read_csv(NEW_TRACKS_CSV)
    done = pd.read_csv(NEW_FEATURES_CSV) if NEW_FEATURES_CSV.exists() else None
    todo = tracks if done is None else tracks[~tracks["Preview"].isin(done["Preview"])]
    print(f"{len(tracks)} morceaux collectes, {len(todo)} a calculer")

    def append(url, feats):
        row = pd.DataFrame([{"Preview": url, **feats}])
        header = not NEW_FEATURES_CSV.exists()
        row.to_csv(NEW_FEATURES_CSV, mode="a", header=header, index=False)

    extract_many(list(todo["Preview"]), workers=workers, on_result=append)
    done = pd.read_csv(NEW_FEATURES_CSV)
    missing = tracks[~tracks["Preview"].isin(done["Preview"])]
    print(f"{len(done)} morceaux calcules, {len(missing)} en echec (ecartes)")
