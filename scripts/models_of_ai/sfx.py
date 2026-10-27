# -*- coding: utf-8 -*-
"""The Forge SFX model — sound effects: a parametric synthesizer in the spirit of sfxr."""

import random

import numpy as np

from scripts.audio.synth import _quant_tri
from scripts.core.i18n import T, Tn
from scripts.core.theory import clamp
from scripts.models_of_ai.common import _ai_match, _ai_peaks, _ai_strength, AI_NEG


SFX_INFO = dict(name='Forge SFX', icon='✸', desc='звуковые эффекты: прыжок, лазер, взрыв, магия, интерфейс…')


def _rr(r, a, b):
    return r.uniform(a, b)


AI_SFX = {  # key: (name, word stems, parameter generator)
    'jump': ('Прыжок', ('прыж', 'прыг', 'jump', 'подскок'),
             lambda r: dict(wave='square', duty=r.choice([.25, .5]), f0=_rr(r, 180, 320), f1=_rr(r, 520, 900),
                            curve=.6, dur=_rr(r, .16, .28), decay=1.5)),
    'coin': ('Монетка', ('монет', 'coin', 'деньг', 'золот', 'кристал', '=gem', '=очко', '=очки'),
             lambda r: dict(wave='square', duty=.25, f0=_rr(r, 850, 1150),
                            arp=[(_rr(r, .1, .2), r.choice([1.335, 1.5, 1.26]))], dur=_rr(r, .3, .5), hold=.15,
                            decay=2.5)),
    'laser': ('Лазер / выстрел', ('лазер', 'выстрел', 'стрельб', 'пиу', 'бласт', 'laser', 'shoot', '=shot', 'пушк',
                                  'пистолет', 'ружь', 'оруж'),
              lambda r: dict(wave=r.choice(['square', 'saw']), duty=.125, duty_sweep=.3, f0=_rr(r, 1100, 2400),
                             f1=_rr(r, 120, 400), curve=.5, dur=_rr(r, .12, .3), decay=1.6)),
    'explosion': ('Взрыв', ('взрыв', '=бум', 'бомб', 'explos', 'boom', 'детон', 'гранат'),
                  lambda r: dict(wave='noise', f0=_rr(r, 1800, 3200), f1=_rr(r, 40, 110), curve=.7,
                                 dur=_rr(r, .7, 1.4), decay=1.8, sub=_rr(r, .4, .8), lp=r.choice([0, 1, 2]))),
    'hit': ('Удар / урон', ('удар', 'урон', 'больн', 'hurt', '=hit', 'ранен', 'попадан', 'damage', 'ауч', 'пинок'),
            lambda r: dict(wave='square', duty=.5, f0=_rr(r, 380, 600), f1=_rr(r, 70, 140), curve=.8,
                           dur=_rr(r, .14, .26), noise=.45, decay=2)),
    'powerup': ('Усиление', ('усилен', 'power', 'апгрейд', 'upgrade', 'бафф', 'buff', 'гриб', 'суперсил'),
                lambda r: dict(wave='square', duty=.25, f0=_rr(r, 260, 400), f1=_rr(r, 800, 1300),
                               steps=r.choice([6, 8, 10]), dur=_rr(r, .55, .9), hold=.6, decay=1.5, vib=.02,
                               vib_rate=12)),
    'select': ('Меню / выбор', ('выбор', 'клик', 'click', 'select', 'курсор', 'кнопк', 'навед', 'hover', 'переключ'),
               lambda r: dict(wave='square', duty=r.choice([.25, .5]), f0=_rr(r, 700, 1300),
                              arp=[(.4, r.choice([1.5, 1.335, 2.0]))], dur=_rr(r, .07, .13), decay=1.2)),
    'confirm': ('Подтверждение', ('подтвержд', '=ок', '=ok', 'confirm', 'принят', 'успех', 'success', 'готово',
                                  'сохранен'),
                lambda r: dict(wave='square', duty=.25, f0=_rr(r, 600, 900), arp=[(.33, 1.26), (.66, 1.19)],
                               dur=_rr(r, .22, .32), hold=.5, decay=2)),
    'error': ('Ошибка', ('ошибк', 'error', 'нельзя', 'отказ', 'неверн', 'wrong', 'deny', 'запрет'),
              lambda r: dict(wave='square', duty=.5, f0=_rr(r, 140, 220), arp=[(.5, .84)], dur=_rr(r, .25, .35),
                             hold=.7, decay=1.2, noise=.1)),
    'pickup': ('Подбор предмета', ('подбор', 'предмет', '=item', 'pickup', 'взял', 'сундук', 'ключ', 'бонус',
                                   'артефакт'),
               lambda r: dict(wave='square', duty=.5, f0=_rr(r, 500, 700), arp=[(.25, 1.5), (.5, 1.335)],
                              dur=_rr(r, .2, .3), hold=.4, decay=2)),
    'magic': ('Магия', ('маги', 'волшеб', 'заклин', 'spell', 'magic', 'исцел', 'heal', 'лечен', 'блест', 'sparkle',
                        'искр'),
              lambda r: dict(wave=r.choice(['tri', 'sine', 'square']), duty=.125, f0=_rr(r, 900, 1500),
                             f1=_rr(r, 1800, 3000), steps=r.choice([6, 8, 10]), vib=.03, vib_rate=14,
                             dur=_rr(r, .6, 1.0), hold=.3, decay=2, echo=.35)),
    'teleport': ('Телепорт', ('телепорт', 'портал', 'warp', 'варп', 'teleport', 'исчез', 'появлен'),
                 lambda r: dict(wave='sine', f0=_rr(r, 150, 260), f1=_rr(r, 1800, 2600), curve=1.4, vib=.12,
                                vib_rate=_rr(r, 18, 30), dur=_rr(r, .6, .9), hold=.5, decay=1.5, echo=.2)),
    'death': ('Проигрыш / смерть', ('смерт', 'умер', 'погиб', 'death', '=die', 'проигр', 'game over', 'гейм овер',
                                    'конец игры', '=lose'),
              lambda r: dict(wave='square', duty=.5, f0=_rr(r, 500, 700), f1=_rr(r, 60, 110), vib=.06,
                             vib_rate=10, dur=_rr(r, .9, 1.4), hold=.6, decay=1.2)),
    'bounce': ('Пружина / отскок', ('пружин', 'отскок', 'boing', 'бойнг', '=мяч', 'мячик', 'bounce', 'батут'),
               lambda r: dict(wave=r.choice(['sine', 'tri']), f0=_rr(r, 180, 260), f1=_rr(r, 500, 700), curve=.4,
                              vib=.25, vib_rate=_rr(r, 14, 20), dur=_rr(r, .35, .55), decay=1.3)),
    'step': ('Шаг', ('=шаг', 'шаги', 'шагов', 'step', 'ходьб', 'топот', 'foot'),
             lambda r: dict(wave='noise', f0=_rr(r, 700, 1200), f1=_rr(r, 200, 400), dur=_rr(r, .04, .07), decay=3)),
    'swing': ('Взмах / меч', ('=меч', 'мечом', '=меча', 'взмах', 'sword', 'slash', 'рассек', 'whoosh', 'свист',
                              'кнут', 'клинок'),
              lambda r: dict(wave='noise', f0=_rr(r, 3000, 5500), f1=_rr(r, 500, 1000), curve=.7,
                             dur=_rr(r, .14, .24), att=.03, decay=2.5)),
    'alarm': ('Тревога', ('тревог', 'сирен', 'alarm', 'alert', 'warning'),
              lambda r: dict(wave='square', duty=.5, f0=_rr(r, 700, 900), arp=[(.5, .75)], dur=_rr(r, .22, .3),
                             hold=.9, decay=1, rep=r.choice([3, 4]), rep_decay=False)),
    'bubble': ('Пузыри / вода', ('пузыр', 'буль', 'bubble', 'капл', 'всплеск', 'плеск', 'нырн'),
               lambda r: dict(wave='sine', f0=_rr(r, 300, 500), f1=_rr(r, 900, 1500), curve=.5,
                              dur=_rr(r, .06, .1), decay=2, rep=r.choice([3, 4, 5]), rep_pitch=_rr(r, 1.05, 1.25),
                              rep_gap=_rr(r, .06, .1))),
    'charge': ('Заряд / мотор', ('заряж', 'заряд', 'charge', 'накоп', 'разгон', 'мотор', 'двигат', 'engine', '=рев',
                                 'ревущ'),
               lambda r: dict(wave='saw', f0=_rr(r, 80, 140), f1=_rr(r, 500, 900), curve=1.3, vib=.04,
                              vib_rate=_rr(r, 20, 30), dur=_rr(r, 1.0, 1.6), hold=.9, decay=1, lp=1)),
    'door': ('Дверь / механизм', ('двер', 'door', 'механизм', 'рычаг', 'открыва', 'закрыва', 'засов'),
             lambda r: dict(wave='square', duty=.125, f0=_rr(r, 90, 160), f1=_rr(r, 60, 90), dur=_rr(r, .25, .4),
                            noise=.5, decay=1.5, rep=2, rep_gap=_rr(r, .12, .18), rep_pitch=.8)),
    'shield': ('Блок / металл', ('щит', '=блок', 'металл', 'shield', 'block', 'парир', 'clang', 'наковальн'),
               lambda r: dict(wave='fm', fm=_rr(r, 4, 7), fm_ratio=r.choice([3.5, 2.76, 4.2]), f0=_rr(r, 500, 900),
                              dur=_rr(r, .35, .6), decay=2.5)),
    'thunder': ('Гром', ('гром', 'молни', 'thunder', 'шторм', 'гроз'),
                lambda r: dict(wave='noise', f0=_rr(r, 400, 900), f1=_rr(r, 30, 60), curve=1.2, dur=_rr(r, 1.4, 2.2),
                               att=.01, decay=1.2, sub=.6, lp=3)),
}


