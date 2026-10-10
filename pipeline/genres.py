"""Ecriture des genres dans data/df_recommendation.csv.

Seules les colonnes Main_Genre et family_genre sont modifiees. Le fichier est
traite comme du texte, sans passer par pandas : les autres champs restent
identiques octet pour octet et les flottants ne sont jamais reformates.

Depuis le 2026-10-08, les genres sont ceux de Deezer (genre de l'album),
choisis dans notebooks/classifieur_genre.ipynb, pour les morceaux de 2021
comme pour les morceaux ajoutes. Deezer n'a qu'un niveau de genre :
family_genre recoit par defaut la meme valeur que Main_Genre. Les etiquettes
de 2021 (77 genres « genre seeds » Spotify) sont gardees dans
data/genres_2021.csv.

L'app place Main_Genre sur le cercle des genres dans l'espace de similarite
(components/engine/functions.py:_similarity_space, GENRE_CIRCLE) : changer le
vocabulaire change les recommandations de tout le catalogue, et un genre
absent de GENRE_CIRCLE est traite comme Pop (au centre).
"""
import csv
import io

import pandas as pd

from . import CATALOG_CSV, REPO_DIR

GENRE_COLUMNS = ["Main_Genre", "family_genre"]
GENRES_2021_CSV = REPO_DIR / "data" / "genres_2021.csv"
GENRE_LISTS_CSV = REPO_DIR / "data" / "genres_deezer.csv"

# Sous-genres Deezer -> genre parent parmi les 17 genres de l'app
# (components/engine/functions.py:GENRES). Les genres sans parent
# (Films/Games, Kids, Musicals, Spirituality & Religion) sont ignores.
DEEZER_PARENT = {
    "Indie Rock": "Alternative", "Indie Rock/Rock pop": "Alternative", "Indie Pop": "Alternative",
    "Indie Pop/Folk": "Folk", "Singer & Songwriter": "Folk",
    "Hard Rock": "Rock", "Rock & Roll/Rockabilly": "Rock",
    "Techno/House": "Electro", "Trance": "Electro", "Dubstep": "Electro",
    "Chill Out/Trip-Hop/Lounge": "Electro", "Electro Pop/Electro Rock": "Electro",
    "Disco": "Dance",
    "Dancehall/Ragga": "Reggae", "Ska": "Reggae", "Dub": "Reggae",
    "Soul & Funk": "R&B", "Contemporary Soul": "R&B", "Contemporary R&B": "R&B",
    "International Pop": "Pop",
    "Blues": "Jazz", "Chicago Blues": "Jazz",
    "Film Scores": "Classical", "Opera": "Classical",
}


def _fields(line):
    return next(csv.reader([line.decode("utf-8")]))


def _line(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(fields)
    return buf.getvalue().encode("utf-8")


def _cell(value):
    """Genre -> champ CSV : vide pour un genre manquant."""
    if pd.isna(value):
        return ""
    assert isinstance(value, str) and value.strip() and "\n" not in value, f"genre invalide : {value!r}"
    return value


def write_genres(main_genres, families=None, path=CATALOG_CSV):
    """Ecrit Main_Genre (et family_genre) des lignes donnees.

    main_genres : Series indexee par numero de ligne du catalogue (l'index de
    pd.read_csv) ; une valeur manquante vide le champ. families : idem, par
    defaut egale a main_genres. Les lignes absentes ne changent pas.
    Idempotent : se relance apres chaque reglage du notebook.
    """
    if families is None:
        families = main_genres
    assert main_genres.index.is_unique and main_genres.index.equals(families.index)

    raw = path.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw, "fins de ligne LF attendues"
    lines = [line + b"\n" for line in raw.split(b"\n")[:-1]]
    n_rows = len(lines) - 1
    assert main_genres.index.min() >= 0 and main_genres.index.max() < n_rows, \
        f"lignes du catalogue : 0 a {n_rows - 1}"

    header = _fields(lines[0])
    i_genre, i_family = (header.index(c) for c in GENRE_COLUMNS)

    changed = 0
    for pos in main_genres.index:
        fields = _fields(lines[pos + 1])
        assert _line(fields) == lines[pos + 1], f"ligne {pos} non reproductible"
        fields[i_genre], fields[i_family] = _cell(main_genres[pos]), _cell(families[pos])
        new_line = _line(fields)
        changed += new_line != lines[pos + 1]
        lines[pos + 1] = new_line
    out = b"".join(lines)

    before, after = pd.read_csv(io.BytesIO(raw)), pd.read_csv(io.BytesIO(out))
    assert len(before) == len(after) == n_rows, "saut de ligne dans un champ"
    pd.testing.assert_frame_equal(before.drop(columns=GENRE_COLUMNS),
                                  after.drop(columns=GENRE_COLUMNS))

    path.write_bytes(out)
    print(f"{changed} lignes modifiees sur {n_rows} ; "
          f"{after['Main_Genre'].nunique()} genres ; "
          f"{after['Main_Genre'].isna().sum()} morceaux sans genre")
    return after


def write_genre_lists(path=GENRE_LISTS_CSV):
    """Ecrit data/genres_deezer.csv : pour chaque ligne du catalogue, les
    genres Deezer de l'album ramenes aux 17 genres de l'app, separes par « | ».

    L'app s'en sert comme genres secondaires, en plus de Main_Genre. Lit la
    sortie de l'etape deezer, sans aucune requete : se relance apres deezer
    ou apres un ajout au catalogue (les lignes manquantes n'ont pas de genre
    secondaire).
    """
    from components.engine.functions import GENRES
    from .deezer import DEEZER_GENRES_CSV

    catalog = pd.read_csv(CATALOG_CSV)
    tags = pd.read_csv(DEEZER_GENRES_CSV, keep_default_na=False)
    assert tags["row"].tolist() == list(range(len(catalog))) and tags["Song"].equals(catalog["Song"]), \
        "deezer_genres.csv ne correspond plus au catalogue : relancer l'etape deezer"

    ignored = set()

    def to_app(genres):
        out = []
        for genre in genres.split("|") if genres else []:
            genre = DEEZER_PARENT.get(genre, genre)
            if genre not in GENRES:
                ignored.add(genre)
            elif genre not in out:
                out.append(genre)
        return "|".join(out)

    out = pd.DataFrame({"row": tags["row"], "Artist": catalog["Artist"], "Song": catalog["Song"],
                        "Genres": tags["deezer_genres"].map(to_app)})
    out.to_csv(path, index=False, lineterminator="\n")
    n = out["Genres"].map(lambda s: len(s.split("|")) if s else 0)
    print(f"{path.name} : {(n >= 2).sum()} morceaux avec plusieurs genres, "
          f"{(n == 0).sum()} sans genre Deezer ; ignores : {sorted(ignored)}")
    return out
