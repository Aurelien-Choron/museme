# Museme

Application Dash de recommandation musicale par similarite cosinus, sur un
corpus de 4 724 morceaux decrits par 63 descripteurs audio (`data/df_recommendation.csv`) :
3 815 collectes en 2021, 909 ajoutes en octobre 2026 (voir *Alimenter le catalogue*).

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
3. Choisir un artiste, puis un de ses titres.
4. L'app affiche le morceau (pochette + extrait audio) et 10 recommandations.

Autres pages : `/page-1` synthese + graphe Plotly, `/page-2` a propos, `/page-3` ressources.

## Structure

```
app.py              objet Dash partage
index.py            point d'entree : layout, routage, callbacks
components/
  engine/functions.py   extraction des donnees + recommandation cosinus
  layout/               une page par fichier (home, summary, about_us, ressources)
data/                 les deux CSV (features + recommandation)
assets/               CSS, images, favicon, video de fond (servis par Dash)
audio/                dossiers de travail de l'app d'origine
legacy/               scripts hors application, conserves pour reference
pipeline/             alimentation du catalogue (local, jamais deploye)
render.yaml           blueprint de deploiement Render
requirements-pipeline.txt   dependances du pipeline (librosa...)
```

## Alimenter le catalogue

Le dossier `pipeline/` ajoute des morceaux a `data/df_recommendation.csv`.
Il tourne en local uniquement : librosa et numba ne sont pas deployes.
Prerequis en plus de l'app : `ffmpeg` dans le PATH.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-pipeline.txt
.\.venv\Scripts\python.exe -m pipeline validate  # l'extracteur redonne-t-il les vecteurs de 2021 ?
.\.venv\Scripts\python.exe -m pipeline collect   # morceaux des playlists de pipeline/playlists.csv
.\.venv\Scripts\python.exe -m pipeline extract   # 63 descripteurs par morceau
.\.venv\Scripts\python.exe -m pipeline merge     # ajout au CSV (--dry-run pour verifier)
```

Le cache audio, les pages Spotify et les sorties intermediaires vont dans
`%LOCALAPPDATA%\museme\` (variable `MUSEME_WORK_DIR` pour changer), hors
OneDrive. `collect` et `extract` reprennent la ou ils se sont arretes.

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
- **Les nouveaux morceaux n'ont pas de genre** (`Main_Genre` et
  `family_genre` vides). Les playlists de tops n'en donnent pas, et un
  classifieur entraine sur les descripteurs du catalogue de 2021
  (`HistGradientBoostingClassifier`, 23 % de bonnes reponses sur 77 genres en
  validation croisee) se trompait nettement sur les tubes recents : par
  exemple *Die With A Smile* classe `cantopop` a 94 %. Un genre vide donne
  des indicatrices nulles dans l'espace de similarite et n'est affiche nulle
  part. Le classifieur est a refaire, dans un notebook.
  Consequence en attendant : ces indicatrices nulles forment de fait un genre
  commun aux 909 nouveaux morceaux, qui ne se recommandent presque qu'entre eux
  (99,7 % de leurs recommandations), tandis que les anciens n'en recoivent
  presque jamais (1,2 %).
- **La fusion ajoute des lignes sans reecrire le fichier** : les lignes
  existantes restent identiques octet pour octet, et le schema ne change pas
  (une colonne de plus casserait `_similarity_space`).
- **Prochaine etape envisagee** : une version corrigee des descripteurs
  (mono, audio normalise, vrais MFCC par coefficient), recalculee sur tout le
  catalogue, a comparer sur la qualite des recommandations avant de basculer.

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
