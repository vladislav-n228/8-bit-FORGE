# -*- coding: utf-8 -*-
"""Громкость для соцсетей (LUFS, ITU-R BS.1770) и лимитер."""

import math

import numpy as np


LOUDNESS_TARGETS = {'-14 LUFS — YouTube / Spotify': -14.0, '-16 LUFS — Apple / подкасты': -16.0,
                    '-11 LUFS — TikTok / Reels (громко)': -11.0, '-9 LUFS — максимально громко': -9.0,
                    'Без выравнивания': None}


_K_CACHE = {}


def _biquad_response(b, a, w, cs=None):
    c1, s1 = cs if cs is not None else (np.cos(w), np.sin(w))
    c2, s2 = 2 * c1 * c1 - 1, 2 * s1 * c1  # cos 2w, sin 2w без второй экспоненты
    num = (b[0] + b[1] * c1 + b[2] * c2) - 1j * (b[1] * s1 + b[2] * s2)
    den = (a[0] + a[1] * c1 + a[2] * c2) - 1j * (a[1] * s1 + a[2] * s2)
    return num / den


def _k_filter(nf, sr):
    """АЧХ K-фильтра (полка +4 дБ над 1.5 кГц и срез ниже 38 Гц) для БПФ длины nf; кэшируется —
    при нормализации громкость меряется дважды на одной длине."""
    key = (nf, sr)
    H = _K_CACHE.get(key)
    if H is not None:
        return H
    A = 10 ** (4.0 / 40)
    w0 = 2 * math.pi * 1500.0 / sr
    al = math.sin(w0) / (2 * (1 / math.sqrt(2)))
    c = math.cos(w0)
    shelf_b = (A * ((A + 1) + (A - 1) * c + 2 * math.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * c),
               A * ((A + 1) + (A - 1) * c - 2 * math.sqrt(A) * al))
    shelf_a = ((A + 1) - (A - 1) * c + 2 * math.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * c),
               (A + 1) - (A - 1) * c - 2 * math.sqrt(A) * al)
    w0 = 2 * math.pi * 38.0 / sr
    al, c = math.sin(w0) / (2 * 0.5), math.cos(w0)
    hp_b, hp_a = ((1 + c) / 2, -(1 + c), (1 + c) / 2), (1 + al, -2 * c, 1 - al)
    w = 2 * math.pi * np.fft.rfftfreq(nf)
    cs = (np.cos(w), np.sin(w))
    H = _biquad_response(shelf_b, shelf_a, w, cs) * _biquad_response(hp_b, hp_a, w, cs)
    _K_CACHE.clear()
    _K_CACHE[key] = H
    return H


def _fast_len(n):
    """Ближайшая длина ≥ n из множителей 2, 3, 5 — БПФ такой длины в разы быстрее, чем длины трека «как есть»."""
    best = 1 << max(0, (n - 1).bit_length())
    p5 = 1
    while p5 < best:
        p35 = p5
        while p35 < best:
            p = p35 * (1 << max(0, (-(-n // p35) - 1).bit_length()))
            best = min(best, p)
            p35 *= 3
        p5 *= 5
    return best


def measure_lufs(audio, sr):
    """Интегральная громкость: K-фильтр (в частотной области) + стробирование блоками 400 мс."""
    n = len(audio)
    if n < int(0.4 * sr):
        return -70.0
    nf = _fast_len(n)  # с запасом нулей: быстрее и без «заворота» фильтра с конца трека в начало
    H = _k_filter(nf, sr)
    power = np.zeros(n)
    for ch in range(audio.shape[1]):
        y = np.fft.irfft(np.fft.rfft(audio[:, ch].astype(np.float64), nf) * H, nf)[:n]
        power += y * y
    blk, hop = int(0.4 * sr), int(0.1 * sr)
    cs = np.concatenate([[0.0], np.cumsum(power)])
    starts = np.arange(0, n - blk + 1, hop)
    z = (cs[starts + blk] - cs[starts]) / blk
    z = z[z > 0]
    if not len(z):
        return -70.0
    lk = -0.691 + 10 * np.log10(z)
    z = z[lk > -70]
    if not len(z):
        return -70.0
    rel = -0.691 + 10 * math.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > rel]
    return float(-0.691 + 10 * math.log10(z.mean())) if len(z) else -70.0


def limit_peaks(audio, sr, ceiling=0.891, block=256):
    """Простой лимитер: мгновенная атака, плавное отпускание, потолок −1 dBFS."""
    n = len(audio)
    pk = np.abs(audio).max(axis=1)
    nb = (n + block - 1) // block
    pk = np.concatenate([pk, np.zeros(nb * block - n)]).reshape(nb, block).max(axis=1)
    g = np.minimum(1.0, ceiling / np.maximum(pk, 1e-9))
    g = np.minimum(g, np.minimum(np.concatenate([g[1:], [1.0]]), np.concatenate([[1.0], g[:-1]])))
    rel = block / (0.15 * sr)
    # плавное отпускание: gs[i] = min(g[i], gs[i-1] + rel) — то же самое без цикла через накопленный минимум
    ramp = np.arange(nb) * rel
    gs = np.minimum.accumulate(g - ramp) + ramp
    gain = np.interp(np.arange(n), np.arange(nb) * block + block / 2, gs)
    return np.clip(audio * gain[:, None].astype(np.float32), -ceiling, ceiling).astype(np.float32)


def normalize_loudness(audio, sr, target):
    if target is None:
        return audio, None
    lufs = measure_lufs(audio, sr)
    if lufs <= -69:
        return audio, lufs
    out = limit_peaks(audio * np.float32(10 ** ((target - lufs) / 20)), sr)
    return out, measure_lufs(out, sr)