def _sfx_pitch(P, k):
    P['f0'] *= k
    if P.get('f1'):
        P['f1'] *= k


def _sfx_dir(P, d):
    f0, f1 = P['f0'], P.get('f1') or P['f0'] * (1.8 if d > 0 else .5)
    if (f1 - f0) * d < 0:
        f0, f1 = f1, f0
    P['f0'], P['f1'] = f0, f1


AI_SFX_MODS = [  # (stems, what to call it in the reply, what to do with the parameters)
    (('высок', 'звонк', 'писк', 'тонк', '=high', 'higher', 'squeak', 'shrill', 'thin'), 'выше', lambda P: _sfx_pitch(P, 1.5)),
    (('низк', 'басов', 'глух', 'тяжел', 'глубок', '=low', 'lower', 'deep', 'bassy', 'heavy', 'muffled'), 'ниже', lambda P: _sfx_pitch(P, .6)),
    (('длинн', 'долг', 'протяж', '=long', 'longer', 'lengthy', 'drawn'), 'длиннее', lambda P: P.update(dur=P['dur'] * 1.6)),
    (('коротк', 'short', 'резк', 'sharp', 'brief', 'snappy'), 'короче', lambda P: P.update(dur=P['dur'] * .6)),
    (('мягк', 'нежн', 'тих', 'soft', 'чист', 'gentle', 'quiet', 'clean', 'pure'), 'мягче',
     lambda P: P.update(wave='tri' if P.get('wave') in ('square', 'saw') else P.get('wave'), crush=False)),
    (('жестк', 'грязн', 'агресс', 'злой', 'злая', 'hard', 'dirty', 'мощн', 'harsh', 'gritty', 'angry', 'powerful'), 'жёстче',
     lambda P: P.update(noise=min(.6, P.get('noise', 0) + .2), bits=3,
                        wave='saw' if P.get('wave') == 'sine' else P.get('wave'))),
    (('эхо', 'echo', 'реверб', 'reverb', 'пещер', '=зал', 'cave', '=hall'), 'с эхом', lambda P: P.update(echo=.45)),
    (('двойн', 'double', 'дважды'), 'двойной', lambda P: P.update(rep=2, rep_gap=P.get('rep_gap') or P['dur'] * .8)),
    (('тройн', 'triple', 'трижды'), 'тройной', lambda P: P.update(rep=3, rep_gap=P.get('rep_gap') or P['dur'] * .8)),
    (('робот', 'механич', 'robot', 'электрон', 'mechanic', 'electronic', 'digital'), 'механический',
     lambda P: P.update(wave='fm', fm=5, fm_ratio=3.5) if P.get('wave') != 'noise' else None),
    (('космич', 'space', 'инопланет', 'alien', '=нло', 'ufo'), 'космический',
     lambda P: P.update(vib=.1, vib_rate=6, echo=max(.3, P.get('echo', 0)))),
    (('мульт', 'смешн', 'cartoon', 'забавн', 'funny', 'silly', 'goofy'), 'мультяшный', lambda P: P.update(vib=.15, vib_rate=12)),
    (('быстр', 'fast', 'quick', 'rapid'), 'быстрее', lambda P: P.update(dur=P['dur'] * .7)),
    (('медлен', 'slow'), 'медленнее', lambda P: P.update(dur=P['dur'] * 1.4)),
    (('вверх', 'восход', 'поднима', '=up', 'растущ', 'rising', 'upward', 'ascend'), 'вверх', lambda P: _sfx_dir(P, 1)),
    (('вниз', 'пада', 'down', 'нисход', 'falling', 'descend'), 'вниз', lambda P: _sfx_dir(P, -1)),
]


