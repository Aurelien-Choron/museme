"""Porte de validation : l'extracteur redonne-t-il les vecteurs de 2021 ?

On recalcule un echantillon de morceaux du catalogue a partir de leurs
extraits, et on compare aux valeurs stockees dans df_recommendation.csv :
- erreur relative par descripteur ;
- ecart exprime en ecarts-types du catalogue (l'unite qui compte, l'app
  centrant-reduisant les descripteurs) ;
- cosinus entre vecteur stocke et recalcule dans l'espace de l'app ;
- recouvrement des 10 recommandations.
"""
import numpy as np
import pandas as pd

from . import CATALOG_CSV, OUT_DIR
from .extract import extract_many
from .features_legacy import FEATURE_COLUMNS

MAX_MEDIAN_REL_ERR = 0.01
MAX_Z_ERR = 0.01
MIN_COSINE = 0.999
MIN_RECO_OVERLAP = 9


def similarity_matrix(catalog):
    """Espace de l'app au moment de la validation, avant centrage-reduction :
    descripteurs + indicatrices de Main_Genre. Depuis le 2026-10-09, l'app
    remplace les indicatrices par la position du genre sur le cercle
    (components/engine/functions.py:_similarity_space)."""
    df = pd.concat([catalog, catalog["Main_Genre"].str.get_dummies()], axis=1)
    data = df.drop(columns=["Unnamed: 0", "Song", "Artist", "Album", "Preview",
                            "Main_Genre", "Cover", "family_genre"])
    return data.to_numpy(dtype=float), list(data.columns)


def top10(scaled, i):
    norms = np.linalg.norm(scaled, axis=1)
    sim = scaled @ scaled[i] / (norms * norms[i])
    sim[i] = -np.inf
    return set(np.argsort(-sim, kind="stable")[:10])


def run(per_family=3, workers=4, seed=0):
    catalog = pd.read_csv(CATALOG_CSV)
    valid = catalog[catalog["rms_mean"] > 0]
    sample = valid.groupby("family_genre").sample(per_family, random_state=seed)
    print(f"Echantillon : {len(sample)} morceaux ({per_family} par famille)")

    feats = extract_many(list(sample["Preview"]), workers=workers)
    sample = sample[sample["Preview"].isin(feats)]
    recomputed = pd.DataFrame([feats[u] for u in sample["Preview"]], index=sample.index)
    stored = sample[FEATURE_COLUMNS].astype(float)

    rel = (recomputed - stored).abs() / stored.abs().clip(lower=1e-12)
    z = (recomputed - stored).abs() / catalog[FEATURE_COLUMNS].std()
    report = pd.DataFrame({
        "rel_median": rel.median(), "rel_max": rel.max(), "z_max": z.max(),
    })

    X, columns = similarity_matrix(catalog)
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std == 0] = 1.0
    scaled = (X - mean) / std
    feat_idx = [columns.index(c) for c in FEATURE_COLUMNS]
    cosines, overlaps = [], []
    for idx in sample.index:
        i = catalog.index.get_loc(idx)
        swapped = scaled.copy()
        swapped[i, feat_idx] = (recomputed.loc[idx].to_numpy() - mean[feat_idx]) / std[feat_idx]
        a, b = scaled[i], swapped[i]
        cosines.append(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
        overlaps.append(len(top10(scaled, i) & top10(swapped, i)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUT_DIR / "validation_report.csv")
    with pd.option_context("display.width", 120, "display.max_rows", 100):
        print(report.sort_values("z_max", ascending=False).head(10).map(lambda v: f"{v:.1e}"))

    checks = {
        f"erreur relative mediane < {MAX_MEDIAN_REL_ERR:.0%} (pire : {report.rel_median.max():.1e})":
            report.rel_median.max() < MAX_MEDIAN_REL_ERR,
        f"ecart < {MAX_Z_ERR} ecart-type (pire : {report.z_max.max():.1e})":
            report.z_max.max() < MAX_Z_ERR,
        f"cosinus > {MIN_COSINE} (pire : {min(cosines):.8f})":
            min(cosines) > MIN_COSINE,
        f"recommandations communes >= {MIN_RECO_OVERLAP}/10 (pire : {min(overlaps)}/10)":
            min(overlaps) >= MIN_RECO_OVERLAP,
        f"{len(sample)} morceaux recalcules sur {per_family * catalog.family_genre.nunique()}":
            len(sample) == per_family * catalog["family_genre"].nunique(),
    }
    for label, ok in checks.items():
        print(("OK   " if ok else "ECHEC") + " " + label)
    passed = all(checks.values())
    print("Porte de validation : " + ("PASSEE" if passed else "NON PASSEE"))
    return passed
