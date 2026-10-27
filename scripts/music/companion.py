# -*- coding: utf-8 -*-
"""The old "Companion": a track from a description by keywords (works offline)."""

import re

from scripts.core.constants import ARP_RATES, CHORD_RATES, NOTE_NAMES, SOUND_PRESETS, STYLES, TRACK_DEFS, VOWEL_NAMES
from scripts.core.i18n import T
from scripts.core.theory import clamp, fmt_time
from scripts.music.structure import PLATFORM_PRESETS


COMPANION_GENRES = {
    'Авто (по описанию)': None,
    'Приключение': ('Dendy · Приключение', []),
    'Экшен / скорость': ('Sega · Скоростная зона', []),
    'Битва с боссом': ('Dendy · Битва с боссом', []),
    'Хоррор / подземелье': ('Dendy · Подземелье', ['хоррор']),
    'Замок / готика': ('Dendy · Замок', []),
    'Чилл / деревня': ('Dendy · Мирная деревня', []),
    'Победа / фанфары': ('Dendy · Победа!', []),
    'Гонки': ('Sega · Гонки', []),
    'Синтвейв / ночной город': ('Sega · Ночной город', []),
    'Блюз / джаз': ('Sega · Блюз-бит', []),
    'Космос': ('Sega · Ночной город', ['космос']),
    'Грустная мелодия': ('Dendy · Подземелье', ['грусть']),
}


COMPANION_DURATIONS = {'15 секунд': 15, '30 секунд': 30, '45 секунд': 45, '1 минута': 60, '1.5 минуты': 90,
                       '2 минуты': 120, '3 минуты': 180}


COMPANION_EXAMPLES = ['эпичная битва с боссом в замке', 'спокойное утро в деревне', 'быстрые ночные гонки, sega',
                      'грустный дождь, медленно', 'загадочный космос с голосом', 'весёлое приключение как в марио',
                      'жуткая пещера без барабанов', 'неоновый город, синтвейв, 2 минуты']


MAJOR_SCALES = {'Мажор', 'Лидийский', 'Миксолидийский', 'Пентатоника мажор'}


MINOR_SCALES = {'Минор', 'Гармонический минор', 'Дорийский', 'Фригийский', 'Пентатоника минор', 'Блюзовый'}


