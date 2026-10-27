# -*- coding: utf-8 -*-
"""The models' musical knowledge: progressions by scale, motif rhythms, grooves, bass figures."""

from scripts.core.constants import BASS_EVENTS, PROGRESSIONS


AI_FAMILY = {'Пентатоника мажор': 'Мажор', 'Пентатоника минор': 'Минор', 'Блюзовый': 'blues'}


# Progressions by scale (degrees of the parent scale); diminished chords are not used.
AI_PROGS = {
    'Мажор': dict(verse=[[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 0, 4], [0, 2, 3, 4], [0, 3, 5, 4]],
                  chorus=[[3, 4, 0, 5], [0, 4, 5, 3], [3, 0, 4, 0], [5, 3, 0, 4], [3, 4, 2, 5]],
                  bridge=[[5, 2, 3, 4], [1, 4, 0, 5], [3, 2, 1, 4]], cad=4),
    'Минор': dict(verse=[[0, 5, 2, 6], [0, 3, 6, 2], [0, 6, 5, 6], [0, 5, 6, 0], [0, 3, 4, 0]],
                  chorus=[[5, 6, 0, 0], [5, 2, 6, 0], [3, 6, 2, 5], [0, 5, 2, 6]],
                  bridge=[[3, 4, 5, 6], [5, 3, 6, 6], [3, 0, 3, 4]], cad=6),
    'Гармонический минор': dict(verse=[[0, 5, 3, 4], [0, 3, 4, 0], [0, 5, 1, 4], [0, 3, 5, 4]],
                                chorus=[[5, 3, 4, 0], [3, 4, 0, 5], [5, 1, 4, 4]],
                                bridge=[[3, 0, 5, 4], [5, 5, 4, 4]], cad=4),
    'Дорийский': dict(verse=[[0, 3, 0, 3], [0, 6, 3, 0], [0, 2, 6, 3], [0, 3, 6, 0]],
                      chorus=[[3, 6, 0, 0], [2, 6, 3, 0], [6, 3, 0, 4]],
                      bridge=[[1, 2, 3, 6], [4, 3, 2, 6]], cad=6),
    'Фригийский': dict(verse=[[0, 1, 0, 1], [0, 1, 6, 0], [0, 5, 1, 0], [0, 3, 1, 0]],
                       chorus=[[5, 1, 0, 0], [3, 1, 6, 0], [5, 6, 1, 0]],
                       bridge=[[3, 2, 1, 1], [5, 3, 1, 1]], cad=1),
    'Лидийский': dict(verse=[[0, 1, 0, 1], [0, 1, 5, 4], [0, 1, 2, 1], [0, 4, 1, 0]],
                      chorus=[[5, 1, 0, 4], [1, 4, 0, 0], [2, 1, 0, 1]],
                      bridge=[[5, 4, 1, 1], [2, 5, 1, 4]], cad=1),
    'Миксолидийский': dict(verse=[[0, 6, 3, 0], [0, 6, 0, 3], [0, 4, 6, 3], [0, 3, 6, 0]],
                           chorus=[[3, 6, 0, 0], [6, 3, 0, 4], [3, 4, 6, 0]],
                           bridge=[[5, 3, 6, 6], [1, 4, 6, 6]], cad=6),
    'blues': dict(verse=[PROGRESSIONS['blues'][0]], chorus=[PROGRESSIONS['blues'][0]], bridge=[[3, 3, 0, 0]], cad=4),
}


# Motif rhythm per bar (16 steps of 1/16): x — note, . — continuation / rest
AI_RHYTHMS = {
    'calm': ['x...x...x.......', 'x.......x...x...', 'x.....x.x.......', 'x...........x...', 'x.....x...x.....',
             'x.......x.......', 'x...x.......x...'],
    'medium': ['x.x.x...x.x.x...', 'x...x.x.x...x...', 'x.x...x.x.x.....', 'x..x..x.x...x...', 'x.x.x.x.x.......',
               'x...x..x..x.x...', 'x..x..x...x.x...', 'x.x.x...x...x.x.'],
    'busy': ['x.xxx.x.x.xxx.x.', 'xxx.x.x.xxx.x...', 'x.x.xxx.x.x.xx..', 'x.xxx.xxx.x.x...', 'xx.xx.x.xx.xx.x.',
             'x.x.x.xxx.x.x.x.', 'x.xxx.x.x.x.x...'],
}


