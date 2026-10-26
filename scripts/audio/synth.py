# -*- coding: utf-8 -*-
"""Синтез звука: осцилляторы, ADSR, ударные, рендер песни, WAV и MIDI."""

import math
import struct
import wave

import numpy as np

from scripts.core.constants import APP_NAME, VOWELS
from scripts.core.i18n import T
from scripts.core.theory import clamp, midi_to_freq


def adsr(t, gate, a, d, s, r):
    a, d, r = max(a, 0.001), max(d, 0.001), max(r, 0.005)
    xs, ys = [0.0, a, a + d], [0.0, 1.0, s]
    env = np.interp(t, xs, ys)
    lvl = float(np.interp(gate, xs, ys))
    rel = t >= gate
    env[rel] = lvl * np.clip(1.0 - (t[rel] - gate) / r, 0.0, 1.0)
    return env


def _phase(f0, t, sr, depth, rate):
    if depth > 0 and rate > 0:
        onset = np.clip((t - 0.10) / 0.15, 0.0, 1.0)
        f = f0 * np.power(2.0, depth * onset * np.sin(2 * np.pi * rate * t) / 12.0)
        return np.cumsum(f) / sr
    return f0 * t


def _quant_tri(ph):
    tri = 1.0 - 4.0 * np.abs((ph % 1.0) - 0.5)
    return np.round((tri + 1.0) * 7.5) / 7.5 - 1.0  # 4-битный треугольник как у NES