AI_SFX_PACKS = [  # a sound pack for a type of game
    (('шутер', 'shooter', 'космическ', 'стрелял', 'shmup', 'shoot-em', 'space shooter'), ['laser', 'explosion', 'hit', 'powerup', 'alarm', 'death']),
    (('rpg', 'рпг', 'фэнтез', 'fantasy', 'подземел', 'данж', 'dungeon', 'adventure'), ['swing', 'magic', 'pickup', 'door', 'confirm', 'death']),
    (('интерфейс', '=ui', 'меню', 'кнопк', 'menu', 'interface', 'button', '=app'), ['select', 'confirm', 'error', 'pickup']),
    (('платформ', 'марио', 'mario', 'аркад', 'platform', 'arcade'), ['jump', 'coin', 'hit', 'powerup', 'pickup', 'death']),
]


AI_PACK_WORDS = ('набор', '=пак', 'pack', 'комплект', 'все звуки', 'несколько звук', 'звуки для', 'set of', 'sounds for',
                 'all sounds', 'several sounds', 'sound kit', 'sfx kit', 'bundle', 'collection')



# English word stems — sounds can be ordered in English too.
_EN_SFX = {
    'jump': ('=hop', 'hopping', 'leap'), 'coin': ('money', '=gold', 'gems', 'crystal', 'score', 'point'),
    'laser': ('gun', 'blaster', 'pew', 'zap', 'bullet', 'fire'), 'explosion': ('bomb', 'blast', 'grenade', 'kaboom'),
    'hit': ('punch', 'ouch', 'kick', 'impact'), 'powerup': ('power-up', 'boost', 'mushroom', 'superpower'),
    'select': ('button', 'cursor', 'menu move', 'toggle', '=tick'),
    'confirm': ('accept', 'approved', '=done', 'saved', 'okay'),
    'error': ('fail', 'denied', 'invalid', 'buzzer', 'forbidden'),
    'pickup': ('collect', 'grab', '=key', 'keys', 'loot', 'artifact', 'treasure'),
    'magic': ('wizard', 'enchant', 'healing', 'fairy dust', 'glitter'),
    'teleport': ('vanish', 'disappear', 'appear', 'blink'), 'death': ('dying', 'dead', 'lose a life', 'life lost'),
    'bounce': ('spring', 'trampoline', '=ball', 'boing'), 'step': ('footstep', '=walk', 'walking', 'stomp'),
    'swing': ('blade', 'whip', 'swoosh', 'woosh'), 'alarm': ('siren', 'alert'),
    'bubble': ('water', 'splash', 'drip', 'droplet', 'dive', 'blub'), 'charge': ('motor', 'rev', 'charging', 'power up'),
    'door': ('lever', 'gate', 'mechanism', 'open', 'close', 'creak'), 'shield': ('metal', 'parry', 'anvil', 'armor'),
    'thunder': ('lightning', 'storm', 'thunderbolt'),
}


