# -*- coding: utf-8 -*-
"""Модель данных: нота, трек, песня и их сохранение."""

from dataclasses import dataclass, field, asdict, fields

from scripts.core.constants import SOUND_PRESETS, TRACK_COLORS


@dataclass(eq=False)
class Note:
    s: int          # начало (шаг 1/16)
    l: int          # длина в шагах
    p: int          # MIDI-высота (для ударных — тип барабана)
    v: float = 0.8  # громкость 0..1


@dataclass(eq=False)
class Track:
    name: str
    kind: str
    color: str
    wave: str = 'pulse'
    duty: float = 0.5
    pwm: float = 0.0
    volume: float = 0.6
    pan: float = 0.0
    octave: int = 0
    attack: float = 0.003
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.06
    vib_depth: float = 0.0
    vib_rate: float = 5.5
    echo: float = 0.0
    fm_ratio: float = 1.0
    fm_index: float = 2.0
    detune: float = 0.0
    kit: str = 'NES'
    vowel: str = 'а'
    mute: bool = False
    solo: bool = False
    notes: list = field(default_factory=list)


@dataclass(eq=False)
class Song:
    bpm: int = 140
    bars: int = 16
    key: int = 0
    scale: str = 'Мажор'
    style: str = ''
    seed: int = 0
    swing: float = 0.0
    chord_steps: int = 16
    chords: list = field(default_factory=list)
    params: dict = field(default_factory=dict)
    tracks: list = field(default_factory=list)

    @property
    def total_steps(self):
        return self.bars * 16

    @property
    def step_dur(self):
        return 60.0 / self.bpm / 4


def song_to_dict(song):
    return asdict(song)


def song_from_dict(d):
    tf = {f.name for f in fields(Track)}
    sf = {f.name for f in fields(Song)}
    tracks = []
    for t in d.get('tracks', []):
        notes = [Note(int(n['s']), int(n['l']), int(n['p']), float(n.get('v', .8))) for n in t.get('notes', [])]
        kw = {k: v for k, v in t.items() if k in tf and k != 'notes'}
        tracks.append(Track(notes=notes, **kw))
    kw = {k: v for k, v in d.items() if k in sf and k != 'tracks'}
    return Song(tracks=tracks, **kw)


def make_track(kind, name, preset, **over):
    snd = dict(SOUND_PRESETS[preset])
    snd.update(over)
    return Track(name=name, kind=kind, color=TRACK_COLORS[kind], **snd)


def default_tracks(chip):
    voice = make_track('voice', 'Голос', 'Голос · хор «А»', volume=.45, pan=.1)
    if chip == 'sega':
        return [make_track('lead', 'Лид', 'Sega · FM брасс', volume=.45),
                make_track('harmony', 'Гармония', 'Sega · FM э-пиано', volume=.3, pan=-.3),
                make_track('bass', 'Бас', 'Sega · FM слэп-бас', volume=.7),
                make_track('arp', 'Арпеджио', 'NES · Арпеджио-блип', volume=.18, pan=.35),
                make_track('drums', 'Ударные', 'NES · Квадрат 50%', wave='noise', volume=.55, kit='Sega'),
                voice]
    return [make_track('lead', 'Лид', 'NES · Лид 25%', volume=.5),
            make_track('harmony', 'Гармония', 'NES · Тонкий 12.5%', volume=.3, pan=-.3),
            make_track('bass', 'Бас', 'NES · Треугольный бас', volume=.8),
            make_track('arp', 'Арпеджио', 'NES · Арпеджио-блип', duty=.5, volume=.2, pan=.35),
            make_track('drums', 'Ударные', 'NES · Квадрат 50%', wave='noise', volume=.55, kit='NES'),
            voice]
