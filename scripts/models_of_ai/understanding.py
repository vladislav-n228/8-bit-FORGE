# -*- coding: utf-8 -*-
"""Request understanding: text and chat options → track plan (model, genre, scale, tempo, form…)."""

import re

from scripts.core.constants import VOWEL_NAMES
from scripts.core.i18n import T
from scripts.core.theory import clamp
from scripts.models_of_ai.instruments import vary_sounds
from scripts.models_of_ai.auto import choose_model
from scripts.models_of_ai.common import _ai_seconds, _ai_strength, _ai_words, AI_DURATIONS, AI_VOCALS, key_text
from scripts.models_of_ai.genres import _NES, _SEGA, AI_DEFAULT_GENRES, AI_GENRES
from scripts.models_of_ai.jingle import AI_JINGLE_TITLES, AI_JINGLES
from scripts.models_of_ai.lexicon import AI_LEXICON
from scripts.models_of_ai.registry import AI_MODELS
from scripts.models_of_ai.sfx import _ai_sfx_kinds
from scripts.music.companion import EN_KEYS, KEY_WORDS, MINOR_SCALES, NEGATIONS


def ai_understand(text, opts, rng):
    """Request + chosen options → plan: model, genre, scale, tempo, duration, form, sounds, vocals."""
    t, words = _ai_words(text)
    feat = dict(val=0.0, en=0.0, dark=0.0, epic=0.0, dream=0.0)  # character shift relative to the genre
    votes = dict(melody=.3, ambient=0.0, action=0.0, jingle=0.0, sfx=0.0)
    gvotes, tags, notes = {}, [], []
    S = dict(tempo=0, voc=None, chip=None, mood=None, lead=None, jt=None, vowel=None, loop=False)
    for stems, eff in AI_LEXICON:
        k = _ai_strength(t, words, stems)
        if not k:
            continue
        if k < 0:  # "not sad" — a slight shift in the opposite direction
            for f, d in eff.get('f', {}).items():
                feat[f] -= d * .5
            continue
        for f, d in eff.get('f', {}).items():
            feat[f] += d * k
        for m, w in eff.get('m', {}).items():
            votes[m] += w
        for g, w in eff.get('g', {}).items():
            gvotes[g] = gvotes.get(g, 0) + w
        S['tempo'] += eff.get('tempo', 0)
        for key in ('voc', 'chip', 'mood', 'lead', 'jt', 'vowel', 'loop'):
            if key in eff:
                S[key] = eff[key]
        if eff.get('tag'):
            tags.append(eff['tag'])
    for name, g in AI_GENRES.items():  # every matched genre word is a vote ("boss battle" > "in a castle")
        k = sum(max(0.0, _ai_strength(t, words, (s,))) for s in g['kw'])
        if k > 0:
            gvotes[name] = gvotes.get(name, 0) + 2 * k
    sfx_kinds = _ai_sfx_kinds(t, words)
    if sfx_kinds:
        votes['sfx'] += .8 + .4 * len(sfx_kinds)
    u = dict(val=feat['val'], en=.5 + feat['en'], dark=.25 + feat['dark'], epic=.3 + feat['epic'],
             dream=.3 + feat['dream'])
    wts = (('val', 1.2), ('en', 1.0), ('dark', .8), ('epic', .6), ('dream', .8))

    def dist(n):  # how far the genre's character is from the request's character
        return sum(w * (AI_GENRES[n]['feat'][k] - u[k]) ** 2 for k, w in wts)
    genre = opts.get('genre') if opts.get('genre') in AI_GENRES else None
    if genre:
        notes.append(T('жанр выбран вручную: {0}').format(T(genre)))
    elif gvotes:
        genre = max(gvotes, key=lambda k: (gvotes[k], -dist(k), rng.random()))
    seconds, drop = _ai_seconds(t)
    seconds_req = AI_DURATIONS.get(opts.get('dur'))
    if seconds_req:
        notes.append(T('длительность выбрана вручную: {0}').format(T(opts["dur"])))
    elif seconds:
        seconds_req = seconds
        notes.append(T('длительность взял из запроса'))
    model = opts.get('model', 'auto')
    auto = model not in AI_MODELS or model == 'auto'
    if auto:
        if genre:
            votes[AI_GENRES[genre]['model']] += .8
        if seconds_req is not None:
            votes['jingle'] += 2 if seconds_req <= 10 else -2 if seconds_req >= 20 else 0
        if S['jt']:
            votes['jingle'] += .3
        model = choose_model(votes)
    if model == 'sfx':
        return dict(model='sfx', auto=auto, text=text, t=t, words=words, kinds=sfx_kinds, chip=S['chip'],
                    tags=list(dict.fromkeys(tags)), notes=notes)
    if not genre:
        if model == 'action':
            u['en'] += .35
        if model == 'ambient':
            u['en'] -= .25
            u['dream'] += .2
        pool = [n for n, g in AI_GENRES.items() if model not in ('ambient', 'action') or g['model'] == model]
        if any(abs(v) > 1e-6 for v in feat.values()):
            genre = min(pool, key=lambda n: dist(n) + rng.random() * .05)
            notes.append(T('жанр подобрал по настроению запроса'))
        else:
            genre = rng.choice(AI_DEFAULT_GENRES[model])
            notes.append(T('явных подсказок о жанре не нашёл — выбрал сам'))
    g = AI_GENRES[genre]
    F = {k: clamp(g['feat'][k] + feat[k], -1.0 if k == 'val' else 0.0, 1.0) for k in feat}
    if model == 'ambient':
        F['en'] = min(F['en'], .45)
    elif model == 'action':
        F['en'] = max(F['en'], .75)
    chip = S['chip'] or g['chip']
    sounds = list(g['sounds'])
    if chip != g['chip']:
        conv, other = (_NES, 'Sega') if chip == 'nes' else (_SEGA, 'NES')
        sounds = [conv[i] if s.startswith(other) else s for i, s in enumerate(sounds)]
    if not opts.get('instruments'):  # instruments on "auto" — timbres change a little from track to track
        sounds = vary_sounds(sounds, chip, rng, lead_fixed=bool(S['lead']))
    if S['lead']:
        sounds[0] = S['lead']
    key, exact_scale = rng.randrange(12), None
    for w, kk in KEY_WORDS.items():
        m = re.search(rf'\b{w}(\s+диез|\s+бемоль)?[\s-]+(минор|мажор)', t)
        if m:
            key = (kk + (0 if not m.group(1) else 1 if 'диез' in m.group(1) else -1)) % 12
            S['mood'] = 'minor' if m.group(2) == 'минор' else 'major'
            exact_scale = 'Минор' if m.group(2) == 'минор' else 'Мажор'
    if exact_scale is None:  # in English: "A minor", "C# major", "Bb minor" (a lowercase "a" is an article)
        for m in re.finditer(r'\b([A-Ga-g])\s*(#|♯|b|♭|-?sharp|-?flat)?[\s-]+(minor|major)\b', text, re.I):
            if m.group(1) == 'a':
                continue
            acc = (m.group(2) or '').lower().lstrip('-')
            key = (EN_KEYS[m.group(1).upper()] + (1 if acc in ('#', '♯', 'sharp') else -1 if acc else 0)) % 12
            minor = m.group(3).lower() == 'minor'
            S['mood'] = 'minor' if minor else 'major'
            exact_scale = 'Минор' if minor else 'Мажор'
            break
    if exact_scale:
        notes.append(T('тональность из запроса: {0}').format(key_text(key, exact_scale)))
    scale = exact_scale or rng.choice(g['scales'])
    minorish = scale in MINOR_SCALES
    if S['mood'] == 'minor' or (S['mood'] is None and F['val'] < -.35 and not minorish):
        if not minorish:
            scale = {'Лидийский': 'Дорийский', 'Пентатоника мажор': 'Пентатоника минор',
                     'Миксолидийский': 'Дорийский'}.get(scale, 'Минор')
    elif S['mood'] == 'major' or (F['val'] > .45 and minorish):
        if minorish:
            scale = {'Пентатоника минор': 'Пентатоника мажор', 'Дорийский': 'Миксолидийский',
                     'Блюзовый': 'Миксолидийский'}.get(scale, 'Мажор')
    if F['dark'] > .85 and scale == 'Минор' and not exact_scale:
        scale = rng.choice(['Фригийский', 'Гармонический минор'])
    if F['dream'] > .85 and scale == 'Мажор' and not exact_scale:
        scale = 'Лидийский'
    lo, hi = g['bpm']
    bpm = (lo + hi) / 2 + (F['en'] - g['feat']['en']) * 45 + clamp(S['tempo'], -2, 2) * 10 + rng.uniform(-3, 3)
    if model == 'ambient':
        bpm *= .92
    m = re.search(r'(\d{2,3})\s*(bpm|бпм|уд)', t)
    if m:
        bpm = int(m.group(1))
        notes.append(T('темп из запроса: {0} BPM').format(bpm))
    bpm = clamp(bpm, 56, 210)
    seconds = seconds_req or (None if model == 'jingle' else 60)
    bars = 0
    if model != 'jingle':
        seconds = clamp(seconds, 6, 600)
        bars = max(2, int(round(seconds * bpm / 240)))
        fit = bars * 240 / seconds
        if abs(fit - bpm) / bpm <= .15:
            bpm = fit
    exclude = set()
    for mm in re.finditer(r'(?:без|without|no)\s+([a-zа-я]+)', t):
        for stem, kind in NEGATIONS.items():
            if mm.group(1).startswith(stem):
                exclude.add(kind)
    voc = AI_VOCALS.get(opts.get('voc'))
    if voc is None:
        voc = bool(S['voc'])
    else:
        notes.append(T('вокал выбран вручную'))
    if 'voice' in exclude:
        voc = False
    if model == 'jingle' and voc:
        voc = False
        notes.append(T('в коротком джингле вокал не используется'))
    vowel = opts.get('vowel') if opts.get('vowel') in VOWEL_NAMES else (
        S['vowel'] or ('о' if F['dark'] > .6 else g['vowel']))
    loop = bool(S['loop']) or model == 'ambient'
    intro = not re.search(r'(без|without|no)\s+(вступ|intro)', t) and model != 'ambient'
    outro = not loop and not re.search(r'(без|without|no)\s+(концовк|финал|ending|outro|finale)', t)
    jt = S['jt']
    if model == 'jingle' and not jt:
        jt = {'Победа / фанфары': 'victory', 'Главное меню / титры': 'logo', 'Битва с боссом': 'danger',
              'Подземелье / хоррор': 'danger', 'Грусть / дождь': 'gameover'}.get(genre) or (
            'gameover' if F['val'] < -.3 else 'start' if F['en'] > .6 else 'logo')
    if model == 'jingle':
        jt = jt if jt in AI_JINGLES else 'victory'
    title = T(AI_JINGLE_TITLES[jt] if model == 'jingle' else rng.choice(g['titles']))
    return dict(
        model=model, auto=auto, genre=genre, style=g['style'], chip=chip, key=key, scale=scale, bpm=round(bpm, 2),
        seconds=seconds, seconds_req=seconds_req, bars=bars,
        density=clamp(g['density'] + (F['en'] - g['feat']['en']) * .35 - (.12 if model == 'ambient' else 0), .2, .95),
        complexity=clamp(g['complexity'] + (F['epic'] - g['feat']['epic']) * .2 + (.1 if model == 'action' else 0),
                         .2, .9),
        legato=g['legato'], swing=g['swing'], echo=max(g['echo'], max(0.0, F['dream'] - .5) * .5),
        emul=.75 + .5 * F['en'], voc=voc, vowel=vowel, sounds=sounds, groove=g['groove'], bass=g['bass'],
        harm=g['harm'], arp=g['arp'], chord_len=2 if model == 'ambient' else g['chord_len'],
        kit=g['kit'] or ('Sega' if chip == 'sega' else 'NES'), exclude=exclude, intro=intro, outro=outro,
        loop=loop, drop=drop, jt=jt, feat=F, tags=list(dict.fromkeys(tags)), notes=notes, title=title, text=text)
