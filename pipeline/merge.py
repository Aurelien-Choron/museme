"""Ajout des nouveaux morceaux a data/df_recommendation.csv.

Le fichier n'est pas reecrit : les lignes sont ajoutees a la fin, au format
d'origine (fins de ligne LF, flottants en repr a 17 chiffres), de sorte que
les 3 815 lignes existantes restent identiques octet pour octet.
Le schema ne change pas : _similarity_space (components/engine/functions.py)
centre-reduit toutes les colonnes qu'il ne retire pas, une colonne de plus
casserait l'app. La provenance (id Spotify, playlist) reste dans les sorties
du pipeline.

Main_Genre et family_genre sont laisses vides : le classifieur de genre est a
refaire (le modele entraine sur le catalogue de 2021 se trompait sur les tubes
recents). L'app s'en accommode : un genre vide donne des indicatrices nulles
dans l'espace de similarite, et le genre n'est affiche nulle part.
"""
import csv
import io
import math

import pandas as pd

from . import CATALOG_CSV
from .collect import normalize
from .extract import NEW_FEATURES_CSV, NEW_TRACKS_CSV


def _cell(value):
    if isinstance(value, float):
        return "" if math.isnan(value) else repr(value)
    return value


def run(dry_run=False):
    catalog = pd.read_csv(CATALOG_CSV)
    columns = list(catalog.columns)
    feats = pd.read_csv(NEW_FEATURES_CSV).drop_duplicates("Preview")
    new = pd.read_csv(NEW_TRACKS_CSV).merge(feats, on="Preview", how="inner")
    new["Main_Genre"] = float("nan")
    new["family_genre"] = float("nan")

    known = set(zip(catalog["Artist"].map(normalize), catalog["Song"].map(normalize)))
    keys = list(zip(new["Artist"].map(normalize), new["Song"].map(normalize)))
    keep = [k not in known for k in keys]
    if not all(keep):
        print(f"{len(keep) - sum(keep)} morceaux deja au catalogue, ecartes")
    new = new[keep].reset_index(drop=True)
    if new.empty:
        print("Rien a ajouter.")
        return

    start = int(catalog["Unnamed: 0"].max()) + 1
    new["Unnamed: 0"] = range(start, start + len(new))
    rows = new[columns]

    numeric = rows.drop(columns=["Unnamed: 0", "Artist", "Album", "Song", "Main_Genre",
                                 "Preview", "family_genre", "Cover"])
    assert numeric.notna().all().all(), "descripteurs manquants"

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for row in rows.itertuples(index=False):
        writer.writerow([_cell(v.item() if hasattr(v, "item") else v) for v in row])

    print(f"{len(rows)} morceaux a ajouter (index {start} a {start + len(rows) - 1}), "
          f"catalogue : {len(catalog)} -> {len(catalog) + len(rows)}")
    if dry_run:
        print("--dry-run : rien d'ecrit")
        return

    raw = CATALOG_CSV.read_bytes()
    with open(CATALOG_CSV, "a", encoding="utf-8", newline="") as f:
        if not raw.endswith(b"\n"):
            f.write("\n")
        f.write(buf.getvalue())

    merged = pd.read_csv(CATALOG_CSV)
    assert list(merged.columns) == columns and len(merged) == len(catalog) + len(rows)
    assert CATALOG_CSV.read_bytes().startswith(raw), "lignes existantes modifiees"

    from components.engine import functions
    functions.load_catalog.cache_clear()
    functions._similarity_space.cache_clear()
    df_rec, data_scaled = functions._similarity_space()
    sample = rows["Song"].iloc[0]
    recos = functions.recommandation_cosine(sample)
    print(f"Espace de similarite : {data_scaled.shape} ; "
          f"{len(recos)} recommandations pour {sample!r}")
