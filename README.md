# Museme

Application Dash de recommandation musicale par similarite cosinus, sur un
corpus de 4 724 morceaux (`data/df_recommendation.csv`) : 3 815 collectes en
2021, 909 ajoutes en octobre 2026 (voir *Alimenter le catalogue*). Chaque
morceau est decrit par le son de son extrait de 30 s (vecteur CLAP de 512
dimensions, `data/embeddings_clap.npy`) et par son genre Deezer.

Projet d'origine : 2021, Python 3.7 / Dash 1.19.
Remis en fonctionnement en aout 2026 sur Python 3.12 (voir *Migration* plus bas).

## Lancer l'application

Prerequis : Python 3.12 (`py -3.12 --version`).

```powershell
# depuis le dossier du projet
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe index.py
```

Puis ouvrir http://127.0.0.1:8050/

> Lancer `index.py`, **pas** `app.py` : `app.py` ne cree que l'objet Dash,
> c'est `index.py` qui porte le layout et les callbacks.

### Parcours

1. Page d'accueil : video de fond + bouton *Get it, let's try*.
2. Le clic affiche deux listes deroulantes.
3. Choisir un artiste, puis un de ses titres ; ou, sans artiste, chercher
   directement dans tous les titres (affiches « Titre — Artiste »).
4. L'app affiche le morceau (pochette + extrait audio) et 10 recommandations.

Autres pages : `/page-1` synthese + graphe Plotly, `/page-2` a propos, `/page-3` ressources.

## Structure

```
app.py              objet Dash partage
index.py            point d'entree : layout, routage, callbacks
components/
  engine/functions.py   extraction des donnees + recommandation cosinus
  layout/               une page par fichier (home, summary, about_us, ressources)
data/                 catalogue (df_recommendation.csv), vecteurs CLAP, genres Deezer et de 2021
notebooks/            classifieur de genre, banc d'essai audio (evaluation_audio.ipynb)
docs/                 cercle des genres, etat des lieux de la recommandation (recommandation.md)
assets/               CSS, images, favicon, video de fond (servis par Dash)
audio/                dossiers de travail de l'app d'origine
legacy/               scripts hors application, conserves pour reference
pipeline/             alimentation du catalogue (local, jamais deploye)
render.yaml           blueprint de deploiement Render
requirements-pipeline.txt   dependances du pipeline (librosa...)
```

## Alimenter le catalogue

