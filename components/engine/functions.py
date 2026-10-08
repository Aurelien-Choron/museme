import functools
import os

import numpy as np
import pandas as pd
from sklearn import preprocessing
from sklearn.metrics.pairwise import cosine_similarity

# Chemins absolus : gunicorn peut demarrer depuis un repertoire courant
# different de la racine du projet.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
RECOMMENDATION_CSV = os.path.join(DATA_DIR, "df_recommendation.csv")
FEATURES_CSV = os.path.join(DATA_DIR, "df_66features_clean2.csv")


@functools.lru_cache(maxsize=1)
def load_catalog():
  """Catalogue des morceaux, lu une seule fois par processus.

  Le CSV pese 5 Mo et etait relu a chaque callback.
  """
  return pd.read_csv(RECOMMENDATION_CSV, sep=',')


@functools.lru_cache(maxsize=1)
def _similarity_space():
  """Descripteurs centres-reduits + catalogue aligne.

  Ne depend pas du morceau demande : calcule une fois puis reutilise.
  """
  df_rec = load_catalog().copy()
  df_rec = pd.concat([df_rec, df_rec["Main_Genre"].str.get_dummies()], axis=1)
  df_rec.drop(columns='Unnamed: 0', inplace=True)
  data = df_rec.set_index("Song")
  data = data.drop(columns=["Artist", "Album", "Preview", "Main_Genre", "Cover", 'family_genre'])
  data_scaled = preprocessing.scale(data)
  return df_rec, data_scaled


def input_data_extraction(song_input):
  df_all = load_catalog()
  result = df_all[df_all['Song'] == song_input].copy()
  result.reset_index(inplace=True)
  try:
      track_artist = result['Artist'][0]
  except: 
      track_artist = 'Unknown'

  try:
      track_title = result['Song'][0]
  except:
      track_title = 'Unknown'

  try:
      track_coverimg_hq = result['Cover'][0]
  except:
      track_coverimg_hq = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/600px-No_image_available.svg.png"

  try:
      audio_preview = result['Preview'][0]
  except:
      audio_preview = None
  try:
      track_genre = result['family_genre'][0]
  except:
      track_genre=None
  
  return track_artist, track_title, track_coverimg_hq, audio_preview,track_genre


def recommandation_cosine(song_title):
  df_rec, data_scaled = _similarity_space()
  index_input = pd.Index(list(df_rec['Song']))
  index_input = index_input.get_loc(song_title)
  # 31 titres sont dupliques dans le CSV: get_loc renvoie alors un masque/slice
  if isinstance(index_input, slice):
      index_input = index_input.start
  elif not isinstance(index_input, (int, np.integer)):
      index_input = int(np.flatnonzero(np.asarray(index_input))[0])

  # Une seule ligne de similarite au lieu de la matrice 3815 x 3815 (116 Mo,
  # doublee par la copie DataFrame). La matrice etant symetrique, la ligne
  # index_input vaut la colonne index_input : resultat identique, mais on tient
  # dans les 512 Mo de RAM de l'offre gratuite Render.
  similarity_row = cosine_similarity(data_scaled[index_input:index_input + 1], data_scaled)[0]
  series = pd.Series(similarity_row, index=df_rec.index).sort_values(ascending=False)
  series = series.drop(index_input)
  resultat = list(series.index)[1:12]
  output = df_rec.iloc[resultat][["Song", "Artist", "Preview", "Main_Genre", "Cover"]]

  return output
