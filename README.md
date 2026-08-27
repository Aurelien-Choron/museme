# Museme

Application Dash de recommandation musicale par similarite cosinus, sur un
corpus de 3 815 morceaux decrits par 66 descripteurs audio (`data/df_recommendation.csv`).

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
render.yaml           blueprint de deploiement Render
```

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
- La colonne de recommandations (`.track-recommended-player-box`, a droite)
  est encore positionnee en absolu : ses dernieres lignes sortent de l'ecran
  sur une fenetre basse, sans possibilite de defiler. Non traite ici.

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
