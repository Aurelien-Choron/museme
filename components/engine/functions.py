import functools
import os

import numpy as np
import pandas as pd
from sklearn import preprocessing
from sklearn.metrics.pairwise import cosine_similarity

# Chemins absolus : le moteur est appele par le pipeline et les notebooks,
# depuis des repertoires courants differents.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
RECOMMENDATION_CSV = os.path.join(DATA_DIR, "df_recommendation.csv")
# Genres secondaires (genres Deezer de l'album), ecrits par
# python -m pipeline genre-lists.
GENRE_LISTS_CSV = os.path.join(DATA_DIR, "genres_deezer.csv")
# Vecteurs audio CLAP (laion/larger_clap_general, 512 dimensions), une ligne
# par ligne de RECOMMENDATION_CSV, ecrits par python -m pipeline embeddings.
# Ils remplacent les 63 descripteurs du CSV depuis le 2026-10-10.
CLAP_NPY = os.path.join(DATA_DIR, "embeddings_clap.npy")

# Cercle des genres (notebooks/classifieur_genre.ipynb) : deux genres voisins
# sont proches. Pop, proche de tous, a son propre axe : au centre du cercle,
# il n'apportait rien et les morceaux Pop etaient recommandes sur l'audio seul.
GENRE_CIRCLE = ["Asian Music", "R&B", "African Music", "Reggae", "Rap/Hip Hop",
                "Latin Music", "Brazilian Music", "Jazz", "Classical", "Folk",
                "Country", "Alternative", "Rock", "Metal", "Electro", "Dance"]
GENRES = GENRE_CIRCLE + ["Pop"]
# Similarite entre deux genres : 1 pour le meme genre, NEIGHBOR_SIMILARITY
# entre voisins du cercle, POP_SIMILARITY entre Pop et chacun des autres,
# 0 sinon. Pour rester une similarite valide : NEIGHBOR_SIMILARITY <= 0,5 et
# POP_SIMILARITY <= racine((1 + 2 * NEIGHBOR_SIMILARITY) / 16).
NEIGHBOR_SIMILARITY = 0.5
POP_SIMILARITY = 0.3
# Poids d'un genre secondaire face a Main_Genre (qui pese 1).
SECONDARY_GENRE_SHARE = 0.5
# Poids du genre face aux 512 dimensions CLAP centrees-reduites : 0 = audio
# seul (46 % des recommandations dans le genre du morceau), 4 = 54 %,
# 12 = 90 %. Avec les 63 descripteurs de 2021, le poids etait de 3.
GENRE_WEIGHT = 4


@functools.lru_cache(maxsize=1)
def load_catalog():
  """Catalogue des morceaux, lu une seule fois par processus.

  Le CSV pese 5 Mo et etait relu a chaque callback.
  """
  return pd.read_csv(RECOMMENDATION_CSV, sep=',')


def _genre_similarity_root():
  """Racine L de la similarite entre genres S (L @ L.T = S).

  Un morceau aux poids de genres m devient m @ L : le produit scalaire de
  deux morceaux vaut alors m_a . S . m_b.
  """
  n = len(GENRE_CIRCLE)
  similarity = np.eye(n + 1)
  for k in range(n):
      similarity[k, (k + 1) % n] = similarity[(k + 1) % n, k] = NEIGHBOR_SIMILARITY
  similarity[n, :n] = similarity[:n, n] = POP_SIMILARITY
  values, vectors = np.linalg.eigh(similarity)
  return vectors @ np.diag(np.sqrt(np.clip(values, 0, None))) @ vectors.T


def _genre_weights(df_rec):
  """Une ligne par morceau : poids des 17 genres, de norme 1.

  Main_Genre pese 1, chaque genre secondaire SECONDARY_GENRE_SHARE. Un
  morceau sans genre a une ligne nulle : le genre ne joue pas pour lui.
  """
  secondary = pd.read_csv(GENRE_LISTS_CSV, keep_default_na=False).set_index("row")["Genres"]
  secondary = secondary.reindex(df_rec.index, fill_value="")
  weights = np.zeros((len(df_rec), len(GENRES)))
  for i, (main, others) in enumerate(zip(df_rec["Main_Genre"], secondary)):
      for genre in others.split("|") if others else []:
          if genre in GENRES:
              weights[i, GENRES.index(genre)] = SECONDARY_GENRE_SHARE
      if main in GENRES:
          weights[i, GENRES.index(main)] = 1
  norms = np.linalg.norm(weights, axis=1, keepdims=True)
  return np.divide(weights, norms, out=np.zeros_like(weights), where=norms > 0)


@functools.lru_cache(maxsize=1)
def _similarity_space():
  """Vecteurs CLAP centres-reduits + genres, et catalogue aligne.

  Ne depend pas du morceau demande : calcule une fois puis reutilise.
  Le genre n'est plus en indicatrices : centrees-reduites, elles pesaient
  jusqu'a 11 ecarts-types (genres rares) et agissaient comme un filtre.
  Les 63 descripteurs du CSV ne servent plus ici (banc d'essai et ecoute a
  l'aveugle du 2026-10-10, docs/recommandation.md) ; ils restent dans le CSV
  pour pipeline/validate_legacy.py.
  """
  df_rec = load_catalog().copy()
  df_rec.drop(columns='Unnamed: 0', inplace=True)
  # float64 avant le centrage-reduction : memes calculs que les mesures.
  clap = np.load(CLAP_NPY).astype(np.float64)
  if len(clap) != len(df_rec):
      raise ValueError(f"{CLAP_NPY} : {len(clap)} vecteurs pour {len(df_rec)} morceaux. "
                       "Relancer python -m pipeline embeddings apres un ajout au catalogue.")
  audio = preprocessing.scale(clap)
  genres = GENRE_WEIGHT * _genre_weights(df_rec) @ _genre_similarity_root()
  return df_rec, np.hstack([audio, genres])


def recommandation_cosine(track_row):
  """track_row : numero de ligne du catalogue, et non le titre : 54 titres
  existent chez plusieurs artistes (Baby : Brandy et Justin Bieber)."""
  df_rec, data_scaled = _similarity_space()
  index_input = track_row

  # Une seule ligne de similarite au lieu de la matrice 3815 x 3815 (116 Mo,
  # doublee par la copie DataFrame). La matrice etant symetrique, la ligne
  # index_input vaut la colonne index_input : resultat identique, mais on tient
  # dans les 512 Mo de RAM de l'offre gratuite Render.
  similarity_row = cosine_similarity(data_scaled[index_input:index_input + 1], data_scaled)[0]
  series = pd.Series(similarity_row, index=df_rec.index).sort_values(ascending=False)
  series = series.drop(index_input)
  # Le morceau lui-meme est retire ci-dessus. Jusqu'au 2026-10-09, [1:12]
  # sautait en plus le meilleur voisin (depuis 2021).
  resultat = list(series.index)[0:11]
  output = df_rec.iloc[resultat][["Song", "Artist", "Preview", "Main_Genre", "Cover"]]

  return output
