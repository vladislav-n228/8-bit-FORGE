# -*- coding: utf-8 -*-
"""Константы музыки: лады, прогрессии, стили, пресеты звука, треки."""

import os


APP_NAME = '8-BIT FORGE'


PREFS_PATH = os.path.join(os.path.expanduser('~'), '.8bit_forge_prefs.json')


NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']


SCALES = {
    'Мажор': [0, 2, 4, 5, 7, 9, 11],
    'Минор': [0, 2, 3, 5, 7, 8, 10],
    'Гармонический минор': [0, 2, 3, 5, 7, 8, 11],
    'Дорийский': [0, 2, 3, 5, 7, 9, 10],
    'Фригийский': [0, 1, 3, 5, 7, 8, 10],
    'Лидийский': [0, 2, 4, 6, 7, 9, 11],
    'Миксолидийский': [0, 2, 4, 5, 7, 9, 10],
    'Пентатоника мажор': [0, 2, 4, 7, 9],
    'Пентатоника минор': [0, 3, 5, 7, 10],
    'Блюзовый': [0, 3, 5, 6, 7, 10],
}


PARENT_SCALE = {'Пентатоника мажор': 'Мажор', 'Пентатоника минор': 'Минор', 'Блюзовый': 'Минор'}


PROGRESSIONS = {
    'major': [[0, 4, 5, 3], [0, 3, 4, 0], [0, 5, 3, 4], [0, 3, 0, 4], [5, 3, 0, 4], [0, 2, 3, 4], [0, 4, 3, 4], [3, 4, 0, 0]],
    'minor': [[0, 5, 2, 6], [0, 3, 4, 0], [0, 6, 5, 6], [0, 5, 3, 4], [0, 3, 6, 2], [0, 6, 5, 4], [0, 0, 5, 6]],
    'mixed': [[0, 6, 3, 0], [0, 4, 5, 3], [0, 6, 5, 6], [3, 4, 0, 0], [0, 2, 3, 4]],
    'blues': [[0, 0, 0, 0, 3, 3, 0, 0, 4, 3, 0, 4]],
}


BASS_PATTERNS = ['Корень четвертями', 'Октавы восьмыми', 'Корень-квинта', 'Драйв восьмыми',
                 'Синкопы', 'Шагающий', 'Пульс 16-ми']


BASS_EVENTS = {
    'Корень четвертями': [(0, 3, 'r'), (4, 3, 'r'), (8, 3, 'r'), (12, 3, 'r')],
    'Октавы восьмыми': [(i * 2, 1, 'r' if i % 2 == 0 else 'o') for i in range(8)],
    'Корень-квинта': [(0, 3, 'r'), (4, 2, 'f'), (8, 3, 'r'), (12, 2, 'f')],
    'Драйв восьмыми': [(i * 2, 2, 'r') for i in range(6)] + [(12, 2, 'f'), (14, 2, 'o')],
    'Синкопы': [(0, 3, 'r'), (3, 3, 'r'), (6, 2, 'o'), (8, 3, 'r'), (11, 2, 'f'), (14, 2, 'o')],
    'Шагающий': [(0, 4, 'r'), (4, 4, 'w1'), (8, 4, 'w2'), (12, 4, 'w3')],
    'Пульс 16-ми': [(i, 1, 'o' if i % 8 == 4 else 'r') for i in range(16)],
}


ARP_PATTERNS = ['Вверх', 'Вниз', 'Вверх-вниз', 'Ломаный', 'Случайный', 'Трель']


ARP_RATES = {'1/16': 1, '1/8': 2, '1/4': 4}


HARMONY_MODES = ['Терции под мелодией', 'Октава мелодии', 'Долгие аккорды', 'Контрмелодия', 'Стабы на слабые доли']


CHORD_RATES = {'Каждые полтакта': 8, 'Каждый такт': 16, 'Каждые 2 такта': 32}


CHIPS = {'Dendy (NES)': 'nes', 'Sega (FM)': 'sega'}


RECREATE_MODES = ['Полностью новый', 'Вариация', 'Тот же ритм', 'Зеркало']


BAR_CHOICES = ['4', '8', '12', '16', '24', '32', '48', '64']


CHARACTER_KEYS = ('density', 'complexity', 'repetition', 'drums', 'bass', 'arp', 'arp_rate', 'harmony', 'chip')


