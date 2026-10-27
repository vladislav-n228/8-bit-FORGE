# -*- coding: utf-8 -*-
"""Track import: MIDI (including the app's own export) and console music rips —
NSF (Dendy / NES), VGM / VGZ (Sega Mega Drive / Genesis, Master System, and NES in VGM format).
Notes are recovered channel by channel from the sound chip register logs. No Tk — can run in a process."""

import gzip
import math
import struct

import numpy as np

from scripts.core.constants import APP_NAME, SCALES, TRACK_DEFS
from scripts.core.model import make_track, Note, Song

IMPORT_EXTS = ('.mid', '.midi', '.nsf', '.vgm', '.vgz', '.json')
MAX_SECONDS = 240      # console rips usually loop — take no more than this
NSF_SECONDS = 150      # an NSF with no loop found is recorded for this long
FRAME = 1 / 60.0       # the chips are polled once per NTSC frame


class ImportFailed(ValueError):
    """The file couldn't be parsed — the error text is shown to the user (translated via T)."""


# ── what kind of file ──
def probe(path):
    """Quickly reads the file and figures out what it is. → dict(fmt, data, title, songs, start)"""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:2] == b'\x1f\x8b':
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError) as ex:
            raise ImportFailed('Файл повреждён (не удалось распаковать)') from ex
    info = dict(data=data, title='', songs=1, start=1)
    if data[:4] == b'MThd':
        info['fmt'] = 'midi'
    elif data[:4] == b'Vgm ':
        info.update(fmt='vgm', title=_gd3_title(data))
    elif data[:5] == b'NESM\x1a':
        if len(data) < 0x80:
            raise ImportFailed('Файл повреждён')
        info.update(fmt='nsf', songs=max(1, data[6]), start=max(1, data[7]),
                    title=_cstr(data[0x0E:0x2E]) or '')
    elif data[:4] == b'NSFE':
        raise ImportFailed('Формат NSFe не поддерживается — сохраните трек как обычный .nsf')
    elif data.lstrip()[:1] == b'{':
        info['fmt'] = 'project'
    else:
        raise ImportFailed('Неизвестный формат файла. Поддерживаются: MIDI, NSF (Dendy), VGM / VGZ (Sega), '
                           'проекты 8-BIT FORGE (.json)')
    return info


def convert(info, song_no=None):
    """Parsed probe() → Song. The heavy part (the NSF is emulated) — call from the background."""
    fmt = info['fmt']
    if fmt == 'midi':
        return _from_midi(info['data'])
    if fmt == 'vgm':
        return _from_vgm(info['data'], info['title'])
    if fmt == 'nsf':
        return _from_nsf(info['data'], song_no or info['start'], info['title'])
    raise ImportFailed('Неизвестный формат файла')


def _cstr(b):
    return b.split(b'\0', 1)[0].decode('latin-1', 'replace').strip()


# ── building a song from parts ──
_PRESETS = {('fm', 'lead'): 'Sega · FM брасс', ('fm', 'harmony'): 'Sega · FM э-пиано', ('fm', 'bass'): 'Sega · FM слэп-бас',
            ('fm', 'arp'): 'Sega · FM колокол', ('pulse', 'lead'): 'NES · Лид 25%', ('pulse', 'harmony'): 'NES · Тонкий 12.5%',
            ('pulse', 'bass'): 'NES · Квадрат 50%', ('pulse', 'arp'): 'NES · Арпеджио-блип'}
_VOLUMES = {'lead': .5, 'harmony': .3, 'bass': .8, 'arp': .2, 'drums': .55, 'voice': .45}
_KIND_NAMES = {}  # track name (in Russian and English) → kind; needed to recognize the app's own MIDI export


def _kind_by_name(name):
    if not _KIND_NAMES:
        from scripts.core.lang_en import EN
        for kind, ru in TRACK_DEFS:
            _KIND_NAMES[ru.lower()] = kind
            _KIND_NAMES[EN.get(ru, ru).lower()] = kind
    return _KIND_NAMES.get((name or '').strip().lower())


def _assign_roles(parts):
    """Who's the bass and who's the lead: by average pitch, number and length of notes."""
    mel = [p for p in parts if p['kind'] is None]
    if not mel:
        return
    for p in mel:
        w = np.array([n[1] for n in p['notes']], dtype=float)
        p['avg'] = float(np.average([n[2] for n in p['notes']], weights=w))
        p['mlen'] = float(w.mean())
    if not any(p['kind'] == 'bass' for p in parts):
        low = min(mel, key=lambda p: p['avg'])
        if low['avg'] < 50 or (len(mel) > 1 and low['avg'] < 57):
            low['kind'] = 'bass'
    rest = [p for p in mel if p['kind'] is None]
    if rest and not any(p['kind'] == 'lead' for p in parts):
        most = max(len(p['notes']) for p in rest)
        cands = [p for p in rest if len(p['notes']) >= .3 * most and p['mlen'] > 1.3] or rest
        max(cands, key=lambda p: p['avg'])['kind'] = 'lead'
    for p in rest:
        if p['kind'] is None:
            p['kind'] = 'arp' if p['mlen'] <= 1.3 and len(p['notes']) > 48 else 'harmony'


_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _guess_key(tracks):
    """Key from the Krumhansl profiles. → (tonic, scale)"""
    hist = np.zeros(12)
    for tr in tracks:
        if tr.kind != 'drums':
            for n in tr.notes:
                hist[n.p % 12] += n.l
    if not hist.any():
        return 0, 'Мажор'
    best = (-2, 0, 'Мажор')
    for k in range(12):
        for prof, scale in ((_MAJOR, 'Мажор'), (_MINOR, 'Минор')):
            r = np.corrcoef(hist, np.roll(prof, k))[0, 1]
            if r > best[0]:
                best = (r, k, scale)
    return best[1], best[2]


