"""Les 63 descripteurs audio du catalogue, port fidele du pipeline de 2021.

Sources retrouvees : Downloads/66_features.ipynb (cellule 5, analyze_music) et
_archive/Dash_music/music2/components/engine/functions.py (analyze_music_reco).
Calcule en 2021 avec librosa 0.8, porte ici sur librosa 0.11.

Les particularites suivantes sont VOLONTAIRES. Elles reproduisent les vecteurs
de data/df_recommendation.csv ; les corriger rendrait les nouveaux morceaux
incomparables aux anciens.

- Decodage pydub -> get_array_of_samples() -> float : echantillons entiers
  16 bits, non normalises dans [-1, 1] (rms_mean ~ 8000 au lieu de ~0.2).
- Les extraits Spotify sont des MP3 stereo 44,1 kHz : get_array_of_samples
  entrelace G/D en un seul vecteur, analyse comme du mono a sr=22050. Le code
  d'origine passait sr=22050 a pydub, qui l'ignore.
- mfcc{k}_mean / mfcc{k}_var : moyenne / variance de mfcc(n_mfcc=k), donc des
  k premiers coefficients pris ensemble, pas du k-ieme seul.
- chroma, contrast, poly, tonnetz : moyenne / variance sur toutes les bandes
  et toutes les trames.
- tonnetz sur harmonic(harmonic(y, margin=3)), onset sur
  percussive(percussive(y, margin=3)) : marge 3, puis marge 1 par defaut.

Ecarts de librosa 0.8 -> 0.11 neutralises ici :
- remplissage des trames : 'reflect' en 0.8, 'constant' depuis 0.10 ;
- effects.harmonic / percussive : en 0.8, l'istft est faite sans longueur
  cible puis completee par des zeros (les ~500 derniers echantillons valent
  0) ; depuis 0.10 ils sont reconstruits ;
- CQT (tonnetz) reecrite en 0.10 : celle de 0.8.1 est reprise dans _cqt08 ;
- librosa.beat.tempo -> librosa.feature.tempo.

Optimisations sans effet sur les valeurs (verifie a l'identique bit a bit) :
- chaque descripteur n'est calcule qu'une fois (le code d'origine le faisait
  pour la moyenne puis pour la variance, et 40 fois pour les MFCC : la DCT
  orthonormee etant tronquee, mfcc(n_mfcc=k) == mfcc(n_mfcc=20)[:k]) ;
- une seule STFT du signal, partagee par les descripteurs spectraux, HPSS et
  le spectrogramme mel (MFCC, tempo) ;
- les filtres medians de HPSS ne dependent pas de la marge : calcules une
  fois pour les marges 1 et 3, par une mediane glissante compilee (numba)
  5 fois plus rapide que scipy.ndimage.median_filter ;
- STFT / iSTFT par blocs de 64 Mo au lieu de 256 Ko (MAX_MEM_BLOCK).
"""
import librosa
import numba
import numpy as np
from pydub import AudioSegment

from . import _cqt08

SR = 22050
PAD_MODE = "reflect"
HPSS_KERNEL = 31

# Taille des blocs de calcul des STFT : n'affecte que la vitesse.
librosa.util.MAX_MEM_BLOCK = 2 ** 26

FEATURE_COLUMNS = (
    ["chroma_stft_mean", "chroma_stft_var", "rms_mean", "rms_var",
     "spectral_centroid_mean", "spectral_centroid_var",
     "spectral_bandwidth_mean", "spectral_bandwidth_var",
     "rolloff_mean", "rolloff_var",
     "zero_crossing_rate_mean", "zero_crossing_rate_var",
     "harmony_mean", "harmony_var", "tempo"]
    + [f"mfcc{k}_{stat}" for k in range(1, 21) for stat in ("mean", "var")]
    + ["spectral_contrast_mean", "spectral_contrast_var",
       "polyfeat_mean", "polyfeat_var", "tonnetz_mean", "tonnetz_var",
       "onset_mean", "onset_var"]
)


def load_legacy(path):
    """Decodage identique a 2021 : stereo entrelacee, echelle int16."""
    sound = AudioSegment.from_file(str(path))
    return np.array(sound.get_array_of_samples()).astype(float)


