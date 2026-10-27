# -*- coding: utf-8 -*-
"""The Forge Jingle model — short, complete jingles."""

import random

from scripts.core.constants import SOUND_PRESETS
from scripts.core.model import default_tracks, Note, Song
from scripts.core.theory import chord_at, chord_pitches, clamp, nearest, scale_pitches
from scripts.models_of_ai.base_composer import _ai_params
from scripts.music.composer import Composer


JINGLE_INFO = dict(name='Forge Jingle', icon='★', desc='короткие джинглы 1–10 с: победа, game over, старт уровня')


# Notes: (1/16 step, length, semitones from the tonic); chords — every half bar (scale degrees).
AI_JINGLES = {
    'victory': dict(minor=False, bpm=150, kind='fanfare', tpls=[
        ([(0, 2, 0), (2, 2, 4), (4, 2, 7), (6, 6, 12), (12, 2, 9), (14, 2, 11), (16, 14, 12)], [0, 4, 0, 0]),
        ([(0, 1, 7), (1, 1, 7), (2, 2, 7), (4, 4, 12), (8, 2, 9), (10, 2, 11), (12, 2, 14), (14, 2, 11),
          (16, 14, 12)], [0, 4, 0, 0]),
        ([(0, 2, 0), (2, 2, 7), (4, 2, 4), (6, 2, 7), (8, 2, 9), (10, 2, 12), (12, 4, 17), (16, 14, 16)],
         [0, 3, 0, 0])]),
    'gameover': dict(minor=True, bpm=104, kind='sad', tpls=[
        ([(0, 4, 7), (4, 4, 6), (8, 4, 5), (12, 4, 4), (16, 4, 3), (20, 12, 0)], [0, 3, 0, 0]),
        ([(0, 2, 12), (2, 2, 10), (4, 2, 8), (6, 2, 7), (8, 4, 5), (12, 4, 3), (16, 6, 2), (24, 8, 0)],
         [0, 3, 4, 0])]),
    'start': dict(minor=False, bpm=160, kind='fanfare', tpls=[
        ([(0, 1, 7), (2, 1, 7), (4, 4, 12), (8, 1, 9), (10, 1, 9), (12, 4, 14), (16, 4, 11), (20, 2, 14),
          (22, 2, 11), (24, 8, 12)], [0, 1, 4, 0]),
        ([(0, 2, 0), (2, 2, 4), (4, 2, 7), (6, 2, 12), (8, 4, 11), (12, 4, 14), (16, 16, 12)], [0, 4, 0, 0])]),
    'item': dict(minor=False, bpm=150, kind='sparkle', tpls=[
        ([(i, 1, v) for i, v in enumerate((0, 4, 7, 12, 16, 19, 24))] + [(7, 9, 28)], [0, 0]),
        ([(0, 1, 7), (1, 1, 9), (2, 1, 11), (3, 1, 12), (4, 2, 14), (6, 2, 16), (8, 8, 19)], [0, 0])]),
    'levelup': dict(minor=False, bpm=150, kind='fanfare', tpls=[
        ([(i, 1, v) for i, v in enumerate((0, 2, 4, 5, 7, 9, 11))] + [(7, 9, 12)], [0, 0]),
        ([(0, 2, 5), (2, 2, 9), (4, 2, 12), (6, 2, 14), (8, 8, 16)], [3, 0])]),
    'logo': dict(minor=False, bpm=120, kind='soft', tpls=[
        ([(0, 2, 7), (2, 2, 12), (4, 4, 16), (8, 2, 17), (10, 2, 16), (12, 4, 12), (16, 4, 14), (20, 4, 11),
          (24, 8, 12)], [0, 3, 4, 0])]),
    'fail': dict(minor=True, bpm=140, kind='sad', tpls=[([(0, 2, 7), (2, 2, 6), (4, 2, 5), (6, 10, 0)], [0, 0])]),
    'danger': dict(minor=True, phryg=True, bpm=126, kind='tense', tpls=[
        ([(0, 2, 0), (2, 2, 1), (4, 2, 0), (6, 2, 1), (8, 2, 3), (10, 2, 1), (12, 4, 0), (16, 16, 6)],
         [0, 1, 0, 1])]),
}


AI_JINGLE_TITLES = {'victory': 'Победный джингл', 'gameover': 'Game Over', 'start': 'Старт уровня',
                    'item': 'Находка!', 'levelup': 'Level Up!', 'logo': 'Заставка', 'fail': 'Потеря жизни',
                    'danger': 'Опасность!'}


