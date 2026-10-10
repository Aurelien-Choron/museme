"""Descripteurs audio v2 : memes familles qu'en 2021, audio lu correctement.

Banc d'essai (docs/recommandation.md, partie 7) : a comparer aux 63
descripteurs de 2021 (features_legacy), sans toucher au catalogue. Les
resultats vont dans OUT_DIR, jamais dans data/.

Differences avec features_legacy :
- l'extrait est decode en mono a 22 050 Hz, valeurs dans [-1, 1] (en 2021 :
  stereo entrelacee lue a 22 050 Hz, soit un signal 4 fois trop long,
  transpose de deux octaves) ;
- mfcc{k}_mean / _var : statistiques du k-ieme coefficient seul, comme dans
  GTZAN (en 2021 : des k premiers coefficients pris ensemble) ;
- librosa 0.11 standard, sans les particularites de 0.8 ;
- tonnetz et onset : une seule separation harmonique / percussive (marge 3).

Un meme calcul donne deux jeux de colonnes :
- V1_COLUMNS : les 63 colonnes de 2021, memes noms ;
- V2_COLUMNS : chroma (12 bandes), contraste (7), tonnetz (6) et poly (2)
  decrits bande par bande au lieu d'une moyenne sur toutes les bandes.
"""
import concurrent.futures as cf
import warnings

import librosa
import numpy as np
import pandas as pd

from . import AUDIO_DIR, CATALOG_CSV, OUT_DIR
from .extract import preview_hash
from .features_legacy import FEATURE_COLUMNS, _hpss

SR = 22050

V1_COLUMNS = list(FEATURE_COLUMNS)
_SCALARS = ["rms", "spectral_centroid", "spectral_bandwidth", "rolloff",
            "zero_crossing_rate", "harmony", "onset"]
_BANDS = {"chroma_stft": 12, "spectral_contrast": 7, "tonnetz": 6, "polyfeat": 2}
V2_COLUMNS = (
    [f"{name}_{stat}" for name in _SCALARS for stat in ("mean", "var")]
    + ["tempo"]
    + [f"mfcc{k}_{stat}" for k in range(1, 21) for stat in ("mean", "var")]
    + [f"{name}_b{b}_{stat}" for name, n in _BANDS.items()
       for b in range(1, n + 1) for stat in ("mean", "var")]
)
COLUMNS = list(dict.fromkeys(V1_COLUMNS + V2_COLUMNS))


def output_csv(window=None):
    return OUT_DIR / ("features_v2.csv" if window is None else f"features_v2_w{window:g}.csv")


def load(path, seconds=None, offset=0.0):
    """Extrait decode en mono 22 050 Hz, dans [-1, 1]."""
    y, _ = librosa.load(str(path), sr=SR, mono=True, offset=offset, duration=seconds)
    return y.astype(np.float64)


def extract(y, sr=SR):
    """{colonne: valeur} pour COLUMNS."""
    out = {}

    def stats(name, values):
        out[f"{name}_mean"] = float(np.mean(values))
        out[f"{name}_var"] = float(np.var(values))

    def per_band(name, values):
        stats(name, values)
        for b, band in enumerate(values, 1):
            stats(f"{name}_b{b}", band)

    n = len(y)
    D = librosa.stft(y)
    S = np.abs(D)
    log_mel = librosa.power_to_db(librosa.feature.melspectrogram(S=S ** 2, sr=sr))
    (harm_1, _), (harm_3, perc_3) = _hpss(D, margins=(1.0, 3.0))

    per_band("chroma_stft", librosa.feature.chroma_stft(S=S ** 2, sr=sr))
    stats("rms", librosa.feature.rms(y=y))
    stats("spectral_centroid", librosa.feature.spectral_centroid(S=S, sr=sr))
    stats("spectral_bandwidth", librosa.feature.spectral_bandwidth(S=S, sr=sr))
    stats("rolloff", librosa.feature.spectral_rolloff(S=S, sr=sr))
    stats("zero_crossing_rate", librosa.feature.zero_crossing_rate(y))
    stats("harmony", librosa.istft(harm_1, length=n))

    onset_env = librosa.onset.onset_strength(S=log_mel, sr=sr)
    out["tempo"] = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])

    mfcc = librosa.feature.mfcc(S=log_mel, n_mfcc=20)
    for k in range(1, 21):
        stats(f"mfcc{k}", mfcc[k - 1])

    per_band("spectral_contrast", librosa.feature.spectral_contrast(S=S, sr=sr))
    per_band("polyfeat", librosa.feature.poly_features(S=S, sr=sr))
    per_band("tonnetz", librosa.feature.tonnetz(y=librosa.istft(harm_3, length=n), sr=sr))
    stats("onset", librosa.onset.onset_strength(y=librosa.istft(perc_3, length=n), sr=sr))
    return {col: out[col] for col in COLUMNS}


def features_for(task):
    """(row, chemin, debut, duree) -> (row, descripteurs)."""
    row, path, offset, seconds = task
    warnings.filterwarnings("ignore")
    y = load(path, seconds, offset)
    feats = extract(y)
    if not np.isfinite(list(feats.values())).all():
        raise ValueError("descripteurs non finis")
    return row, {"duree": len(y) / SR, **feats}


def tasks(out_csv, window=None, n_rows=None, seed=0):
    """[(row, chemin, debut, duree)] des extraits en cache, hors ceux deja
    ecrits dans out_csv (reprise).

    window : duree analysee en secondes, a une position tiree au hasard dans
    l'extrait (courbe de duree) ; None = extrait entier. n_rows : nombre de
    morceaux tires au hasard. Seed fixe : memes morceaux et memes positions
    pour features_v2 et embeddings.
    """
    catalog = pd.read_csv(CATALOG_CSV)
    rng = np.random.default_rng(seed)
    rows = catalog.index if n_rows is None else np.sort(rng.choice(catalog.index, n_rows, replace=False))
    found = []
    for row in rows:
        url = catalog["Preview"][row]
        path = AUDIO_DIR / f"{preview_hash(url)}.mp3" if isinstance(url, str) else None
        offset = 0.0
        if path is not None and path.exists():
            if window:
                offset = rng.uniform(0, max(librosa.get_duration(path=str(path)) - window, 0))
            found.append((int(row), str(path), offset, window))
    done = set(pd.read_csv(out_csv, usecols=["row"])["row"]) if out_csv.exists() else set()
    todo = [t for t in found if t[0] not in done]
    print(f"{len(rows)} morceaux, {len(found)} extraits en cache, {len(todo)} a calculer -> {out_csv}", flush=True)
    return todo


def run(workers=4, window=None, n_rows=None, seed=0):
    """Descripteurs v2 des morceaux dont l'extrait est en cache, avec reprise."""
    out_csv = output_csv(window)
    todo = tasks(out_csv, window, n_rows, seed)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    with cf.ProcessPoolExecutor(workers) as pool:
        futures = {pool.submit(features_for, t): t[0] for t in todo}
        for i, fut in enumerate(cf.as_completed(futures), 1):
            try:
                row, feats = fut.result()
            except Exception as exc:
                failed += 1
                print(f"  ligne {futures[fut]} : ECHEC {type(exc).__name__}: {exc}", flush=True)
                continue
            pd.DataFrame([{"row": row, **feats}]).to_csv(
                out_csv, mode="a", header=not out_csv.exists(), index=False)
            if i % 200 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    print(f"termine : {len(todo) - failed} calcules, {failed} en echec", flush=True)