@numba.njit(cache=True)
def _running_median(padded, k, out):
    """Mediane glissante de largeur k sur chaque ligne (fenetre triee)."""
    rows, n = out.shape
    half = k // 2
    win = np.empty(k)
    for r in range(rows):
        for j in range(k):
            win[j] = padded[r, j]
        win.sort()
        out[r, 0] = win[half]
        for i in range(1, n):
            old = padded[r, i - 1]
            new = padded[r, i + k - 1]
            pos = np.searchsorted(win, old)
            for j in range(pos, k - 1):
                win[j] = win[j + 1]
            ins = np.searchsorted(win[:k - 1], new)
            for j in range(k - 1, ins, -1):
                win[j] = win[j - 1]
            win[ins] = new
            out[r, i] = win[half]


def _median_filter(S, axis):
    """scipy.ndimage.median_filter(S, mode='reflect') le long d'un axe."""
    x = np.ascontiguousarray(S if axis == 1 else S.T)
    half = HPSS_KERNEL // 2
    padded = np.pad(x, ((0, 0), (half, half)), mode="symmetric")
    out = np.empty(x.shape)
    _running_median(padded, HPSS_KERNEL, out)
    return out if axis == 1 else out.T


def _hpss(D, margins=(1.0,)):
    """librosa.decompose.hpss(D, margin=m) pour chaque marge -> [(H, P), ...]."""
    S, phase = librosa.magphase(D)
    harm = _median_filter(S, axis=1)
    perc = _median_filter(S, axis=0)
    parts = []
    for margin in margins:
        split_zeros = margin == 1
        mask_harm = librosa.util.softmask(harm, perc * margin, power=2.0, split_zeros=split_zeros)
        mask_perc = librosa.util.softmask(perc, harm * margin, power=2.0, split_zeros=split_zeros)
        parts.append(((S * mask_harm) * phase, (S * mask_perc) * phase))
    return parts


def _istft_08(D, n):
    """iSTFT de librosa 0.8 effects.* : sans longueur cible, completee de zeros."""
    return librosa.util.fix_length(librosa.istft(D, dtype=np.float64), size=n)


def _stft(y):
    return librosa.stft(y, pad_mode=PAD_MODE)


def _chroma_cqt_08(y, sr):
    """chroma_cqt de librosa 0.8 : 7 octaves de 36 bandes, accordage estime."""
    bins_per_octave = 36
    C = np.abs(_cqt08.cqt(
        y, sr=sr, n_bins=7 * bins_per_octave, bins_per_octave=bins_per_octave,
        tuning=None, pad_mode=PAD_MODE,
    ))
    return librosa.feature.chroma_cqt(C=C, sr=sr, bins_per_octave=bins_per_octave)


def extract(y, sr=SR):
    """Les 63 descripteurs, dans l'ordre des colonnes du catalogue."""
    out = {}

    def mean_var(name, values):
        out[f"{name}_mean"] = float(np.mean(values))
        out[f"{name}_var"] = float(np.var(values))

    n = len(y)
    D = _stft(y)
    S = np.abs(D)
    log_mel = librosa.power_to_db(librosa.feature.melspectrogram(S=S ** 2, sr=sr))
    (harm_1, _), (harm_3, perc_3) = _hpss(D, margins=(1.0, 3.0))

    mean_var("chroma_stft", librosa.feature.chroma_stft(S=S ** 2, sr=sr))
    mean_var("rms", librosa.feature.rms(y=y, pad_mode=PAD_MODE))
    mean_var("spectral_centroid", librosa.feature.spectral_centroid(S=S, sr=sr))
    mean_var("spectral_bandwidth", librosa.feature.spectral_bandwidth(S=S, sr=sr))
    mean_var("rolloff", librosa.feature.spectral_rolloff(S=S, sr=sr))
    mean_var("zero_crossing_rate", librosa.feature.zero_crossing_rate(y))
    mean_var("harmony", _istft_08(harm_1, n))

    onset_env = librosa.onset.onset_strength(S=log_mel, sr=sr)
    out["tempo"] = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])

    mfcc = librosa.feature.mfcc(S=log_mel, n_mfcc=20)
    for k in range(1, 21):
        mean_var(f"mfcc{k}", mfcc[:k])

    mean_var("spectral_contrast", librosa.feature.spectral_contrast(S=S, sr=sr))
    mean_var("polyfeat", librosa.feature.poly_features(S=S, sr=sr))

    y_harm = _istft_08(_hpss(_stft(_istft_08(harm_3, n)))[0][0], n)
    mean_var("tonnetz", librosa.feature.tonnetz(chroma=_chroma_cqt_08(y_harm, sr), sr=sr))

    y_perc = _istft_08(_hpss(_stft(_istft_08(perc_3, n)))[0][1], n)
    mean_var("onset", librosa.onset.onset_strength(y=y_perc, sr=sr, pad_mode=PAD_MODE))

    return {col: out[col] for col in FEATURE_COLUMNS}