def _guess_chords(song):
    """Chord degree for every bar — the generator needs it so ♻ Recreate fits the harmony."""
    sc = SCALES[song.scale]
    chords = []
    for b in range(song.bars):
        s0, s1 = b * 16, b * 16 + 16
        hist = np.zeros(12)
        for tr in song.tracks:
            if tr.kind == 'drums':
                continue
            w = 3 if tr.kind == 'bass' else 1
            for n in tr.notes:
                ov = min(s1, n.s + n.l) - max(s0, n.s)
                if ov > 0:
                    hist[n.p % 12] += ov * w
        if not hist.any():
            chords.append(chords[-1] if chords else 0)
            continue
        score = [sum(hist[(song.key + sc[(d + i) % 7]) % 12] for i in (0, 2, 4)) + hist[(song.key + sc[d]) % 12] * .5
                 for d in range(7)]
        chords.append(int(np.argmax(score)))
    return chords


def _assemble(parts, bpm, title, source, chip='nes'):
    """parts: [dict(name, kind | None, src: 'pulse'/'triangle'/'fm'/'noise', notes=[(s, l, p, v)], extra={})]"""
    parts = [p for p in parts if p['notes']]
    if not parts:
        raise ImportFailed('В файле не нашлось нот (или звуковой чип этой записи не поддерживается)')
    _assign_roles(parts)
    order = {k: i for i, (k, _) in enumerate(TRACK_DEFS)}
    parts.sort(key=lambda p: order.get(p['kind'], 9))
    total = max(n[0] + n[1] for p in parts for n in p['notes'])
    bars = int(min(512, max(4, math.ceil(total / 16))))
    tracks = []
    for p in parts:
        kind = p['kind']
        if kind == 'drums':
            tr = make_track('drums', p['name'], 'NES · Квадрат 50%', wave='noise', volume=_VOLUMES['drums'],
                            kit='Sega' if chip == 'sega' else 'NES')
        elif p['src'] == 'triangle':
            tr = make_track(kind, p['name'], 'NES · Треугольный бас', volume=_VOLUMES.get(kind, .5))
        else:
            src = 'fm' if p['src'] == 'fm' else 'pulse'
            tr = make_track(kind, p['name'], _PRESETS.get((src, kind), 'NES · Квадрат 50%'), volume=_VOLUMES.get(kind, .5))
        tr.octave = 0  # note pitches are already absolute
        for k, v in p.get('extra', {}).items():
            setattr(tr, k, v)
        seen, notes = set(), []
        for s, l, pitch, vel in sorted(p['notes']):
            s, l, pitch = int(s), int(max(1, l)), int(min(127, max(0, pitch)))
            if s >= bars * 16 or (s, pitch) in seen:
                continue
            seen.add((s, pitch))
            notes.append(Note(s, min(l, bars * 16 - s), pitch, float(min(1.0, max(.05, vel)))))
        tr.notes = notes
        tracks.append(tr)
    song = Song(bpm=int(round(bpm)), bars=bars, style='', seed=0, chord_steps=16, tracks=tracks,
                params=dict(title=title, imported=source, chip=chip))
    song.key, song.scale = _guess_key(tracks)
    song.chords = _guess_chords(song)
    return song


# ── MIDI ──
def _vlq(data, i):
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if b < 0x80:
            return v, i


_GM_DRUMS = {35: 36, 36: 36, 37: 38, 38: 38, 39: 38, 40: 38, 41: 45, 42: 42, 43: 45, 44: 42, 45: 45, 46: 46, 47: 45,
             48: 45, 49: 49, 50: 45, 51: 49, 52: 49, 53: 49, 55: 49, 57: 49, 59: 49}


def _from_midi(data):
    try:
        hlen = struct.unpack('>I', data[4:8])[0]
        _fmt, ntrk, div = struct.unpack('>HHH', data[8:14])
    except struct.error as ex:
        raise ImportFailed('Файл MIDI повреждён') from ex
    if div & 0x8000 or div == 0:
        raise ImportFailed('MIDI с SMPTE-временем не поддерживается')
    pos, tempo, own = 8 + hlen, None, False
    groups, names = {}, {}
    try:
        for ti in range(ntrk):
            while pos + 8 <= len(data) and data[pos:pos + 4] != b'MTrk':
                pos += 8 + struct.unpack('>I', data[pos + 4:pos + 8])[0]
            if pos + 8 > len(data):
                break
            end = min(len(data), pos + 8 + struct.unpack('>I', data[pos + 4:pos + 8])[0])
            i, t, status, held = pos + 8, 0, 0, {}
            while i < end:
                dt, i = _vlq(data, i)
                t += dt
                b = data[i]
                if b >= 0x80:
                    status = b
                    i += 1
                elif status == 0:
                    raise ImportFailed('Файл MIDI повреждён')
                if status == 0xFF:
                    typ = data[i]
                    ln, j = _vlq(data, i + 1)
                    payload, i, status = data[j:j + ln], j + ln, 0
                    if typ == 0x51 and tempo is None and ln == 3:
                        tempo = int.from_bytes(payload, 'big')
                    elif typ == 0x03:
                        name = payload.decode('utf-8', 'replace').strip()
                        names.setdefault(ti, name)
                        if name == APP_NAME:
                            own = True
                    elif typ == 0x2F:
                        break
                    continue
                if status in (0xF0, 0xF7):
                    ln, i = _vlq(data, i)
                    i, status = i + ln, 0
                    continue
                if status > 0xF0:
                    i += {0xF2: 2, 0xF3: 1}.get(status, 0)
                    status = 0
                    continue
                hi, ch = status & 0xF0, status & 0x0F
                if hi in (0xC0, 0xD0):
                    d1, d2 = data[i], 0
                    i += 1
                else:
                    d1, d2 = data[i], data[i + 1]
                    i += 2
                g = groups.setdefault((ti, ch), dict(notes=[], program=None, vol=None, pan=None))
                if hi == 0x90 and d2 > 0:
                    held.setdefault((ch, d1), []).append((g, len(g['notes'])))
                    g['notes'].append([t, None, d1, d2])
                elif hi in (0x80, 0x90):
                    stack = held.get((ch, d1))
                    if stack:
                        gg, k = stack.pop(0)
                        gg['notes'][k][1] = t
                elif hi == 0xC0 and g['program'] is None:
                    g['program'] = d1
                elif hi == 0xB0 and d1 == 7 and g['vol'] is None:
                    g['vol'] = d2
                elif hi == 0xB0 and d1 == 10 and g['pan'] is None:
                    g['pan'] = d2
            for stack in held.values():
                for gg, k in stack:
                    gg['notes'][k][1] = t
            pos = end
    except IndexError as ex:
        raise ImportFailed('Файл MIDI повреждён') from ex
    bpm = 60_000_000 / tempo if tempo else 120.0
    q = 1.0  # tempo too fast or too slow — change the grid step so the tempo stays within reasonable limits
    while bpm * q > 230:
        q /= 2
    while bpm * q < 55:
        q *= 2
    spt = 4 * q / div  # 1/16 steps per tick
    parts = []
    for (ti, ch), g in sorted(groups.items()):
        if not g['notes']:
            continue
        drums = ch == 9
        notes = []
        for t0, t1, p, v in g['notes']:
            s = int(round(t0 * spt))
            l = 1 if drums else max(1, int(round(t1 * spt)) - s)
            if drums:
                p = _GM_DRUMS.get(p, 42)
            notes.append((s, l, p, v / 127.0))
        name = names.get(ti) or ''
        kind = 'drums' if drums else _kind_by_name(name) if own else None
        if kind is None and not drums and g['program'] is not None and 32 <= g['program'] <= 39:
            kind = 'bass'
        if own and kind:  # our own tracks — under internal names, so they get translated when the language changes
            name = dict(TRACK_DEFS)[kind]
        elif not name or name == APP_NAME:
            name = 'Ударные' if drums else f'MIDI {ch + 1}'
        extra = {}
        if own:  # our own export: restore volume and pan as they were
            if g['vol'] is not None:
                extra['volume'] = g['vol'] / 127.0
            if g['pan'] is not None:
                extra['pan'] = max(-1.0, min(1.0, g['pan'] / 63.5 - 1))
        parts.append(dict(name=name, kind=kind, src='pulse', notes=notes, extra=extra))
    return _assemble(parts, bpm * q, '', 'midi')


