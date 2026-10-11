# Recommandation : etat des lieux des reglages et des tests

Etat au 2026-10-11. Depuis le 2026-10-10, l'audio est decrit par le modele
CLAP (V3 de la partie 7) et le genre pese 4. Depuis le 2026-10-11, l'app
Dash est remplacee par un site statique (`web/`) : les recommandations sont
calculees d'avance par le meme moteur, sans rien changer au calcul. Points
de retour : `dc9439f` (63 descripteurs de 2021, genre sur le cercle, poids
3), `fb73ead` (genre en indicatrices, morceau repere par son titre, meilleur
voisin saute) et le tag `dash-final` (derniere version de l'app Dash).

**Objectif** : recommander par l'audio. Les autres informations, dont le
genre, sont la pour aider.

Les liens pointent vers des numeros de ligne, qui bougent quand le code
change : le nom de la fonction ou de la constante est toujours donne a cote.

## 1. Le calcul, etape par etape

1. [`load_catalog`](../components/engine/functions.py#L44) lit
   `data/df_recommendation.csv`, une seule fois par processus.
2. [`_similarity_space`](../components/engine/functions.py#L87) construit
   l'espace de similarite : les 512 dimensions des vecteurs CLAP
   (`data/embeddings_clap.npy`, une ligne par ligne du CSV, ecrit par
   `python -m pipeline embeddings`) centrees-reduites, puis 17 colonnes de
   genre ([lignes 104-106](../components/engine/functions.py#L104-L106)),
   calculees par [`_genre_weights`](../components/engine/functions.py#L67)
   et [`_genre_similarity_root`](../components/engine/functions.py#L52).
   Calcule une seule fois. Refuse de demarrer si le nombre de vecteurs ne
   correspond pas au CSV. Les 63 descripteurs du CSV ne servent plus.
3. [`recommandation_cosine`](../components/engine/functions.py#L109) calcule
   le cosinus entre le morceau et tout le catalogue, trie, retire le morceau
   lui-meme ([ligne 121](../components/engine/functions.py#L121)) et garde les
   11 premiers ([ligne 124](../components/engine/functions.py#L124)).
4. [`python -m pipeline site`](../pipeline/site.py) calcule d'un coup les
   10 premiers de chaque morceau ([`neighbors`](../pipeline/site.py#L35)),
   verifie pour les 4 724 morceaux qu'ils sont ceux de
   `recommandation_cosine`, puis ecrit `web/data/neighbors.json` et
   `web/data/catalog.json`. Le site les affiche tels quels
   ([`recommend`](../web/app.js), seule fonction a remplacer pour
   recommander autrement).

Le morceau est designe par son numero de ligne dans le CSV, qui est aussi
sa position dans `catalog.json` et `neighbors.json`.

**Apres une modification** du moteur, des genres ou des vecteurs : relancer
`python -m pipeline site` (environ 2 min, dont 95 s de controle ;
`--no-check` pour s'en passer), puis recharger la page. `embeddings` le fait
d'office apres un ajout au catalogue.

## 2. Reglages actuels

| Reglage | Valeur | Ou | Effet |
|---|---|---|---|
| Audio | CLAP (`laion/larger_clap_general`), 512 dimensions centrees-reduites | [`CLAP_NPY`](../components/engine/functions.py#L20) | jusqu'au 2026-10-09 : les 63 descripteurs de 2021 |
| Ordre du cercle | 16 genres | [`GENRE_CIRCLE`](../components/engine/functions.py#L25) | voisins du cercle rapproches |
| Pop | son propre axe | [`GENRES`](../components/engine/functions.py#L28) | Pop attire Pop, reste un peu proche de tous |
| Similarite entre voisins | 0,5 | [`NEIGHBOR_SIMILARITY`](../components/engine/functions.py#L33) | 0 = voisins traites comme des genres eloignes |
| Similarite Pop / autres | 0,3 | [`POP_SIMILARITY`](../components/engine/functions.py#L34) | |
| Genres secondaires | `data/genres_deezer.csv`, poids 0,5 | [`SECONDARY_GENRE_SHARE`](../components/engine/functions.py#L36) | 0 = un seul genre par morceau |
| Poids du genre | 4 | [`GENRE_WEIGHT`](../components/engine/functions.py#L40) | 0 = audio seul |
| Recos renvoyees / affichees | 11 / 10, meilleur voisin compris | [`[0:11]`](../components/engine/functions.py#L124), [`N_NEIGHBORS`](../pipeline/site.py#L30) = 10 | |
| Recherche | une barre : titre, artiste ou album, sans accents, dans n'importe quel ordre | [`web/search.js`](../web/search.js) | |

Resultat sur les 4 724 morceaux, 11 recommandations chacun : 53,8 % des
recommandations dans le genre du morceau, 13,6 % dans un genre eloigne sur le
cercle, et 66,5 % des morceaux retrouvent un autre titre de leur artiste.
Avec les 63 descripteurs et un poids de 3 (jusqu'au 2026-10-09) : 86,6 %,
3,6 % et 53,1 %.

## 3. Le genre dans l'espace de similarite

<img src="cercle_genres.png" alt="Le cercle des genres : 16 genres sur un cercle, Pop au centre" width="480">

**Le cercle** : Asian Music, R&B, African Music, Reggae, Rap/Hip Hop, Latin
Music, Brazilian Music, Jazz, Classical, Folk, Country, Alternative, Rock,
Metal, Electro, Dance (le dernier touche le premier). Pop n'est plus au
centre du cercle dans l'app : il a son propre axe (voir H10).

**Les genres d'un morceau** ([`_genre_weights`](../components/engine/functions.py#L67)) :
`Main_Genre` pese 1, chaque genre secondaire 0,5, puis le vecteur est ramene a
une norme de 1. Les genres secondaires sont les genres Deezer de l'album,
ramenes aux 17 genres par [`DEEZER_PARENT`](../pipeline/genres.py#L33)
(Indie Rock → Alternative, Techno/House → Electro, Soul & Funk → R&B…) et
ecrits dans `data/genres_deezer.csv` par
[`python -m pipeline genre-lists`](../pipeline/genres.py#L110). 855 morceaux
ont plusieurs genres. Un morceau sans genre n'a que des zeros : le genre ne
joue pas pour lui.

**La similarite entre genres** ([`_genre_similarity_root`](../components/engine/functions.py#L52)) :
une matrice S de 17 x 17 vaut 1 pour un meme genre, 0,5 entre voisins du
cercle, 0,3 entre Pop et chacun des autres, 0 sinon. Chaque morceau recoit
`GENRE_WEIGHT × m @ L`, ou m est son vecteur de genres et L la racine de S
(L @ L.T = S) : le produit scalaire de deux morceaux gagne alors
`GENRE_WEIGHT² × m_a . S . m_b`. Pour un genre unique et un poids de 4 :

| Les deux morceaux | Exemple | Apport au produit scalaire |
|---|---|---|
| meme genre | Rock / Rock | +16 |
| voisins sur le cercle | Rock / Metal | +8 |
| Pop et un autre genre | Pop / Rock | +4,8 |
| genres non voisins | Rock / Electro | 0 |
| l'un sans genre | | 0 |

Ordre de grandeur : les 512 dimensions CLAP centrees-reduites pesent 512
dans le carre de la norme d'un morceau, le genre environ 17 (3 % du total).
Avec les 63 descripteurs et un poids de 3, le genre pesait 9 sur 72 (12,5 %) ;
garde a 3 face a CLAP, il serait tombe a 1,7 %. Aucun
genre ne repousse un autre : l'ancien cercle (Pop au centre) faisait
s'opposer les genres diametralement opposes.

**Contraintes** : S doit rester une similarite valide, sinon la racine est
approchee sans avertissement. Il faut `NEIGHBOR_SIMILARITY <= 0,5` et
`POP_SIMILARITY <= racine((1 + 2 × NEIGHBOR_SIMILARITY) / 16)`, soit 0,35
avec des voisins a 0,5.

**Le cercle est defini a trois endroits**, a garder synchronises :
[`GENRE_CIRCLE`](../components/engine/functions.py#L25), la cellule `CENTRE`
/ `CERCLE` du notebook [`classifieur_genre.ipynb`](../notebooks/classifieur_genre.ipynb)
(qui met Pop au centre, pour juger le classifieur), et l'image
`cercle_genres.png` exportee par ce notebook.

## 4. Tests menes

Tests du 2026-10-09, avec les 63 descripteurs de 2021 (l'audio de l'app
jusqu'au 2026-10-10). Les tests de l'audio sont dans la partie 7.

### Methode

- Chaque morceau du catalogue (4 724) est pris tour a tour comme requete.
  Sauf mention contraire, avec l'ancienne logique `[1:12]` (meilleur voisin
  saute), seule en place au moment des mesures.
- **Meme genre** : part des recommandations du meme `Main_Genre` que la
  requete (morceaux sans genre exclus). Au hasard : 9,7 %.
- **Voisin** : meme genre, genres voisins sur le cercle, ou l'un des deux est
  Pop. **Eloigne** : tout le reste.
- **Communs** : recommandations en commun avec la version audio seul, sur 11.
- **Cas signales a l'ecoute** : *4 Minutes* (Madonna), *Boom Clap* (Charli
  XCX) → *Quem Vem de La* (Grupo Nzinga), *Next To You* (Ciara) → *Cuando te
  conoci* (Andres Calamaro). Rang dans les 11 recommandations (– si absent).

### Resultats

| Espace de similarite | Meme genre | Eloigne | Communs | Boom Clap → Quem | Ciara → Calamaro |
|---|---|---|---|---|---|
| audio seul (`GENRE_WEIGHT = 0`) | 24,1 % | 35,2 % | 11,0 | 7 | 1 |
| indicatrices centrees-reduites (jusqu'a `fb73ead`) | 96,4 % | 1,9 % | 2,3 | – | 3 |
| audio, familles de descripteurs equilibrees | 23,4 % | 35,7 % | 5,8 | 7 | 1 |
| audio, ACP blanchie sur 20 axes | 24,3 % | 35,3 % | 3,4 | – | – |
| audio + indicatrices non reduites, poids 2 | 78,5 % | 13,7 % | 4,1 | – | 3 |
| audio + indicatrices non reduites, poids 3 | 92,3 % | 5,3 % | 2,7 | – | 6 |
| audio + cercle, Pop au centre, poids 2 | 48,4 % | 12,9 % | 5,8 | 7 | 1 |
| audio + cercle, Pop au centre, poids 3 | 61,6 % | 6,3 % | 4,4 | – | 1 |
| audio + Pop sur son axe, un genre, poids 3 | 88,4 % | 3,7 % | | | |
| audio + Pop sur son axe, un genre, poids 4 | 94,8 % | 1,4 % | | | |
| audio + Pop sur son axe, liste Deezer, poids 3 | 85,3 % | 4,1 % | | | |
| audio + Pop sur son axe, liste Deezer, poids 4 | 92,8 % | 1,8 % | | | |
| **actuel : Pop sur son axe, liste Deezer, poids 3, `[0:11]`** | **86,7 %** | **3,6 %** | | | |

*4 Minutes*, selon la version :

| Version | Recommandations |
|---|---|
| `fb73ead` (morceaux de 2026 sans genre) | KISS, Mark Ronson, Red Hot Chili Peppers… (ilot des morceaux de 2026) |
| indicatrices + genres Deezer | Kylie Minogue, Ellie Goulding, Taylor Swift, David Bowie, Queen, Harry Styles |
| cercle, Pop au centre, poids 2 | Romeo Santos, Twisted Sister, Ratt, Country Gentlemen, Samba Enredo |
| **actuel** | Kylie Minogue, ROLE MODEL, Romeo Santos, Taylor Swift, Ellie Goulding, David Bowie, Harry Styles |

Ilots (part des recommandations des 909 morceaux ajoutes qui vont vers
d'autres morceaux ajoutes ; ils forment 19 % du catalogue) : 51,9 % avec les
indicatrices, 39,0 % en audio seul, 43,8 % avec le cercle (Pop au centre,
poids 2).

### Hypotheses

| | Hypothese | Test | Resultat | Conclusion |
|---|---|---|---|---|
| H1 | Les indicatrices de genre agissent comme un filtre | recos avec indicatrices | 96,4 % dans le meme genre. Centree-reduite, une indicatrice vaut √((1−p)/p) ecarts-types pour un genre de frequence p : 11 pour Folk (39 morceaux), 2,3 pour Pop (746) | confirmee |
| H2 | L'audio seul, tel qu'il est extrait, suffit | `GENRE_WEIGHT = 0` | 35,2 % de sauts vers un genre eloigne. *Dona Cila* (Maria Gadu) → Billie Eilish, Anvil, Air, The Dead South | insuffisant a l'ecoute ; piste : ameliorer l'extraction (partie 7) |
| H3 | Les cas bizarres viennent d'une valeur aberrante | ecarts-types de chaque descripteur pour 2 paires | aucun au-dela de 4 ; contributions diffuses | rejetee |
| H4 | Quelques morceaux « aimants » sont recommandes partout | nombre de fois ou chaque morceau est recommande (audio seul) | maximum 50 (*Get Out Alive*, Three Days Grace) pour 11 en moyenne ; les 5 % les plus recommandes font 13 % des recos | rejetee |
| H5 | Les MFCC redondants faussent la distance | correlations, ACP, reponderation par famille | 40 colonnes sur 63 sont des MFCC emboites (`mfccK` = statistiques des K premiers coefficients) : `mfcc10_var` et `mfcc20_var` correles a 1,00 ; 8 axes portent 90 % de la variance. Reponderer : memes chiffres | redondance confirmee, sans effet sur les cas |
| H5b | Decorreler les descripteurs (ACP blanchie) corrige les cas | ACP sur 20 axes de meme variance | les 2 cas disparaissent, mais 35,3 % de sauts eloignes et 3,4 recos communes | non retenue ; a ecouter |
| H6 | Le genre aurait evite Ciara → Calamaro | rang avec indicatrices | 3e : Deezer classe les deux en Pop | rejetee : le genre de Ciara est discutable (voir H11) |
| H7 | Un genre « doux » (cercle) reduit les sauts sans filtrer | cercle, Pop au centre, poids 2 et 3 | voir tableau | retenu le matin du 2026-10-09, abandonne le soir (H10) |
| H8 | Un morceau proche du centre de l'espace a des voisins fragiles | Ciara : norme 2,7 pour une mediane de 5,8 | — | non testee |
| H9 | Le code saute le meilleur voisin | tri complet compare a la sortie | confirme : *Boom Clap* → *Lady Marmalade* (cosinus 0,85) n'etait jamais affiche. Present depuis 2021 (`drop` du morceau puis `[1:6]` dans `_archive/Dash_music/music2/components/engine/functions.py`). Presque jamais un doublon : 2 vrais doublons, cosinus median 0,921 | **corrige le 2026-10-09** |
| H10 | Pop au centre du cercle ne gene pas | *4 Minutes* (Pop) | faux : au centre, Pop vaut (0, 0). Les 746 morceaux Pop (16 %) etaient recommandes sur l'audio seul | **corrige : Pop sur son axe** |
| H11 | Le genre Deezer est fiable | coherence par artiste | genre de l'album, pas de l'artiste ni du morceau. 167 artistes (970 morceaux) ont plusieurs genres ; Nasum (grindcore) est moitie Alternative, moitie Pop ; Pop sert de fourre-tout (Ciara). 907 morceaux n'ont pas de genre Deezer | a revoir : `docs/revue_genres.csv` |
| H12 | Plusieurs genres par morceau elargissent les recos | liste Deezer, poids 3 | 85,3 % meme genre au lieu de 88,4 % : effet modeste | retenu (aide, sans risque) |
| H13 | Les descripteurs audio portent un signal | audio seul : un autre titre du meme artiste dans les 10 plus proches ? | 32,2 % des morceaux, contre 1,3 % au hasard (4 066 morceaux dont l'artiste a d'autres titres) | confirmee ; indicateur de reference pour la partie 7 |

## 5. Modifier ou revenir en arriere

### Changer le poids du genre

[`GENRE_WEIGHT`](../components/engine/functions.py#L40). Reperes avec CLAP
(recommandations dans le genre du morceau / dans un genre eloigne, 11 par
morceau) : `0` donne exactement l'audio seul (colonnes nulles), 45,9 % /
17,7 % ; `4` (actuel) 53,8 % / 13,6 % ; `8` 73,7 % / 5,9 % ; `12` 89,6 % /
1,7 % ; `20` 98,6 % / 0,1 %.

### Un seul genre par morceau

[`SECONDARY_GENRE_SHARE`](../components/engine/functions.py#L36) a `0`.

### Changer le voisinage

[`NEIGHBOR_SIMILARITY`](../components/engine/functions.py#L33) et
[`POP_SIMILARITY`](../components/engine/functions.py#L34), dans les limites
de la partie 3. Pour l'ordre du cercle,
[`GENRE_CIRCLE`](../components/engine/functions.py#L25) : un genre retire
n'a plus de voisin.

### Regenerer les genres secondaires

```powershell
.\.venv\Scripts\python.exe -m pipeline genre-lists
```

Lit `%LOCALAPPDATA%\museme\out\deezer_genres.csv` (etape `deezer`), sans
requete. Le rattachement des sous-genres est dans
[`DEEZER_PARENT`](../pipeline/genres.py#L33). A relancer apres un ajout au
catalogue : les lignes absentes du fichier n'ont pas de genre secondaire.

### Revenir aux 63 descripteurs de 2021 (avant le 2026-10-10)

```powershell
git checkout dc9439f -- components/engine/functions.py
```

Redonne les descripteurs du CSV avec un poids du genre de 3. Le fichier
`data/embeddings_clap.npy` peut rester : il n'est alors plus lu. La commande
ecrase les modifications non commitees de `functions.py`.

### Revenir aux indicatrices (avant le 2026-10-09)

Partir de la version `dc9439f` ci-dessus. Dans `_similarity_space`, remplacer
le corps par :

```python
  df_rec = load_catalog().copy()
  df_rec = pd.concat([df_rec, df_rec["Main_Genre"].str.get_dummies()], axis=1)
  df_rec.drop(columns='Unnamed: 0', inplace=True)
  data = df_rec.set_index("Song")
  data = data.drop(columns=["Artist", "Album", "Preview", "Main_Genre", "Cover", 'family_genre'])
  data_scaled = preprocessing.scale(data)
  return df_rec, data_scaled
```

### Sauter de nouveau le meilleur voisin

Dans [`recommandation_cosine`](../components/engine/functions.py#L124),
remplacer `[0:11]` par `[1:12]`.

### Revenir a l'app Dash

```powershell
git checkout dash-final -- index.py app.py components/layout assets Procfile runtime.txt requirements.txt requirements-deploy.txt render.yaml
```

L'app Dash recalcule chaque recommandation a la demande avec le meme moteur ;
`render.yaml` redevient un service Python (gunicorn).

### Revenir entierement a `fb73ead`

```powershell
git diff fb73ead -- components/engine/functions.py index.py pipeline/merge.py   # voir les ecarts
git checkout fb73ead -- components/engine/functions.py index.py pipeline/merge.py # les annuler
```

Ces trois fichiers vont ensemble : `fb73ead` designe les morceaux par leur
titre, la version actuelle par leur numero de ligne. La seconde commande
ecrase les modifications non commitees de ces fichiers. `index.py` etant
l'app Dash, revenir d'abord a l'app Dash (ci-dessus).

## 6. Journal des modifications

Les liens de ce journal pointent vers le code actuel ; l'app Dash
(`index.py`, `components/layout/`) a ete retiree le 2026-10-11 et se
retrouve au tag `dash-final`.

**2026-10-09**

| Modification | Ou | Raison |
|---|---|---|
| Genre en indicatrices retire, essai de l'audio seul | [`_similarity_space`](../components/engine/functions.py#L87) | ne pas empecher de recommander un autre genre |
| Cercle, Pop au centre, poids 2 | idem | H7 ; abandonne le soir meme (H10) |
| Pop sur son axe, voisins 0,5, Pop / autres 0,3, poids 3 | [`_genre_similarity_root`](../components/engine/functions.py#L52) | H10 |
| Genres secondaires Deezer, poids 0,5 | [`_genre_weights`](../components/engine/functions.py#L67), [`write_genre_lists`](../pipeline/genres.py#L110), `data/genres_deezer.csv` | H12 |
| Meilleur voisin affiche | [`recommandation_cosine`](../components/engine/functions.py#L124) | H9 |
| Sans artiste choisi, la liste propose tous les titres | `display_titles_dropdown` (`index.py`, app Dash) | la liste etait vide : « dona » ne trouvait rien |
| Morceau designe par son numero de ligne | `input_data_extraction` (app Dash, retiree le 2026-10-11), [`recommandation_cosine`](../components/engine/functions.py#L109), `index.py` (app Dash) | 54 titres existent chez plusieurs artistes : choisir le *Baby* de Justin Bieber affichait celui de Brandy |

**2026-10-10**

| Modification | Ou | Raison |
|---|---|---|
| Audio decrit par les vecteurs CLAP (512 dimensions) au lieu des 63 descripteurs | [`_similarity_space`](../components/engine/functions.py#L87), [`CLAP_NPY`](../components/engine/functions.py#L20), `data/embeddings_clap.npy` | banc d'essai et ecoute a l'aveugle (partie 7) |
| Poids du genre : 3 → 4 | [`GENRE_WEIGHT`](../components/engine/functions.py#L40) | le poids 3 etait cale face a 63 colonnes ; recommander des morceaux proches, meme d'un autre genre |
| `embeddings` sur tout le catalogue ecrit `data/embeddings_clap.npy` et verifie l'app ; `merge` renvoie vers cette etape | [`publish`](../pipeline/embeddings.py#L90), [`merge.py`](../pipeline/merge.py#L34) | l'app refuse de demarrer s'il manque un vecteur |

**2026-10-11**

| Modification | Ou | Raison |
|---|---|---|
| Recommandations precalculees pour tout le catalogue, controlees morceau par morceau contre `recommandation_cosine` (4 724 / 4 724 identiques) | [`pipeline/site.py`](../pipeline/site.py), `web/data/` | la demo Render gratuite mettait 63 s a se reveiller et ~1,2 s par recommandation |
| L'app Dash devient un site statique, recherche unique dans le navigateur | [`web/`](../web/) | meme algorithme, aucun calcul en ligne |
| `embeddings` met a jour les donnees du site au lieu de verifier l'app | [`publish`](../pipeline/embeddings.py#L90) | le site lit `web/data/`, pas les vecteurs |

[`pipeline/validate_legacy.py`](../pipeline/validate_legacy.py#L24) garde
l'ancien espace (indicatrices) : la validation de l'extracteur n'a pas ete
relancee.

## 7. Chantier : analyser plus d'audio par morceau

### Ce qui est analyse aujourd'hui

- **La source** : l'extrait Spotify de chaque morceau, telecharge par
  [`features_for`](../pipeline/extract.py#L45). Il dure environ 30 s
  (mediane 29 s sur 200 extraits, minimum 15 s), en stereo 44,1 kHz. Les
  extraits recents sont souvent plus courts (20 a 24 s sur 4 des 6 morceaux
  testes).
- **L'extrait est analyse en entier** : [`load_legacy`](../pipeline/features_legacy.py#L70)
  ne coupe rien, et [`extract`](../pipeline/features_legacy.py#L143) calcule
  les descripteurs sur tout le signal.
- **Mais il est deforme**, volontairement, pour reproduire 2021 : la stereo
  est entrelacee et lue comme du mono a 22 050 Hz. 30 s d'extrait deviennent
  un signal de 116 s, ralenti 4 fois, transpose de deux octaves vers le bas,
  et la difference gauche/droite apparait dans les aigus. Les echantillons
  restent en entiers 16 bits non normalises.
- **Le morceau entier** (3 a 4 min) n'est jamais analyse : aucune source
  publique ne le fournit.

### Sources possibles

| Source | Duree | Couverture | Remarque |
|---|---|---|---|
| extrait Spotify (actuel) | ~30 s | tout le catalogue | pages embed, hors conditions developpeur |
| extrait Deezer | 30 s | ~4 200 morceaux trouves | API publique, deja utilisee pour les genres |
| extrait iTunes (Apple) | 30 s | non teste | API publique sans compte |
| morceau entier (YouTube…) | 3-4 min | non teste | contraire aux conditions d'utilisation et au droit d'auteur : deconseille |

**Spotify et Deezer couvrent-ils le meme passage ?** Test sur 6 morceaux
(correlation des formes d'onde) : sur *Sure Thing* (Miguel), les deux
extraits partagent environ 15 s ; sur les autres, ils couvrent surtout des
passages differents. Le test ne tranche pas tout : dans un morceau a boucles,
une boucle repetee ressemble autant que le meme passage. Combiner les deux
extraits donnerait donc environ 45 a 60 s d'audio distinct par morceau.

### Couts

- Extraction : 8 s par extrait, 17 s pour deux extraits bout a bout, soit
  environ 6 h pour tout le catalogue avec 4 processus.
- Tous les vecteurs changent : il faut tout recalculer, y compris les 3 815
  morceaux de 2021, et retelecharger leurs extraits (954 sont en cache).

### Mesurer l'amelioration

Indicateur de H13, calculable sans appel externe : part des morceaux dont un
autre titre du meme artiste est dans les 10 plus proches, en audio seul.
Reference actuelle : **32,2 %** (hasard : 1,3 %). Complement : part des
recommandations du meme genre en audio seul (24,1 %, hasard 9,7 %).

### Banc d'essai (2026-10-09) : resultats

Plan suivi : comparer plusieurs facons de decrire l'audio sur tout le
catalogue, en audio seul, puis departager a l'oreille. Outils :
[`features_v2.py`](../pipeline/features_v2.py),
[`embeddings.py`](../pipeline/embeddings.py),
[`ecoute.py`](../pipeline/ecoute.py) et le notebook
[`evaluation_audio.ipynb`](../notebooks/evaluation_audio.ipynb). L'app n'a
change qu'apres l'ecoute a l'aveugle (2026-10-10, ci-dessous).

| | Variante | Colonnes | Meme artiste | Meme genre | Eloigne |
|---|---|---|---|---|---|
| V0 | descripteurs de 2021 (CSV) | 63 | 32,2 % | 25,2 % | 34,2 % |
| V1 | audio lu correctement (mono 22 050 Hz), un MFCC par coefficient | 63 | 39,8 % | 28,8 % | 30,6 % |
| V2 | V1 + chroma, contraste, tonnetz, poly bande par bande | 109 | 34,5 % | 27,5 % | 30,7 % |
| V4 | V1 + contraste et poly bande par bande | 81 | 41,8 % | 29,5 % | 30,2 % |
| **V3** | **CLAP (`laion/larger_clap_general`), modele pre-entraine** | 512 | **61,7 %** | **46,4 %** | **17,5 %** |

Mesures sur les 4 724 morceaux, 10 plus proches voisins, sans genre. Ecarts
avec V0, intervalles de confiance a 95 % : V1 +7,6 points de meme artiste
[+6,1 ; +9,1], V4 +9,6 [+8,1 ; +11,1], **V3 +29,5 [+27,8 ; +31,2]**, avec
+21,2 points de meme genre et −16,7 points de sauts vers un genre eloigne.
V3 est en tete dans chacun des 17 genres, sur les deux mesures (detail :
partie 5 du notebook). Ecarts les plus nets, en part des voisins du meme
genre : Reggae 17 % → 70 %, Country 16 % → 67 %, R&B 12 % → 35 %.

- **La lecture corrigee fait le gros du gain des descripteurs** (+7,6 points
  de meme artiste). Exemples sans genre : *4 Minutes* → Charli XCX, Taylor
  Swift, Kim Petras, Britney Spears (V0 : Twisted Sister, Ratt) ; *Next To
  You* → Ciara, Yolanda Adams, Brandy, Sia (V0 : Cody Simpson, Andres
  Calamaro, Osees).
- **CLAP (V3), exemples sans genre** : *4 Minutes* → RAYE, Dua Lipa, Tate
  McRae, Justin Bieber, Nelly Furtado ; *Bad Moon Rising* → The Clean, The
  Rolling Stones, The Byrds, Allah-Las, The Kinks ; *Next To You* → Yolanda
  Adams, Ciara, K. Michelle, Brandy, Sevyn Streeter.
- **Poids des familles** (V1 = reference) : la chroma par bande fait perdre
  5 points (elle decrit surtout la tonalite) ; le contraste par bande en fait
  gagner, le poly par bande aussi ; baisser le poids des MFCC fait perdre
  (x0,5 : −3,0 ; familles equilibrees : −7,7) ; les augmenter n'apporte rien.
  Vp (V2, chroma par bande x0,3) : 38,7 %, sous V1.
- **Tempo** : en 2021, environ 75 % des morceaux tombaient entre 110 et 130 BPM (le
  signal ralenti ne laissait que la valeur par defaut de l'estimateur) ; en
  V1, ils s'etalent de 80 a 180 BPM.
- **Courbe de duree** (1 000 morceaux, fenetre au hasard dans l'extrait) :

  | Fenetre | 5 s | 10 s | 15 s | 20 s | 25 s |
  |---|---|---|---|---|---|
  | Reconnu 1er sur 4 724, V4 | 88 % | 96 % | 98 % | 99 % | 100 % |
  | Reconnu 1er sur 4 724, V3 | 79 % | | 98 % | | 100 % |
  | Recos identiques a l'extrait entier, V4 | 39 % | 54 % | 65 % | 74 % | 84 % |
  | Recos identiques a l'extrait entier, V3 | 40 % | | 63 % | | 79 % |

  Pas de palier, pour les descripteurs comme pour CLAP : les recommandations
  dependent du passage analyse. Plus d'audio les rendrait plus
  representatives du morceau entier ; meilleures a l'oreille, non verifie.
- **CLAP** : `laion/larger_clap_music` (prevu) est publie avec des couches de
  projection non entrainees (biais nuls) : tous ses vecteurs se ressemblent,
  zero-shot au hasard. Remplace par `laion/larger_clap_general` (Apache 2.0),
  qui classe correctement les morceaux tests. Les vecteurs du premier modele
  sont mis de cote (`out/embeddings_clap.invalide_larger_clap_music.csv`).
  Les vecteurs CLAP sont tous proches les uns des autres (cosinus ~0,9 entre
  deux morceaux au hasard) : ils sont centres-reduits avant le cosinus, comme
  les descripteurs.
- **Limite des mesures** : « meme artiste » recompense aussi l'effet album et
  production. L'ecoute a l'aveugle tranche.

**Ecoute a l'aveugle (rendue le 2026-10-10)** :
`%LOCALAPPDATA%\museme\out\ecoute.html`, 20 morceaux (les 5 exemples
ci-dessus et 15 tires au sort, un par genre), 277 propositions de V0, V4 et
V3 (5 premiers voisins de chacune, audio seul) melangees sans indiquer leur
origine, notees proche (2), moyen (1) ou sans rapport (0) par une seule
personne. Reponses : `Telechargements\ecoute_reponses.csv` ; cle :
`out/ecoute_cle.csv` ; resultats : derniere cellule du notebook.

| | Proche | Moyen | Sans rapport | Note moyenne [IC 95 %] |
|---|---|---|---|---|
| V0 | 17 % | 28 % | 55 % | 0,62 [0,43 ; 0,82] |
| V4 | 31 % | 34 % | 35 % | 0,96 [0,77 ; 1,17] |
| **V3** | **63 %** | 26 % | **11 %** | **1,52** [1,26 ; 1,71] |

- **Morceau par morceau** (note moyenne des 5 propositions) : V3 bat V0 sur
  17 morceaux, 2 egalites, 1 defaite (ecart +0,90 [+0,63 ; +1,16]) ; V3 bat
  V4 sur 16 (+0,56 [+0,34 ; +0,78]).
- **Lecture** : les notes sont relatives aux autres propositions du meme
  morceau (la moins coherente d'un bon lot peut etre « sans rapport ») et
  hesitent entre proche et moyen quand l'ambiance colle mais pas le genre.
  Les pourcentages ne sont donc pas des taux d'erreur absolus ; la
  comparaison morceau par morceau reste juste.
- **Autres genres** : les propositions d'un autre genre que le morceau sont
  jugees proches a 47 % pour V3, 21 % pour V4, 7 % pour V0.
- **Echecs de toutes les variantes** : *Down in Mexico* (The Coasters :
  capoeira et samba), *Nkrumah Dub* (King Tubby : electro pour V3).

**Poids du genre avec V3** (11 recommandations par morceau ; le poids 3 etait
cale face aux 63 descripteurs) :

| Poids | Meme genre | Eloigne | Meme artiste |
|---|---|---|---|
| app jusqu'au 2026-10-09 (V0, poids 3) | 86,6 % | 3,6 % | 53,1 % |
| 0 (V3 seul) | 45,9 % | 17,7 % | 63,2 % |
| **4** | **53,8 %** | **13,6 %** | **66,5 %** |
| 8 | 73,7 % | 5,9 % | 71,7 % |
| 12 | 89,6 % | 1,7 % | 74,5 % |

Parmi les 100 propositions de V3 ecoutees, le poids 4 en fait sortir 12 du
top 5, toutes d'un autre genre (6 proches, 3 sans rapport) ; le poids 8 en
fait sortir 29 (14 proches, 5 sans rapport). Leurs remplacantes n'ont pas ete
ecoutees : avec le poids 4, 89 des 100 premieres propositions l'avaient ete
(64 % proches, note moyenne 1,54).

**Decision (2026-10-10)** : V3 avec un poids du genre de 4, pour recommander
des morceaux proches meme d'un autre genre, quitte a quelques cas ambigus.

**Integration (2026-10-10)** : l'app lit `data/embeddings_clap.npy`
(4 724 x 512, float32, 9,7 Mo, identique a `out/embeddings_clap.csv`) ; Render
n'a pas besoin de torch. Le serveur local occupe 233 Mo apres une
recommandation. Par rapport a l'app precedente, 1,4 recommandation sur 11
reste la meme en moyenne. Les 909 ajouts de 2026 recommandent d'autres ajouts
de 2026 a 62,3 % (53,2 % avant), pour 19 % du catalogue. Chaque ajout au
catalogue demande le calcul CLAP en local : `python -m pipeline embeddings`
apres `merge`.

**Tout recalculer** (les calculs reprennent la ou ils se sont arretes ;
extraits Spotify en cache dans `%LOCALAPPDATA%\museme\previews`, 1,6 Go) :

```powershell
.\.venv\Scripts\python.exe -m pipeline features-v2 --workers 4      # V1, V2, V4 : ~1 h (estimation)
.\.venv\Scripts\python.exe -m pipeline embeddings                   # V3 : ~2 h 30 sur CPU
foreach ($w in 5, 10, 15, 20, 25) {                                  # courbe de duree
  .\.venv\Scripts\python.exe -m pipeline features-v2 --window $w --rows 1000
  .\.venv\Scripts\python.exe -m pipeline embeddings --window $w --rows 1000
}
```

`embeddings` sans `--window` ni `--rows` reecrit aussi
`data/embeddings_clap.npy`, lu par le moteur, puis les donnees du site.

### Ecoute ciblee Electro / Dance / Pop (2026-10-11)

**Pourquoi** : les recommandations de *Get Lucky* (Daft Punk) jugees
mauvaises : *那一端* (RubberBand), *Soy Tu Superhéroe* (Melendi), une charanga
cubaine, *Perdi Você* (Raça Negra). Pas d'erreur : le vecteur CLAP recalcule
depuis l'extrait est identique a celui du catalogue. En zero-shot, CLAP entend
*Get Lucky* comme du disco, puis french house et funk, mais il entend aussi ces
voisins comme du disco. A l'ecoute, ils partagent une ligne de basse et des
cocottes de guitare ; d'autres, des motifs de voix. Les autres titres de Daft
Punk arrivent au 63e rang ou au-dela.

**Effet de CLAP sur Electro / Dance** (10 recommandations) : depuis un depart
Electro ou Dance, 93 % des voisins etaient Electro ou Dance avec les 63
descripteurs (poids 3), 79 % avec CLAP x4, 90 % avec CLAP x8 ; le meme
artiste revient plus souvent avec CLAP (Electro : 31 % → 41 %).

**Ecoute** : trois reglages, top 10 melanges a l'aveugle : genre x4 (actuel),
x8 partout, x4 avec Electro et Dance a x8. 15 departs tires au sort (6
Electro, 5 Dance, 3 Pop, plus *Get Lucky*) ; **7 notes en entier** (3 Electro,
1 Dance, 3 Pop), 83 propositions. Page, cle et script d'analyse :
`%LOCALAPPDATA%\museme\out\ecoute_electro*` et `analyse_ecoute_electro.py`.

| Note moyenne du top 10 (0-2) | x4 | x8 | x4, Electro/Dance x8 |
|---|---|---|---|
| Tous les departs (7) | 1,23 | 1,27 | 1,26 |
| Electro (3) | 0,90 | 0,93 | 0,93 |
| Dance (1) | 0,9 | 1,0 | 1,0 |
| Pop (3) | 1,67 | 1,70 | 1,67 |

- Ecart avec x4, par depart : x8 +0,04 [−0,03 ; +0,11], Electro/Dance x8
  +0,03 [−0,03 ; +0,07] : pas de difference. x8 ne change qu'environ 2
  recommandations sur 10, et pas celles qui posent probleme.
- L'ecart est entre les genres : Electro et Dance 0,9, Pop 1,7, quel que soit
  le reglage. Les propositions du meme genre que le depart obtiennent 1,46,
  les autres 0,89.
- *Get Lucky* : LCD Soundsystem et Crazy P notes proches (meme groove et meme
  univers) ; la charanga, RubberBand et Raça Negra sans rapport (meme groove,
  autre univers).

**Decision (2026-10-11)** : garder x4. Le poids du genre ne corrige pas ces
cas : les 17 genres sont trop larges (« Electro » regroupe techno, house,
trip-hop, french touch). Les 8 departs non notes sont tous Electro ou Dance :
l'ecoute peut etre terminee plus tard (les reponses restent dans le
navigateur).

## 8. Pistes ouvertes

- **Signal de style** (2026-10-11) : CLAP rapproche par le jeu (basse,
  guitare, phrase de voix), pas par la scene, la langue ni la production.
  Piste : un modele entraine sur des styles (Discogs-EffNet, 400 styles
  Discogs ; compatibilite Windows a verifier ; MERT en repli), en complement
  de CLAP, puis ecoute a l'aveugle.
- **Reglages par l'utilisateur** (lot 2) : rester dans le style ou suivre le
  groove, meme tempo ou non. Faisable sur le site statique : tables de
  voisins par position du curseur, ou vecteurs en int8 et cosinus pondere
  recalcule dans le navigateur. Le `tempo` de 2021 est inutilisable ; celui
  de `features_v2.csv` (audio bien lu) reste a fiabiliser (erreurs du
  simple au double).

- **Revue des genres** : [`revue_genres.csv`](revue_genres.csv) liste
  997 morceaux a verifier (970 d'artistes classes dans plusieurs genres, 27
  sans genre avec une proposition). Colonne `Nouveau_genre` a remplir. Les
  corrections devront passer par le notebook, qui reecrit les genres du CSV.
- **Les 27 morceaux sans genre** : propositions dans la revue, a valider.
- **Artistes similaires Deezer** : reference externe possible pour noter les
  variantes (pour Madonna, 8 des 20 artistes lies sont dans le catalogue).
- **ACP blanchie (H5b)** et **morceaux proches du centre (H8)** : non
  explores (mesures faites avec les 63 descripteurs).
- **Ajouts de 2026 entre eux** : avec CLAP, 62 % des recommandations des 909
  ajouts vont vers d'autres ajouts (19 % du catalogue). Cause non etablie
  (epoque, production, extraits plus courts ?).
- **Versions d'un meme titre** (original et remaster, live d'un meme
  concert) : elles se suivent dans les recommandations.
- **Mesures non versionnees** : les scripts qui ont produit les chiffres de
  la partie 4 sont restes hors du depot.
