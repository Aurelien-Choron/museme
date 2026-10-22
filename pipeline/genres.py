"""Ecriture des genres dans data/df_recommendation.csv.

Seules les colonnes Main_Genre et family_genre sont modifiees (et Artist par
write_artists, pour corriger un artiste faux). Le fichier est traite comme du
texte, sans passer par pandas : les autres champs restent identiques octet
pour octet et les flottants ne sont jamais reformates.

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
# Morceaux dont l'album Deezer est faux ou mal classe : pas de genre secondaire
# (leur genre principal est corrige dans le notebook des genres).
SANS_GENRES_SECONDAIRES = {
    ("Pitbull", "Greenlight (feat. Flo Rida & LunchMoney Lewis)"),  # single classe Classical, Film Scores...
    ("Sting", "Englishman In New York"),  # trouve sur Live In Berlin (avec orchestre), classe Classical
    ("John Cage", "4'33\""),  # trouve sur Cage Against The Machine (reprise de 2010), classe Pop
}


def _fields(line):
    return next(csv.reader([line.decode("utf-8")]))


def _line(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(fields)
    return buf.getvalue().encode("utf-8")


def _cell(value):
    """Valeur -> champ CSV : vide pour une valeur manquante."""
    if pd.isna(value):
        return ""
    assert isinstance(value, str) and value.strip() and "\n" not in value, f"valeur invalide : {value!r}"
    return value


def _write_columns(values, path):
    """Ecrit les champs donnes, le reste du fichier a l'octet pres.

    values : {colonne: Series indexee par numero de ligne du catalogue (l'index
    de pd.read_csv)}, toutes sur les memes lignes. Les lignes absentes ne
    changent pas. Renvoie (catalogue relu, nombre de lignes modifiees).
    """
    index = next(iter(values.values())).index
    assert index.is_unique and all(v.index.equals(index) for v in values.values())

    raw = path.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw, "fins de ligne LF attendues"
    lines = [line + b"\n" for line in raw.split(b"\n")[:-1]]
    n_rows = len(lines) - 1
    assert index.min() >= 0 and index.max() < n_rows, f"lignes du catalogue : 0 a {n_rows - 1}"

    header = _fields(lines[0])
    columns = {header.index(c): v for c, v in values.items()}

    changed = 0
    for pos in index:
        fields = _fields(lines[pos + 1])
        assert _line(fields) == lines[pos + 1], f"ligne {pos} non reproductible"
        for i, v in columns.items():
            fields[i] = _cell(v[pos])
        new_line = _line(fields)
        changed += new_line != lines[pos + 1]
        lines[pos + 1] = new_line
    out = b"".join(lines)

    before, after = pd.read_csv(io.BytesIO(raw)), pd.read_csv(io.BytesIO(out))
    assert len(before) == len(after) == n_rows, "saut de ligne dans un champ"
    pd.testing.assert_frame_equal(before.drop(columns=list(values)),
                                  after.drop(columns=list(values)))

    path.write_bytes(out)
    return after, changed


def write_genres(main_genres, families=None, path=CATALOG_CSV):
    """Ecrit Main_Genre (et family_genre) des lignes donnees.

    main_genres : Series indexee par numero de ligne du catalogue (l'index de
    pd.read_csv) ; une valeur manquante vide le champ. families : idem, par
    defaut egale a main_genres. Les lignes absentes ne changent pas.
    Idempotent : se relance apres chaque reglage du notebook.
    """
    if families is None:
        families = main_genres
    after, changed = _write_columns(dict(zip(GENRE_COLUMNS, (main_genres, families))), path)
    n_rows = len(after)
    print(f"{changed} lignes modifiees sur {n_rows} ; "
          f"{after['Main_Genre'].nunique()} genres ; "
          f"{after['Main_Genre'].isna().sum()} morceaux sans genre")
    return after


def write_artists(artists, path=CATALOG_CSV):
    """Ecrit la colonne Artist des lignes donnees (Series indexee par numero
    de ligne), pour corriger un artiste faux. Les vecteurs et les genres ne
    changent pas ; la recherche du site et la recherche Spotify, si."""
    assert artists.notna().all(), "artiste manquant"
    after, changed = _write_columns({"Artist": artists}, path)
    print(f"{changed} artistes modifies sur {len(after)} lignes")
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
    ignore = pd.Series(list(zip(out["Artist"], out["Song"]))).isin(SANS_GENRES_SECONDAIRES)
    assert ignore.sum() == len(SANS_GENRES_SECONDAIRES), "SANS_GENRES_SECONDAIRES : morceau introuvable"
    out.loc[ignore, "Genres"] = ""
    out.to_csv(path, index=False, lineterminator="\n")
    n = out["Genres"].map(lambda s: len(s.split("|")) if s else 0)
    print(f"{path.name} : {(n >= 2).sum()} morceaux avec plusieurs genres, "
          f"{(n == 0).sum()} sans genre Deezer ; ignores : {sorted(ignored)}")
    return out