for _k, _extra in _EN_SFX.items():
    _label, _stems, _gen = AI_SFX[_k]
    AI_SFX[_k] = (_label, _stems + _extra, _gen)

def sfx_synth(P, sr=44100, rng=None):
    """One sound from parameters: waveform, pitch slide (curve / steps), arpeggio jumps, vibrato,
    noise mix, sub-bass, envelope (attack, hold, decay), smoothing. Returns mono float64."""
    rng = rng if rng is not None else np.random.default_rng()
    dur = max(.02, float(P['dur']))
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = t / dur
    f0 = float(P['f0'])
    f1 = float(P.get('f1') or f0)
    xs = np.floor(x * P['steps']) / P['steps'] if P.get('steps') else x
    f = f0 * (f1 / f0) ** (xs ** P.get('curve', 1.0))
    for at, mult in P.get('arp', ()):
        f = np.where(x >= at, f * mult, f)
    if P.get('vib'):
        f = f * (1 + P['vib'] * np.sin(2 * np.pi * P.get('vib_rate', 8) * t))
    f = np.clip(f, 20, sr * .45)
    ph = np.cumsum(f) / sr
    wave = P.get('wave', 'square')
    if wave == 'square':
        duty = np.clip(P.get('duty', .5) + P.get('duty_sweep', 0) * x, .05, .95)
        y = np.where((ph % 1) < duty, 1.0, -1.0)
    elif wave == 'tri':
        y = _quant_tri(ph)
    elif wave == 'saw':
        y = 2 * (ph % 1) - 1
    elif wave == 'fm':
        y = np.sin(2 * np.pi * ph + P.get('fm', 3.0) * np.exp(-t * P.get('fm_decay', 6)) *
                   np.sin(2 * np.pi * ph * P.get('fm_ratio', 2)))
    elif wave == 'noise':
        idx = np.floor(np.cumsum(f * 2 / sr)).astype(np.int64)
        y = rng.uniform(-1, 1, int(idx[-1]) + 2)[idx]
    else:
        y = np.sin(2 * np.pi * ph)
    if P.get('noise'):
        y = y * (1 - P['noise']) + rng.uniform(-1, 1, n) * P['noise']
    if P.get('sub'):
        fs = 90 * (30 / 90) ** x
        y = y + P['sub'] * np.sin(2 * np.pi * np.cumsum(fs) / sr)
    hold = clamp(P.get('hold', 0), 0, .95)
    rel = np.clip((x - hold) / (1 - hold), 0, 1)
    y = y * np.minimum(1.0, t / max(.001, P.get('att', .002))) * (1 - rel) ** P.get('decay', 2.0)
    if P.get('lp'):
        k = 1 + 2 * int(P['lp'])
        y = np.convolve(y, np.ones(k) / k, mode='same')
    return y