# ── notes from chip channel states (seconds → grid) ──
class _Voice:
    """Follows a tonal channel frame by frame and cuts the stream into notes (t0, t1, pitch, volume)."""

    def __init__(self):
        self.notes, self.cur, self.last_v = [], None, 0.0

    def feed(self, t, on, freq, vel, trig=False):
        if not on or freq <= 20 or freq > 12000 or vel <= 0.01:
            self.close(t)
            self.last_v = 0.0
            return
        pf = 69 + 12 * math.log2(freq / 440.0)
        cur = self.cur
        p = cur[2] if cur and abs(pf - cur[2]) < .6 else int(round(pf))  # a little vibrato doesn't cut the note
        if cur is None or p != cur[2] or trig or vel - self.last_v >= .25:
            self.close(t)
            self.cur = [t, None, p, vel]
        else:
            cur[3] = max(cur[3], vel)
        self.last_v = vel

    def close(self, t):
        if self.cur:
            self.cur[1] = t
            self.notes.append(tuple(self.cur))
            self.cur = None


class _Hits:
    """Drums: hits on the noise channel / samples. The pitch "type" is decided on close, by the sound's length."""

    def __init__(self, classify):
        self.notes, self.cur, self.last_v, self.classify = [], None, 0.0, classify

    def feed(self, t, on, kind, vel, trig=False):
        if not on or vel <= 0.01:
            self.close(t)
            self.last_v = 0.0
            return
        if self.cur is None or trig or vel - self.last_v >= .2:
            self.close(t)
            self.cur = [t, None, kind, vel]
        self.last_v = vel

    def hit(self, t, pitch, vel=.8):
        self.notes.append((t, t + .05, None, vel, pitch))

    def close(self, t):
        if self.cur:
            t0, _, kind, vel = self.cur
            self.notes.append((t0, t, kind, vel, None))
            self.cur = None

    def result(self):
        return [(t0, t1, pitch if pitch is not None else self.classify(kind, t1 - t0), vel)
                for t0, t1, kind, vel, pitch in self.notes]


def _grid(onsets):
    """1/16 step duration (s) and grid offset from the note onsets."""
    t = np.asarray(sorted(onsets), dtype=float)
    if len(t) < 4:
        return .125, 0.0

    def fit(d):
        ph = t * (2 * math.pi / d)
        c, s = np.cos(ph).mean(), np.sin(ph).mean()
        return math.hypot(c, s), math.atan2(s, c)
    cands = np.arange(.0625, .2505, .0005)
    rs = np.array([fit(d)[0] for d in cands])
    good = [d for d, r in zip(cands, rs) if r >= .92 * rs.max()]
    pick = [d for d in good if d <= .2] or good
    d0 = max(pick)
    fine = np.arange(d0 * .985, d0 * 1.015, d0 * .0005)
    d = float(fine[int(np.argmax([fit(x)[0] for x in fine]))])
    phase = (fit(d)[1] / (2 * math.pi)) * d % d
    return d, phase


def _to_steps(timed_parts, title, source, chip):
    """Parts in seconds → parts in grid steps → song."""
    onsets = [n[0] for p in timed_parts for n in p['notes']]
    if not onsets:
        raise ImportFailed('В файле не нашлось нот (или звуковой чип этой записи не поддерживается)')
    d, phase = _grid(onsets)
    step = lambda x: int(round((x - phase) / d))
    first = max(0, min(step(x) for x in onsets))
    shift = first // 16 * 16  # empty bars at the start aren't needed
    parts = []
    for p in timed_parts:
        notes = []
        for t0, t1, pitch, vel in p['notes']:
            s = max(0, step(t0) - shift)
            l = 1 if p['kind'] == 'drums' else max(1, step(t1) - shift - s)
            notes.append((s, l, pitch, vel))
        parts.append(dict(p, notes=notes))
    return _assemble(parts, 15.0 / d, title, source, chip)


# ── APU Dendy / NES ──
_LEN = [10, 254, 20, 2, 40, 4, 80, 6, 160, 8, 60, 10, 14, 12, 26, 14,
        12, 16, 24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30]
_NES_CPU = 1789773.0


