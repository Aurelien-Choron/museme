"""CQT de librosa 0.8.1, reprise pour reproduire le tonnetz de 2021.

librosa 0.10 a reecrit la CQT (longueurs et normalisation des filtres) : sur
les extraits du catalogue, le tonnetz s'ecarte alors d'environ 1 % des valeurs
stockees. Ce module reprend l'implementation 0.8.1 pour le seul cas utilise
par le pipeline (cqt, gamma=0, parametres par defaut) et s'appuie sur
librosa 0.11 pour le reste (stft, resample, estimate_tuning, normalize...),
dont le comportement est identique entre les deux versions.

Code d'origine : librosa 0.8.1, core/constantq.py et filters.py.
Copyright (c) 2013--2017, librosa development team. Licence ISC.
"""
import librosa
import numpy as np
import resampy

BW_FASTEST = resampy.filters.get_filter("kaiser_fast")[2]


def _float_window(window, n):
    """Fenetre de longueur ceil(n), nulle a partir de floor(n)."""
    n_min, n_max = int(np.floor(n)), int(np.ceil(n))
    w = librosa.filters.get_window(window, n_min)
    if len(w) < n_max:
        w = np.pad(w, [(0, n_max - len(w))], mode="constant")
    w[n_min:] = 0.0
    return w


def _constant_q_lengths(sr, fmin, n_bins, bins_per_octave, window, filter_scale):
    alpha = 2.0 ** (1.0 / bins_per_octave) - 1.0
    Q = float(filter_scale) / alpha
    freq = fmin * (2.0 ** (np.arange(n_bins, dtype=float) / bins_per_octave))
    if freq[-1] * (1 + 0.5 * librosa.filters.window_bandwidth(window) / Q) > sr / 2.0:
        raise librosa.ParameterError("Filter pass-band lies beyond Nyquist")
    return Q * sr / freq


