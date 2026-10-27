# -*- coding: utf-8 -*-
"""Animations for the Tk canvas: smooth transitions (tweens), per-frame effects and pixel "dust" in the background."""

import math
import random
import time
import traceback
import tkinter as tk

from scripts.core.theory import blend


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def ease_back(t):
    """With a slight "overshoot" at the end — for springy appearances."""
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


class Animator:
    """One shared timer at ~60 frames/s.
    tween(key, dur, fn) — fn(t) every frame, t goes from 0 to 1 (already eased);
    loop(key, fn) — fn(dt, now) every frame until it returns False.
    A new tween with the same key replaces the old one. When there are no animations, the timer sleeps."""
    FRAME_MS = 16

    def __init__(self, widget):
        self.w = widget
        self.tweens, self.loops = {}, {}
        self._job = None
        self._last = time.perf_counter()
        self._n = 0

    def tween(self, key, dur, fn, done=None, ease=ease_out, delay=0.0):
        if key is None:
            self._n += 1
            key = ('anon', self._n)
        self.tweens[key] = (time.perf_counter() + delay, max(1e-3, dur), fn, done, ease)
        self._wake()
        return key

    def loop(self, key, fn):
        self.loops[key] = fn
        self._wake()

    def cancel(self, key):
        self.tweens.pop(key, None)
        self.loops.pop(key, None)

    def stop(self):
        """Stops all animations (the window is closing)."""
        self.tweens.clear()
        self.loops.clear()
        if self._job is not None:
            try:
                self.w.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _wake(self):
        if self._job is None:
            self._last = time.perf_counter()
            self._job = self.w.after(self.FRAME_MS, self._frame)

    def _frame(self):
        self._job = None
        now = time.perf_counter()
        dt = min(.1, now - self._last)
        self._last = now
        for key, tw in list(self.tweens.items()):
            t0, dur, fn, done, ease = tw
            if now < t0:
                continue
            t = min(1.0, (now - t0) / dur)
            try:
                fn(ease(t))
            except tk.TclError:
                t = 1.0
            except Exception:  # noqa
                traceback.print_exc()
                t = 1.0
            if t >= 1.0:
                if self.tweens.get(key) is tw:
                    del self.tweens[key]
                if done:
                    try:
                        done()
                    except Exception:  # noqa
                        traceback.print_exc()
        for key, fn in list(self.loops.items()):
            try:
                keep = fn(dt, now)
            except tk.TclError:
                keep = False
            except Exception:  # noqa
                traceback.print_exc()
                keep = False
            if keep is False and self.loops.get(key) is fn:
                del self.loops[key]
        if self.tweens or self.loops:
            try:
                self._job = self.w.after(self.FRAME_MS, self._frame)
            except tk.TclError:
                pass


def collect_colors(cv, items):
    """Current colors (fill, outline) of canvas items — to fade them in / out smoothly."""
    out = []
    for it in items:
        for opt in ('fill', 'outline'):
            try:
                col = cv.itemcget(it, opt)
            except tk.TclError:
                continue
            if col and col.startswith('#') and len(col) == 7:
                out.append((it, opt, col))
    return out


def tint(cv, colors, bg, t):
    """t = 0 — colors dissolved into the background, t = 1 — the original ones. bg is a color or a dict {item: background color under it}."""
    for it, opt, col in colors:
        cv.itemconfigure(it, **{opt: blend(bg.get(it, '#000000') if isinstance(bg, dict) else bg, col, t)})


class PixelDust:
    """Pixel "dust": little squares slowly float up and sway — a living 8-bit style background.
    energy (0..1) speeds them up and makes them more visible while the model is composing."""

    def __init__(self, cv, n=38):
        self.cv, self.n = cv, n
        rnd = random.Random(8)
        self.parts = [dict(fx=rnd.random(), fy=rnd.random(), size=rnd.choice((2, 3, 3, 4)), v=rnd.uniform(.012, .035),
                           f=rnd.uniform(.3, .9), ph=rnd.uniform(0, 6.3), a=rnd.uniform(4, 14), tone=rnd.random(),
                           ci=rnd.randrange(3)) for _ in range(n)]
        self.items = []
        self.energy, self.target = 0.0, 0.0
        self.W = self.H = 1
        self.k = 1.0
        self.colors, self.bg = ['#ffffff'], '#000000'
        self._shade = -1

    def build(self, W, H, colors, bg, k):
        """Recreates the squares (after the window is redrawn) — right above the background image."""
        self.W, self.H, self.k, self.colors, self.bg = W, H, k, colors, bg
        cv = self.cv
        self.items = []
        for p in self.parts:
            s = p['size'] * k
            self.items.append(cv.create_rectangle(0, 0, s, s, outline='', tags=('dust',)))
        self._shade = -1
        self._recolor()
        cv.tag_raise('dust', 'bg')
        self.step(0, time.perf_counter())

    def _recolor(self):
        shade = round(self.energy, 1)
        if shade == self._shade:
            return
        self._shade = shade
        for p, it in zip(self.parts, self.items):
            a = (.18 + .32 * p['tone']) * (1 + .7 * self.energy)
            self.cv.itemconfigure(it, fill=blend(self.bg, self.colors[p['ci'] % len(self.colors)], min(.95, a)))

    def step(self, dt, now):
        if not self.items:
            return False
        self.energy += (self.target - self.energy) * min(1.0, dt * 2.5)
        self._recolor()
        speed = 1 + 3 * self.energy
        cv, W, H, k = self.cv, self.W, self.H, self.k
        for p, it in zip(self.parts, self.items):
            p['fy'] -= p['v'] * dt * speed
            if p['fy'] < -.03:
                p['fy'] = 1.03
                p['fx'] = random.random()
            x = p['fx'] * W + math.sin(now * p['f'] + p['ph']) * p['a'] * k
            y = p['fy'] * H
            s = p['size'] * k
            cv.coords(it, x, y, x + s, y + s)
        return True
