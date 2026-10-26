# -*- coding: utf-8 -*-
"""Классический генератор 8-битных звуковых эффектов (окно «Звуковые эффекты»)."""

import random

import numpy as np

from scripts.audio.synth import _quant_tri


def _sfx_tone(f0, f1, dur, sr, wave='square', duty=.5, decay=4.0, vib=0.0, vol=1.0, rng=None, fm=False):
    n = max(1, int(dur * sr))
    t = np.arange(n) / sr
    f = f0 * (f1 / f0) ** (t / dur) if f0 > 0 and f1 > 0 else np.full(n, max(f0, 1.0))
    if vib:
        f = f * (1 + vib * np.sin(2 * np.pi * 11 * t))
    ph = np.cumsum(f) / sr
    if fm:
        y = np.sin(2 * np.pi * ph + 2.5 * np.exp(-t * 6) * np.sin(2 * np.pi * ph * 2))
    elif wave == 'square':
        y = np.where((ph % 1) < duty, 1.0, -1.0) - (2 * duty - 1)
    elif wave == 'tri':
        y = _quant_tri(ph)
    elif wave == 'noise':
        rate = np.clip(f, 30, sr / 2)
        idx = np.floor(np.cumsum(rate / sr)).astype(int)
        v = (rng or np.random.default_rng()).uniform(-1, 1, idx[-1] + 2)
        y = v[idx]
    else:
        y = np.sin(2 * np.pi * ph)
    env = np.minimum(1.0, t / 0.002) * np.exp(-t * decay)
    return y * env * vol


def _mix(*parts):
    n = max(len(p) for p in parts)
    return sum(np.pad(p, (0, n - len(p))) for p in parts)


def _notes(freqs, durs, sr, **kw):
    return np.concatenate([_sfx_tone(f, f, d, sr, **kw) for f, d in zip(freqs, durs)])


def _semi(base, st):
    return base * 2 ** (st / 12.0)


SFX_TYPES = {
    'Прыжок': lambda p, L, sr, r, k: _sfx_tone(260 * p, 760 * p, .2 * L, sr, duty=r.choice([.25, .5]), decay=6, **k),
    'Монетка': lambda p, L, sr, r, k: np.concatenate([_sfx_tone(988 * p, 988 * p, .06 * L, sr, duty=.25, decay=0, **k),
                                                       _sfx_tone(1319 * p, 1319 * p, .34 * L, sr, duty=.25, decay=9, **k)]),
    'Взрыв': lambda p, L, sr, r, k: _mix(_sfx_tone(2200 * p, 60, .9 * L, sr, wave='noise', decay=3.5, rng=r.np),
                                         _sfx_tone(90 * p, 30, .9 * L, sr, wave='sine', decay=6, vol=.7)),
    'Лазер / выстрел': lambda p, L, sr, r, k: _sfx_tone(1800 * p, 160 * p, .22 * L, sr, duty=.125, decay=10, **k),
    'Усиление (power-up)': lambda p, L, sr, r, k: _notes(
        [_semi(262 * p, s) for s in (0, 4, 7, 12, 16, 19, 24, 28, 31, 36)], [.045 * L] * 9 + [.25 * L], sr,
        duty=.25, decay=3, **k),
    'Урон': lambda p, L, sr, r, k: np.concatenate([_sfx_tone(3000, 800, .06 * L, sr, wave='noise', decay=8, rng=r.np),
                                                   _sfx_tone(420 * p, 90 * p, .25 * L, sr, duty=.5, decay=8, **k)]),
    'Game Over': lambda p, L, sr, r, k: _notes([_semi(523 * p, s) for s in (0, -1, -2, -3, -7, -12)],
                                               [.17 * L] * 5 + [.7 * L], sr, wave='tri', decay=1.5, vib=.012),
    'Победа (джингл)': lambda p, L, sr, r, k: _notes([_semi(523 * p, s) for s in (0, 4, 7, 12, 7, 12)],
                                                     [.1 * L, .1 * L, .1 * L, .3 * L, .1 * L, .55 * L], sr, duty=.25,
                                                     decay=2.5, **k),
    'Меню / выбор': lambda p, L, sr, r, k: np.concatenate([_sfx_tone(880 * p, 880 * p, .04 * L, sr, decay=0, **k),
                                                           _sfx_tone(1320 * p, 1320 * p, .07 * L, sr, decay=20, **k)]),
    'Телепорт': lambda p, L, sr, r, k: _sfx_tone(180 * p, 2200 * p, .6 * L, sr, wave='sine', vib=.08, decay=1.5),
    'Подбор предмета': lambda p, L, sr, r, k: _notes([660 * p, 990 * p, 1320 * p], [.05 * L, .05 * L, .14 * L], sr,
                                                     duty=.5, decay=6, **k),
    'Новая жизнь (1UP)': lambda p, L, sr, r, k: _notes(
        [_semi(659 * p, s) for s in r.sample([0, 2, 4, 7, 9, 12, 14, 16], 5) + [24]], [.08 * L] * 5 + [.3 * L], sr,
        duty=.25, decay=3, **k),
    'Пауза': lambda p, L, sr, r, k: _notes([1200 * p, 900 * p, 1200 * p], [.05 * L, .05 * L, .09 * L], sr,
                                           duty=.5, decay=8, **k),
    'Шаг': lambda p, L, sr, r, k: _sfx_tone(900 * p, 300 * p, .05 * L, sr, wave='noise', decay=40, rng=r.np),
    'Тревога': lambda p, L, sr, r, k: _notes([880 * p, 660 * p] * 4, [.12 * L] * 8, sr, duty=.5, decay=1, **k),
    'Удар мечом': lambda p, L, sr, r, k: _mix(_sfx_tone(5000, 900, .16 * L, sr, wave='noise', decay=14, rng=r.np) * .8,
                                              _sfx_tone(700 * p, 300 * p, .12 * L, sr, duty=.125, decay=18, **k) * .5),
}


class _SfxRng(random.Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.np = np.random.default_rng(seed)


def render_sfx(kind, seed, pitch=1.0, length=1.0, chip='nes', crush=True, sr=44100):
    """Возвращает стерео float32. Каждый seed — новая вариация того же типа звука."""
    r = _SfxRng(seed)
    p = pitch * r.uniform(.88, 1.14)
    L = length * r.uniform(.88, 1.14)
    kw = {'fm': True} if chip == 'sega' else {}
    y = np.asarray(SFX_TYPES[kind](p, L, sr, r, kw), dtype=np.float64)
    if crush:
        y = np.round(y * 15) / 15
        y = y[(np.arange(len(y)) // 2) * 2]
    k = min(len(y), int(.006 * sr))
    if k:
        y[-k:] *= np.linspace(1, 0, k)
    y /= max(1e-6, float(np.max(np.abs(y))))
    y *= 0.89
    return np.column_stack([y, y]).astype(np.float32)