AI_CAD_RHYTHMS = {'calm': ['x...............', 'x.......x.......', 'x...x...........'],
                  'medium': ['x.x.x...........', 'x...x...x.......', 'x..x..x.........', 'x.x.x.x.x.......'],
                  'busy': ['x.xxx.x.x.......', 'xxx.x...x.......', 'x.x.x.xxx.......']}


# Drum grooves: k — kick, s — snare (o — quiet "ghost" note), h — hi-hat (o — open)
AI_GROOVES = {
    'pop': dict(k='x.......x.x.....', s='....x.......x...', h='x.x.x.x.x.x.x.x.'),
    'rock': dict(k='x.....x.x.......', s='....x.......x...', h='x.x.x.x.x.x.x.x.'),
    'drive': dict(k='x.x.x.x.x.x.x.x.', s='....x.......x...', h='xxxxxxxxxxxxxxxx'),
    'four': dict(k='x...x...x...x...', s='....x.......x...', h='..o...o...o...o.'),
    'breakbeat': dict(k='x.........x.....', s='....x..o.o..x...', h='x.x.x.x.x.x.x.x.'),
    'halftime': dict(k='x.........x.....', s='........x.......', h='x...x...x...x...'),
    'march': dict(k='x.......x.......', s='....x..o....x.oo', h='x...x...x...x...'),
    'shuffle': dict(k='x.....x.x.......', s='....x.......x...', h='x.x.x.x.x.x.x.x.'),
    'lofi': dict(k='x......x..x.....', s='....x.......x...', h='x.x.x.x.x.x.x.x.'),
    'synthwave': dict(k='x...x...x...x...', s='....x.......x...', h='x.x.x.x.x.x.x.x.'),
    'sparse': dict(k='x.........x.....', s='................', h='....x.......x...'),
}


AI_BASS = {
    'whole': [(0, 16, 'r')],
    'root': [(0, 8, 'r'), (8, 8, 'r')],
    'pulse8': [(i * 2, 2, 'r') for i in range(8)],
    'octave8': BASS_EVENTS['Октавы восьмыми'],
    'rootfifth': BASS_EVENTS['Корень-квинта'],
    'synco': BASS_EVENTS['Синкопы'],
    'walk': BASS_EVENTS['Шагающий'],
    'gallop': [(0, 1, 'r'), (2, 1, 'r'), (3, 1, 'r'), (4, 1, 'r'), (6, 1, 'r'), (7, 1, 'r'), (8, 1, 'r'),
               (10, 1, 'r'), (11, 1, 'r'), (12, 1, 'o'), (14, 1, 'r'), (15, 1, 'r')],
}


AI_GROOVE_NAMES = {'pop': 'поп-бит', 'rock': 'рок-бит', 'drive': 'драйв с 16-ми хэтами', 'four': 'бочка на каждую долю',
                   'breakbeat': 'брейкбит', 'halftime': 'полутемп', 'march': 'марш', 'shuffle': 'шаффл',
                   'lofi': 'лоу-фай бит', 'synthwave': 'синтвейв-бит', 'sparse': 'редкий и воздушный'}


AI_BASS_NAMES = {'whole': 'долгие ноты', 'root': 'долгие корни аккордов', 'pulse8': 'пульс восьмыми',
                 'octave8': 'октавы восьмыми', 'rootfifth': 'корень-квинта', 'synco': 'синкопы', 'walk': 'шагающий',
                 'gallop': 'галоп'}


AI_HARM_NAMES = {'pad': 'долгие аккорды', 'stabs': 'стабы на слабые доли', 'counter': 'контрмелодия',
                 'thirds': 'терции под мелодией'}


AI_SECTION_NAMES = {'I': 'вступление', 'A': 'куплет', 'B': 'припев', 'C': 'бридж', 'O': 'концовка'}


AI_AMBIENT_NAMES = {'A': 'тема', 'B': 'развитие', 'C': 'переход'}
