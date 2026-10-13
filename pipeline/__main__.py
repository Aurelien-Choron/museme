"""python -m pipeline <etape>

Ordre normal : validate -> collect -> extract -> merge -> embeddings.
embeddings : vecteurs CLAP des nouveaux morceaux (data/embeddings_clap.npy),
puis donnees du site (web/data/, etape site, lancee d'office).
site : recommandations de tout le catalogue -> web/data/, a relancer seule
apres un changement des genres ou des reglages du moteur.
Puis deezer : genres des morceaux, pour le classifieur (notebooks/),
et genre-lists : genres secondaires de l'app (data/genres_deezer.csv).
spotify-ids : identifiant Spotify de chaque morceau (lecture complete du
site), puis site pour publier web/data/spotify.json.
Banc d'essai (hors catalogue) : features-v2, et embeddings avec --window ou --rows.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="step", required=True)

    p = sub.add_parser("validate", help="porte de validation de l'extracteur sur le catalogue")
    p.add_argument("--per-family", type=int, default=3)
    p.add_argument("--workers", type=int, default=4)

    sub.add_parser("collect", help="morceaux des playlists de playlists.csv (pages embed Spotify)")

    p = sub.add_parser("extract", help="descripteurs des morceaux collectes")
    p.add_argument("--workers", type=int, default=4)

    p = sub.add_parser("merge", help="ajout des nouveaux morceaux a data/df_recommendation.csv")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("deezer", help="genres Deezer des morceaux du catalogue (API publique)")
    p.add_argument("--workers", type=int, default=6)

    sub.add_parser("genre-lists", help="genres Deezer ramenes aux 17 genres -> data/genres_deezer.csv")

    p = sub.add_parser("features-v2", help="banc d'essai : descripteurs v2 (audio lu correctement)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--window", type=float, help="secondes analysees, a une position au hasard")
    p.add_argument("--rows", type=int, help="nombre de morceaux tires au hasard")

    p = sub.add_parser("embeddings", help="vecteurs CLAP du catalogue -> data/embeddings_clap.npy (banc d'essai avec --window / --rows)")
    p.add_argument("--window", type=float, help="secondes analysees, a une position au hasard")
    p.add_argument("--rows", type=int, help="nombre de morceaux tires au hasard")

    p = sub.add_parser("spotify-ids", help="identifiants Spotify des morceaux -> data/spotify_ids.csv")
    p.add_argument("--sample", type=int, help="essai sur N morceaux de 2021 tires au hasard")
    p.add_argument("--rematch", action="store_true",
                   help="reappliquer la regle aux morceaux deja cherches (depuis le cache)")
    p.add_argument("--max", type=int, dest="max_requests",
                   help="arret propre apres N recherches envoyees a Spotify (le cache ne compte pas)")

    p = sub.add_parser("site", help="catalogue et 10 voisins de chaque morceau -> web/data/")
    p.add_argument("--no-check", action="store_true",
                   help="sans le controle contre recommandation_cosine (~95 s)")

    args = parser.parse_args()

    if args.step == "validate":
        from . import validate_legacy
        return 0 if validate_legacy.run(per_family=args.per_family, workers=args.workers) else 1
    if args.step == "collect":
        from . import collect
        collect.run()
    elif args.step == "extract":
        from . import extract
        extract.run(workers=args.workers)
    elif args.step == "merge":
        from . import merge
        merge.run(dry_run=args.dry_run)
    elif args.step == "deezer":
        from . import deezer
        deezer.run(workers=args.workers)
    elif args.step == "genre-lists":
        from . import genres
        genres.write_genre_lists()
    elif args.step == "features-v2":
        from . import features_v2
        features_v2.run(workers=args.workers, window=args.window, n_rows=args.rows)
    elif args.step == "embeddings":
        from . import embeddings
        embeddings.run(window=args.window, n_rows=args.rows)
    elif args.step == "spotify-ids":
        from . import spotify_ids
        spotify_ids.run(sample=args.sample, rematch=args.rematch, max_requests=args.max_requests)
    elif args.step == "site":
        from . import site
        site.run(check=not args.no_check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
