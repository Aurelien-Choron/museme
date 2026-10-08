"""python -m pipeline <etape>

Ordre normal : validate -> collect -> extract -> merge.
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