class _Apu:
    """Simplified APU model: note length, envelopes, the triangle's linear counter."""

    def __init__(self, cpu_clock=_NES_CPU):
        self.clock = cpu_clock
        self.reg = [0] * 0x18
        self.enabled = 0
        self.length = [0, 0, 0, 0]
        self.env = [[False, 0, 0] for _ in range(3)]  # pulse1, pulse2, noise: start, divider, level
        self.lin, self.lin_reload = 0, False
        self.trig = [False] * 4
        self.dmc_hit = False
        self.duty_use = [[0] * 4, [0] * 4]
        self.voices = [_Voice(), _Voice(), _Voice()]
        self.drums = _Hits(self._noise_drum)

    @staticmethod
    def _noise_drum(idx, dur):
        if idx <= 3:
            return 46 if dur > .12 else 42
        if idx <= 8:
            return 49 if dur > .35 else 38
        return 36

    def write(self, r, v):
        if r > 0x17:
            return
        self.reg[r] = v
        ch = r >> 2
        if r == 0x15:
            self.enabled = v
            for i in range(4):
                if not v & (1 << i):
                    self.length[i] = 0
            if v & 0x10:
                self.dmc_hit = True
        elif r in (0x03, 0x07, 0x0B, 0x0F):
            if self.enabled & (1 << ch):
                self.length[ch] = _LEN[v >> 3]
            self.trig[ch] = True
            if ch == 2:
                self.lin_reload = True
            else:
                self.env[0 if ch == 0 else 1 if ch == 1 else 2][0] = True

    def _quarter(self):
        for k, base in enumerate((0x00, 0x04, 0x0C)):
            e, rv = self.env[k], self.reg[base]
            if e[0]:
                e[0], e[1], e[2] = False, rv & 15, 15
            elif e[1] == 0:
                e[1] = rv & 15
                if e[2]:
                    e[2] -= 1
                elif rv & 0x20:
                    e[2] = 15
            else:
                e[1] -= 1
        if self.lin_reload:
            self.lin = self.reg[0x08] & 0x7F
        elif self.lin:
            self.lin -= 1
        if not self.reg[0x08] & 0x80:
            self.lin_reload = False

    def _half(self):
        for ch, halt in ((0, self.reg[0] & 0x20), (1, self.reg[4] & 0x20), (2, self.reg[8] & 0x80),
                         (3, self.reg[0x0C] & 0x20)):
            if not halt and self.length[ch]:
                self.length[ch] -= 1

    def frame(self, t):
        """End of frame: capture the channel states at time t, then run the frame counters."""
        for ch in (0, 1):
            b = ch * 4
            r0 = self.reg[b]
            per = self.reg[b + 2] | (self.reg[b + 3] & 7) << 8
            vol = (r0 & 15) if r0 & 0x10 else self.env[ch][2]
            on = bool(self.enabled & (1 << ch)) and self.length[ch] > 0 and per >= 8 and vol > 0
            if on:
                self.duty_use[ch][r0 >> 6] += 1
            self.voices[ch].feed(t, on, self.clock / (16 * (per + 1)), vol / 15.0, self.trig[ch])
        per = self.reg[0x0A] | (self.reg[0x0B] & 7) << 8
        on = bool(self.enabled & 4) and self.length[2] > 0 and self.lin > 0 and per >= 2
        self.voices[2].feed(t, on, self.clock / (32 * (per + 1)), .8, self.trig[2])
        r0 = self.reg[0x0C]
        vol = (r0 & 15) if r0 & 0x10 else self.env[2][2]
        on = bool(self.enabled & 8) and self.length[3] > 0 and vol > 0
        self.drums.feed(t, on, self.reg[0x0E] & 15, vol / 15.0, self.trig[3])
        if self.dmc_hit:
            self.drums.hit(t, 36)
        self.trig = [False] * 4
        self.dmc_hit = False
        for k in range(4):
            self._quarter()
            if k & 1:
                self._half()

    def audible(self):
        return any(v.cur for v in self.voices) or self.drums.cur is not None

    def parts(self, t_end):
        for v in self.voices:
            v.close(t_end)
        self.drums.close(t_end)
        duty = {0: .125, 1: .25, 2: .5, 3: .25}
        out = []
        for ch, name in ((0, 'Пульс 1'), (1, 'Пульс 2')):
            use = self.duty_use[ch]
            out.append(dict(name=name, kind='lead' if ch == 0 else 'harmony', src='pulse', notes=self.voices[ch].notes,
                            extra=dict(duty=duty[use.index(max(use))]) if any(use) else {}))
        out.append(dict(name='Треугольник', kind='bass', src='triangle', notes=self.voices[2].notes))
        out.append(dict(name='Шум', kind='drums', src='noise', notes=self.drums.result()))
        return out


# ── NSF: a tiny 6502 emulator that runs the file's player and records APU accesses ──
class _Cpu:
    __slots__ = ('mem', 'a', 'x', 'y', 's', 'pc', 'c', 'z', 'n', 'v', 'i', 'd', 'on_write', 'bank', 'halted')

    def __init__(self, mem, on_write, bank):
        self.mem, self.on_write, self.bank = mem, on_write, bank
        self.a = self.x = self.y = 0
        self.s, self.pc = 0xFD, 0
        self.c = self.z = self.n = self.v = self.d = False
        self.i = True
        self.halted = False

    def rd(self, a):
        if a >= 0x8000:
            return self.mem[a]
        if a < 0x2000:
            return self.mem[a & 0x7FF]
        if a < 0x4000:
            return 0x80 if a & 7 == 2 else 0  # PPUSTATUS: "the frame is over" — so wait loops don't hang
        if a == 0x4015:
            return 0
        return self.mem[a]

    def wr(self, a, v):
        if a < 0x2000:
            self.mem[a & 0x7FF] = v
        elif 0x4000 <= a <= 0x4017:
            self.on_write(a - 0x4000, v)
        elif 0x5FF8 <= a <= 0x5FFF:
            self.bank(a - 0x5FF8, v)
        elif 0x6000 <= a < 0x8000:
            self.mem[a] = v

    def push(self, v):
        self.mem[0x100 + self.s] = v
        self.s = (self.s - 1) & 0xFF

    def pull(self):
        self.s = (self.s + 1) & 0xFF
        return self.mem[0x100 + self.s]

    def p(self, b=0x30):
        return (self.n << 7) | (self.v << 6) | b | (self.d << 3) | (self.i << 2) | (self.z << 1) | self.c

    def set_p(self, v):
        self.n, self.v, self.d = bool(v & 0x80), bool(v & 0x40), bool(v & 8)
        self.i, self.z, self.c = bool(v & 4), bool(v & 2), bool(v & 1)

    def call(self, addr, a=0, x=0, limit=200000):
        """JSR addr and execute until it returns (or until the instruction limit)."""
        ret = 0x5FF4
        self.push((ret - 1) >> 8)
        self.push((ret - 1) & 0xFF)
        self.pc, self.a, self.x, self.halted = addr, a, x, False
        mem, table = self.mem, _OPS
        for _ in range(limit):
            pc = self.pc
            if pc == ret or self.halted:
                return True
            mode, op = table[mem[pc]]
            self.pc = (pc + 1) & 0xFFFF
            op(self, mode(self))
        return False


