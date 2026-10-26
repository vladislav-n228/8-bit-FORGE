# -*- coding: utf-8 -*-
"""Классический композитор ручного режима: генерация треков по стилю и вариации кусков."""

from scripts.core.constants import BASS_EVENTS, BASS_PATTERNS, CELLS, HARMONY_MODES, RANGES
from scripts.core.model import Note
from scripts.core.theory import chord_at, chord_pcs, chord_pitches, clamp, nearest, scale_pitches


class Composer:
    def __init__(self, song, rng):
        self.song = song
        self.rng = rng

    @property
    def P(self):
        return self.song.params

    @staticmethod
    def clean(notes, s0, s1):
        res = []
        for n in notes:
            if s0 <= n.s < s1:
                n.l = max(1, min(n.l, s1 - n.s))
                n.p = int(clamp(n.p, 0, 127))
                res.append(n)
        res.sort(key=lambda n: (n.s, n.p))
        return res

    def generate(self, tr, s0, s1, allow_repeat=False):
        s0, s1 = max(0, s0), min(self.song.total_steps, s1)
        if s1 <= s0:
            return []
        fn = {'lead': self.gen_lead, 'harmony': self.gen_harmony, 'bass': self.gen_bass,
              'arp': self.gen_arp, 'drums': self.gen_drums, 'voice': self.gen_voice}.get(tr.kind, self.gen_lead)
        return self.clean(fn(tr, s0, s1, allow_repeat), s0, s1)

    # ── мелодия ──
    def _next_pitch(self, st, pos, pool, cx):
        rng, sg = self.rng, self.song
        cur = st['cur']
        if pos % 4 == 0 and rng.random() < 0.72 - 0.3 * cx:
            ct = chord_pitches(sg, chord_at(sg, pos), pool[0], pool[-1])
            if ct:
                new = rng.choice(sorted(ct, key=lambda p: (abs(p - cur), rng.random()))[:3])
                st['cur'] = new
                return new
        i = pool.index(nearest(pool, cur))
        maxleap = 1 + int(round(cx * 3))
        steps = list(range(-maxleap, maxleap + 1))
        weights = []
        for s in steps:
            w = 0.35 if s == 0 else 1.0 / abs(s)
            if s * st['dir'] > 0:
                w *= 1.6
            weights.append(w)
        s = rng.choices(steps, weights)[0]
        if rng.random() < 0.22:
            st['dir'] = -st['dir']
        j = i + s
        if j < 0 or j >= len(pool):
            j = i - s
            st['dir'] = -st['dir']
        j = clamp(j, 0, len(pool) - 1)
        st['cur'] = pool[j]
        return pool[j]

    def _melody_span(self, a, b, pool, cells, rest_p, cx, st, vel_base=0.8):
        rng = self.rng
        out = []
        for beat in range((a // 4) * 4, b, 4):
            pos = beat
            for d in rng.choice(cells):
                dur = abs(d)
                if d > 0 and a <= pos < b and rng.random() >= rest_p:
                    p = self._next_pitch(st, pos, pool, cx)
                    ln = dur if dur == 1 or rng.random() > 0.25 else dur - 1
                    v = vel_base + (0.12 if pos % 8 == 0 else 0.05 if pos % 4 == 0 else 0) + rng.uniform(-.05, .05)
                    out.append(Note(pos, min(ln, b - pos), p, clamp(v, 0.2, 1.0)))
                pos += dur
        return out

    def gen_lead(self, tr, s0, s1, allow_repeat):
        sg, rng, P = self.song, self.rng, self.P
        dens, cx, rep = P.get('density', .6), P.get('complexity', .5), P.get('repetition', .5)
        lo, hi = RANGES['lead']
        pool = scale_pitches(sg, lo, hi)
        cells = CELLS['calm' if dens < .38 else 'normal' if dens < .72 else 'busy']
        rest_p = max(0.0, 0.28 * (1 - dens) - 0.02)
        st = {'cur': nearest(pool, (lo + hi) // 2 + rng.randint(-3, 3)), 'dir': rng.choice((-1, 1))}
        out = []
        PH = 32
        for ph in range(s0 // PH, (s1 - 1) // PH + 1):
            ps, pe = ph * PH, ph * PH + PH
            src = ps - 2 * PH
            if allow_repeat and src >= 0 and rng.random() < rep:
                existing = [n for n in tr.notes + out if src <= n.s < src + PH]
                if existing:
                    for n in existing:
                        ns = n.s + 2 * PH
                        if s0 <= ns < s1:
                            p = n.p
                            if ns % 8 == 0:
                                ct = chord_pitches(sg, chord_at(sg, ns), lo - 5, hi + 5)
                                if ct and p % 12 not in {c % 12 for c in ct}:
                                    p = nearest(ct, p)
                            out.append(Note(ns, n.l, p, n.v))
                    if rng.random() < 0.6:
                        t0 = pe - 8
                        out = [n for n in out if not (t0 <= n.s < pe)]
                        if out:
                            st['cur'] = out[-1].p
                        out += self._melody_span(max(t0, s0), min(pe, s1), pool, cells, rest_p, cx, st)
                    continue
            out += self._melody_span(max(ps, s0), min(pe, s1), pool, cells, rest_p, cx, st)
            if ph % 2 == 1 and s0 <= pe - 4 and pe <= s1:  # каденция в конце 4-тактовой фразы
                out = [n for n in out if not (pe - 4 <= n.s < pe)]
                rpc = chord_pcs(sg, chord_at(sg, pe - 4))[0]
                cand = [p for p in range(lo, hi + 1) if p % 12 == rpc]
                if cand:
                    tgt = nearest(cand, st['cur'])
                    out.append(Note(pe - 4, 3, tgt, 0.85))
                    st['cur'] = tgt
        return out

    def gen_harmony(self, tr, s0, s1, allow_repeat):
        sg, rng, P = self.song, self.rng, self.P
        mode = P.get('harmony', HARMONY_MODES[0])
        lead = next((t for t in sg.tracks if t.kind == 'lead'), None)
        lead_notes = [n for n in lead.notes if s0 <= n.s < s1] if lead else []
        lo, hi = RANGES['harmony']
        out = []
        if mode in HARMONY_MODES[:2] and lead_notes:
            pool = scale_pitches(sg, lo - 12, hi + 12)
            for n in lead_notes:
                if mode == HARMONY_MODES[0]:
                    p = pool[max(0, pool.index(nearest(pool, n.p)) - 2)]
                else:
                    p = n.p - 12
                out.append(Note(n.s, n.l, p, n.v * 0.85))
            return out
        if mode == HARMONY_MODES[3]:
            pool = scale_pitches(sg, lo, hi)
            st = {'cur': nearest(pool, (lo + hi) // 2), 'dir': rng.choice((-1, 1))}
            return self._melody_span(s0, s1, pool, CELLS['calm'], 0.2, P.get('complexity', .5) * .6, st, 0.7)
        if mode == HARMONY_MODES[4]:
            for pos in range(s0, s1):
                if pos % 4 == 2:
                    tones = chord_pitches(sg, chord_at(sg, pos), 60, 76) or [64]
                    k = (pos // 4) % len(tones)
                    out.append(Note(pos, 1, tones[k], 0.72))
                    if P.get('density', .6) > .7 and pos + 1 < s1 and rng.random() < .3:
                        out.append(Note(pos + 1, 1, tones[(k + 1) % len(tones)], 0.6))
            return out
        cs = sg.chord_steps
        for k, c0 in enumerate(range((s0 // cs) * cs, s1, cs)):
            a, b = max(c0, s0), min(c0 + cs, s1)
            if b <= a:
                continue
            tones = chord_pitches(sg, chord_at(sg, c0), 60, 74) or [64]
            out.append(Note(a, b - a, tones[(1 + k % 2) % len(tones)], 0.62))
        return out

    def gen_voice(self, tr, s0, s1, allow_repeat):
        """Голос «поёт» упрощённую мелодию лида: без быстрых нот, связно, в вокальном диапазоне."""
        sg, rng = self.song, self.rng
        lo, hi = RANGES['voice']
        lead = next((t for t in sg.tracks if t.kind == 'lead'), None)
        src = [n for n in lead.notes if s0 <= n.s < s1] if lead else []
        if not src:
            pool = scale_pitches(sg, lo, hi)
            st = {'cur': nearest(pool, (lo + hi) // 2), 'dir': rng.choice((-1, 1))}
            return self._melody_span(s0, s1, pool, CELLS['calm'], 0.15, 0.3, st, 0.75)
        out = []
        for n in src:
            if n.s % 2 and n.l < 2 and rng.random() < .7:
                continue
            p = n.p
            while p > hi:
                p -= 12
            while p < lo:
                p += 12
            if out and out[-1].p == p and out[-1].s + out[-1].l >= n.s - 1:
                out[-1].l = n.s + n.l - out[-1].s
                continue
            out.append(Note(n.s, n.l, p, 0.8))
        for a, b in zip(out, out[1:]):
            if b.s - a.s <= 8:
                a.l = max(a.l, b.s - a.s)
        return out

    def _bass_pitch(self, role, pos):
        sg = self.song
        pcs = chord_pcs(sg, chord_at(sg, pos))
        root = 36 + pcs[0]
        if root > 45:
            root -= 12
        third = root + (pcs[1] - pcs[0]) % 12
        if role == 'o':
            return root + 12
        if role in ('f', 'w2'):
            return root + 7
        if role in ('t', 'w1'):
            return third
        if role == 'w3':
            nxt = chord_pcs(sg, chord_at(sg, (pos // 16 + 1) * 16))
            nroot = 36 + nxt[0]
            if nroot > 45:
                nroot -= 12
            return nroot - 1 if self.rng.random() < .6 else nroot + 2
        return root

    def gen_bass(self, tr, s0, s1, allow_repeat):
        rng, P = self.rng, self.P
        cx = P.get('complexity', .5)
        events = BASS_EVENTS.get(P.get('bass'), BASS_EVENTS[BASS_PATTERNS[1]])
        out = []
        for bar in range(s0 // 16, (s1 - 1) // 16 + 1):
            for off, ln, role in events:
                pos = bar * 16 + off
                if not (s0 <= pos < s1):
                    continue
                if role == 'r' and pos % 4 and rng.random() < cx * 0.25:
                    role = rng.choice('of')
                out.append(Note(pos, ln, self._bass_pitch(role, pos), 0.9 if pos % 4 == 0 else 0.78))
        return out

    def gen_arp(self, tr, s0, s1, allow_repeat):
        sg, rng, P = self.song, self.rng, self.P
        rate = int(P.get('arp_rate', 1))
        pat = P.get('arp', 'Вверх')
        dens = P.get('density', .6)
        out, skip = [], {}
        for pos in range(((s0 + rate - 1) // rate) * rate, s1, rate):
            beat = pos // 4
            if beat not in skip:
                skip[beat] = rng.random() < max(0.0, 0.45 - dens * 0.5)
            if skip[beat]:
                continue
            tones = chord_pitches(sg, chord_at(sg, pos), 72, 92)[:4] or [76]
            n = len(tones)
            k = (pos - (pos // sg.chord_steps) * sg.chord_steps) // rate
            if pat == 'Вниз':
                p = tones[::-1][k % n]
            elif pat == 'Вверх-вниз':
                seq = tones + tones[-2:0:-1]
                p = seq[k % len(seq)]
            elif pat == 'Ломаный':
                p = tones[[0, 2, 1, 3][k % 4] % n]
            elif pat == 'Случайный':
                p = rng.choice(tones)
            elif pat == 'Трель':
                p = tones[0] if k % 2 == 0 else tones[min(2, n - 1)]
            else:
                p = tones[k % n]
            out.append(Note(pos, rate, p, 0.6 + (0.15 if pos % 4 == 0 else 0)))
        return out

    def gen_drums(self, tr, s0, s1, allow_repeat):
        rng, P = self.rng, self.P
        I, cx = P.get('drums', .6), P.get('complexity', .5)
        if I <= 0.02:
            return []
        kicks = {0: [[0], [0, 8]], 1: [[0, 8], [0, 8, 10], [0, 7, 8]],
                 2: [[0, 6, 8], [0, 8, 10], [0, 3, 8, 11], [0, 6, 8, 14]],
                 3: [[0, 3, 6, 8, 11, 14], [0, 4, 8, 12], [0, 6, 8, 10, 14]]}
        tier = 0 if I < .3 else 1 if I < .55 else 2 if I < .8 else 3
        kick_a, kick_b = rng.choice(kicks[tier]), rng.choice(kicks[tier])
        snare = [8] if tier == 0 else [4, 12]
        hat_rate = 4 if tier == 0 else 2 if tier < 3 else 1
        out = []
        for bar in range(s0 // 16, (s1 - 1) // 16 + 1):
            b0 = bar * 16
            ev = {}

            def add(off, kind, v):
                if s0 <= b0 + off < s1:
                    ev.setdefault(off, {})[kind] = v
            for o in (kick_a if bar % 2 == 0 else kick_b):
                add(o, 36, 0.95)
            for o in snare:
                add(o, 38, 0.9)
            if I >= .15:
                for o in range(0, 16, hat_rate):
                    add(o, 42, 0.6 if o % 4 == 0 else 0.42)
            if tier >= 2 and rng.random() < .5 and 14 in ev:
                ev[14].pop(42, None)
                add(14, 46, 0.55)
            for o in range(1, 16, 2):
                if rng.random() < cx * 0.1:
                    add(o, 38, 0.3)
            if bar % 4 == 3 and I > .3 and rng.random() < .75:
                for o in range(12, 16):
                    ev.pop(o, None)
                tom = rng.random() < .5
                for o in range(12, 16):
                    if tier >= 2 or o % 2 == 0:
                        add(o, 45 if tom and o < 14 else 38, 0.5 + 0.12 * (o - 12))
            if bar % 8 == 0 and I > .35:
                add(0, 49, 0.7)
            for off, kinds in ev.items():
                for kind, v in kinds.items():
                    out.append(Note(b0 + off, 1, kind, v))
        return out

    # ── варианты существующего куска ──
    def vary(self, tr, old, s0, s1, mode):
        if not old:
            return self.generate(tr, s0, s1)
        rng, sg = self.rng, self.song
        if tr.kind == 'drums':
            if mode == 'Зеркало':
                return self.clean([Note(s0 + s1 - 1 - n.s, 1, n.p, n.v) for n in old], s0, s1)
            out = []
            for n in old:
                r = rng.random()
                if mode == 'Тот же ритм':
                    if n.p in (42, 46, 49):
                        kind = 49 if n.p == 49 else rng.choice([42, 42, 46])
                    else:
                        kind = rng.choice([36, 38, 45]) if n.s % 4 else rng.choice([36, 36, 38])
                    out.append(Note(n.s, 1, kind, n.v))
                    continue
                if r < .15:
                    continue
                if r < .3:
                    out.append(Note(clamp(n.s + rng.choice((-1, 1)), s0, s1 - 1), 1, n.p, n.v))
                    continue
                out.append(Note(n.s, 1, n.p, n.v))
                if r > .85 and n.s + 1 < s1:
                    out.append(Note(n.s + 1, 1, rng.choice([42, 38, 45]), n.v * .6))
            return self.clean(out, s0, s1)
        lo, hi = RANGES.get(tr.kind, (48, 84))
        cx = self.P.get('complexity', .5)
        pool = scale_pitches(sg, max(0, lo - 12), min(127, hi + 12))

        def ix(p):
            return pool.index(nearest(pool, p))
        if mode == 'Зеркало':
            c = round(sum(ix(n.p) for n in old) / len(old))
            out = [Note(n.s, n.l, pool[clamp(2 * c - ix(n.p), 0, len(pool) - 1)], n.v) for n in old]
        elif mode == 'Тот же ритм':
            if tr.kind == 'bass':
                out = [Note(n.s, n.l, self._bass_pitch(rng.choice('rrrfot'), n.s), n.v) for n in old]
            else:
                p2 = scale_pitches(sg, lo, hi)
                st = {'cur': nearest(p2, old[0].p), 'dir': rng.choice((-1, 1))}
                out = [Note(n.s, n.l, self._next_pitch(st, n.s, p2, cx), n.v) for n in old]
        else:  # вариация
            out = []
            for n in old:
                r = rng.random()
                p = n.p
                if r < .4:
                    p = pool[clamp(ix(n.p) + rng.choice((-2, -1, 1, 2)), 0, len(pool) - 1)]
                elif r < .55 and n.l >= 2:
                    h = n.l // 2
                    out.append(Note(n.s, h, n.p, n.v))
                    out.append(Note(n.s + h, n.l - h, pool[clamp(ix(n.p) + rng.choice((-1, 1)), 0, len(pool) - 1)],
                                    n.v * .9))
                    continue
                elif r < .65 and len(old) > 2:
                    continue
                out.append(Note(n.s, n.l, p, n.v))
            if not out:
                return self.generate(tr, s0, s1)
        return self.clean(out, s0, s1)