AI_JINGLE_LEAD = {('nes', 'fanfare'): 'NES · Лид 25%', ('nes', 'sad'): 'Мягкая флейта',
                  ('nes', 'sparkle'): 'NES · Тонкий 12.5%', ('nes', 'soft'): 'NES · Тонкий 12.5%',
                  ('nes', 'tense'): 'NES · Квадрат 50%', ('sega', 'fanfare'): 'Sega · FM брасс',
                  ('sega', 'sad'): 'Sega · FM э-пиано', ('sega', 'sparkle'): 'Sega · FM колокол',
                  ('sega', 'soft'): 'Sega · FM колокол', ('sega', 'tense'): 'Sega · FM орган'}


def _ai_jingle(plan, seed):
    rng = random.Random(seed)
    J = AI_JINGLES[plan['jt']]
    kind, chip = J['kind'], plan['chip']
    tpl, ch8 = rng.choice(J['tpls'])
    tpl = [list(x) for x in tpl]
    if kind == 'fanfare' and rng.random() < .35 and tpl[-1][2] % 12 == 0:
        tpl[-1][2] += 4  # sometimes the finale lands on the third — sounds brighter
    L = max(s + ln for s, ln, _ in tpl)
    bars = max(1, -(-L // 16))
    total = bars * 16
    secs = plan['seconds_req']
    bpm = clamp(total * 15 / secs, 60, 220) if secs else J['bpm'] + rng.randint(-6, 6)
    scale = 'Фригийский' if J.get('phryg') else 'Минор' if J['minor'] else 'Мажор'
    song = Song(bpm=round(bpm, 2), bars=bars, key=plan['key'], scale=scale, style=plan['style'], seed=seed,
                chord_steps=8)
    song.chords = (list(ch8) + [ch8[-1]] * (bars * 2))[:bars * 2]
    song.tracks = default_tracks(chip)
    by = {t.kind: t for t in song.tracks}
    semis = [x[2] for x in tpl]
    base = 60 + plan['key']
    while base + max(semis) > 93:
        base -= 12
    while base + min(semis) < 55:
        base += 12
    fin = tpl[-1][0]
    lead = [Note(s, total - s if i == len(tpl) - 1 else ln, base + semi, .9 if s % 4 == 0 else .8)
            for i, (s, ln, semi) in enumerate(tpl)]
    by['lead'].notes = lead
    if kind in ('fanfare', 'soft'):
        pool = scale_pitches(song, base - 14, base + 40)
        by['harmony'].notes = [Note(n.s, n.l, pool[max(0, pool.index(nearest(pool, n.p)) - 2)], .55) for n in lead]
    comp = Composer(song, rng)
    bass = []
    for pos in range(0, fin, 8):
        root = comp._bass_pitch('r', pos)
        if kind == 'fanfare':
            bass += [Note(pos + o, 2, root + (12 if o % 4 else 0), .85) for o in (0, 2, 4, 6) if pos + o < fin]
        else:
            bass.append(Note(pos, min(8, fin - pos), root, .85))
    bass.append(Note(fin, total - fin, comp._bass_pitch('r', fin), .95))
    by['bass'].notes = bass
    drums = []
    if kind == 'fanfare':
        drums.append(Note(0, 1, 36, .9))
        drums += [Note(o, 1, 38, .5 + .12 * (o - fin + 4)) for o in range(max(1, fin - 4), fin)]
        drums += [Note(fin, 1, 49, .9), Note(fin, 1, 36, 1.0)]
    elif kind == 'tense':
        drums += [Note(pos, 1, 36, .8 if pos % 8 == 0 else .55) for pos in range(0, fin, 4)]
        drums.append(Note(fin, 1, 49, .7))
    elif kind == 'soft':
        drums.append(Note(fin, 1, 49, .5))
        tones = chord_pitches(song, chord_at(song, fin), 76, 94)[:4] or [84]
        by['arp'].notes = [Note(fin + k, 1 if k < 3 else total - fin - k, tones[k % len(tones)], .5)
                           for k in range(min(4, total - fin))]
    by['drums'].notes = drums
    for k, v in SOUND_PRESETS[AI_JINGLE_LEAD[(chip, kind)]].items():
        setattr(by['lead'], k, v)
    for k, v in SOUND_PRESETS['NES · Тонкий 12.5%' if chip == 'nes' else 'Sega · FM э-пиано'].items():
        setattr(by['harmony'], k, v)
    by['drums'].kit = plan['kit']
    if kind in ('sparkle', 'soft'):
        by['lead'].echo = max(by['lead'].echo, .25)
    if kind == 'sad':
        by['lead'].vib_depth = max(by['lead'].vib_depth, .3)
    for t in song.tracks:
        t.notes = Composer.clean(t.notes, 0, total)
    song.params = _ai_params(song, plan, outro=True)
    if secs and abs(total * song.step_dur - secs) < .05:
        song.params['exact_sec'] = secs  # exactly to the requested length: the tail is cut with a soft fade
    return song