def render_ai_sfx(P, seed, sr=44100):
    """The whole sound: repeats, echo, retro crunch, normalization → stereo float32."""
    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    rep = int(P.get('rep', 1))
    if rep > 1:
        gap = P.get('rep_gap') or P['dur']
        k = P.get('rep_pitch', 1.0)
        parts = []
        for i in range(rep):
            Q = dict(P, rep=1, f0=P['f0'] * k ** i, f1=(P.get('f1') or P['f0']) * k ** i)
            parts.append((int(i * gap * sr), sfx_synth(Q, sr, rng) * (.85 ** i if P.get('rep_decay', True) else 1)))
        y = np.zeros(max(o + len(p) for o, p in parts))
        for o, p in parts:
            y[o:o + len(p)] += p
    else:
        y = sfx_synth(P, sr, rng)
    if P.get('echo'):
        d = int(.11 * sr)
        out = np.concatenate([y, np.zeros(d * 4)])
        for i in range(1, 5):
            out[d * i:d * i + len(y)] += y * P['echo'] ** i
        y = out
    y /= max(1e-6, float(np.max(np.abs(y))))
    if P.get('crush', True):
        lv = 15 if P.get('bits', 4) >= 4 else 7
        y = np.round(y * lv) / lv
        y = y[(np.arange(len(y)) // 2) * 2]
    k = min(len(y), int(.006 * sr))
    if k:
        y[-k:] *= np.linspace(1, 0, k)
    y = y / max(1e-6, float(np.max(np.abs(y)))) * .89
    return np.column_stack([y, y]).astype(np.float32)


def ai_sfx_sound(key, mods, seed, chip):
    P = AI_SFX[key][2](random.Random(seed))
    for fn in mods:
        fn(P)
    if chip == 'sega' and P.get('wave') in ('square', 'tri'):
        P.update(wave='fm', fm=P.get('fm', 2.5), fm_ratio=P.get('fm_ratio', 2))
    return P, render_ai_sfx(P, seed)


def _ai_sfx_desc(P, audio, sr=44100):
    wave = {'square': T('квадрат'), 'tri': T('треугольник'), 'saw': T('пила'), 'sine': T('синус'), 'fm': 'FM',
            'noise': T('шум')}.get(P.get('wave'), P.get('wave'))
    f0, f1 = P['f0'], P.get('f1') or P['f0']
    mv = T('вверх') if f1 > f0 * 1.15 else T('вниз') if f1 < f0 / 1.15 else T('ровно')
    if P.get('arp') or P.get('steps'):
        mv = T('арпеджио') + ('' if mv == T('ровно') else ' ' + mv)
    extra = [x for x, on in ((T('повторы'), P.get('rep', 1) > 1), (T('эхо'), P.get('echo')),
                             (T('ретро-хруст'), P.get('crush', True))) if on]
    return ' · '.join([wave, mv, T('{0:.2f} с').format(len(audio) / sr)] + extra)


def _ai_sfx_kinds(t, words):
    found = []
    for key, (_label, stems, _gen) in AI_SFX.items():
        pos = [i for i in _ai_match(t, words, stems) if i < 0 or not (i > 0 and words[i - 1] in AI_NEG)]
        if pos:
            found.append((min(max(i, 0) for i in pos), key))
    return [k for _, k in sorted(found)]


def _ai_sfx_reply(plan, seed):
    t, words = plan['t'], plan['words']
    keys = list(plan['kinds'])
    notes = []
    if _ai_strength(t, words, AI_PACK_WORDS) > 0:
        pack = next((lst for stems, lst in AI_SFX_PACKS if _ai_strength(t, words, stems) > 0), AI_SFX_PACKS[-1][1])
        keys = keys + [k for k in pack if k not in keys]
        notes.append(T('собрал набор под тип игры'))
    if not keys:
        keys = [random.Random(seed).choice(['magic', 'powerup', 'coin', 'laser', 'select'])]
        notes.append(T('тип звука не узнал — сделал наугад; попробуйте: прыжок, монетка, лазер, взрыв, магия, '
                     'меню, дверь, тревога'))
    keys = list(dict.fromkeys(keys))[:8]
    mods = [(label, fn) for stems, label, fn in AI_SFX_MODS if _ai_strength(t, words, stems) > 0]
    results = []
    for i, key in enumerate(keys):
        s = seed + i * 7919
        P, audio = ai_sfx_sound(key, [fn for _, fn in mods], s, plan['chip'])
        results.append(dict(kind='sfx', title=T(AI_SFX[key][0]), sub=_ai_sfx_desc(P, audio), audio=audio, sr=44100,
                            peaks=_ai_peaks(audio), sfx=key, mods=[fn for _, fn in mods], seed=s,
                            chip=plan['chip'], variant=1))
    n = len(results)
    head = T('Готово! {0} {1} в ретро-стиле.').format(n, Tn(n, "звук", "звука", "звуков"))
    lines = []
    heard = [T(AI_SFX[k][0]).lower() for k in plan['kinds']] + [T(lb) for lb, _ in mods] + \
            [T(x) for x in plan['tags'] if x not in ('звуковой эффект',)]
    if heard:
        lines.append(T('Что я услышал: ') + ', '.join(dict.fromkeys(heard)) + '.')
    lines += [f'• {n_[0].upper() + n_[1:]}' for n_ in notes + plan['notes']]
    lines.append(T('Каждая карточка — отдельный звук: «⚄ Другой вариант» перегенерирует только его.'))
    return dict(model='sfx', head=head, text='\n'.join(lines), results=results)