def _m_imp(c):
    return None


def _m_imm(c):
    a = c.pc
    c.pc = (a + 1) & 0xFFFF
    return a


def _m_zp(c):
    a = c.mem[c.pc]
    c.pc = (c.pc + 1) & 0xFFFF
    return a


def _m_zpx(c):
    a = (c.mem[c.pc] + c.x) & 0xFF
    c.pc = (c.pc + 1) & 0xFFFF
    return a


def _m_zpy(c):
    a = (c.mem[c.pc] + c.y) & 0xFF
    c.pc = (c.pc + 1) & 0xFFFF
    return a


def _m_abs(c):
    m, pc = c.mem, c.pc
    c.pc = (pc + 2) & 0xFFFF
    return m[pc] | m[(pc + 1) & 0xFFFF] << 8


def _m_abx(c):
    return (_m_abs(c) + c.x) & 0xFFFF


def _m_aby(c):
    return (_m_abs(c) + c.y) & 0xFFFF


def _m_ind(c):
    a = _m_abs(c)
    return c.rd(a) | c.rd((a & 0xFF00) | ((a + 1) & 0xFF)) << 8  # the famous 6502 page-boundary bug


def _m_izx(c):
    z = (c.mem[c.pc] + c.x) & 0xFF
    c.pc = (c.pc + 1) & 0xFFFF
    return c.mem[z] | c.mem[(z + 1) & 0xFF] << 8


def _m_izy(c):
    z = c.mem[c.pc]
    c.pc = (c.pc + 1) & 0xFFFF
    return ((c.mem[z] | c.mem[(z + 1) & 0xFF] << 8) + c.y) & 0xFFFF


def _m_rel(c):
    o = c.mem[c.pc]
    c.pc = (c.pc + 1) & 0xFFFF
    return (c.pc + (o - 256 if o > 127 else o)) & 0xFFFF


def _nz(c, r):
    c.z = r == 0
    c.n = r >= 0x80
    return r


def _adc_val(c, m):
    a = c.a
    r = a + m + c.c
    c.v = bool(~(a ^ m) & (a ^ r) & 0x80)
    c.c = r > 0xFF
    c.a = _nz(c, r & 0xFF)


def _cmp(c, reg, m):
    c.c = reg >= m
    _nz(c, (reg - m) & 0xFF)


def _rmw(fn):
    """Shifts and the like: an address of None means the accumulator."""
    def op(c, a):
        if a is None:
            c.a = fn(c, c.a)
        else:
            c.wr(a, fn(c, c.rd(a)))
    return op


def _asl(c, v):
    c.c = v >= 0x80
    return _nz(c, (v << 1) & 0xFF)


def _lsr(c, v):
    c.c = bool(v & 1)
    return _nz(c, v >> 1)


def _rol(c, v):
    r = ((v << 1) | c.c) & 0xFF
    c.c = v >= 0x80
    return _nz(c, r)


def _ror(c, v):
    r = (v >> 1) | (c.c << 7)
    c.c = bool(v & 1)
    return _nz(c, r)


def _branch(flag, want):
    def op(c, a):
        if getattr(c, flag) == want:
            c.pc = a
    return op


def _set(flag, val):
    def op(c, a):
        setattr(c, flag, val)
    return op


def _jsr(c, a):
    r = (c.pc - 1) & 0xFFFF
    c.push(r >> 8)
    c.push(r & 0xFF)
    c.pc = a


def _rts(c, a):
    lo = c.pull()
    c.pc = ((c.pull() << 8 | lo) + 1) & 0xFFFF


def _rti(c, a):
    c.set_p(c.pull())
    lo = c.pull()
    c.pc = c.pull() << 8 | lo


def _bit(c, a):
    m = c.rd(a)
    c.z = not (c.a & m)
    c.n, c.v = bool(m & 0x80), bool(m & 0x40)


def _halt(c, a):
    c.halted = True