# (word stems, effect). A word matches if it starts with a stem; phrases with a space are searched as a whole.
PROMPT_KEYWORDS = [
    (('босс', 'битв', 'бой', 'боя', 'сраж', 'драк', 'файт', 'boss', 'battle', 'fight', 'контра', 'враг'),
     dict(style='Dendy · Битва с боссом', w=2, tag='битва')),
    (('замок', 'замк', 'вампир', 'дракул', 'готич', 'castle', 'кастлвани', 'рыцар'), dict(style='Dendy · Замок', w=1.5, tag='замок')),
    (('подзем', 'пещер', 'данж', 'dungeon', 'cave', 'шахт', 'метроид', 'лабиринт'),
     dict(style='Dendy · Подземелье', w=1.5, tag='подземелье')),
    (('хоррор', 'страш', 'жут', 'ужас', 'horror', 'scary', 'призрак', 'крип', 'зомби', 'кошмар'),
     dict(style='Dendy · Подземелье', mood='minor', scale='Фригийский', tempo=-1, tag='жуть')),
    (('деревн', 'мирн', 'уют', 'village', 'town', 'ферм', 'утр', 'дом'),
     dict(style='Dendy · Мирная деревня', tag='уют')),
    (('чилл', 'chill', 'расслаб', 'relax', 'спокой', 'calm', 'лоуфай', 'lofi', 'lo-fi', 'отдых'),
     dict(style='Dendy · Мирная деревня', w=.8, tempo=-1, drums=-.15, tag='спокойствие')),
    (('побед', 'фанфар', 'триумф', 'victory', 'win', 'награ', 'финал', 'титр'),
     dict(style='Dendy · Победа!', w=2, mood='major', tag='победа')),
    (('приключ', 'путешеств', 'adventure', 'герой', 'лес', 'поле', 'overworld', 'марио', 'mario', 'зельд', 'zelda',
      'квест', 'остров'), dict(style='Dendy · Приключение', tag='приключение')),
    (('гонк', 'race', 'racing', 'машин', 'дрифт', 'мотоц', 'трасс', 'турбо', 'тачк'),
     dict(style='Sega · Гонки', w=2, tempo=1, tag='гонка')),
    (('ночн', 'ночь', 'неон', 'синтв', 'synthwave', 'ретровейв', 'retrowave', 'кибер', 'cyber', 'мегапол', 'город', 'city'),
     dict(style='Sega · Ночной город', w=.8, tag='ночной город')),
    (('блюз', 'джаз', 'blues', 'jazz', 'свинг', 'swing', 'фанк', 'funk', 'грув'),
     dict(style='Sega · Блюз-бит', w=1.5, swing=.35, tag='грув')),
    (('соник', 'sonic', 'еж', 'зона', 'платформ', 'zone'), dict(style='Sega · Скоростная зона', w=1.5, tag='зона')),
    (('экшн', 'экшен', 'action', 'погон', 'чейз', 'chase', 'бег', 'побег'),
     dict(style='Sega · Скоростная зона', tempo=1, drums=.15, tag='экшен')),
    (('грус', 'печал', 'дожд', 'одинок', 'меланх', 'sad', 'тоск', 'слез', 'осен', 'прощ'),
     dict(mood='minor', tempo=-1, density=-.15, drums=-.2, tag='грусть')),
    (('весел', 'радост', 'счаст', 'happy', 'fun', 'позитив', 'солнеч', 'летн', 'лето', 'праздн'),
     dict(mood='major', tempo=1, tag='радость')),
    (('эпич', 'epic', 'мощн', 'героич', 'величе', 'масштаб', 'легенд'),
     dict(drums=.2, complexity=.15, harmony='Контрмелодия', tag='эпик')),
    (('космос', 'космич', 'звезд', 'space', 'галакт', 'планет', 'орбит', 'galaxy', 'вселен'),
     dict(chip='sega', scale='Лидийский', echo=.3, lead_preset='Sega · FM колокол', tempo=-1, tag='космос')),
    (('подвод', 'океан', 'море', 'морск', 'вода', 'воды', 'water', 'ocean', 'аквар', 'река'),
     dict(scale='Дорийский', echo=.3, tempo=-1, density=-.1, tag='вода')),
    (('зим', 'снег', 'лед', 'мороз', 'winter', 'ice', 'рожд', 'новый год', 'новогод'),
     dict(scale='Пентатоника мажор', mood='major', lead_preset='Sega · FM колокол', tag='зима')),
    (('таинств', 'загад', 'мистик', 'mystery', 'тайн', 'магия', 'магич', 'волшеб', 'сказ'),
     dict(scale='Дорийский', density=-.1, tag='загадка')),
    (('быстр', 'энерг', 'fast', 'драйв', 'бешен', 'интенсив', 'агресс', 'жестк', 'хардкор', 'скорост'),
     dict(tempo=1, drums=.2, density=.1, tag='энергия')),
    (('медлен', 'slow', 'неспеш', 'тягуч', 'ленив', 'плавн'), dict(tempo=-1, density=-.1, tag='медленно')),
    (('сложн', 'виртуоз', 'техничн'), dict(complexity=.25, tag='сложно')),
    (('прост', 'минимал', 'легк'), dict(complexity=-.2, repetition=.2, density=-.1, tag='просто')),
    (('минор', 'minor'), dict(mood='minor', tag='минор')),
    (('мажор', 'major'), dict(mood='major', tag='мажор')),
    (('денди', 'dendy', 'nes', 'нинтенд', 'nintendo', 'famicom', 'фамиком', '8-бит', '8 бит', '8бит', '8-bit'),
     dict(chip='nes', tag='Dendy')),
    (('сега', 'sega', 'мега драйв', 'mega drive', 'genesis', '16-бит', '16 бит', '16бит', '16-bit'),
     dict(chip='sega', tag='Sega')),
    (('вокал', 'голос', 'поет', 'пени', 'хор', 'vocal', 'voice', 'choir', 'песн'), dict(voice=True, tag='голос')),
]