Le dossier `pipeline/` ajoute des morceaux a `data/df_recommendation.csv`,
puis leurs vecteurs CLAP a `data/embeddings_clap.npy`. Il tourne en local
uniquement : librosa, numba, torch et transformers ne sont pas deployes.
Prerequis en plus de l'app : `ffmpeg` dans le PATH, et torch en version CPU
(voir `requirements-pipeline.txt`).

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-pipeline.txt
.\.venv\Scripts\python.exe -m pipeline validate  # l'extracteur redonne-t-il les vecteurs de 2021 ?
.\.venv\Scripts\python.exe -m pipeline collect   # morceaux des playlists de pipeline/playlists.csv
.\.venv\Scripts\python.exe -m pipeline extract   # 63 descripteurs par morceau
.\.venv\Scripts\python.exe -m pipeline merge     # ajout au CSV (--dry-run pour verifier)
.\.venv\Scripts\python.exe -m pipeline embeddings # vecteurs CLAP des nouveaux morceaux -> data/embeddings_clap.npy
.\.venv\Scripts\python.exe -m pipeline deezer    # genres Deezer, pour notebooks/classifieur_genre.ipynb
```

Le cache audio, les pages Spotify et les sorties intermediaires vont dans
`%LOCALAPPDATA%\museme\` (variable `MUSEME_WORK_DIR` pour changer), hors
OneDrive. `collect`, `extract` et `embeddings` reprennent la ou ils se sont
arretes. **Apres `merge`, lancer `embeddings`** : l'app refuse de demarrer si
un morceau n'a pas de vecteur CLAP (environ 2 s par morceau sur CPU).

Points a connaitre :

- **Les descripteurs reproduisent ceux de 2021, bugs compris.** Le code
  d'extraction d'origine a ete retrouve (`Downloads\66_features.ipynb`,
  `_archive\Dash_music\music2\components\engine\functions.py`) et porte dans
  `pipeline/features_legacy.py`. Ses particularites sont conservees
  volontairement pour qu'un meme morceau donne le meme vecteur :
  audio en entiers 16 bits non normalises, MP3 stereo entrelace et analyse
  comme du mono a 22 050 Hz, `mfcc{k}` = statistiques des k *premiers*
  coefficients. Les changements de librosa 0.8 -> 0.11 sont neutralises (la
  CQT de 0.8.1 est reprise dans `pipeline/_cqt08.py`).
  `validate` le verifie sur 45 morceaux du catalogue : ecart maximal de
  7e-5 ecart-type, 10 recommandations sur 10 identiques.
- **Source : pages embed publiques de Spotify** (`open.spotify.com/embed/...`).
  L'API Web ne donne plus d'extraits depuis novembre 2024 et exige un compte
  Premium depuis mars 2026. Les pages embed fournissent l'extrait de 30 s sans
  compte, au meme format que le catalogue, mais ne sont pas une API : elles
  peuvent changer ou disparaitre sans preavis, et cet usage n'est pas couvert
  par les conditions developpeur de Spotify.
- **Les genres sont ceux de Deezer**, pour tout le catalogue : 16 genres
  Deezer (de `Pop` a `African Music`), plus `Country`. `deezer` note le genre
  de l'album de chaque morceau sur l'API publique de Deezer (sans compte),
  dans `%LOCALAPPDATA%\museme\out\deezer_genres.csv`. Le notebook
  `notebooks/classifieur_genre.ipynb` corrige ces genres, complete les
  morceaux non trouves (genre de l'artiste, ou correspondance avec le genre
  de 2021), puis les ecrit dans `Main_Genre` et `family_genre` (meme valeur)
  avec `pipeline/genres.py`. Deezer ne donne aucun genre aux albums country
  (`genre_id` -1) : les 149 morceaux des genres country, bluegrass et
  honky-tonk de 2021 forment le genre `Country`. 27 morceaux ajoutes restent
  sans genre. Les etiquettes de 2021 (77 « genre seeds » Spotify, bruitees
  au niveau de l'artiste) sont gardees dans `data/genres_2021.csv`.
- **La recommandation part de l'audio, le genre l'aide.** L'audio est decrit
  par le modele pre-entraine CLAP de LAION (`laion/larger_clap_general`,
  Apache 2.0) : 512 dimensions par morceau, calculees en local par
  `python -m pipeline embeddings`. L'app ne lit que les vecteurs
  (`data/embeddings_clap.npy`) : Render n'a pas besoin de torch. CLAP a ete
  retenu le 2026-10-10 face aux 63 descripteurs de 2021 et a leurs versions
  corrigees, sur des mesures automatiques puis une ecoute a l'aveugle (63 %
  de propositions jugees proches, contre 17 % pour les descripteurs de 2021).
  L'app y ajoute 17 colonnes de genre (`components/engine/functions.py`) : le
  genre principal, les genres Deezer de l'album en secondaire
  (`data/genres_deezer.csv`, ecrit par `python -m pipeline genre-lists`), et
  une similarite entre genres (voisins du cercle ci-dessous, Pop sur son
  propre axe), avec un poids de 4. Resultat : 54 % des recommandations dans
  le genre du morceau, et 66 % des morceaux retrouvent un autre titre de leur
  artiste. Reglages, tests, ecoute et retours en arriere :
  [`docs/recommandation.md`](docs/recommandation.md).
- **Le cercle des genres** : deux genres voisins sont proches, et Pop, proche
  de presque tout, est au centre, voisin de tous. Il sert a juger le
  classifieur avec indulgence : predire un genre voisin du vrai genre est une
  erreur pardonnable. L'ordre est un choix musical, verifie sur les albums
  Deezer qui portent plusieurs genres. Revers de Pop au centre : repondre Pop
  n'est jamais une erreur lointaine, donc un modele qui se refugie dans Pop
  gonfle son score « a un voisin pres ».

  <img src="docs/cercle_genres.png" alt="Le cercle des genres : 16 genres sur un cercle, Pop au centre" width="560">

- **Le classifieur de genre** (meme notebook) predit le genre a partir des 63
  descripteurs. Cinq modeles compares sur 940 morceaux de test (genre exact,
  exact equilibre entre genres, exact ou voisin sur le cercle) : SVC
  39 % / 43 % / 74 %, gradient boosting 40 % / 34 % / 80 % (mais un quart de
  reponses Pop), foret aleatoire 38 % / 40 % / 74 %, kNN cosinus 36 % /
  35 % / 74 %, regression logistique 33 % / 41 % / 68 %. Le SVC est retenu.
- **La fusion ajoute des lignes sans reecrire le fichier** : les lignes
  existantes restent identiques octet pour octet, et le schema ne change pas.
  Les 63 descripteurs restent calcules et ecrits dans le CSV (le classifieur
  de genre et `validate` s'en servent), mais l'app ne les utilise plus.

## Deploiement (Render, offre gratuite)

L'app tourne sur le plan **free** de Render : 512 Mo de RAM, mise en veille
apres 15 min sans trafic (~1 min de reveil), 750 h/mois par workspace.

Le blueprint `render.yaml` decrit tout le service. Sur https://render.com :
*New > Blueprint*, pointer sur le depot GitHub, deployer.

Trois points a connaitre, qui ne sont pas evidents :

- **Render ne lit ni `Procfile` ni `runtime.txt`.** Ces deux fichiers sont un
  heritage Heroku, conserves mais inertes ici. La version de Python vient de
  `.python-version` ; sans lui Render prendrait son defaut actuel (3.14), pour
  lequel les versions epinglees de pandas / numpy n'ont pas de roue.
- **Un seul worker gunicorn** (`--workers 1 --threads 4`). Chaque worker charge
  sa propre copie du catalogue : a deux workers on depasse les 512 Mo.
- L'empreinte mesuree est de ~195 Mo au demarrage et ~206 Mo en regime stable.

Le plan free n'accepte ni disque persistant ni mise a l'echelle : l'app etant
entierement en lecture seule sur des CSV versionnes, cela n'a pas d'incidence.

## Migration 2021 -> 2026

Le code metier est volontairement reste tel quel. Seul ce qui empechait
l'execution a ete corrige :

| Correction | Fichier | Raison |
|---|---|---|
| `dash_html_components` / `dash_core_components` -> `from dash import html, dcc` | les 4 pages de `components/layout/` | paquets absorbes dans `dash` puis supprimes |
| `DataFrame.append` -> indexation directe | `components/engine/functions.py` | supprime en pandas 2.0 |
| `app.run_server()` -> `app.run()` | `index.py` | renomme en Dash 3 |
| Normalisation du retour de `get_loc` | `components/engine/functions.py` | 31 titres du CSV sont en double : `get_loc` renvoyait un masque booleen et faisait planter la recommandation |
| Suppression des imports `librosa` / `matplotlib` | `functions.py`, `index.py` | importes mais jamais appeles ; imposaient tout le stack audio non compilable en 3.12 |
| `gunicorn app:server` -> `gunicorn index:server` | `Procfile` | `app.py` n'a pas de layout : le deploiement servait une page vide |

## Mise en ligne 2026

Changements apportes pour l'hebergement et le rendu :

| Changement | Fichier | Raison |
|---|---|---|
| Titre d'onglet `Museme` + `assets/favicon.ico` | `app.py`, `index.py` | l'onglet affichait `Dash`. Le favicon est genere depuis `assets/images/Logo_Museme.jpg` ; Dash sert automatiquement `assets/favicon.ico` |
| Colonne de gauche regroupee dans `.left-panel` | `components/layout/home.py`, `assets/style.css` | `.input-box` (top 10 %) et `.track-audio-player-box` (top 40 %) etaient positionnes en absolu chacun de leur cote : leurs hauteurs ne dependant pas de la fenetre, les deux blocs se superposaient des qu'un titre etait selectionne. Ils sont desormais empiles dans un unique conteneur flex |
| `dbc.Row` retires du bloc de selection | `components/layout/home.py` | les marges negatives de Bootstrap faisaient deborder les listes deroulantes de leur boite |
| Similarite calculee sur une seule ligne | `components/engine/functions.py` | la matrice complete 3 815 x 3 815 faisait 116 Mo, doublee par la copie DataFrame : pic a 243 Mo par requete. La matrice etant symetrique, le resultat est identique |
| Catalogue et descripteurs mis en cache (`lru_cache`) | `components/engine/functions.py` | le CSV de 5 Mo etait relu a chaque callback |
| Chemins de donnees absolus | `components/engine/functions.py` | les chemins relatifs supposaient que le repertoire courant soit la racine du projet |
| Colonne de recommandations dans `.right-panel`, bornee et defilante | `components/layout/home.py`, `assets/style.css` | le bloc etait absolu et sans limite de hauteur : ses dernieres lignes sortaient de l'ecran, et le corps de page (entierement en absolu, donc de hauteur nulle) n'offrait aucun defilement pour les atteindre |
| Fond sombre translucide sous les recommandations | `assets/style.css` | le texte blanc devenait illisible sur les plans clairs de la video |
| Lignes de recommandation generees par une boucle, en grille CSS | `components/layout/home.py` | les 10 lignes etaient ecrites a la main en `dbc.Row` de 4 colonnes de largeur egale : la pochette de 50 px occupait un quart de la largeur pendant que les titres longs se repliaient sur trois lignes |
| Morceau repere par son numero de ligne, et non par son titre ; recherche dans tous les titres sans artiste choisi | `index.py`, `components/engine/functions.py` | 54 titres existent chez plusieurs artistes (*Baby* : Brandy et Justin Bieber) : choisir l'un affichait et recommandait a partir du premier du CSV. Sans artiste, la liste des titres etait vide |
| Pochette de remplacement quand `Cover` est absent | `components/layout/home.py` | 61 morceaux du catalogue n'ont pas de pochette : le code produisait `<img src="nan">`, donc une icone d'image cassee |
| Video de fond reencodee : 179 Mo -> 5,7 Mo | `assets/videos/background.mp4` | au-dela de la limite de 100 Mo par fichier de GitHub. 854x480, sans piste audio, avec un flou leger a l'encodage — invisible puisque le CSS applique deja `blur(5px)` |

Effet sur la recommandation, mesure sur 7 titres (dont un titre duplique) :
resultats strictement identiques a l'ancienne implementation, 243 Mo -> 17 Mo
de pic memoire, 1,22 s -> 0,02 s une fois le cache chaud.

Points connus, laisses en l'etat :

- `index.py` recree un second objet `Dash` qui masque celui de `app.py`.
  Bancal mais fonctionnel.
- `preprocessing.scale` emet un `UserWarning` sur l'echelle de certaines
  colonnes du CSV. Sans consequence sur les resultats.
- Le passage de Bootstrap 4 a 5 peut induire de legers ecarts visuels ;
  l'essentiel du design vient de `assets/style.css`.

## Video de fond

`assets/videos/background.mp4` (5,7 Mo) est la version web, versionnee.
Le master d'origine (`assets/videos/Mon film 1.mp4`, 179 Mo) est exclu par
`.gitignore` : il n'est plus utilise par l'app et peut etre supprime ou
archive ailleurs. Pour le regenerer :

```powershell
ffmpeg -i "assets\videos\Mon film 1.mp4" -an `
  -vf "gblur=sigma=1.2,scale=854:480:flags=lanczos" `
  -c:v libx264 -preset slow -crf 33 -pix_fmt yuv420p -g 50 `
  -movflags +faststart "assets\videos\background.mp4"
```
