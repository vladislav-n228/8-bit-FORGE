# -*- coding: utf-8 -*-
"""Графика для холста: скруглённые прямоугольники, мягкий фон со «свечением», пиксельная иконка программы."""

import math
import tkinter as tk

import numpy as np

from scripts.core.theory import _rgb, clamp

# Пиксельная иконка 16×16: нота на тёмной «кнопке». . — фон, # — нота, o — тень, b — рамка.
# Ею помечены окна программы, и из неё же build.py делает иконку .exe.
ICON_PIXELS = ['bbbbbbbbbbbbbbbb',
               'b..............b',
               'b......######..b',
               'b......#....#..b',
               'b......######..b',
               'b......#....#..b',
               'b......#....#..b',
               'b......#....#..b',
               'b......#....#..b',
               'b...###o..###o.b',
               'b..####o.####o.b',
               'b..####o.####o.b',
               'b...###o..###o.b',
               'b....ooo...ooo.b',
               'b..............b',
               'bbbbbbbbbbbbbbbb']
ICON_COLORS = {'.': '#0d0d16', '#': '#00d9ff', 'o': '#a970ff', 'b': '#2c2c40'}


def set_app_icon(root):
    """Иконка для всех окон программы (заголовок и панель задач) — рисуется прямо из пикселей, без файла."""
    images = []
    for scale in (1, 2, 4):  # Windows сам выберет подходящий размер
        img = tk.PhotoImage(master=root, width=16 * scale, height=16 * scale)
        for y, row in enumerate(ICON_PIXELS):
            line = '{' + ' '.join(ICON_COLORS[ch] for ch in row for _ in range(scale)) + '}'
            img.put(' '.join([line] * scale), to=(0, y * scale))
        images.append(img)
    root.iconphoto(True, *images)
    root._forge_icons = images  # держим ссылки, иначе картинки удалит сборщик мусора


def round_rect(cv, x0, y0, x1, y1, r, **kw):
    """Прямоугольник со скруглёнными углами (точные дуги — подходит и для «пилюль»)."""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    n = int(clamp(r / 3, 3, 14))
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts += (cx + r * math.cos(a), cy + r * math.sin(a))
    return cv.create_polygon(pts, **kw)


def _glow_image(W, H, base, glows, scale=3):
    """Мягкий фон с цветными «свечениями» (как у нейросетевых чатов) → массив H×W×3 uint8."""
    w, h = max(1, -(-W // scale)), max(1, -(-H // scale))
    yy, xx = np.ogrid[0:h, 0:w]
    img = np.empty((h, w, 3), np.float32)
    img[:] = _rgb(base)
    for cx, cy, rx, ry, col, a in glows:
        d = ((xx - cx * w) / (rx * w)) ** 2 + ((yy - cy * h) / (ry * h)) ** 2
        k = (a * np.exp(-d * 2.2))[..., None]
        img = img * (1 - k) + _rgb(col) * k
    img = img.repeat(scale, 0).repeat(scale, 1)[:H, :W]
    img += np.random.default_rng(7).uniform(-1.5, 1.5, img.shape).astype(np.float32)  # шум против «ступенек»
    return np.clip(img, 0, 255).astype(np.uint8)


def _photo(arr):
    h, w = arr.shape[:2]
    return tk.PhotoImage(data=b'P6 %d %d 255 ' % (w, h) + np.ascontiguousarray(arr).tobytes(), format='PPM')