# English stems for the same groups — the description can be written in English too.
_EN_PROMPT = {
    'битва': ('combat', 'enemy', 'monster', 'dragon'), 'замок': ('vampire', 'dracula', 'gothic', 'knight', 'fortress'),
    'подземелье': ('mine', 'labyrinth', 'maze', 'metroid'),
    'жуть': ('spooky', 'ghost', 'haunt', 'zombie', 'nightmare', 'creep', 'eerie'),
    'уют': ('peaceful', 'cozy', 'cosy', 'farm', 'morning', 'home', 'house'),
    'спокойствие': ('peace', 'quiet', 'gentle', 'soft'), 'победа': ('triumph', 'fanfare', 'reward', 'credits'),
    'приключение': ('journey', 'hero', 'forest', 'woods', 'quest', 'island'),
    'гонка': ('car', 'drift', 'highway', 'turbo', 'nitro'), 'ночной город': ('night', 'neon', 'downtown', 'midnight'),
    'грув': ('groove', 'soul'), 'зона': ('platform', 'speed zone'), 'экшен': ('escape', 'running', 'pursuit'),
    'грусть': ('rain', 'lonel', 'melanch', 'tear', 'autumn', 'farewell', 'nostalg', 'sorrow'),
    'радость': ('joy', 'cheer', 'upbeat', 'sunny', 'summer', 'festiv', 'bright'),
    'эпик': ('heroic', 'majest', 'legend', 'grand', 'power', 'cinematic'),
    'космос': ('cosmic', 'star', 'planet', 'orbit', 'universe', 'moon', 'rocket', 'nebula'),
    'вода': ('underwater', 'sea', 'marine', 'river', 'fish', 'coral'),
    'зима': ('snow', 'frost', 'xmas', 'new year', 'holiday', 'frozen', 'icy'),
    'загадка': ('myster', 'mystic', 'magic', 'enchant', 'fairy', 'wizard', 'secret'),
    'энергия': ('energ', 'drive', 'intens', 'aggress', 'hard', 'speed', 'quick', 'rapid'),
    'медленно': ('lazy', 'smooth', 'laid-back', 'laid back'), 'сложно': ('complex', 'virtuos', 'technical', 'tricky'),
    'просто': ('simple', 'minimal', 'easy'), 'голос': ('sing', 'sung', 'chant'),
}


for _stems, _eff in PROMPT_KEYWORDS:
    _extra = _EN_PROMPT.get(_eff['tag'])
    if _extra:
        PROMPT_KEYWORDS[PROMPT_KEYWORDS.index((_stems, _eff))] = (_stems + _extra, _eff)


NEGATIONS = {'удар': 'drums', 'бараб': 'drums', 'drum': 'drums', 'бас': 'bass', 'арп': 'arp', 'гармон': 'harmony',
             'голос': 'voice', 'вокал': 'voice', 'слов': 'voice', 'мелод': 'lead', 'лид': 'lead',
             'percuss': 'drums', 'bass': 'bass', 'harmon': 'harmony', 'chord': 'harmony', 'vocal': 'voice',
             'voice': 'voice', 'sing': 'voice', 'lyric': 'voice', 'choir': 'voice', 'melod': 'lead', 'lead': 'lead'}


KEY_WORDS = {'до': 0, 'ре': 2, 'ми': 4, 'фа': 5, 'соль': 7, 'ля': 9, 'си': 11}


