"""python -m pipeline <etape>

Ordre normal : validate -> collect -> extract -> merge -> embeddings.
embeddings : vecteurs CLAP des nouveaux morceaux (data/embeddings_clap.npy),
sans lesquels l'app ne demarre pas.
Puis deezer : genres des morceaux, pour le classifieur (notebooks/),
et genre-lists : genres secondaires de l'app (data/genres_deezer.csv).
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