def _build_ops():
    modes = dict(imp=_m_imp, acc=_m_imp, imm=_m_imm, zp=_m_zp, zpx=_m_zpx, zpy=_m_zpy, abs=_m_abs, abx=_m_abx,
                 aby=_m_aby, ind=_m_ind, izx=_m_izx, izy=_m_izy, rel=_m_rel)
    rd = lambda c, a: c.rd(a)
    ops = {
        'ADC': lambda c, a: _adc_val(c, rd(c, a)),
        'SBC': lambda c, a: _adc_val(c, rd(c, a) ^ 0xFF),
        'AND': lambda c, a: setattr(c, 'a', _nz(c, c.a & rd(c, a))),
        'ORA': lambda c, a: setattr(c, 'a', _nz(c, c.a | rd(c, a))),
        'EOR': lambda c, a: setattr(c, 'a', _nz(c, c.a ^ rd(c, a))),
        'CMP': lambda c, a: _cmp(c, c.a, rd(c, a)),
        'CPX': lambda c, a: _cmp(c, c.x, rd(c, a)),
        'CPY': lambda c, a: _cmp(c, c.y, rd(c, a)),
        'LDA': lambda c, a: setattr(c, 'a', _nz(c, rd(c, a))),
        'LDX': lambda c, a: setattr(c, 'x', _nz(c, rd(c, a))),
        'LDY': lambda c, a: setattr(c, 'y', _nz(c, rd(c, a))),
        'STA': lambda c, a: c.wr(a, c.a),
        'STX': lambda c, a: c.wr(a, c.x),
        'STY': lambda c, a: c.wr(a, c.y),
        'INC': lambda c, a: c.wr(a, _nz(c, (rd(c, a) + 1) & 0xFF)),
        'DEC': lambda c, a: c.wr(a, _nz(c, (rd(c, a) - 1) & 0xFF)),
        'INX': lambda c, a: setattr(c, 'x', _nz(c, (c.x + 1) & 0xFF)),
        'INY': lambda c, a: setattr(c, 'y', _nz(c, (c.y + 1) & 0xFF)),
        'DEX': lambda c, a: setattr(c, 'x', _nz(c, (c.x - 1) & 0xFF)),
        'DEY': lambda c, a: setattr(c, 'y', _nz(c, (c.y - 1) & 0xFF)),
        'TAX': lambda c, a: setattr(c, 'x', _nz(c, c.a)),
        'TAY': lambda c, a: setattr(c, 'y', _nz(c, c.a)),
        'TXA': lambda c, a: setattr(c, 'a', _nz(c, c.x)),
        'TYA': lambda c, a: setattr(c, 'a', _nz(c, c.y)),
        'TSX': lambda c, a: setattr(c, 'x', _nz(c, c.s)),
        'TXS': lambda c, a: setattr(c, 's', c.x),
        'PHA': lambda c, a: c.push(c.a),
        'PHP': lambda c, a: c.push(c.p()),
        'PLA': lambda c, a: setattr(c, 'a', _nz(c, c.pull())),
        'PLP': lambda c, a: c.set_p(c.pull()),
        'ASL': _rmw(_asl), 'LSR': _rmw(_lsr), 'ROL': _rmw(_rol), 'ROR': _rmw(_ror),
        'BCC': _branch('c', False), 'BCS': _branch('c', True), 'BNE': _branch('z', False),
        'BEQ': _branch('z', True), 'BPL': _branch('n', False), 'BMI': _branch('n', True),
        'BVC': _branch('v', False), 'BVS': _branch('v', True),
        'CLC': _set('c', False), 'SEC': _set('c', True), 'CLI': _set('i', False), 'SEI': _set('i', True),
        'CLD': _set('d', False), 'SED': _set('d', True), 'CLV': _set('v', False),
        'JMP': lambda c, a: setattr(c, 'pc', a), 'JSR': _jsr, 'RTS': _rts, 'RTI': _rti, 'BIT': _bit,
        'NOP': lambda c, a: None, 'BRK': _halt, 'JAM': _halt,
        # undocumented opcodes that show up in music drivers
        'LAX': lambda c, a: setattr(c, 'x', setattr(c, 'a', _nz(c, rd(c, a))) or c.a),
        'SAX': lambda c, a: c.wr(a, c.a & c.x),
        'DCP': lambda c, a: (c.wr(a, (rd(c, a) - 1) & 0xFF), _cmp(c, c.a, rd(c, a))),
        'ISB': lambda c, a: (c.wr(a, (rd(c, a) + 1) & 0xFF), _adc_val(c, rd(c, a) ^ 0xFF)),
        'SLO': lambda c, a: (c.wr(a, _asl(c, rd(c, a))), setattr(c, 'a', _nz(c, c.a | rd(c, a)))),
        'RLA': lambda c, a: (c.wr(a, _rol(c, rd(c, a))), setattr(c, 'a', _nz(c, c.a & rd(c, a)))),
        'SRE': lambda c, a: (c.wr(a, _lsr(c, rd(c, a))), setattr(c, 'a', _nz(c, c.a ^ rd(c, a)))),
        'RRA': lambda c, a: (c.wr(a, _ror(c, rd(c, a))), _adc_val(c, rd(c, a))),
    }
    spec = """
    ADC imm 69 zp 65 zpx 75 abs 6D abx 7D aby 79 izx 61 izy 71
    AND imm 29 zp 25 zpx 35 abs 2D abx 3D aby 39 izx 21 izy 31
    ORA imm 09 zp 05 zpx 15 abs 0D abx 1D aby 19 izx 01 izy 11
    EOR imm 49 zp 45 zpx 55 abs 4D abx 5D aby 59 izx 41 izy 51
    CMP imm C9 zp C5 zpx D5 abs CD abx DD aby D9 izx C1 izy D1
    SBC imm E9 zp E5 zpx F5 abs ED abx FD aby F9 izx E1 izy F1 imm EB
    LDA imm A9 zp A5 zpx B5 abs AD abx BD aby B9 izx A1 izy B1
    STA zp 85 zpx 95 abs 8D abx 9D aby 99 izx 81 izy 91
    LDX imm A2 zp A6 zpy B6 abs AE aby BE
    LDY imm A0 zp A4 zpx B4 abs AC abx BC
    STX zp 86 zpy 96 abs 8E
    STY zp 84 zpx 94 abs 8C
    CPX imm E0 zp E4 abs EC
    CPY imm C0 zp C4 abs CC
    INC zp E6 zpx F6 abs EE abx FE
    DEC zp C6 zpx D6 abs CE abx DE
    ASL acc 0A zp 06 zpx 16 abs 0E abx 1E
    LSR acc 4A zp 46 zpx 56 abs 4E abx 5E
    ROL acc 2A zp 26 zpx 36 abs 2E abx 3E
    ROR acc 6A zp 66 zpx 76 abs 6E abx 7E
    BIT zp 24 abs 2C
    JMP abs 4C ind 6C
    JSR abs 20
    BCC rel 90 BCS rel B0 BEQ rel F0 BMI rel 30 BNE rel D0 BPL rel 10 BVC rel 50 BVS rel 70
    INX imp E8 INY imp C8 DEX imp CA DEY imp 88 TAX imp AA TAY imp A8 TXA imp 8A TYA imp 98 TSX imp BA TXS imp 9A
    PHA imp 48 PHP imp 08 PLA imp 68 PLP imp 28 RTS imp 60 RTI imp 40 BRK imp 00
    CLC imp 18 SEC imp 38 CLI imp 58 SEI imp 78 CLD imp D8 SED imp F8 CLV imp B8
    NOP imp EA imp 1A imp 3A imp 5A imp 7A imp DA imp FA imm 80 imm 82 imm 89 imm C2 imm E2
    NOP zp 04 zp 44 zp 64 zpx 14 zpx 34 zpx 54 zpx 74 zpx D4 zpx F4 abs 0C abx 1C abx 3C abx 5C abx 7C abx DC abx FC
    LAX zp A7 zpy B7 abs AF aby BF izx A3 izy B3
    SAX zp 87 zpy 97 abs 8F izx 83
    DCP zp C7 zpx D7 abs CF abx DF aby DB izx C3 izy D3
    ISB zp E7 zpx F7 abs EF abx FF aby FB izx E3 izy F3
    SLO zp 07 zpx 17 abs 0F abx 1F aby 1B izx 03 izy 13
    RLA zp 27 zpx 37 abs 2F abx 3F aby 3B izx 23 izy 33
    SRE zp 47 zpx 57 abs 4F abx 5F aby 5B izx 43 izy 53
    RRA zp 67 zpx 77 abs 6F abx 7F aby 7B izx 63 izy 73
    """
    table = [(_m_imp, ops['JAM'])] * 256
    name = None
    for tok in spec.split():
        if tok in ops:
            name = tok
        elif tok in modes:
            mode = tok
        else:
            table[int(tok, 16)] = (modes[mode], ops[name])
    return table