EN_KEYS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def interpret_prompt(text, genre, duration_label, voice_on, voice_type, rng):
    """Parses the description → generator parameters + an "as I understood it" explanation."""
    t = text.lower().replace('ё', 'е')
    words = re.findall(r'[a-zа-я0-9\-]+', t)

    def has(stem):
        return stem in t if ' ' in stem else any(w.startswith(stem) for w in words)
    scores, tags, exclude = {}, [], set()
    mods = dict(tempo=0, density=0.0, drums=0.0, complexity=0.0, repetition=0.0)
    S = dict(mood=None, scale=None, chip=None, voice=None, harmony=None, lead_preset=None, swing=None, echo=0.0)

    def apply(eff):
        if 'style' in eff:
            scores[eff['style']] = scores.get(eff['style'], 0) + eff.get('w', 1)
        for k in mods:
            mods[k] += eff.get(k, 0)
        for k in ('mood', 'scale', 'chip', 'voice', 'harmony', 'lead_preset', 'swing'):
            if k in eff:
                S[k] = eff[k]
        S['echo'] = max(S['echo'], eff.get('echo', 0))
    for stems, eff in PROMPT_KEYWORDS:
        if any(has(s) for s in stems):
            tags.append(eff['tag'])
            apply(eff)
    for m in re.finditer(r'(?:без|without|no)\s+([a-zа-я]+)', t):
        for stem, kind in NEGATIONS.items():
            if m.group(1).startswith(stem):
                exclude.add(kind)
    if 'voice' in exclude:
        S['voice'] = False
        tags = [x for x in tags if x != 'голос']
    notes = []
    g = COMPANION_GENRES.get(genre)
    if g:
        style = g[0]
        for tag in g[1]:
            for stems, eff in PROMPT_KEYWORDS:
                if eff['tag'] == tag:
                    apply(eff)
        notes.append(T('жанр выбран вручную: {0}').format(T(genre)))
    elif scores:
        style = max(scores, key=lambda k: (scores[k], rng.random()))
    else:
        minor = S['mood'] == 'minor'
        if S['chip'] == 'sega':
            style = 'Sega · Ночной город' if minor else 'Sega · Скоростная зона'
        else:
            style = ('Dendy · Подземелье' if mods['tempo'] < 0 else 'Dendy · Замок') if minor else 'Dendy · Приключение'
        notes.append(T('ключевых слов о жанре не нашёл — выбрал по настроению'))
    st = STYLES[style]
    chip = S['chip'] or st['chip']
    scale = S['scale'] or rng.choice(st['scales'])
    if S['mood'] == 'minor' and scale in MAJOR_SCALES:
        scale = 'Дорийский' if chip == 'sega' else 'Минор'
    elif S['mood'] == 'major' and scale in MINOR_SCALES:
        scale = 'Миксолидийский' if chip == 'sega' else 'Мажор'
    key = rng.randrange(12)
    for w, k in KEY_WORDS.items():
        if re.search(rf'\b{w}\s+(минор|мажор)', t):
            key = k
    for m in re.finditer(r'\b([A-Ga-g])\s*(#|♯|b|♭|-?sharp|-?flat)?[\s-]+(minor|major)\b', text, re.I):
        if m.group(1) != 'a':  # a lowercase "a" is an article, not the note A
            acc = (m.group(2) or '').lower().lstrip('-')
            key = (EN_KEYS[m.group(1).upper()] + (1 if acc in ('#', '♯', 'sharp') else -1 if acc else 0)) % 12
            break
    bpm = (st['bpm'][0] + st['bpm'][1]) // 2 + clamp(mods['tempo'], -2, 2) * 12 + rng.randint(-4, 4)
    m = re.search(r'(\d{2,3})\s*(bpm|бпм|уд)', t)
    if m:
        bpm = int(m.group(1))
        notes.append(T('темп из описания: {0} BPM').format(bpm))
    bpm = int(clamp(bpm, 60 if m else 66, 220))
    seconds = COMPANION_DURATIONS.get(duration_label) or PLATFORM_PRESETS.get(duration_label) or 45
    drop_sec = None
    m_drop = re.search(r'(дроп|акцент|кульминац|взрыв|пик|drop|climax|peak)\D{0,20}?(\d+(?:[.,]\d+)?)\s*(сек|sec|с\b|s\b)?',
                       t)
    if m_drop:
        drop_sec = float(m_drop.group(2).replace(',', '.'))
        notes.append(T('дроп / акцент на {0:g} с — из описания').format(drop_sec))
        t = t[:m_drop.start()] + t[m_drop.end():]  # so the number isn't taken for a duration
    m_min = re.search(r'(\d+(?:[.,]\d+)?)\s*(мин|min)', t)
    m_sec = re.search(r'(\d+)\s*(сек|sec|s\b|с\b)', t)
    m_clk = re.search(r'\b(\d):([0-5]\d)\b', t)
    if m_clk:
        seconds = int(m_clk.group(1)) * 60 + int(m_clk.group(2))
    elif m_min:
        seconds = float(m_min.group(1).replace(',', '.')) * 60 + (int(m_sec.group(1)) if m_sec else 0)
    elif m_sec:
        seconds = int(m_sec.group(1))
    if m_clk or m_min or m_sec:
        notes.append(T('длительность взял из описания'))
    seconds = clamp(seconds, 8, 600)
    bars = int(clamp(max(4, round(seconds * bpm / 240 / 4) * 4), 4, 128))
    voice = voice_on if S['voice'] is None else S['voice']
    if S['voice'] is not None and S['voice'] != voice_on:
        notes.append(T('голос ') + (T('включил') if voice else T('выключил')) + T(' — так сказано в описании'))
    include = [kind not in exclude and (kind != 'voice' or voice) for kind, _ in TRACK_DEFS]
    params = dict(style=style, key=key, scale=scale, bpm=bpm, bars=bars, chord_steps=CHORD_RATES[st['chords']],
                  density=clamp(st['density'] + mods['density'], .1, 1), complexity=clamp(st['complexity'] + mods['complexity'], 0, 1),
                  repetition=clamp(st['repetition'] + mods['repetition'], 0, 1), drums=clamp(st['drums'] + mods['drums'], 0, 1),
                  swing=S['swing'] if S['swing'] is not None else st['swing'], bass=st['bass'], arp=st['arp'],
                  arp_rate=ARP_RATES[st['arp_rate']], harmony=S['harmony'] or st['harmony'], chip=chip, include=include)
    real = bars * 16 * 60.0 / bpm / 4
    names = dict(TRACK_DEFS)
    summary = [T('Стиль: {0}  ({1})').format(T(style), "Dendy / NES" if chip == "nes" else "Sega / FM"),
               T('Тональность: {0} {1} · темп {2} BPM').format(NOTE_NAMES[key], T(scale), bpm),
               T('Длительность: {0} тактов ≈ {1}').format(bars, fmt_time(real)),
               T('Инструменты: {0}').format(", ".join(T(names[k]) for (k, _), inc in zip(TRACK_DEFS, include) if inc)),
               T('Голос: {0}').format(T(VOWEL_NAMES.get(voice_type, voice_type)) if voice else T("без голоса"))]
    if tags:
        summary.insert(0, T('Услышал в описании: ') + ', '.join(T(x) for x in dict.fromkeys(tags)))
    summary += [f'• {n}' for n in notes]
    return dict(params=params, lead_preset=S['lead_preset'], echo=S['echo'], voice=voice, voice_type=voice_type,
                summary=summary, seconds=seconds, drop_sec=drop_sec)


def apply_companion_sound(song, res):
    """Extra sound touches from the description."""
    for tr in song.tracks:
        if tr.kind == 'lead' and res['lead_preset']:
            vol = tr.volume
            for k, v in SOUND_PRESETS[res['lead_preset']].items():
                setattr(tr, k, v)
            tr.volume = vol
        if tr.kind in ('lead', 'arp', 'voice') and res['echo']:
            tr.echo = max(tr.echo, res['echo'])
        if tr.kind == 'voice':
            tr.vowel = res['voice_type']
            if tr.vowel == 'robot':
                tr.detune, tr.vib_depth = 0.0, 0.0
        if tr.kind == 'lead' and res['voice']:
            tr.volume = round(tr.volume * 0.7, 3)