STYLES = {
    'Dendy · Приключение': dict(chip='nes', bpm=(128, 150), scales=['Мажор', 'Миксолидийский'], progs='major', drums=.6,
                                density=.65, complexity=.5, repetition=.55, bass='Октавы восьмыми', arp='Вверх',
                                arp_rate='1/16', harmony='Терции под мелодией', chords='Каждый такт', swing=0),
    'Dendy · Подземелье': dict(chip='nes', bpm=(84, 104), scales=['Минор', 'Фригийский'], progs='minor', drums=.3,
                               density=.42, complexity=.4, repetition=.6, bass='Корень четвертями', arp='Вверх-вниз',
                               arp_rate='1/8', harmony='Долгие аккорды', chords='Каждые 2 такта', swing=0),
    'Dendy · Замок': dict(chip='nes', bpm=(116, 136), scales=['Гармонический минор'], progs='minor', drums=.6,
                          density=.68, complexity=.62, repetition=.5, bass='Октавы восьмыми', arp='Ломаный',
                          arp_rate='1/16', harmony='Контрмелодия', chords='Каждый такт', swing=0),
    'Dendy · Битва с боссом': dict(chip='nes', bpm=(160, 186), scales=['Гармонический минор', 'Фригийский'],
                                   progs='minor', drums=.92, density=.85, complexity=.75, repetition=.45,
                                   bass='Драйв восьмыми', arp='Вверх', arp_rate='1/16',
                                   harmony='Стабы на слабые доли', chords='Каждые полтакта', swing=0),
    'Dendy · Мирная деревня': dict(chip='nes', bpm=(92, 112), scales=['Пентатоника мажор', 'Мажор', 'Лидийский'],
                                   progs='major', drums=.35, density=.5, complexity=.35, repetition=.65,
                                   bass='Корень-квинта', arp='Ломаный', arp_rate='1/8', harmony='Долгие аккорды',
                                   chords='Каждый такт', swing=.25),
    'Dendy · Победа!': dict(chip='nes', bpm=(136, 152), scales=['Мажор'], progs='major', drums=.7, density=.75,
                            complexity=.5, repetition=.5, bass='Октавы восьмыми', arp='Вверх', arp_rate='1/16',
                            harmony='Терции под мелодией', chords='Каждые полтакта', swing=0),
    'Sega · Скоростная зона': dict(chip='sega', bpm=(150, 176), scales=['Дорийский', 'Миксолидийский', 'Мажор'],
                                   progs='mixed', drums=.85, density=.8, complexity=.65, repetition=.5,
                                   bass='Синкопы', arp='Вверх', arp_rate='1/16', harmony='Стабы на слабые доли',
                                   chords='Каждый такт', swing=0),
    'Sega · Ночной город': dict(chip='sega', bpm=(96, 118), scales=['Дорийский', 'Минор', 'Пентатоника минор'],
                                progs='minor', drums=.6, density=.55, complexity=.55, repetition=.6, bass='Синкопы',
                                arp='Вверх-вниз', arp_rate='1/8', harmony='Долгие аккорды', chords='Каждый такт',
                                swing=.3),
    'Sega · Гонки': dict(chip='sega', bpm=(170, 196), scales=['Миксолидийский', 'Мажор'], progs='major', drums=.95,
                         density=.8, complexity=.6, repetition=.5, bass='Драйв восьмыми', arp='Вверх',
                         arp_rate='1/16', harmony='Октава мелодии', chords='Каждый такт', swing=0),
    'Sega · Блюз-бит': dict(chip='sega', bpm=(100, 124), scales=['Блюзовый', 'Пентатоника минор'], progs='blues',
                            drums=.65, density=.6, complexity=.55, repetition=.55, bass='Шагающий', arp='Трель',
                            arp_rate='1/8', harmony='Контрмелодия', chords='Каждый такт', swing=.45),
}


CELLS = {  # ритмические ячейки на одну долю (4 шага по 1/16); минус — пауза
    'calm': [[4], [4], [2, 2], [3, 1], [-2, 2], [2, -2], [-4]],
    'normal': [[2, 2], [1, 1, 2], [2, 1, 1], [3, 1], [4], [1, 1, 1, 1], [-1, 1, 2], [-2, 1, 1], [2, 2]],
    'busy': [[1, 1, 1, 1], [1, 1, 2], [2, 1, 1], [1, 2, 1], [2, 2], [1, 1, 1, 1], [-1, 1, 1, 1]],
}


RANGES = {'lead': (64, 86), 'harmony': (55, 76), 'bass': (33, 52), 'arp': (72, 92), 'voice': (57, 76)}


DRUM_ROWS = [(49, 'Тарелка'), (46, 'Откр. хэт'), (42, 'Хай-хэт'), (45, 'Том'), (38, 'Малый'), (36, 'Бочка')]


DRUM_PITCHES = [p for p, _ in DRUM_ROWS]


DRUM_NAMES = dict(DRUM_ROWS)


KITS = ['NES', 'Sega', 'Lo-Fi']


TRACK_DEFS = [('lead', 'Лид'), ('harmony', 'Гармония'), ('bass', 'Бас'), ('arp', 'Арпеджио'), ('drums', 'Ударные'),
              ('voice', 'Голос')]


TRACK_COLORS = {'lead': '#ff5c7a', 'harmony': '#ffb547', 'bass': '#3dc8ff', 'arp': '#b77bff', 'drums': '#7ee05a',
                'voice': '#ff8fd8'}


