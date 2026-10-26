# -*- coding: utf-8 -*-
"""Стартовый экран: выбор — чат-промпт или ручное создание."""

import tkinter as tk

from scripts.core.constants import APP_NAME
from scripts.core import i18n
from scripts.core.i18n import LANGUAGES, T
from scripts.ui.graphics import _glow_image, _photo, round_rect
from scripts.ui.style import ACCENTS


class Launcher:
    """Стартовый экран: тёмный фон и вопрос — как создавать музыку."""
    CARDS = (
        ('chat', '✦', 'Чат-промпт',
         'Опишите словами, что нужно, — модели Forge сочинят трек, фон, джингл или звуковой эффект.',
         ('Пишете запрос как в чате с нейросетью', 'Модели Melody, Ambient, Action, Jingle и SFX',
          'Длительность, вокал и жанр — вручную или «по запросу»', 'Готовый трек можно открыть в редакторе')),
        ('manual', '✎', 'Ручное создание',
         'Полный редактор: генератор по стилю, пиано-ролл, звук каждого трека, видео и экспорт.',
         ('Стили Dendy и Sega, лад, темп, плотность', 'Редактор нот и ♻ Recreate любого куска',
          'Звук треков, мастер, звуковые эффекты', 'Экспорт WAV, MP3, MIDI и MP4')),
    )
    BG = '#0b0b12'

    def __init__(self, root, shell):
        self.root, self.shell = root, shell
        self.hover = None
        self.cards = {}
        self.langs = {}  # кнопки языка в правом верхнем углу: ключ 'lang:en' / 'lang:ru' → прямоугольник
        self._job = None
        self._bg = (None, None)
        self.retitle()
        shell.center(root, 1040, 660)
        root.minsize(int(760 * shell.k), int(540 * shell.k))
        root.configure(bg=self.BG)
        self.cv = tk.Canvas(root, highlightthickness=0, bd=0, bg=self.BG)
        self.cv.pack(fill='both', expand=True)
        self.cv.bind('<Configure>', lambda e: self._schedule())
        self.cv.bind('<Motion>', self._on_motion)
        self.cv.bind('<Leave>', lambda e: self._set_hover(None))
        self.cv.bind('<Button-1>', lambda e: self._open(self._card_at(e.x, e.y)))
        root.bind('<Key-1>', lambda e: shell.open_chat())
        root.bind('<Key-2>', lambda e: shell.open_manual())
        root.bind('<Return>', lambda e: self._open(self.hover))

    def retitle(self):
        self.root.title(T('{0} — выбор режима').format(APP_NAME))

    def _schedule(self):
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(30, self.draw)

    def _card_at(self, x, y):
        zones = list(self.langs.items()) + list(self.cards.items())
        return next((key for key, (x0, y0, x1, y1) in zones if x0 <= x <= x1 and y0 <= y <= y1), None)

    def _on_motion(self, e):
        self._set_hover(self._card_at(e.x, e.y))

    def _set_hover(self, key):
        if key != self.hover:
            self.hover = key
            self.cv.configure(cursor='hand2' if key else '')
            self.draw()

    def _open(self, key):
        if key == 'chat':
            self.shell.open_chat()
        elif key == 'manual':
            self.shell.open_manual()
        elif key and key.startswith('lang:'):
            self.shell.set_language(key[5:])

    def draw(self):
        self._job = None
        cv, k = self.cv, self.shell.k
        W, H = max(cv.winfo_width(), 200), max(cv.winfo_height(), 200)
        acc = ACCENTS.get(self.shell.prefs.get('accent'), '#00d9ff')
        if self._bg[0] != (W, H, acc):
            arr = _glow_image(W, H, self.BG, ((.72, .8, .5, .55, acc, .14), (.26, .28, .4, .45, '#6a5cff', .12)))
            self._bg = ((W, H, acc), _photo(arr))
        cv.delete('all')
        cv.create_image(0, 0, image=self._bg[1], anchor='nw', tags=('bg',))
        cx = W / 2
        y = max(k * 46, H * .1)
        cv.create_text(cx, y, text='▚▞  8-BIT FORGE', font=('Consolas', 14, 'bold'), fill=acc)
        cv.create_text(cx, y + k * 50, text=T('Какой тип создания музыки вы выберете?'), font=('Segoe UI Semibold', 22),
                       fill='#f1f1f8', width=W - k * 60, justify='center')
        cv.create_text(cx, y + k * 90, text=T('Режим можно сменить в любой момент'), font=('Segoe UI', 11),
                       fill='#8b8ba3')
        gap, pad = k * 28, k * 26
        cw = min(k * 400, (W - k * 80 - gap) / 2)
        top = y + k * 132
        bottoms = []
        self._draw_langs(W, k, acc)
        for i, (key, icon, title, desc, feats) in enumerate(self.CARDS):
            title, desc, feats = T(title), T(desc), [T(f) for f in feats]
            x0 = cx - cw - gap / 2 if i == 0 else cx + gap / 2
            cv.create_oval(x0 + pad, top + pad, x0 + pad + k * 52, top + pad + k * 52, fill=acc, outline='')
            cv.create_text(x0 + pad + k * 26, top + pad + k * 26, text=icon, font=('Segoe UI Symbol', 19),
                           fill=self.BG)
            t = cv.create_text(x0 + pad, top + pad + k * 72, text=title, font=('Segoe UI Semibold', 17),
                               fill='#f1f1f8', anchor='nw')
            t = cv.create_text(x0 + pad, cv.bbox(t)[3] + k * 8, text=desc, font=('Segoe UI', 10), fill='#a3a3bb',
                               anchor='nw', width=cw - 2 * pad)
            ty = cv.bbox(t)[3] + k * 14
            for f in feats:
                cv.create_text(x0 + pad, ty, text='•', fill=acc, font=('Segoe UI', 10, 'bold'), anchor='nw')
                t = cv.create_text(x0 + pad + k * 16, ty, text=f, font=('Segoe UI', 10), fill='#d6d6e4', anchor='nw',
                                   width=cw - 2 * pad - k * 16)
                ty = cv.bbox(t)[3] + k * 6
            bottoms.append(ty + k * 58)
            self.cards[key] = (x0, top, x0 + cw, 0)
        bot = max(bottoms)
        for i, key in enumerate(list(self.cards)):
            x0, y0, x1, _ = self.cards[key]
            self.cards[key] = (x0, y0, x1, bot)
            hov = self.hover == key
            r = round_rect(cv, x0, y0, x1, bot, k * 22, fill='#1b1b2a' if hov else '#14141f',
                           outline=acc if hov else '#2a2a3c', width=2 if hov else 1)
            cv.tag_raise(r, 'bg')
            cv.create_text(x0 + pad, bot - k * 32, text=T('Выбрать  →'), font=('Segoe UI Semibold', 11), fill=acc,
                           anchor='w')
            cv.create_text(x1 - pad, bot - k * 32, text=T('клавиша {0}').format(i + 1), font=('Segoe UI', 9), fill='#6f6f88',
                           anchor='e')
        if bot + k * 44 < H:
            cv.create_text(cx, H - k * 24, text=T('Модели Forge работают прямо на вашем компьютере — без интернета'),
                           font=('Segoe UI', 9), fill='#5f5f78')

    def _draw_langs(self, W, k, acc):
        """Переключатель языка: «EN | RU», текущий язык подсвечен."""
        cv = self.cv
        f = ('Segoe UI Semibold', 9)
        h, seg = k * 26, k * 40
        x1, y0 = W - k * 18, k * 16
        x0 = x1 - seg * len(LANGUAGES)
        round_rect(cv, x0, y0, x1, y0 + h, h / 2, fill='#14141f', outline='#2a2a3c')
        self.langs = {}
        for i, code in enumerate(LANGUAGES):
            sx = x0 + i * seg
            key = f'lang:{code}'
            on = code == i18n.LANG
            if on or self.hover == key:
                round_rect(cv, sx + k * 2, y0 + k * 2, sx + seg - k * 2, y0 + h - k * 2, (h - k * 4) / 2,
                           fill=acc if on else '#22222f', outline='')
            cv.create_text(sx + seg / 2, y0 + h / 2, text=code.upper(), font=f,
                           fill=self.BG if on else '#d6d6e4')
            self.langs[key] = (sx, y0, sx + seg, y0 + h)
