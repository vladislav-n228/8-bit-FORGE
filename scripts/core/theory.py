# -*- coding: utf-8 -*-
"""Музыкальная теория и мелкие помощники: аккорды, лады, ноты, цвета, время."""

import numpy as np

from scripts.core.constants import NOTE_NAMES, PARENT_SCALE, SCALES


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def midi_to_freq(p):
    return 440.0 * 2.0 ** ((p - 69) / 12.0)


def midi_name(p):
    return f'{NOTE_NAMES[p % 12]}{p // 12 - 1}'


def fmt_time(sec):
    m = int(sec // 60)
    return f'{m:02d}:{sec - m * 60:04.1f}'


def bb(step):
    return f'{step // 16 + 1}.{(step % 16) // 4 + 1}'


def blend(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def parent_scale(song):
    return SCALES[PARENT_SCALE.get(song.scale, song.scale)]


def chord_at(song, step):
    if not song.chords:
        return 0
    return song.chords[(step // song.chord_steps) % len(song.chords)]


def chord_pcs(song, degree):
    sc = parent_scale(song)
    return [(song.key + sc[(degree + i) % 7]) % 12 for i in (0, 2, 4)]


def chord_name(song, degree):
    sc = parent_scale(song)
    r = sc[degree % 7]
    t, f = (sc[(degree + 2) % 7] - r) % 12, (sc[(degree + 4) % 7] - r) % 12
    q = {(4, 7): '', (3, 7): 'm', (3, 6): 'dim', (4, 8): '+'}.get((t, f), '')
    return NOTE_NAMES[(song.key + r) % 12] + q


def scale_pitches(song, lo, hi):
    pcs = {(song.key + i) % 12 for i in SCALES[song.scale]}
    res = [p for p in range(lo, hi + 1) if p % 12 in pcs]
    return res or list(range(lo, hi + 1))


def chord_pitches(song, degree, lo, hi):
    pcs = set(chord_pcs(song, degree))
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def nearest(lst, p):
    return min(lst, key=lambda x: abs(x - p))


def _rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32)
