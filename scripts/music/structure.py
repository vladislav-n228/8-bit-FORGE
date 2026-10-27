# -*- coding: utf-8 -*-
"""For video: exact duration, intro, ending, drop."""

from scripts.core.constants import RANGES
from scripts.core.model import Note
from scripts.core.theory import chord_at, chord_pcs, chord_pitches, nearest
from scripts.music.composer import Composer


PLATFORM_PRESETS = {
    'Своя длительность': None,
    'TikTok / Reels — 15 с': 15, 'TikTok / Reels — 30 с': 30, 'TikTok / Reels — 60 с': 60,
    'YouTube Shorts — 59 с': 59, 'Интро YouTube — 7 с': 7, 'Аутро YouTube — 15 с': 15,
    'Сторис — 15 с': 15, 'Фон для видео — 2 мин': 120,
}


def fmt_bpm(b):
    return f'{b:.2f}'.rstrip('0').rstrip('.')


def exact_fit(seconds, bpm_hint, lo=60, hi=220):
    """Picks the number of bars and a fractional tempo so the track lasts exactly seconds."""
    est = seconds * bpm_hint / 240.0
    best = None
    for bars in range(max(2, int(est) - 8), int(est) + 9):
        bpm = bars * 240.0 / seconds
        if not lo <= bpm <= hi:
            continue
        cost = abs(bpm - bpm_hint) / bpm_hint + (0 if bars % 4 == 0 else .04 if bars % 2 == 0 else .09)
        if best is None or cost < best[0]:
            best = (cost, bars, bpm)
    if best is None:
        bars = max(1, int(round(est)))
        return bars, bars * 240.0 / seconds
    return best[1], best[2]


def _clear(tr, a, b):
    tr.notes = [n for n in tr.notes if not (a <= n.s < b)]
    for n in tr.notes:
        if n.s < a < n.s + n.l:
            n.l = a - n.s


def drop_step_for(song, sec):
    if not sec or sec <= 0:
        return None
    s = int(round(sec / song.step_dur / 16)) * 16
    return s if 32 <= s <= song.total_steps - 16 else None


def apply_structure(song, intro=False, outro=False, drop_step=None):
    """Intro (build-up), a drop at the right point and an ending with a final chord."""
    total = song.total_steps
    by = {t.kind: t for t in song.tracks}
    drums = by.get('drums')
    has_drums = drums is not None and bool(drums.notes)
    if drop_step:
        d = drop_step
        bl = 16 if d >= 48 else 8
        a = d - bl
        for kind in ('lead', 'harmony', 'voice'):
            if kind in by:
                _clear(by[kind], a, d)
        bass = by.get('bass')
        if bass and bass.notes:
            _clear(bass, a, d)
            root = 36 + chord_pcs(song, chord_at(song, a))[0]
            root -= 12 if root > 45 else 0
            for s in range(a, d - 2, 2):
                bass.notes.append(Note(s, 1, root, .5 + .45 * (s - a) / bl))
        if has_drums:
            _clear(drums, a, d)
            for s in range(a, d - 2):
                if s < a + bl // 2 and s % 2:
                    continue
                drums.notes.append(Note(s, 1, 38, .3 + .65 * (s - a) / bl))
        for t in song.tracks:
            _clear(t, d - 2, d)  # a short pause before the drop
        if has_drums:
            drums.notes = [n for n in drums.notes if not (n.s == d and n.p in (36, 49))]
            drums.notes += [Note(d, 1, 49, .95), Note(d, 1, 36, 1.0)]
    if intro and song.bars >= 6:
        b = (2 if song.bars >= 16 else 1) * 16
        for kind in ('lead', 'harmony', 'voice'):
            if kind in by:
                _clear(by[kind], 0, b)
        if has_drums:
            _clear(drums, 0, b)
            for s in range(b):
                if s % 16 == 0:
                    drums.notes.append(Note(s, 1, 36, .8))
                if s % 2 == 0 and s < b - 4:
                    drums.notes.append(Note(s, 1, 42, .3 + .4 * s / b))
                if s >= b - 4:
                    drums.notes.append(Note(s, 1, 38, .5 + .12 * (s - b + 4)))
    if outro and song.bars >= 4:
        a = total - 16
        for i in range(a // song.chord_steps, len(song.chords)):
            song.chords[i] = 0
        for t in song.tracks:
            if not t.notes:
                continue
            prev = [n.p for n in t.notes if n.s < a]
            _clear(t, a, total)
            if t.kind == 'drums':
                _clear(t, a - 4, a)
                for k, s in enumerate(range(a - 4, a)):
                    t.notes.append(Note(s, 1, 38 if k < 3 else 45, .55 + .12 * k))
                t.notes += [Note(a, 1, 49, .9), Note(a, 1, 36, 1.0)]
                continue
            lo, hi = RANGES.get(t.kind, (60, 76))
            if t.kind == 'bass':
                p = 36 + song.key
                t.notes.append(Note(a, 12, p - 12 if p > 45 else p, .95))
            elif t.kind == 'harmony':
                tones = chord_pitches(song, 0, 60, 74) or [64]
                t.notes.append(Note(a, 16, tones[1 % len(tones)], .65))
            elif t.kind == 'arp':
                tones = chord_pitches(song, 0, 72, 90)[:4] or [76]
                for k in range(4):
                    t.notes.append(Note(a + k, 1 if k < 3 else 12, tones[k % len(tones)], .6))
            else:
                cand = [p for p in range(lo, hi + 1) if p % 12 == song.key] or [(lo + hi) // 2]
                t.notes.append(Note(a, 16, nearest(cand, prev[-1] if prev else (lo + hi) // 2), .85))
    for t in song.tracks:
        t.notes = Composer.clean(t.notes, 0, total)