WAVE_NAMES = {'pulse': 'Пульс (квадрат)', 'triangle': 'Треугольник', 'saw': 'Пила', 'sine': 'Синус',
              'fm': 'FM (Sega)', 'noise': 'Шум', 'voice': 'Голос (форманты)'}


# форманты гласных: (частота Гц, громкость, ширина Гц)
VOWELS = {'а': ((800, 1.0, 170), (1150, .6, 180), (2900, .25, 260)),
          'о': ((450, 1.0, 150), (800, .55, 170), (2830, .15, 260)),
          'у': ((325, 1.0, 140), (700, .3, 160), (2530, .1, 260)),
          'и': ((290, 1.0, 140), (2250, .45, 220), (3000, .3, 260)),
          'э': ((420, 1.0, 150), (1800, .5, 200), (2600, .25, 260))}


VOWEL_NAMES = {'а': 'Хор «А-а-а»', 'о': 'Голос «О-о-о»', 'у': 'Мягкий «У-у-у»', 'и': 'Звонкий «И-и-и»',
               'э': 'Голос «Э-э-э»', 'mix': 'Смешанный (а-о-у-и-э)', 'robot': 'Робо-голос'}


VOWEL_KEYS = {v: k for k, v in VOWEL_NAMES.items()}


WAVE_KEYS = {v: k for k, v in WAVE_NAMES.items()}


DUTY_NAMES = {0.125: '12.5%', 0.25: '25%', 0.5: '50%', 0.75: '75%'}


DUTY_VALUES = {v: k for k, v in DUTY_NAMES.items()}


PRESET_BASE = dict(wave='pulse', duty=.5, pwm=0.0, attack=.003, decay=.1, sustain=.7, release=.06, vib_depth=0.0,
                   vib_rate=5.5, echo=0.0, fm_ratio=1.0, fm_index=2.0, detune=0.0, vowel='а')


SOUND_PRESETS = {name: dict(PRESET_BASE, **over) for name, over in [
    ('NES · Лид 25%', dict(duty=.25, decay=.12, sustain=.62, release=.05, vib_depth=.22, echo=.18)),
    ('NES · Тонкий 12.5%', dict(duty=.125, decay=.08, sustain=.55, release=.04, vib_depth=.15, echo=.1)),
    ('NES · Квадрат 50%', dict(duty=.5, decay=.1, sustain=.6, release=.05)),
    ('NES · Треугольный бас', dict(wave='triangle', attack=.001, decay=.05, sustain=1.0, release=.02)),
    ('NES · Арпеджио-блип', dict(duty=.25, attack=.001, decay=.07, sustain=.35, release=.03)),
    ('Sega · FM брасс', dict(wave='fm', fm_ratio=1.0, fm_index=3.2, attack=.012, decay=.25, sustain=.6, release=.12,
                             vib_depth=.18, detune=6, echo=.15)),
    ('Sega · FM слэп-бас', dict(wave='fm', fm_ratio=1.0, fm_index=6.0, attack=.001, decay=.18, sustain=.45, release=.05)),
    ('Sega · FM колокол', dict(wave='fm', fm_ratio=3.5, fm_index=4.0, attack=.001, decay=.7, sustain=0.0, release=.4,
                               echo=.3)),
    ('Sega · FM э-пиано', dict(wave='fm', fm_ratio=1.0, fm_index=1.6, attack=.002, decay=.45, sustain=.3, release=.2)),
    ('Sega · FM орган', dict(wave='fm', fm_ratio=2.0, fm_index=1.2, attack=.01, decay=.1, sustain=.9, release=.08,
                             vib_depth=.1)),
    ('Мягкая флейта', dict(wave='sine', attack=.04, decay=.2, sustain=.8, release=.15, vib_depth=.2, vib_rate=5.0)),
    ('Злая пила', dict(wave='saw', decay=.1, sustain=.7, release=.06, detune=14)),
    ('PWM-струны', dict(duty=.5, pwm=.7, attack=.08, decay=.3, sustain=.8, release=.3, detune=8)),
    ('Шумовой синт', dict(wave='noise', decay=.2, sustain=.2, release=.1)),
    ('Голос · хор «А»', dict(wave='voice', vowel='а', attack=.06, decay=.2, sustain=.85, release=.18, vib_depth=.3,
                             vib_rate=5.2, detune=9, echo=.25)),
    ('Голос · смешанный', dict(wave='voice', vowel='mix', attack=.05, decay=.2, sustain=.8, release=.15,
                               vib_depth=.28, vib_rate=5.4, detune=5, echo=.2)),
    ('Голос · робот', dict(wave='voice', vowel='robot', attack=.01, decay=.1, sustain=.9, release=.06, echo=.15)),
]}


SOUND_FIELDS = ['wave', 'duty', 'pwm', 'volume', 'pan', 'octave', 'attack', 'decay', 'sustain', 'release',
                'vib_depth', 'vib_rate', 'echo', 'fm_ratio', 'fm_index', 'detune', 'kit', 'vowel']