def _formant_voice(tr, f0, ph, t, sr, rng):
    """Синтетический голос: гармоники с формантами гласной + немного «дыхания»."""
    v = tr.vowel
    if v not in VOWELS:
        v = 'аоуиэ'[int(round(f0)) % 5]
    forms = VOWELS[v]
    kmax = max(2, int(min(5000.0, sr * 0.45) // f0))
    y = np.zeros(len(t))
    base = 2 * np.pi * ph
    for k in range(1, kmax + 1):
        fk = k * f0
        a = sum(amp * math.exp(-((fk - F) / bw) ** 2) for F, amp, bw in forms) + 0.015 / k
        if a > 1e-3:
            y += a * np.sin(k * base)
    y /= max(1e-6, float(np.max(np.abs(y))))
    y += rng.normal(0, 0.03, len(t))
    if tr.vowel == 'robot':
        y = np.round(y * 6) / 6
    return y * 0.9


def _osc(tr, f0, t, sr, rng):
    ph = _phase(f0, t, sr, tr.vib_depth, tr.vib_rate)
    w = tr.wave
    if w == 'voice':
        return _formant_voice(tr, f0, ph, t, sr, rng)
    if w == 'pulse':
        duty = tr.duty
        if tr.pwm > 0:
            duty = np.clip(tr.duty + tr.pwm * 0.42 * np.sin(2 * np.pi * 0.9 * t), 0.06, 0.94)
        y = np.where((ph % 1.0) < duty, 1.0, -1.0) - (2 * duty - 1)
        return y * 0.8
    if w == 'triangle':
        return _quant_tri(ph)
    if w == 'saw':
        return np.round((2 * (ph % 1.0) - 1) * 15) / 15 * 0.75
    if w == 'fm':
        idx = tr.fm_index * (0.35 + 0.65 * np.exp(-t * 5.0))
        return np.sin(2 * np.pi * ph + idx * np.sin(2 * np.pi * ph * tr.fm_ratio))
    if w == 'noise':
        hold = max(1, int(sr / max(30.0, f0 * 4)))
        v = rng.uniform(-1, 1, len(t) // hold + 2)
        return np.repeat(v, hold)[:len(t)] * 0.7
    return np.sin(2 * np.pi * ph)


def synth_tone(tr, pitch, gate, sr, nes_env, rng):
    n = int((gate + max(tr.release, 0.005)) * sr) + 1
    t = np.arange(n) / sr
    f0 = midi_to_freq(pitch + 12 * tr.octave)
    y = _osc(tr, f0, t, sr, rng)
    if tr.detune > 0 and tr.wave != 'noise':
        y = 0.6 * (y + _osc(tr, f0 * 2 ** (tr.detune / 1200.0), t, sr, rng))
    env = adsr(t, gate, tr.attack, tr.decay, tr.sustain, tr.release)
    if nes_env:
        env = np.round(env * 15) / 15
    return (y * env).astype(np.float32)


def synth_drum(pitch, tr, sr, rng):
    kit = tr.kit
    hold = {'NES': 2, 'Sega': 1, 'Lo-Fi': 4}.get(kit, 2)

    def noise(n, h=hold):
        return np.repeat(rng.uniform(-1, 1, n // h + 2), h)[:n]

    def hp_noise(n):
        x = noise(n, 1)
        return np.diff(x, prepend=0.0) * 0.5

    def tt(sec):
        return np.arange(int(sec * sr)) / sr
    if pitch == 36:
        t = tt(0.3)
        sega = kit == 'Sega'
        f = 48 + (170 if sega else 150) * np.exp(-t * (34 if sega else 26))
        ph = np.cumsum(f) / sr
        body = np.sin(2 * np.pi * ph) if sega else _quant_tri(ph)
        y = body * np.exp(-t * 9) + noise(len(t), hold * 2) * np.exp(-t * 220) * 0.5
    elif pitch == 38:
        t = tt(0.24)
        y = noise(len(t)) * np.exp(-t * 15) * 0.8 + \
            np.sin(2 * np.pi * (180 + 60 * np.exp(-t * 40)) * t) * np.exp(-t * 24) * 0.55
    elif pitch == 46:
        t = tt(0.32)
        y = hp_noise(len(t)) * np.exp(-t * 9) * 0.6
    elif pitch == 45:
        t = tt(0.32)
        ph = np.cumsum(80 + 120 * np.exp(-t * 10)) / sr
        y = _quant_tri(ph) * np.exp(-t * 8)
    elif pitch == 49:
        t = tt(1.3)
        y = hp_noise(len(t)) * np.exp(-t * 3) * 0.55
    else:
        t = tt(0.07)
        y = hp_noise(len(t)) * np.exp(-t * 65) * 0.75
    if kit == 'Lo-Fi':
        y = np.round(y * 7) / 7
    return y.astype(np.float32)


def master_process(mix, m):
    k = int(m.get('smooth', 0))
    if k > 0:
        ker = np.ones(1 + 2 * k, np.float32) / (1 + 2 * k)
        for ch in range(2):
            mix[:, ch] = np.convolve(mix[:, ch], ker, mode='same')
    d = int(m.get('downsample', 1))
    if d > 1:
        mix = mix[(np.arange(len(mix)) // d) * d]
    peak = float(np.max(np.abs(mix))) if len(mix) else 0.0
    if m.get('normalize', True) and peak > 1e-6:
        mix = mix * (0.92 / peak)
    elif peak > 0.99:
        mix = mix * (0.99 / peak)
    mix = mix * float(m.get('volume', 0.8))
    bits = int(m.get('bits', 16))
    if bits < 16:
        q = 2 ** (bits - 1) - 1
        mix = np.round(mix * q) / q
    return np.clip(mix, -1, 1).astype(np.float32)


def render_song(song, m, s0=0, s1=None, loop=False, only=None):
    """Рендер шагов [s0, s1) в стерео float32. Возвращает (audio, sr)."""
    sr = int(m.get('sr', 44100))
    total = song.total_steps
    s1 = total if s1 is None else s1
    s0 = int(clamp(s0, 0, max(0, total - 1)))
    s1 = int(clamp(s1, s0 + 1, total))
    sd = song.step_dur
    n_body = max(1, int(round((s1 - s0) * sd * sr)))
    n = n_body + int(2.0 * sr)
    mix = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(song.seed & 0xFFFFFFFF)
    solo = any(t.solo for t in song.tracks)
    for i, tr in enumerate(song.tracks):
        if only is not None:
            if i not in only:
                continue
        elif tr.mute or (solo and not tr.solo):
            continue
        if not tr.notes or tr.volume <= 0:
            continue
        buf = np.zeros(n, np.float32)
        cache = {}
        for note in tr.notes:
            if not (s0 <= note.s < s1):
                continue
            t0 = (note.s - s0) * sd + (song.swing * sd * 0.5 if note.s % 2 else 0.0)
            i0 = int(t0 * sr)
            key = (note.p, note.l)
            w = cache.get(key)
            if w is None:
                if tr.kind == 'drums':
                    w = synth_drum(note.p, tr, sr, rng)
                else:
                    w = synth_tone(tr, note.p, note.l * sd, sr, m.get('nes_env', True), rng)
                cache[key] = w
            end = min(n, i0 + len(w))
            if end > i0:
                buf[i0:end] += w[:end - i0] * note.v
        if tr.echo > 0:
            dly = int(3 * sd * sr)
            out, g = buf.copy(), 1.0
            for k in range(1, 5):
                g *= tr.echo
                if dly * k >= n:
                    break
                out[dly * k:] += buf[:-dly * k] * g
            buf = out
        buf *= tr.volume
        ang = (clamp(tr.pan, -1, 1) + 1) * math.pi / 4
        mix[:, 0] += buf * (math.cos(ang) * 1.414)
        mix[:, 1] += buf * (math.sin(ang) * 1.414)
    if loop:
        tail = mix[n_body:]
        mix = mix[:n_body].copy()
        k = min(len(tail), n_body)
        mix[:k] += tail[:k]
    else:
        exact = song.params.get('exact_sec')
        if exact and s0 == 0 and s1 == total and abs(total * sd - exact) < 0.05:
            mix = mix[:n_body].copy()  # ровно в секунду: хвост обрезаем с мягким затуханием
            k = min(n_body, int(0.25 * sr))
            mix[-k:] *= np.linspace(1.0, 0.0, k, dtype=np.float32)[:, None]
        else:
            nz = np.nonzero(np.abs(mix).max(axis=1) > 1e-4)[0]
            end = max(n_body, int(nz[-1]) + int(0.05 * sr)) if len(nz) else n_body
            mix = mix[:min(end, n)]
    return master_process(mix, m), sr


def fade_out(audio, sr, sec=3.0):
    k = min(len(audio), int(sec * sr))
    if k > 0:
        audio[-k:] *= np.linspace(1.0, 0.0, k, dtype=np.float32)[:, None]
    return audio


def write_wav(path, audio, sr, bits8=False):
    a = np.clip(audio, -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(1 if bits8 else 2)
        w.setframerate(sr)
        if bits8:
            w.writeframes((a * 127 + 128).astype(np.uint8).tobytes())
        else:
            w.writeframes((a * 32767).astype('<i2').tobytes())


def write_midi(path, song):
    TPQ, TPS = 96, 24

    def vlq(v):
        out = [v & 0x7F]
        v >>= 7
        while v:
            out.append(0x80 | (v & 0x7F))
            v >>= 7
        return bytes(reversed(out))

    def chunk(events):
        events.sort(key=lambda e: (e[0], e[1]))
        data, last = bytearray(), 0
        for tick, _, b in events:
            data += vlq(tick - last) + b
            last = tick
        data += vlq(0) + bytes([0xFF, 0x2F, 0x00])
        return b'MTrk' + struct.pack('>I', len(data)) + bytes(data)

    def meta_name(s):
        b = s.encode('utf-8')
        return bytes([0xFF, 0x03]) + vlq(len(b)) + b
    tempo = int(60_000_000 / song.bpm)
    chunks = [chunk([(0, 0, bytes([0xFF, 0x51, 0x03]) + tempo.to_bytes(3, 'big')),
                     (0, 0, bytes([0xFF, 0x58, 0x04, 0x04, 0x02, 0x18, 0x08])), (0, 0, meta_name(APP_NAME))])]
    programs = {'lead': 80, 'harmony': 81, 'bass': 38, 'arp': 80, 'voice': 52}
    ch_i = 0
    for tr in song.tracks:
        if not tr.notes:
            continue
        drums = tr.kind == 'drums'
        if drums:
            ch = 9
        else:
            ch = ch_i if ch_i < 9 else ch_i + 1
            ch_i += 1
        ev = [(0, 0, meta_name(T(tr.name)))]
        if not drums:
            ev.append((0, 0, bytes([0xC0 | ch, programs.get(tr.kind, 80)])))
        ev.append((0, 0, bytes([0xB0 | ch, 7, int(clamp(tr.volume, 0, 1) * 127)])))
        ev.append((0, 0, bytes([0xB0 | ch, 10, int(clamp((tr.pan + 1) * 63.5, 0, 127))])))
        for n in tr.notes:
            p = int(clamp(n.p if drums else n.p + 12 * tr.octave, 0, 127))
            v = int(clamp(n.v * 120 + 7, 1, 127))
            ev.append((n.s * TPS, 1, bytes([0x90 | ch, p, v])))
            ev.append(((n.s + n.l) * TPS, 0, bytes([0x80 | ch, p, 0])))
        chunks.append(chunk(ev))
    with open(path, 'wb') as f:
        f.write(b'MThd' + struct.pack('>IHHH', 6, 1, len(chunks), TPQ))
        for c in chunks:
            f.write(c)
