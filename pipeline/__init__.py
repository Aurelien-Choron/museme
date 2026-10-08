"""Pipeline d'alimentation du catalogue Museme (hors application).

Lance en local uniquement, jamais deploye : il depend de librosa / numba
(voir requirements-pipeline.txt), absents de l'image Render.

Usage : python -m pipeline <etape>   (python -m pipeline --help)
"""
import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
CATALOG_CSV = REPO_DIR / "data" / "df_recommendation.csv"
PLAYLISTS_CSV = Path(__file__).resolve().parent / "playlists.csv"

# Cache audio et sorties intermediaires hors OneDrive : des centaines de Mo
# de MP3 n'ont rien a faire dans un dossier synchronise.
WORK_DIR = Path(os.environ.get(
    "MUSEME_WORK_DIR",
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "museme",
))
AUDIO_DIR = WORK_DIR / "previews"
EMBED_CACHE_DIR = WORK_DIR / "embed_cache"
OUT_DIR = WORK_DIR / "out"