_OPS = _build_ops()


def _from_nsf(data, song_no, title):
    load, init, play = struct.unpack('<HHH', data[8:14])
    speed = struct.unpack('<H', data[0x6E:0x70])[0] or 16639
    if data[0x7A] & 1 and not data[0x7A] & 2:  # PAL only
        speed = struct.unpack('<H', data[0x78:0x7A])[0] or 19997
    banks, rom = list(data[0x70:0x78]), data[0x80:]
    mem = bytearray(0x10000)
    if any(banks):
        rom = bytes(load & 0xFFF) + rom
        nb = max(1, (len(rom) + 0xFFF) // 0x1000)
        rom = rom.ljust(nb * 0x1000, b'\0')

        def bank(slot, b):
            b %= nb
            mem[0x8000 + slot * 0x1000:0x9000 + slot * 0x1000] = rom[b * 0x1000:(b + 1) * 0x1000]
        for k, b in enumerate(banks):
            bank(k, b)
    else:
        def bank(slot, b):
            pass
        end = min(0x10000, load + len(rom))
        mem[load:end] = rom[:end - load]
    apu = _Apu()
    cpu = _Cpu(mem, apu.write, bank)
    for r in range(0x14):
        apu.write(r, 0)
    apu.write(0x15, 0x0F)
    apu.write(0x17, 0x40)
    cpu.call(init, a=(song_no - 1) & 0xFF, x=0, limit=2_000_000)
    dt = speed / 1e6
    frames = int(NSF_SECONDS / dt)
    seen, heard, t = set(), False, 0.0
    for f in range(frames):
        t = f * dt
        cpu.s = 0xFD
        cpu.call(play, limit=100000)
        apu.frame(t)
        heard = heard or apu.audible()
        # the driver is deterministic: if the whole memory repeats, the music has looped and we're done
        # (or it froze — the track has ended)
        key = hash(bytes(mem[0:0x800])) ^ hash(bytes(mem[0x6000:0x8000]))
        if heard and key in seen:
            break
        seen.add(key)
    song = _to_steps(apu.parts(t + dt), title, 'nsf', 'nes')
    song.params['nsf_song'] = song_no
    return song


# ── VGM / VGZ: Sega Mega Drive (YM2612 + SN76489), Master System (SN76489), NES APU ──
def _gd3_title(data):
    try:
        off = struct.unpack('<I', data[0x14:0x18])[0]
        if not off:
            return ''
        p = 0x14 + off
        if data[p:p + 4] != b'Gd3 ':
            return ''
        texts = data[p + 12:].decode('utf-16-le', 'replace').split('\0')
        name, game = texts[0].strip(), texts[2].strip() if len(texts) > 2 else ''
        return f'{game} — {name}' if game and name else name or game
    except (struct.error, IndexError):
        return ''


def _from_vgm(data, title):
    u32 = lambda o: struct.unpack('<I', data[o:o + 4])[0] if o + 4 <= len(data) else 0
    ver = u32(0x08)
    sn_clock = u32(0x0C) & 0x3FFFFFFF
    ym_clock = (u32(0x2C) if ver >= 0x110 else u32(0x10)) & 0x3FFFFFFF
    nes_clock = u32(0x84) & 0x3FFFFFFF if ver >= 0x161 else 0
    start = 0x34 + u32(0x34) if ver >= 0x150 and u32(0x34) else 0x40
    sr = 44100.0

    # SN76489
    sn_tone, sn_att, sn_noise, sn_latch = [0, 0, 0], [15, 15, 15, 15], 0, (0, 0)
    sn_trig = False
    sn_voices = [_Voice(), _Voice(), _Voice()]
    sn_drums = _Hits(lambda rate, dur: (46 if dur > .15 else 42) if rate == 0 else 38 if rate in (1, 2) else 36)
    # YM2612
    ym = [[0] * 256, [0] * 256]
    ym_on, ym_latch, ym_trig = [False] * 6, [False] * 6, [False] * 6
    ym_voices = [_Voice() for _ in range(6)]
    dac_on, dac_hits, dac_ids = False, _Hits(lambda k, d: k), {}
    nes = _Apu(nes_clock or _NES_CPU) if nes_clock else None
    used = set()

    def ym_freq(ch):
        port, c = divmod(ch, 3)
        r = ym[port]
        fnum = r[0xA0 + c] | (r[0xA4 + c] & 7) << 8
        block = (r[0xA4 + c] >> 3) & 7
        return fnum * (2 ** block) * (ym_clock / 144.0) / 2 ** 21

    def ym_vel(ch):
        port, c = divmod(ch, 3)
        r = ym[port]
        alg = r[0xB0 + c] & 7
        car = {0: [3], 1: [3], 2: [3], 3: [3], 4: [1, 3], 5: [1, 2, 3], 6: [1, 2, 3], 7: [0, 1, 2, 3]}[alg]
        offs = (0x00, 0x08, 0x04, 0x0C)  # operators 1..4 in register order 1, 3, 2, 4
        tl = min(r[0x40 + offs[k] + c] & 0x7F for k in car)
        return min(1.0, (10 ** (-tl * .75 / 20)) ** .5) if tl < 100 else 0.0

    def sample(t):
        nonlocal sn_trig
        for k in range(3):
            n = sn_tone[k]
            sn_voices[k].feed(t, sn_att[k] < 15 and n > 1, sn_clock / (32.0 * max(1, n)), (15 - sn_att[k]) / 15.0)
        sn_drums.feed(t, sn_att[3] < 15, sn_noise & 3, (15 - sn_att[3]) / 15.0, sn_trig)
        sn_trig = False
        for ch in range(6):
            on = ym_on[ch] or ym_latch[ch]
            if ch == 5 and dac_on:
                on = False
            ym_voices[ch].feed(t, on, ym_freq(ch), ym_vel(ch) if on else 0.0, ym_trig[ch])
            ym_latch[ch] = ym_trig[ch] = False

    i, samples, next_tick, nes_next = start, 0, 0.0, 0.0
    limit = int(MAX_SECONDS * sr)
    n = len(data)
    try:
        while i < n and samples < limit:
            cmd = data[i]
            wait = 0
            if cmd == 0x66:
                break
            elif cmd == 0x61:
                wait = data[i + 1] | data[i + 2] << 8
                i += 3
            elif cmd == 0x62:
                wait, i = 735, i + 1
            elif cmd == 0x63:
                wait, i = 882, i + 1
            elif 0x70 <= cmd <= 0x7F:
                wait, i = (cmd & 15) + 1, i + 1
            elif 0x80 <= cmd <= 0x8F:
                wait, i = cmd & 15, i + 1
            elif cmd == 0x67:
                size = struct.unpack('<I', data[i + 3:i + 7])[0] & 0x7FFFFFFF
                i += 7 + size
            elif cmd == 0x50:
                d = data[i + 1]
                i += 2
                used.add('sn')
                if d & 0x80:
                    ch, typ = (d >> 5) & 3, (d >> 4) & 1
                    sn_latch = (ch, typ)
                    if typ:
                        sn_att[ch] = d & 15
                    elif ch < 3:
                        sn_tone[ch] = (sn_tone[ch] & 0x3F0) | (d & 15)
                    else:
                        sn_noise, sn_trig = d & 7, True
                else:
                    ch, typ = sn_latch
                    if typ:
                        sn_att[ch] = d & 15
                    elif ch < 3:
                        sn_tone[ch] = (sn_tone[ch] & 15) | (d & 0x3F) << 4
                    else:
                        sn_noise, sn_trig = d & 7, True
            elif cmd in (0x52, 0x53):
                port, a, d = cmd - 0x52, data[i + 1], data[i + 2]
                i += 3
                used.add('ym')
                ym[port][a] = d
                if port == 0 and a == 0x28:
                    c = d & 7
                    if c in (0, 1, 2, 4, 5, 6):
                        ch = c if c < 3 else c - 1
                        on = bool(d & 0xF0)
                        if on and not ym_on[ch]:
                            ym_trig[ch] = ym_latch[ch] = True
                        ym_on[ch] = on
                elif port == 0 and a == 0x2B:
                    dac_on = bool(d & 0x80)
            elif cmd == 0xE0:
                off = struct.unpack('<I', data[i + 1:i + 5])[0]
                i += 5
                if dac_on:
                    pitch = dac_ids.setdefault(off, [36, 38, 42, 46, 49, 45][len(dac_ids) % 6])
                    dac_hits.hit(samples / sr, pitch)
            elif cmd == 0x95:
                blk = data[i + 2] | data[i + 3] << 8
                i += 5
                pitch = dac_ids.setdefault(('b', blk), [36, 38, 42, 46, 49, 45][len(dac_ids) % 6])
                dac_hits.hit(samples / sr, pitch)
            elif cmd == 0xB4:
                if nes is not None and data[i + 1] <= 0x17:
                    nes.write(data[i + 1], data[i + 2])
                    used.add('nes')
                i += 3
            elif cmd == 0x68:
                i += 12
            elif 0x90 <= cmd <= 0x94:
                i += {0x90: 5, 0x91: 5, 0x92: 6, 0x93: 11, 0x94: 2}[cmd]
            elif 0x30 <= cmd <= 0x3F or cmd == 0x4F:
                i += 2
            elif 0x40 <= cmd <= 0x4E:
                i += 3 if ver >= 0x160 else 2
            elif 0x51 <= cmd <= 0x5F or 0xA0 <= cmd <= 0xBF:
                i += 3
            elif 0xC0 <= cmd <= 0xDF:
                i += 4
            elif 0xE1 <= cmd <= 0xFF:
                i += 5
            else:
                i += 1
            if wait:
                samples += wait
                t = samples / sr
                while next_tick <= t:
                    sample(next_tick)
                    next_tick += FRAME
                while nes is not None and nes_next <= t:
                    nes.frame(nes_next)
                    nes_next += FRAME
    except (IndexError, struct.error):
        pass  # truncated file — take what we managed to read
    t_end = samples / sr
    parts = []
    if 'ym' in used:
        for ch, v in enumerate(ym_voices):
            v.close(t_end)
            parts.append(dict(name=f'FM {ch + 1}', kind=None, src='fm', notes=v.notes))
    if 'sn' in used:
        for ch, v in enumerate(sn_voices):
            v.close(t_end)
            parts.append(dict(name=f'PSG {ch + 1}', kind=None, src='pulse', notes=v.notes))
        sn_drums.close(t_end)
        parts.append(dict(name='Шум', kind='drums', src='noise', notes=sn_drums.result()))
    if dac_hits.notes:
        parts.append(dict(name='Сэмплы (DAC)', kind='drums', src='noise', notes=dac_hits.result()))
    if nes is not None and 'nes' in used:
        parts += nes.parts(t_end)
    chip = 'sega' if 'ym' in used else 'nes'
    return _to_steps(parts, title, 'vgm', chip)
