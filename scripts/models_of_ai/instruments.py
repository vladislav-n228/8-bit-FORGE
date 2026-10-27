# -*- coding: utf-8 -*-
"""Track instruments: picking them by hand with ticks in the chat studio, and timbre variety in "auto" mode."""

from scripts.core.constants import SOUND_PRESETS
from scripts.core.i18n import T

# what can be ticked: key → label; a "mel:…" / "bass:…" key contains the sound preset name
INSTRUMENT_GROUPS = (
    ('Мелодия и аккорды', tuple((f'mel:{p}', p) for p in (
        'NES · Лид 25%', 'NES · Тонкий 12.5%', 'NES · Квадрат 50%', 'PWM-струны', 'Мягкая флейта', 'Злая пила',
        'Sega · FM брасс', 'Sega · FM э-пиано', 'Sega · FM колокол', 'Sega · FM орган'))),
    ('Бас', (('bass:NES · Треугольный бас', 'Треугольный бас (NES)'), ('bass:Sega · FM слэп-бас', 'FM слэп-бас (Sega)'),
             ('bass:NES · Квадрат 50%', 'Квадратный бас (NES)'), ('bass:Злая пила', 'Пила-бас'))),
    ('Ритм', (('drums', 'Ударные'), ('arp', 'Арпеджио-блип'))),
)
INSTRUMENT_LABELS = {key: label for _, items in INSTRUMENT_GROUPS for key, label in items}

# "auto": what else the lead and harmony can sound like besides the genre's sounds — so tracks don't all sound the same
AUTO_LEADS = {'nes': ('NES · Лид 25%', 'NES · Квадрат 50%', 'NES · Тонкий 12.5%', 'PWM-струны'),
              'sega': ('Sega · FM брасс', 'Sega · FM орган', 'Sega · FM колокол', 'Злая пила')}
AUTO_HARMONY = {'nes': ('NES · Тонкий 12.5%', 'NES · Квадрат 50%', 'PWM-струны'),
                'sega': ('Sega · FM э-пиано', 'Sega · FM орган', 'PWM-струны')}


def vary_sounds(sounds, chip, rng, lead_fixed=False):
    """"Auto" mode: sometimes take a different lead and harmony timbre from the same console's sounds."""
    sounds = list(sounds)
    if not lead_fixed and rng.random() < .55:
        sounds[0] = rng.choice(AUTO_LEADS[chip])
    if rng.random() < .45:
        sounds[1] = rng.choice([p for p in AUTO_HARMONY[chip] if p != sounds[0]])
    return sounds


def _put(tr, preset):
    """Changes a track's timbre without touching the volume and pan set by the composer."""
    vol, pan = tr.volume, tr.pan
    for k, v in SOUND_PRESETS[preset].items():
        setattr(tr, k, v)
    tr.volume, tr.pan = vol, pan


def apply_instruments(song, plan, choice, rng):
    """Keeps only the ticked instruments in the track. choice is a list of keys from INSTRUMENT_GROUPS."""
    if not choice:
        return
    choice = [c for c in choice if c in INSTRUMENT_LABELS]
    if not choice:
        return
    by = {t.kind: t for t in song.tracks}
    mel = [c[4:] for c in choice if c.startswith('mel:')]
    basses = [c[5:] for c in choice if c.startswith('bass:')]
    rng.shuffle(mel)
    sounds = list(plan.get('sounds') or ['NES · Лид 25%'] * 4)
    if mel:
        _put(by['lead'], mel[0])
        _put(by['harmony'], mel[1 % len(mel)])
        sounds[0], sounds[1] = mel[0], mel[1 % len(mel)]
    else:
        by['lead'].notes, by['harmony'].notes = [], []
    if 'arp' in choice:
        _put(by['arp'], 'NES · Арпеджио-блип')
    elif len(mel) >= 3:  # three or more timbres — the third one plays the arpeggio
        _put(by['arp'], mel[2])
    else:
        by['arp'].notes = []
    if basses:
        sounds[2] = rng.choice(basses)
        _put(by['bass'], sounds[2])
        by['bass'].volume = .78 if by['bass'].wave == 'triangle' else .6
    else:
        by['bass'].notes = []
    if 'drums' not in choice:
        by['drums'].notes = []
    plan['sounds'] = sounds
    plan['notes'].append(T('инструменты выбраны вручную: {0}').format(
        ', '.join(T(INSTRUMENT_LABELS[c]) for c in choice)))
    if song.params.get('include'):
        from scripts.core.constants import TRACK_DEFS
        song.params['include'] = [bool(by[k].notes) if k in by else False for k, _ in TRACK_DEFS]
