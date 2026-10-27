# -*- coding: utf-8 -*-
"""Shared by the Forge models: chat options, text parsing, helpers."""

import re

import numpy as np

from scripts.core import i18n
from scripts.core.constants import NOTE_NAMES
from scripts.core.i18n import T


AI_ANY = 'По запросу'


AI_DURATIONS = {AI_ANY: None, '3 секунды': 3, '5 секунд': 5, '10 секунд': 10, '15 секунд': 15, '30 секунд': 30,
                '45 секунд': 45, '1 минута': 60, '1.5 минуты': 90, '2 минуты': 120, '3 минуты': 180}


AI_VOCALS = {AI_ANY: None, 'С вокалом': True, 'Без вокала': False}


AI_MASTER = dict(volume=.8, sr=44100, bits=16, downsample=1, smooth=0, nes_env=True, normalize=True)


RU_NOTES = ['до', 'до♯', 'ре', 'ре♯', 'ми', 'фа', 'фа♯', 'соль', 'соль♯', 'ля', 'ля♯', 'си']


_EN_MODES = {'Dorian', 'Phrygian', 'Lydian', 'Mixolydian'}


def key_text(key, scale):
    """Key for the reply text: «ля минор» / "A minor", "C Dorian"."""
    if i18n.LANG == 'ru':
        return f'{RU_NOTES[key]} {scale.lower()}'
    name = T(scale)
    return f'{NOTE_NAMES[key]} {name if name in _EN_MODES else name.lower()}'


_EN_MODES = {'Dorian', 'Phrygian', 'Lydian', 'Mixolydian'}


def key_text(key, scale):
    """Key for the reply text: «ля минор» / "A minor", "C Dorian"."""
    if i18n.LANG == 'ru':
        return f'{RU_NOTES[key]} {scale.lower()}'
    name = T(scale)
    return f'{NOTE_NAMES[key]} {name if name in _EN_MODES else name.lower()}'


AI_NEG = {'не', 'без', 'no', 'not', 'нет', 'ни', 'without', 'non', 'never'}


AI_INTENS = {'очень', 'супер', 'максимально', 'оч', 'крайне', 'very', 'super', 'самый', 'самая', 'самое', 'мега',
             'дико', 'безумно', 'реально', 'по-настоящему', 'really', 'extremely', 'ultra', 'so', 'totally',
             'insanely', 'mega', 'truly', 'most'}


def _ai_words(text):
    t = text.lower().replace('ё', 'е')
    return t, re.findall(r'[a-zа-я0-9\-]+', t)


def _ai_match(t, words, stems):
    """Positions of words that matched the stems. "=word" is an exact match; a phrase with a space is searched as a whole (-1)."""
    out = []
    for s in stems:
        if ' ' in s:
            if s in t:
                out.append(-1)
        elif s[0] == '=':
            out += [i for i, w in enumerate(words) if w == s[1:]]
        else:
            out += [i for i, w in enumerate(words) if w.startswith(s)]
    return out


def _ai_strength(t, words, stems):
    """0 — not found, 1 — found, 1.6 — with an intensifier ("very sad"), -1 — negated ("not fast")."""
    best = 0.0
    for i in _ai_match(t, words, stems):
        prev = words[i - 1] if i > 0 else ''
        if prev in AI_NEG:
            best = best or -1.0
            continue
        best = max(best, 1.6 if prev in AI_INTENS else 1.0)
    return best


def _ai_seconds(t):
    """Duration and drop second from the text → (seconds | None, drop | None)."""
    drop = None
    m = re.search(r'(дроп|акцент|кульминац|взрыв|пик|drop|climax|peak)\D{0,20}?(\d+(?:[.,]\d+)?)\s*(сек|sec|с\b|s\b)?',
                  t)
    if m:
        drop = float(m.group(2).replace(',', '.'))
        t = t[:m.start()] + t[m.end():]
    m_clk = re.search(r'\b(\d{1,2}):([0-5]\d)\b', t)
    m_min = re.search(r'(\d+(?:[.,]\d+)?)\s*(мин|min)', t)
    m_sec = re.search(r'(\d+(?:[.,]\d+)?)\s*(сек|sec|s\b|с\b)', t)
    if m_clk:
        return int(m_clk.group(1)) * 60 + int(m_clk.group(2)), drop
    if m_min:
        return float(m_min.group(1).replace(',', '.')) * 60 + (float(m_sec.group(1).replace(',', '.'))
                                                                if m_sec else 0), drop
    if m_sec:
        return float(m_sec.group(1).replace(',', '.')), drop
    if 'полторы мин' in t or re.search(r'\b(one and a half|a minute and a half|minute and a half)\b', t):
        return 90, drop
    if 'полминут' in t or re.search(r'\bhalf (a )?minute\b', t):
        return 30, drop
    m_words = re.search(r'\b(two|three|four|five)\s+min', t)
    if m_words:
        return {'two': 2, 'three': 3, 'four': 4, 'five': 5}[m_words.group(1)] * 60, drop
    if re.search(r'\bминут[уа]?\b', t) or re.search(r'\b(a|one)\s+minute\b', t):
        return 60, drop
    return None, drop


def _ai_peaks(audio, n=160):
    m = np.abs(audio[:, 0] if audio.ndim == 2 else audio)
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    pk = np.array([c.max() for c in np.array_split(m, n)])
    return np.sqrt(pk / max(1e-6, float(pk.max()))).tolist()
