# -*- coding: utf-8 -*-
"""Video with a visualizer: frames are drawn by numpy, text by PIL, encoded by ffmpeg."""

import math
import subprocess
import tempfile

import numpy as np

from scripts.audio.ffmpeg import ffmpeg_encoders, FFMPEG_HELP, find_ffmpeg
from scripts.core.constants import DRUM_PITCHES
from scripts.core.i18n import T
from scripts.core.theory import _rgb, clamp


VIDEO_SIZES = {'16:9 — 1280×720 (YouTube)': (1280, 720), '16:9 — 1920×1080 (Full HD)': (1920, 1080),
               '9:16 — 1080×1920 (TikTok / Reels / Shorts)': (1080, 1920), '9:16 — 720×1280 (быстрее)': (720, 1280),
               '1:1 — 1080×1080 (Instagram)': (1080, 1080)}


VIDEO_STYLES = ['Ноты + эквалайзер', 'Бегущие ноты', 'Пиксельный эквалайзер', 'Осциллограф']


class RenderCancelled(Exception):
    pass


def _rect(img, x0, y0, x1, y1, col, alpha=1.0):
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(img.shape[1], int(x1)), min(img.shape[0], int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    if alpha >= 1:
        img[y0:y1, x0:x1] = col
    else:
        sub = img[y0:y1, x0:x1]
        sub *= (1 - alpha)
        sub += col * alpha


def _pil_font(size, bold=True):
    from PIL import ImageFont
    names = (['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'] if bold else
             ['segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf'])
    for nm in names:
        try:
            return ImageFont.truetype(nm, size)
        except OSError:
            continue
    return ImageFont.load_default()


class VideoRenderer:
    def __init__(self, song, audio, sr, W, H, fps, style, title, subtitle, bg, accent, bg_image=None,
                 crt=True, stars=True, progress=True):
        self.song, self.audio, self.sr = song, audio, sr
        self.W, self.H, self.fps, self.style = W, H, fps, style
        self.dur = len(audio) / sr
        self.n_frames = int(math.ceil(self.dur * fps))
        self.accent, self.crt, self.progress = _rgb(accent), crt, progress
        self.bgc = _rgb(bg)
        grad = np.linspace(1.0, 0.55, H, dtype=np.float32)[:, None, None]
        self.bg = np.ones((H, W, 3), np.float32) * self.bgc * grad + self.accent * 0.04
        if bg_image:
            self._load_bg_image(bg_image)
        r = np.random.default_rng(7)
        self.stars = np.column_stack([r.uniform(0, W, 140), r.uniform(0, H, 140), r.uniform(.2, 1, 140)]) if stars else None
        self.mono = audio.mean(axis=1) if audio.ndim == 2 else audio
        portrait = H > W
        top = int(H * (.17 if portrait else .2))
        self.title_ov = self._text_overlay(title, subtitle, int(H * .012 + 10))
        bottom = int(H * .9)
        if style == 'Ноты + эквалайзер':
            split = top + int((bottom - top) * .66)
            self.roll_box, self.eq_box, self.osc_box = (int(W * .05), top, int(W * .95), split - 10), \
                (int(W * .05), split + 6, int(W * .95), bottom), None
        elif style == 'Бегущие ноты':
            self.roll_box, self.eq_box, self.osc_box = (int(W * .05), top, int(W * .95), bottom), None, None
        elif style == 'Пиксельный эквалайзер':
            self.roll_box, self.eq_box, self.osc_box = None, (int(W * .08), top + int((bottom - top) * .15), int(W * .92), bottom), None
        else:
            self.roll_box, self.eq_box, self.osc_box = None, None, (int(W * .05), top, int(W * .95), bottom)
        self._prep_notes()
        if self.eq_box:
            self._prep_eq()
        self.peaks = None

    def _load_bg_image(self, path):
        from PIL import Image
        im = Image.open(path).convert('RGB')
        s = max(self.W / im.width, self.H / im.height)
        im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
        x, y = (im.width - self.W) // 2, (im.height - self.H) // 2
        arr = np.asarray(im.crop((x, y, x + self.W, y + self.H)), np.float32)
        self.bg = arr * 0.42 + self.bgc * 0.25

    def _text_overlay(self, title, subtitle, y):
        from PIL import Image, ImageDraw
        W = self.W
        h = int(self.H * .16)
        im = Image.new('RGBA', (W, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        fs = max(18, int(min(W, self.H) * .055))
        f1, f2 = _pil_font(fs, True), _pil_font(max(12, int(fs * .5)), False)
        acc = tuple(int(v) for v in self.accent)
        for text, font, yy, col in ((title, f1, y, (255, 255, 255)), (subtitle, f2, y + int(fs * 1.25), acc)):
            if not text:
                continue
            tw = d.textlength(text, font=font)
            x = (W - tw) / 2
            d.text((x + 3, yy + 3), text, font=font, fill=(0, 0, 0, 170))
            d.text((x, yy), text, font=font, fill=col + (255,))
        arr = np.asarray(im, np.float32) / 255.0
        return arr[..., :3] * 255.0, arr[..., 3:4]

    def _prep_notes(self):
        sg = self.song
        sd = sg.step_dur
        solo = any(t.solo for t in sg.tracks)
        self.tracks, self.drum_hits = [], []
        lo, hi = 127, 0
        for tr in sg.tracks:
            if tr.mute or (solo and not tr.solo) or not tr.notes:
                continue
            st = np.array([n.s * sd + (sg.swing * sd * .5 if n.s % 2 else 0) for n in tr.notes])
            if tr.kind == 'drums':
                self.drum_hits.append((st, np.array([n.p for n in tr.notes]), _rgb(tr.color)))
                continue
            p = np.array([n.p + 12 * tr.octave for n in tr.notes])
            en = st + np.array([n.l for n in tr.notes]) * sd
            lo, hi = min(lo, int(p.min())), max(hi, int(p.max()))
            self.tracks.append((st, en, p, _rgb(tr.color)))
        self.p_lo, self.p_hi = (lo - 2, hi + 2) if hi >= lo else (48, 84)
        kicks = [st[ps == 36] for st, ps, _ in self.drum_hits]
        self.kicks = np.sort(np.concatenate(kicks)) if kicks else np.array([])

    def _prep_eq(self):
        x0, y0, x1, y1 = self.eq_box
        self.n_bands = int(clamp((x1 - x0) // 34, 12, 40))
        n = 2048
        freqs = np.fft.rfftfreq(n, 1 / self.sr)
        edges = np.geomspace(45, min(9000, self.sr / 2.2), self.n_bands + 1)
        self.band_idx = [np.where((freqs >= a) & (freqs < b))[0] for a, b in zip(edges, edges[1:])]
        self.band_idx = [ix if len(ix) else np.array([int(np.argmin(np.abs(freqs - a)))]) for ix, a in zip(self.band_idx, edges)]
        win = np.hanning(n)
        lv = np.zeros((self.n_frames, self.n_bands), np.float32)
        for i in range(self.n_frames):
            c = int(i / self.fps * self.sr)
            seg = self.mono[max(0, c - n // 2): c + n // 2]
            if len(seg) < n:
                seg = np.pad(seg, (0, n - len(seg)))
            mag = np.abs(np.fft.rfft(seg * win))
            lv[i] = [20 * math.log10(mag[ix].mean() + 1e-9) for ix in self.band_idx]
        # high frequencies are quieter — partially normalize each band separately so the right-hand bars "live" too
        top = 0.45 * np.percentile(lv, 99.5) + 0.55 * np.percentile(lv, 99, axis=0)
        lv = np.clip((lv - (top - 40)) / 40, 0, 1)
        for i in range(1, self.n_frames):
            lv[i] = np.maximum(lv[i], lv[i - 1] * .8)
        self.eq_levels = lv

    def frame(self, i):
        t = i / self.fps
        img = self.bg.copy()
        W, H = self.W, self.H
        flash = 0.0
        if len(self.kicks):
            k = np.searchsorted(self.kicks, t, side='right') - 1
            if k >= 0:
                flash = max(0.0, 1 - (t - self.kicks[k]) / .14)
        if flash:
            img += self.accent * (.07 * flash)
        if self.stars is not None:
            xs = (self.stars[:, 0] - t * 25 * self.stars[:, 2]) % W
            for (x, y, z) in zip(xs, self.stars[:, 1], self.stars[:, 2]):
                s = 2 + int(z * 2)
                _rect(img, x, y, x + s, y + s, np.float32(160 + 90 * z), .55 + .4 * math.sin(t * 3 + y))
        if self.roll_box:
            self._draw_roll(img, t)
        if self.eq_box:
            self._draw_eq(img, i)
        if self.osc_box:
            self._draw_osc(img, t)
        rgb, a = self.title_ov
        h = rgb.shape[0]
        img[:h] = img[:h] * (1 - a) + rgb * a
        if self.progress:
            y = int(H * .955)
            _rect(img, W * .05, y, W * .95, y + 6, self.bgc * .5 + 30)
            _rect(img, W * .05, y, W * .05 + W * .9 * min(1, t / max(self.dur, 1e-6)), y + 6, self.accent)
        if self.crt:
            img[::3] *= .8
        return np.clip(img, 0, 255).astype(np.uint8)

    def _draw_roll(self, img, t):
        x0, y0, x1, y1 = self.roll_box
        past, future = 1.4, 3.6
        pps = (x1 - x0) / (past + future)
        px = x0 + past * pps
        drum_h = int((y1 - y0) * .1) if self.drum_hits else 0
        ny1 = y1 - drum_h - (8 if drum_h else 0)
        rows = self.p_hi - self.p_lo + 1
        rh = (ny1 - y0) / rows
        nh = clamp(rh * 1.6, 8, 22)
        white = np.float32(255)
        for st, en, p, col in self.tracks:
            vis = (en > t - past) & (st < t + future)
            for s, e, pp in zip(st[vis], en[vis], p[vis]):
                xa, xb = px + (s - t) * pps, px + (e - t) * pps - 2
                y = y0 + (self.p_hi - pp) * rh
                if s <= t < e:
                    _rect(img, xa - 4, y - 4, xb + 4, y + nh + 4, col, .35)
                    _rect(img, xa, y, xb, y + nh, col * .55 + white * .45)
                elif e <= t:
                    _rect(img, xa, y, xb, y + nh, col * .45 + self.bgc * .55)
                else:
                    _rect(img, xa, y, xb, y + nh, col)
        for st, ps, col in self.drum_hits:
            vis = (st > t - past) & (st < t + future)
            for s, pp in zip(st[vis], ps[vis]):
                xa = px + (s - t) * pps
                r = DRUM_PITCHES.index(pp) if pp in DRUM_PITCHES else 2
                hh = drum_h / len(DRUM_PITCHES)
                yy = y1 - drum_h + r * hh
                act = 0 <= t - s < .12
                _rect(img, xa, yy, xa + max(6, pps * .05), yy + hh - 1, col * .55 + white * .45 if act else col, 1 if s >= t - .12 else .5)
        _rect(img, px - 1, y0 - 6, px + 2, y1 + 6, self.accent * .5 + 127)

    def _draw_eq(self, img, i):
        x0, y0, x1, y1 = self.eq_box
        lv = self.eq_levels[min(i, len(self.eq_levels) - 1)]
        if self.peaks is None or i == 0:
            self.peaks = lv.copy()
        self.peaks = np.maximum(lv, self.peaks - .012)
        nb = self.n_bands
        bw = (x1 - x0) / nb
        blocks = 18
        bh = (y1 - y0) / blocks
        hot, warm = _rgb('#ff3d8b'), _rgb('#ffd23d')
        for b in range(nb):
            xa = x0 + b * bw + 2
            xb = xa + bw - 5
            n = int(round(lv[b] * blocks))
            for k in range(n):
                f = k / blocks
                col = self.accent * (1 - f) + (warm if f < .75 else hot) * f
                ya = y1 - (k + 1) * bh + 2
                _rect(img, xa, ya, xb, ya + bh - 3, col)
            pk = int(round(self.peaks[b] * blocks))
            if pk > 0:
                ya = y1 - pk * bh - 1
                _rect(img, xa, ya, xb, ya + 3, np.float32(240))

    def _draw_osc(self, img, t):
        x0, y0, x1, y1 = self.osc_box
        w, h = x1 - x0, y1 - y0
        c = int(t * self.sr)
        seg = self.mono[c: c + int(self.sr * .03)]
        if len(seg) < 8:
            return
        seg = np.convolve(seg, np.ones(5) / 5, mode='same')
        ys = np.interp(np.linspace(0, len(seg) - 1, w), np.arange(len(seg)), seg)
        ys = ys / max(.3, float(np.abs(ys).max()))
        yy = h / 2 - ys * h * .42
        nxt = np.append(yy[1:], yy[-1])
        lo, hi = np.minimum(yy, nxt), np.maximum(yy, nxt)  # join neighbouring points — a solid line
        rows = np.arange(h)[:, None]
        box = img[y0:y1, x0:x1]
        _rect(img, x0, y0 + h // 2, x1, y0 + h // 2 + 1, self.accent, .25)
        for th, a in ((8, .15), (4, .4)):
            m = (rows >= lo - th) & (rows <= hi + th)
            box[m] = box[m] * (1 - a) + self.accent * a
        m = (rows >= lo - 1.3) & (rows <= hi + 1.3)
        box[m] = self.accent * .45 + 140


def _video_codec_args(W, H):
    enc = ffmpeg_encoders()
    br = '10M' if W * H > 1300000 else '6M'
    if 'libx264' in enc:
        return ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20']
    if 'libopenh264' in enc:
        return ['-c:v', 'libopenh264', '-b:v', br]
    if 'h264_mf' in enc:
        return ['-c:v', 'h264_mf', '-b:v', br]
    return ['-c:v', 'mpeg4', '-q:v', '3']


def render_video(path, renderer, wav_path, progress=None, cancel=None):
    exe = find_ffmpeg()
    if not exe:
        raise RuntimeError(T(FFMPEG_HELP))
    R = renderer
    cmd = [exe, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{R.W}x{R.H}', '-r', str(R.fps), '-i', '-', '-i', wav_path] + _video_codec_args(R.W, R.H) + \
          ['-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', path]
    log = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        for i in range(R.n_frames):
            if cancel is not None and cancel.is_set():
                proc.kill()
                raise RenderCancelled()
            proc.stdin.write(R.frame(i).tobytes())
            if progress and i % 5 == 0:
                progress(i / R.n_frames)
        proc.stdin.close()
        proc.wait()
    except (BrokenPipeError, OSError):
        proc.wait()
    if proc.returncode != 0 and not (cancel is not None and cancel.is_set()):
        log.seek(0)
        raise RuntimeError('ffmpeg: ' + log.read().decode('utf-8', 'ignore')[-800:])
    log.close()
