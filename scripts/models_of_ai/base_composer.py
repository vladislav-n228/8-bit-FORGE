# -*- coding: utf-8 -*-
"""Общий композитор моделей Melody / Ambient / Action: форма → гармония → мотивы → фразы."""

import random

from scripts.core.constants import BASS_PATTERNS, HARMONY_MODES, RANGES, SOUND_PRESETS, TRACK_DEFS
from scripts.core.model import default_tracks, Note, Song
from scripts.core.theory import chord_at, chord_pcs, chord_pitches, clamp, nearest, parent_scale, scale_pitches
from scripts.models_of_ai.music_theory import AI_BASS, AI_CAD_RHYTHMS, AI_FAMILY, AI_GROOVES, AI_PROGS, AI_RHYTHMS
from scripts.music.composer import Composer
from scripts.music.structure import apply_structure, drop_step_for


def _onsets(rhythm):
    return [i for i, ch in enumerate(rhythm) if ch == 'x']


class AIComposer:
    """Общий композитор моделей Melody / Ambient / Action: форма → гармония → мотивы → фразы → аранжировка.
    Модель-наследник задаёт FORM (части и их энергию) и AMBIENT (дышащая фоновая подача)."""
    FORM = [('A', .5), ('B', .8), ('A', .55), ('B', .88), ('C', .45), ('B', .95)]
    AMBIENT = False

    def __init__(self, plan, seed):
        self.P = plan
        self.seed = seed
        self.rng = random.Random(seed)
        self.model = plan['model']

    def compose(self):
        P = self.P
        sg = self.song = Song(bpm=P['bpm'], bars=P['bars'], key=P['key'], scale=P['scale'], style=P['style'],
                              seed=self.seed, swing=P['swing'], chord_steps=16)
        self.secs, b, counts = [], 0, {}
        for name, nb, e in self._form(sg.bars, P['intro'], P['outro']):
            self.secs.append(dict(name=name, b0=b, nb=nb, e=clamp(e * P['emul'], .05, 1.0), n=counts.get(name, 0),
                                  final=False, next=None))
            counts[name] = counts.get(name, 0) + 1
            b += nb
        for a, nxt in zip(self.secs, self.secs[1:]):
            a['next'] = nxt
        body = [s for s in self.secs if s['name'] not in ('I', 'O')]
        if body and not P['loop'] and self.secs[-1]['name'] != 'O':
            body[-1]['final'] = True
        self._chords()
        self.pool = scale_pitches(sg, 57, 88)
        self.motifs = {}
        sg.tracks = default_tracks(P['chip'])
        by = {t.kind: t for t in sg.tracks}
        lead = self._lead()
        by['voice'].notes = self._voice(lead) if P['voc'] else []
        by['lead'].notes = lead
        by['harmony'].notes = self._harmony(lead)
        by['bass'].notes = self._bass()
        by['arp'].notes = self._arp()
        by['drums'].notes = self._drums()
        for kind in P['exclude']:
            if kind in by:
                by[kind].notes = []
        self._sounds(by)
        for t in sg.tracks:
            t.notes = Composer.clean(t.notes, 0, sg.total_steps)
        sg.params = _ai_params(sg, P, intro=any(s['name'] == 'I' for s in self.secs),
                               outro=any(s['name'] == 'O' for s in self.secs),
                               avg_e=sum(s['e'] * s['nb'] for s in self.secs) / max(1, sg.bars))
        if P.get('drop'):
            ds = drop_step_for(sg, P['drop'])
            if ds:
                apply_structure(sg, False, False, ds)
                sg.params['drop_step'] = ds
        return sg


    def _form(self, bars, intro_ok=True, outro_ok=True):
        """Форма трека: [(часть, тактов, энергия 0..1)]. I — вступление, A — куплет, B — припев, C — бридж, O — концовка."""
        seq = self.FORM
        intro = 0 if (not intro_ok or bars < 12) else 2 if bars < 40 else 4
        outro = 0 if (not outro_ok or bars < 8) else 1 if bars < 24 else 2
        body = bars - intro - outro
        form = [('I', intro, .3)] if intro else []
        i = 0
        while body > 0:
            n = 8 if (body >= 12 or body == 8) else body if body <= 8 else 4
            name, e = seq[i % len(seq)]
            if i >= len(seq):
                e = min(1.0, e + .05)
            if i == 0 and n == body and not self.AMBIENT:
                name, e = 'B', .8  # короткий трек — сразу запоминающийся «хук»
            form.append((name, n, e))
            body -= n
            i += 1
        if outro:
            form.append(('O', outro, .35))
        return form

    # ── гармония ──
    def _chords(self):
        P, rng, sg = self.P, self.rng, self.song
        pr = AI_PROGS[AI_FAMILY.get(sg.scale, sg.scale)]
        verse, chorus, bridge = rng.choice(pr['verse']), rng.choice(pr['chorus']), rng.choice(pr['bridge'])
        progs = {'I': verse, 'A': verse, 'B': chorus, 'C': bridge, 'O': [0]}
        chords = []
        for s in self.secs:
            pg = progs[s['name']]
            cl = 1 if len(pg) >= 12 else P['chord_len']
            chords += [pg[(j // cl) % len(pg)] for j in range(s['nb'])]
        cad = pr['cad']
        for s in self.secs:  # перед припевом — доминанта, чтобы припев «распахнулся»
            nxt = s['next']
            if nxt and nxt['name'] == 'B' and s['name'] in ('I', 'A', 'C') and s['nb'] >= 2:
                chords[s['b0'] + s['nb'] - 1] = cad
        n = len(chords)
        if P['loop']:
            if n >= 2:
                chords[-1] = cad  # конец ведёт обратно в начало — петля без шва
        else:
            outro = next((s for s in self.secs if s['name'] == 'O'), None)
            if outro:
                for i in range(outro['b0'], n):
                    chords[i] = 0
                if outro['b0'] >= 1:
                    chords[outro['b0'] - 1] = cad
            else:
                chords[-1] = 0
                if n >= 2:
                    chords[-2] = cad
        sg.chords = chords

    # ── мелодия: мотив → фраза → период ──
    def _level(self, e):
        if self.AMBIENT:
            return 'calm' if self.P['density'] < .55 else 'medium'
        d = self.P['density'] * .6 + e * .4
        return 'calm' if d < .45 else 'medium' if d < .72 else 'busy'

    def _contour(self, n, shape):
        rng, cx = self.rng, self.P['complexity']
        c, cur = [0], 0
        d = 1 if shape in ('rise', 'arch', 'leap') else -1 if shape == 'fall' else rng.choice((-1, 1))
        for i in range(1, n):
            if shape == 'leap' and i == 1:
                step = rng.choice((3, 4))
                d = -1
            elif len(c) >= 2 and abs(c[-1] - c[-2]) >= 2:
                step = -1 if c[-1] > c[-2] else 1  # после скачка — шаг назад, «заполнение»
            else:
                if shape == 'arch' and i >= (n + 1) // 2:
                    d = -1
                r = rng.random()
                step = d * rng.choice((2, 3)) if r < .1 + .22 * cx else 0 if r < .2 + .22 * cx else d
                if shape == 'wave' and rng.random() < .3:
                    d = -d
            cur = clamp(cur + step, -4, 6)
            c.append(cur)
        return c

    def _motif(self, name, e):
        if name in self.motifs:
            return self.motifs[name]
        rng = self.rng
        lvl = self._level(e)
        if name == 'C' and lvl == 'busy':
            lvl = 'medium'
        lib = AI_RHYTHMS[lvl]
        r1 = rng.choice(lib)
        r2 = r1 if rng.random() < .45 else rng.choice(lib)
        shapes = {'A': ('rise', 'wave', 'arch'), 'B': ('arch', 'leap', 'fall'), 'C': ('fall', 'wave')}[name]
        c1 = self._contour(len(_onsets(r1)), rng.choice(shapes))
        if r2 == r1:
            c2 = list(c1)
            for i in rng.sample(range(1, len(c2)), min(2, len(c2) - 1)):
                c2[i] += rng.choice((-1, 1))
        else:
            c2 = self._contour(len(_onsets(r2)), rng.choice(shapes))
        h = len(c1) // 2
        c3 = [v + (2 if i >= h else 1 if i else 0) for i, v in enumerate(c1)]  # развитие: тема поднимается
        m = self.motifs[name] = dict(r1=r1, c1=c1, r2=r2, c2=c2, c3=c3, lvl=lvl)
        return m

    def _center(self, s):
        base = {'A': 69, 'B': 74, 'C': 66}.get(s['name'], 72)
        if s['name'] == 'B':
            base += min(s['n'], 2)
        return base + (3 if self.AMBIENT else 0)

    def _bar(self, bar, rhythm, contour, center, vel, last):
        sg, rng, pool = self.song, self.rng, self.pool
        b0 = bar * 16
        on = _onsets(rhythm)
        ct = chord_pitches(sg, chord_at(sg, b0), pool[0], pool[-1]) or pool
        ref = center if last is None else center * .6 + last * .4
        ai = pool.index(nearest(pool, nearest(ct, ref)))
        leg = self.P['legato']
        out = []
        for k, o in enumerate(on):
            gap = (on[k + 1] if k + 1 < len(on) else 16) - o
            if k == len(on) - 1:
                gap = min(gap, 6)
            ln = gap if leg >= .8 or gap <= 1 else max(1, int(round(gap * leg)))
            p = pool[int(clamp(ai + contour[k % len(contour)], 0, len(pool) - 1))]
            pos = b0 + o
            if o % 4 == 0 or ln >= 4:  # на сильных долях и долгих нотах — звук аккорда
                cts = chord_pitches(sg, chord_at(sg, pos), pool[0], pool[-1])
                if cts:
                    p = nearest(cts, p)
            if out and abs(p - out[-1].p) > 9:
                alt = p - 12 if p > out[-1].p else p + 12
                if pool[0] <= alt <= pool[-1]:
                    p = alt
            v = vel + (.1 if o % 8 == 0 else .04 if o % 4 == 0 else 0) + rng.uniform(-.04, .04)
            out.append(Note(pos, ln, p, clamp(v, .2, 1.0)))
        return out

    def _cadence(self, bar, center, vel, last, final, lvl):
        """Конец фразы: поступенный подход к звуку аккорда; в финале — к тонике."""
        sg, rng, pool = self.song, self.rng, self.pool
        b0 = bar * 16
        pcs = chord_pcs(sg, chord_at(sg, b0))
        tonic = sg.key % 12
        tpcs = [tonic] if final and tonic in pcs else (pcs[1:] if rng.random() < .7 else pcs)
        cand = [p for p in pool if p % 12 in tpcs] or pool
        ref = (center + (last if last is not None else center)) / 2 - (2 if final else 0)
        target = nearest(cand, ref)
        ti = pool.index(target)
        on = _onsets(rng.choice(AI_CAD_RHYTHMS[lvl]))
        side = 1 if (last is None or last >= target) else -1
        out = []
        for k, o in enumerate(on):
            idx = int(clamp(ti + side * (len(on) - 1 - k), 0, len(pool) - 1))
            if k + 1 < len(on):
                ln = on[k + 1] - o
                if self.P['legato'] < .8 and ln > 1:
                    ln -= 1
            else:
                ln = 16 - o if final else max(2, 14 - o)
            out.append(Note(b0 + o, ln, pool[idx], clamp(vel + (.08 if o == 0 else 0), .2, 1.0)))
        return out

    def _lead(self):
        out, last = [], None
        for s in self.secs:
            name, e = s['name'], s['e']
            if name == 'I':
                continue
            if name == 'O':
                cand = [p for p in self.pool if p % 12 == self.song.key % 12]
                out.append(Note(s['b0'] * 16, min(16, s['nb'] * 16), nearest(cand, last or 72), .8))
                continue
            m = self._motif(name, e)
            center = self._center(s)
            vel = .6 + .25 * e
            variants = [(m['r1'], m['c1']), (m['r2'], m['c2'])]
            for j in range(s['nb']):
                bar = s['b0'] + j
                ph, k = divmod(j, 4)
                plen = min(4, s['nb'] - ph * 4)
                if self.AMBIENT and ph % 2 == 1:
                    continue  # в эмбиенте мелодия дышит: через фразу отвечает арпеджио
                if plen >= 2 and k == plen - 1:
                    final = (j == s['nb'] - 1 and s['final']) or ph % 2 == 1
                    notes = self._cadence(bar, center, vel, last, final, m['lvl'])
                elif k == 2:
                    notes = self._bar(bar, m['r1'], m['c3'] if ph % 2 else m['c1'], center, vel, last)
                else:
                    notes = self._bar(bar, *variants[k], center, vel, last)
                if notes:
                    last = notes[-1].p
                out += notes
        return out

    def _voice(self, lead):
        sg = self.song
        lo, hi = RANGES['voice']
        out, prev = [], (lo + hi) // 2
        for s in self.secs:
            a, b = s['b0'] * 16, (s['b0'] + s['nb']) * 16
            name = s['name']
            if name == 'B' and not self.AMBIENT:  # голос поёт тему припева
                src = [n for n in lead if a <= n.s < b]
                part = []
                for n in src:
                    if n.s % 2 and n.l < 2:
                        continue
                    p = n.p
                    while p > hi:
                        p -= 12
                    while p < lo:
                        p += 12
                    if part and part[-1].p == p and part[-1].s + part[-1].l >= n.s - 1:
                        part[-1].l = n.s + n.l - part[-1].s
                        continue
                    part.append(Note(n.s, n.l, p, .82))
                for x, y in zip(part, part[1:]):
                    if y.s - x.s <= 8:
                        x.l = max(x.l, y.s - x.s)
                out += part
                if part:
                    prev = part[-1].p
                for n in src:
                    n.v *= .7  # лид уступает место голосу
            elif name in ('A', 'B', 'C') and (self.AMBIENT or s['e'] >= .35):  # тихий бэк-вокал / хор
                span = 32 if self.AMBIENT else 16
                for pos in range(a, b, span):
                    tones = chord_pitches(sg, chord_at(sg, pos), lo, hi - 4) or [lo + 5]
                    prev = nearest(tones, prev)
                    out.append(Note(pos, max(1, min(span, b - pos) - 2), prev, .6 if self.AMBIENT else .5))
            elif name == 'O':
                tones = chord_pitches(sg, 0, lo, hi) or [lo + 5]
                out.append(Note(a, min(16, b - a), nearest(tones, prev), .7))
        return out

    # ── аккомпанемент ──
    def _voicing(self, pos, prev, lo=55, hi=72):
        tones = chord_pitches(self.song, chord_at(self.song, pos), lo, hi)
        if len(tones) < 2:
            return tones or [64]
        pairs = [(tones[i], tones[i + 1]) for i in range(len(tones) - 1)]
        if prev:
            return min(pairs, key=lambda q: abs(q[0] - prev[0]) + abs(q[1] - prev[-1]))
        return pairs[len(pairs) // 2]

    def _pad(self, out, pos, ln, prev, v):
        prev = self._voicing(pos, prev)
        out += [Note(pos, ln, p, v) for p in prev]
        return prev

    def _harmony(self, lead):
        sg, rng, P = self.song, self.rng, self.P
        hv, hc = P['harm']
        out, prev = [], None
        pool = scale_pitches(sg, 48, 84)
        for s in self.secs:
            name, e = s['name'], s['e']
            a, b = s['b0'] * 16, (s['b0'] + s['nb']) * 16
            style = hc if name == 'B' else hv
            if name in ('I', 'O') or self.AMBIENT:
                style = 'pad'
            elif name == 'C':
                style = 'counter' if hv == 'pad' else 'pad'
            if style == 'thirds':
                src = [n for n in lead if a <= n.s < b and n.l >= 2]
                with_notes = {n.s // 16 for n in src}
                for n in src:
                    p = pool[max(0, pool.index(nearest(pool, n.p)) - 2)]
                    while p > 76:
                        p -= 12
                    out.append(Note(n.s, n.l, p, n.v * .7))
                for bar in range(s['b0'], s['b0'] + s['nb']):
                    if bar not in with_notes:
                        prev = self._pad(out, bar * 16, 16, prev, .42)
            elif style == 'stabs':
                offs = (2, 6, 10, 14) if e >= .5 else (4, 12)
                ln = 2 if P['legato'] >= .8 else 1
                for bar in range(s['b0'], s['b0'] + s['nb']):
                    for o in offs:
                        prev = self._voicing(bar * 16 + o, prev)
                        out += [Note(bar * 16 + o, ln, p, .5 + (.08 if o in (2, 10) else 0)) for p in prev]
            elif style == 'counter':
                cur = prev[-1] if prev else 64
                for pos in range(a, b, 8):
                    tones = chord_pitches(sg, chord_at(sg, pos), 55, 74) or [64]
                    busy = {n.p % 12 for n in lead if n.s <= pos < n.s + n.l}
                    cand = sorted(tones, key=lambda p: (p % 12 in busy, abs(p - cur), rng.random()))
                    cur = cand[1] if cand[0] == cur and len(cand) > 1 and rng.random() < .5 else cand[0]
                    out.append(Note(pos, min(8, b - pos), cur, .5))
                prev = None
            else:  # долгие аккорды с плавным голосоведением
                bar, end = s['b0'], s['b0'] + s['nb']
                while bar < end:
                    span = 1
                    if e < .7:
                        while (bar + span < end and span < 4 and
                               chord_at(sg, (bar + span) * 16) == chord_at(sg, bar * 16)):
                            span += 1
                    prev = self._pad(out, bar * 16, span * 16, prev, .4 + .1 * e)
                    bar += span
        return out

    def _bass(self):
        sg, P = self.song, self.P
        comp = Composer(sg, self.rng)
        scale_pcs = {(sg.key + i) % 12 for i in parent_scale(sg)}
        out = []
        for s in self.secs:
            name, e, style = s['name'], s['e'], P['bass']
            if name == 'O':
                pos = s['b0'] * 16
                out.append(Note(pos, min(16, s['nb'] * 16), comp._bass_pitch('r', pos), .95))
                continue
            if e < .2:
                style = 'whole'
            elif name == 'I' or e < .35 or (name == 'C' and e < .6 and style in ('pulse8', 'gallop', 'octave8')):
                style = 'root'
            for j in range(s['nb']):
                b0 = (s['b0'] + j) * 16
                fill = j == s['nb'] - 1 and e >= .5 and b0 + 16 < sg.total_steps and style not in ('root', 'whole')
                for off, ln, role in AI_BASS[style]:
                    if fill and off >= 12:
                        continue
                    out.append(Note(b0 + off, ln, comp._bass_pitch(role, b0 + off), .9 if off % 4 == 0 else .78))
                if fill:  # подход к следующему аккорду: ступень лада ниже + хроматика
                    nxt = comp._bass_pitch('r', b0 + 16)
                    q = next((p for p in range(nxt - 1, nxt - 5, -1) if p % 12 in scale_pcs), nxt - 2)
                    out += [Note(b0 + 12, 2, q, .8), Note(b0 + 14, 2, nxt + 2 if q == nxt - 1 else nxt - 1, .85)]
        return out

    def _arp(self):
        sg = self.song
        pat, when = self.P['arp']
        if pat == 'none':
            return []
        amb = self.AMBIENT
        out = []
        for s in self.secs:
            name, e = s['name'], s['e']
            a = s['b0'] * 16
            if name == 'O':
                tones = chord_pitches(sg, 0, 72, 90)[:4] or [76]
                out += [Note(a + k, 1 if k < 3 else 12, tones[k % len(tones)], .55) for k in range(4)]
                continue
            on = amb or when == 'always' or (when == 'chorus' and name == 'B')
            if not on:
                continue
            rate = 1 if (e >= .75 and not amb) else 2
            vel = .5 + .15 * e
            for j in range(s['nb']):
                answer = amb and (j // 4) % 2 == 1  # отвечает на паузу мелодии
                for pos in range(a + j * 16, a + j * 16 + 16, rate):
                    tones = chord_pitches(sg, chord_at(sg, pos), 72, 91)[:4] or [76]
                    n = len(tones)
                    k = (pos % 16) // rate
                    if pat == 'down':
                        p = tones[::-1][k % n]
                    elif pat == 'updown':
                        seq = tones + tones[-2:0:-1]
                        p = seq[k % len(seq)]
                    elif pat == 'broken':
                        p = tones[[0, 2, 1, 3][k % 4] % n]
                    elif pat == 'trill':
                        p = tones[0] if k % 2 == 0 else tones[min(2, n - 1)]
                    else:
                        p = tones[k % n]
                    out.append(Note(pos, rate, p, vel + (.12 if pos % 4 == 0 else 0) + (.1 if answer else 0)))
        return out

    def _drums(self):
        rng = self.rng
        G = AI_GROOVES[self.P['groove']]
        amb = self.AMBIENT
        out = []
        for s in self.secs:
            name, e = s['name'], s['e'] * (.55 if amb else 1.0)
            a = s['b0'] * 16
            if name == 'O':
                out += [Note(a, 1, 49, .85), Note(a, 1, 36, 1.0)]
                continue
            if name == 'I':  # вступление: хэты нарастают, в конце — дробь малого
                total = s['nb'] * 16
                for j in range(s['nb']):
                    b0 = a + j * 16
                    last = j == s['nb'] - 1
                    out.append(Note(b0, 1, 36, .8))
                    for o in range(0, 8 if last else 16, 2):
                        out.append(Note(b0 + o, 1, 42, .25 + .25 * (j * 16 + o) / total))
                    if last:
                        out += [Note(b0 + o, 1, 38, .45 + .07 * (o - 8)) for o in range(8, 16) if o >= 12 or o % 2 == 0]
                continue
            if e < .15:
                continue
            nxt = s['next']
            soft = e < .45
            for j in range(s['nb']):
                b0 = a + j * 16
                hits = {}
                for o, ch in enumerate(G['k']):
                    if ch == 'x' and (not soft or o % 8 == 0):
                        hits[(o, 36)] = .95
                for o, ch in enumerate(G['s']):
                    if ch == 'x' and (not soft or o == 12 or (o == 4 and e >= .3)):
                        hits[(o, 38)] = .85
                    elif ch == 'o' and not soft:
                        hits[(o, 38)] = .32
                for o, ch in enumerate(G['h']):
                    if ch != '.' and not (soft and o % 4):
                        hits[(o, 46 if ch == 'o' else 42)] = .48 if o % 4 == 0 else .34
                if e >= .85 and G['h'].count('x') == 8:  # пик энергии — 16-е хэты
                    for o in range(1, 16, 2):
                        hits[(o, 42)] = .24
                if not amb and ((j == 0 and (name == 'B' or e >= .7)) or (j and j % 8 == 0 and e >= .6)):
                    hits[(0, 49)] = .75
                if not amb and e >= .45 and (j % 4 == 3 or j == s['nb'] - 1):  # сбивка в конце фразы
                    big = j == s['nb'] - 1 and nxt is not None and e >= .6
                    st = 8 if big else 12
                    hits = {k: v for k, v in hits.items() if k[0] < st}
                    for o in range(st, 16):
                        if big or o % 2 == 0 or e >= .75:
                            hits[(o, 45 if o >= 14 and rng.random() < .5 else 38)] = .45 + .5 * (o - st) / (16 - st)
                out += [Note(b0 + o, 1, p, v) for (o, p), v in hits.items()]
        return out

    def _sounds(self, by):
        P = self.P
        for kind, preset in zip(('lead', 'harmony', 'bass', 'arp'), P['sounds']):
            for k, v in SOUND_PRESETS[preset].items():
                setattr(by[kind], k, v)
        by['drums'].kit = P['kit']
        voice = by['voice']
        voice.vowel = P['vowel']
        if voice.vowel == 'robot':
            voice.detune, voice.vib_depth = 0.0, 0.0
        for kind in ('lead', 'arp', 'voice'):
            by[kind].echo = max(by[kind].echo, P['echo'])
        by['lead'].volume = .42 if P['voc'] else .5
        by['harmony'].volume = .22
        by['bass'].volume = .78 if by['bass'].wave == 'triangle' else .6
        by['arp'].volume = .2 if self.AMBIENT else .15
        by['drums'].volume = .4 if self.AMBIENT else .55
        by['voice'].volume = .5


def _ai_params(song, plan, intro=False, outro=False, avg_e=.6):
    """Параметры в формате генератора — чтобы в редакторе работали «Сгенерировать» и ♻ Recreate."""
    bass = {'root': 'Корень четвертями', 'whole': 'Корень четвертями', 'pulse8': 'Драйв восьмыми',
            'octave8': 'Октавы восьмыми', 'rootfifth': 'Корень-квинта', 'synco': 'Синкопы', 'walk': 'Шагающий',
            'gallop': 'Пульс 16-ми'}
    arp = {'up': 'Вверх', 'down': 'Вниз', 'updown': 'Вверх-вниз', 'broken': 'Ломаный', 'trill': 'Трель'}
    harm = {'pad': 'Долгие аккорды', 'stabs': 'Стабы на слабые доли', 'counter': 'Контрмелодия',
            'thirds': 'Терции под мелодией'}
    by = {t.kind: t for t in song.tracks}
    return dict(style=plan['style'], key=song.key, scale=song.scale, bpm=song.bpm, bars=song.bars,
                chord_steps=song.chord_steps, density=plan.get('density', .6), complexity=plan.get('complexity', .5),
                repetition=.6, drums=round(avg_e, 2), swing=song.swing, bass=bass.get(plan.get('bass'), BASS_PATTERNS[1]),
                arp=arp.get((plan.get('arp') or ('up',))[0], 'Вверх'),
                arp_rate=1 if plan.get('feat', {}).get('en', .5) > .7 else 2,
                harmony=harm.get((plan.get('harm') or ('pad', 'pad'))[1], HARMONY_MODES[2]), chip=plan['chip'],
                include=[bool(by[k].notes) if k in by else False for k, _ in TRACK_DEFS], exact_sec=None,
                intro=intro, outro=outro, drop_sec=plan.get('drop') or 0, prompt=plan['text'],
                ai_model=plan['model'], ai_genre=plan.get('genre'), title=plan['title'])
