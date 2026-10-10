"""Banc d'essai : vecteurs d'un modele audio pre-entraine (reference V3).

CLAP de LAION (laion/larger_clap_general, licence Apache 2.0 ; entraine sur
musique, parole et sons), via transformers, sur CPU. Local uniquement : torch
et transformers ne sont pas deployes. Sert de reference : jusqu'ou peut aller
l'audio seul ?

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

from . import OUT_DIR
from .features_v2 import tasks

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
    """Vecteurs CLAP des morceaux dont l'extrait est en cache, avec reprise."""
    warnings.filterwarnings("ignore")
    out_csv = output_csv(window)
    todo = tasks(out_csv, window, n_rows, seed)
    if not todo:
        return
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