def _constant_q(sr, fmin, n_bins, bins_per_octave, window, filter_scale, norm):
    lengths = _constant_q_lengths(sr, fmin, n_bins, bins_per_octave, window, filter_scale)
    freqs = fmin * (2.0 ** (np.arange(n_bins, dtype=float) / bins_per_octave))

    filters = []
    for ilen, freq in zip(lengths, freqs):
        sig = np.exp(np.arange(-ilen // 2, ilen // 2, dtype=float) * 1j * 2 * np.pi * freq / sr)
        sig = sig * _float_window(window, len(sig))
        filters.append(librosa.util.normalize(sig, norm=norm))

    max_len = int(2.0 ** (np.ceil(np.log2(max(lengths)))))
    filters = np.asarray(
        [librosa.util.pad_center(f, size=max_len) for f in filters], dtype=np.complex64)
    return filters, np.asarray(lengths)


def _cqt_filter_fft(sr, fmin, n_bins, bins_per_octave, filter_scale, norm, sparsity, window, dtype):
    basis, lengths = _constant_q(sr, fmin, n_bins, bins_per_octave, window, filter_scale, norm)
    n_fft = basis.shape[1]
    basis *= lengths[:, np.newaxis] / float(n_fft)
    # numpy < 2 calculait toujours la FFT en double precision ; numpy 2
    # garde le complex64 du filtre. On force la double precision de 2021.
    fft_basis = np.fft.fft(basis.astype(np.complex128), n=n_fft, axis=1)[:, : (n_fft // 2) + 1]
    fft_basis = librosa.util.sparsify_rows(fft_basis, quantile=sparsity, dtype=dtype)
    return fft_basis, n_fft


def _cqt_response(y, n_fft, hop_length, fft_basis, pad_mode, dtype):
    D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length, window="ones",
                     pad_mode=pad_mode, dtype=dtype)
    return fft_basis.dot(D)


def _num_two_factors(x):
    if x <= 0:
        return 0
    num_twos = 0
    while x % 2 == 0:
        num_twos += 1
        x //= 2
    return num_twos


def _early_downsample(y, sr, hop_length, res_type, n_octaves, nyquist, filter_cutoff):
    count1 = max(0, int(np.ceil(np.log2(BW_FASTEST * nyquist / filter_cutoff)) - 1) - 1)
    count2 = max(0, _num_two_factors(hop_length) - n_octaves + 1)
    downsample_count = min(count1, count2)

    if downsample_count > 0 and res_type == "kaiser_fast":
        factor = 2 ** downsample_count
        hop_length //= factor
        new_sr = sr / float(factor)
        y = librosa.resample(y, orig_sr=sr, target_sr=new_sr, res_type=res_type, scale=True)
        sr = new_sr

    return y, sr, hop_length


def _trim_stack(cqt_resp, n_bins, dtype):
    max_col = min(c_i.shape[-1] for c_i in cqt_resp)
    cqt_out = np.empty((n_bins, max_col), dtype=dtype, order="F")
    end = n_bins
    for c_i in cqt_resp:
        n_oct = c_i.shape[0]
        if end < n_oct:
            cqt_out[:end] = c_i[-end:, :max_col]
        else:
            cqt_out[end - n_oct: end] = c_i[:, :max_col]
        end -= n_oct
    return cqt_out


def cqt(y, sr=22050, hop_length=512, fmin=None, n_bins=84, bins_per_octave=12,
        tuning=0.0, filter_scale=1, norm=1, sparsity=0.01, window="hann",
        pad_mode="reflect"):
    """librosa 0.8.1 cqt (scale=True, res_type automatique)."""
    n_octaves = int(np.ceil(float(n_bins) / bins_per_octave))
    n_filters = min(bins_per_octave, n_bins)
    alpha = 2.0 ** (1.0 / bins_per_octave) - 1
    dtype = librosa.util.dtype_r2c(y.dtype)

    if fmin is None:
        fmin = librosa.note_to_hz("C1")
    if tuning is None:
        tuning = librosa.estimate_tuning(y=y, sr=sr, bins_per_octave=bins_per_octave)
    fmin = fmin * 2.0 ** (tuning / bins_per_octave)

    freqs = librosa.cqt_frequencies(n_bins=n_bins, fmin=fmin, bins_per_octave=bins_per_octave)
    freqs = freqs[-bins_per_octave:]
    fmin_t, fmax_t = np.min(freqs), np.max(freqs)

    Q = float(filter_scale) / alpha
    filter_cutoff = fmax_t * (1 + 0.5 * librosa.filters.window_bandwidth(window) / Q)
    nyquist = sr / 2.0
    res_type = "kaiser_fast" if filter_cutoff < BW_FASTEST * nyquist else "kaiser_best"

    y, sr, hop_length = _early_downsample(
        y, sr, hop_length, res_type, n_octaves, nyquist, filter_cutoff)

    responses = []
    if res_type != "kaiser_fast":
        # Octave du haut a pleine resolution, puis reechantillonnage rapide.
        fft_basis, n_fft = _cqt_filter_fft(
            sr, fmin_t, n_filters, bins_per_octave, filter_scale, norm, sparsity, window, dtype)
        responses.append(_cqt_response(y, n_fft, hop_length, fft_basis, pad_mode, dtype))
        fmin_t /= 2
        n_octaves -= 1
        res_type = "kaiser_fast"

    my_y, my_sr, my_hop = y, sr, hop_length
    for i in range(n_octaves):
        if i > 0:
            my_y = librosa.resample(my_y, orig_sr=2, target_sr=1, res_type=res_type, scale=True)
            my_sr /= 2.0
            my_hop //= 2
        fft_basis, n_fft = _cqt_filter_fft(
            my_sr, fmin_t * 2.0 ** -i, n_filters, bins_per_octave, filter_scale, norm,
            sparsity, window, dtype)
        fft_basis = fft_basis * np.sqrt(2 ** i)
        responses.append(_cqt_response(my_y, n_fft, my_hop, fft_basis, pad_mode, dtype))

    V = _trim_stack(responses, n_bins, dtype)
    lengths = _constant_q_lengths(sr, fmin, n_bins, bins_per_octave, window, filter_scale)
    return V / np.sqrt(lengths[:, np.newaxis])
