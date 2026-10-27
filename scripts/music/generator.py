# -*- coding: utf-8 -*-
"""Builds a manual-mode track from the generator settings."""

import random

from scripts.core.constants import PROGRESSIONS, SOUND_FIELDS, STYLES
from scripts.core.model import default_tracks, Song
from scripts.music.composer import Composer
from scripts.music.structure import apply_structure, drop_step_for, exact_fit


def build_song(params, seed, old_song=None, keep_sounds=False):
    rng = random.Random(seed)
    if params.get('exact_sec'):
        bars, bpm = exact_fit(params['exact_sec'], params['bpm'])
        params = dict(params, bars=bars, bpm=bpm)
    st = STYLES.get(params['style'], next(iter(STYLES.values())))
    song = Song(bpm=params['bpm'], bars=params['bars'], key=params['key'], scale=params['scale'],
                style=params['style'], seed=seed, swing=params['swing'], chord_steps=params['chord_steps'],
                params=dict(params))
    progs = PROGRESSIONS[st['progs']]
    A, B = rng.choice(progs), rng.choice(progs)
    slots = max(1, song.total_steps // song.chord_steps)
    form = 'AABA' if rng.random() < .6 else 'ABAB'
    chords, sec = [], 0
    while len(chords) < slots:
        chords.extend(A if form[sec % 4] == 'A' else B)
        sec += 1
    song.chords = chords[:slots]
    song.tracks = default_tracks(params['chip'])
    if keep_sounds and old_song:
        for new, old in zip(song.tracks, old_song.tracks):
            for f in SOUND_FIELDS + ['mute', 'solo', 'color', 'name']:
                setattr(new, f, getattr(old, f))
    comp = Composer(song, rng)
    for tr, inc in zip(song.tracks, params['include']):
        if inc:
            tr.notes = comp.generate(tr, 0, song.total_steps, allow_repeat=True)
    if params.get('intro') or params.get('outro') or params.get('drop_sec'):
        ds = drop_step_for(song, params.get('drop_sec'))
        song.params['drop_step'] = ds
        apply_structure(song, params.get('intro'), params.get('outro'), ds)
    return song
