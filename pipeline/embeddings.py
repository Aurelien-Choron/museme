"""Vecteurs audio de l'app : modele pre-entraine CLAP (V3 du banc d'essai).

CLAP de LAION (laion/larger_clap_general, licence Apache 2.0 ; entraine sur
musique, parole et sons), via transformers, sur CPU. Local uniquement : torch
et transformers ne sont pas deployes. L'app ne lit que les vecteurs deja
calcules, dans DATA_NPY : retenu le 2026-10-10 apres le banc d'essai et
l'ecoute a l'aveugle (docs/recommandation.md, partie 7).

Sur tout le catalogue (ni --window ni --rows), run() calcule les morceaux qui
n'ont pas encore de vecteur, puis ecrit DATA_NPY : a lancer apres merge. Les
fenetres (--window, --rows) restent un banc d'essai, ecrit dans OUT_DIR
seulement.

Pas laion/larger_clap_music : ses couches de projection publiees sur Hugging
Face ne sont pas entrainees (biais nuls), le 2026-10-09 comme dans le .bin
d'origine. Tous les textes y ont le meme vecteur et le classement zero-shot
tombe au hasard.

Le modele lit 10 s d'audio a 48 kHz. L'extrait est decoupe en tranches de
10 s (une tranche de moins de 5 s est ecartee, sauf si c'est la seule) ; le
vecteur du morceau est la moyenne des vecteurs des tranches, ramenee a une
norme de 1.
"""
import warnings

import librosa
import numpy as np
import pandas as pd

from . import AUDIO_DIR, CATALOG_CSV, OUT_DIR, REPO_DIR
from .features_v2 import tasks

# Lu par l'app (components/engine/functions.py, CLAP_NPY) : float32, une ligne
# par ligne de CATALOG_CSV, dans le meme ordre.
DATA_NPY = REPO_DIR / "data" / "embeddings_clap.npy"
MODEL = "laion/larger_clap_general"
SR = 48000
CHUNK_SECONDS = 10
MIN_CHUNK_SECONDS = 5


def output_csv(window=None):
    return OUT_DIR / ("embeddings_clap.csv" if window is None else f"embeddings_clap_w{window:g}.csv")


def load_model():
    from transformers import ClapModel, ClapProcessor
    model = ClapModel.from_pretrained(MODEL).eval()
    return model, ClapProcessor.from_pretrained(MODEL)


def embed(model, processor, y):
    """Vecteur de norme 1 d'un signal mono a 48 kHz."""
    import torch

    step = CHUNK_SECONDS * SR
    chunks = [y[i:i + step] for i in range(0, len(y), step)]
    chunks = [c for c in chunks if len(c) >= MIN_CHUNK_SECONDS * SR] or [y]
    inputs = processor(audio=chunks, sampling_rate=SR, return_tensors="pt")
    with torch.no_grad():
        vectors = torch.nn.functional.normalize(model.get_audio_features(**inputs), dim=-1).mean(0)
    return (vectors / vectors.norm()).numpy()


def run(window=None, n_rows=None, seed=0):
    """Vecteurs CLAP des morceaux dont l'extrait est en cache, avec reprise.

    Sur tout le catalogue, ecrit ensuite DATA_NPY (publish)."""
    warnings.filterwarnings("ignore")
    out_csv = output_csv(window)
    todo = tasks(out_csv, window, n_rows, seed)
    if todo:
        model, processor = load_model()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for i, (row, path, offset, seconds) in enumerate(todo, 1):
            y, _ = librosa.load(path, sr=SR, mono=True, offset=offset, duration=seconds)
            vector = embed(model, processor, y)
            line = pd.DataFrame([[row, len(y) / SR, *vector]],
                                columns=["row", "duree"] + [f"clap{k}" for k in range(len(vector))])
            line.to_csv(out_csv, mode="a", header=not out_csv.exists(), index=False)
            if i % 200 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
        print(f"termine : {len(todo)} morceaux", flush=True)
    if window is None and n_rows is None:
        publish()


def publish():
    """Ecrit DATA_NPY a partir de OUT_DIR/embeddings_clap.csv : un vecteur par
    ligne du catalogue, dans l'ordre. Refuse s'il en manque un : l'app
    associe les vecteurs aux morceaux par leur position."""
    catalog = pd.read_csv(CATALOG_CSV)
    vectors = pd.read_csv(output_csv()).drop_duplicates("row", keep="last").set_index("row")
    missing = catalog.index.difference(vectors.index)
    if len(missing):
        raise SystemExit(f"{len(missing)} morceaux sans vecteur CLAP (lignes {list(missing[:10])}) : "
                         f"extrait absent de {AUDIO_DIR} ? {DATA_NPY.name} n'est pas ecrit.")
    columns = [c for c in vectors.columns if c.startswith("clap")]
    matrix = vectors.loc[catalog.index, columns].to_numpy(dtype=np.float32)
    np.save(DATA_NPY, matrix)
    print(f"{DATA_NPY} : {matrix.shape[0]} morceaux x {matrix.shape[1]} dimensions")

    from components.engine import functions
    functions.load_catalog.cache_clear()
    functions._similarity_space.cache_clear()
    df_rec, space = functions._similarity_space()
    last = len(catalog) - 1
    recos = functions.recommandation_cosine(last)
    print(f"Espace de similarite : {space.shape} ; {len(recos)} recommandations pour "
          f"{df_rec['Song'][last]!r} : {', '.join(recos['Artist'][:3])}...")
