# -*- coding: utf-8 -*-
"""Чат-студия: запрос словами → модель Forge сочиняет музыку или звук.

Анимации: живой пиксельный фон, плавное появление экрана и сообщений, «думающий» индикатор
(вращающаяся иконка, пульс, переливающийся текст, эквалайзер-заглушка), печать ответа,
рост волны, плейхед и живой эквалайзер при прослушивании, плавные наведения, всплывающие уведомления."""

import copy
import math
import os
import random
import re
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

import numpy as np

from scripts.audio.ffmpeg import export_mp3, FFMPEG_HELP, find_ffmpeg
from scripts.audio.player import Player
from scripts.audio.synth import render_song, write_wav
from scripts.core.constants import APP_NAME, VOWEL_NAMES
from scripts.core import i18n
from scripts.core.i18n import LANGUAGES, T
from scripts.core.prefs import save_prefs
from scripts.core.tasks import run_in_process, TaskRunner
from scripts.core.theory import blend, clamp
from scripts.models_of_ai.common import _ai_peaks, AI_ANY, AI_DURATIONS
from scripts.models_of_ai.genres import AI_GENRES
from scripts.models_of_ai.registry import AI_MODELS
from scripts.models_of_ai.respond import ai_respond
from scripts.models_of_ai.sfx import _ai_sfx_desc, AI_SFX, ai_sfx_sound
from scripts.ui.anim import Animator, collect_colors, ease_back, ease_out, PixelDust, tint
from scripts.ui.graphics import _glow_image, _photo, round_rect
from scripts.ui.popover import Popover
from scripts.ui.style import ACCENTS


CHAT_THEMES = {
    'dark': dict(bg='#0d0d14', fg='#ececf5', muted='#8b8ba3', pill='#1a1a26', pill_border='#2c2c3e',
                 bubble='#262640', card='#14141e', card_border='#26263a', btn='#22222f', btn_hover='#30304a',
                 wave='#3a3a52', glows=((.66, .7, .5, .5, None, .16), (.32, .42, .4, .42, '#6a5cff', .12))),
    'light': dict(bg='#f7f7f9', fg='#1f1f24', muted='#6b6b78', pill='#ffffff', pill_border='#e1e5ea',
                  bubble='#e9eef6', card='#ffffff', card_border='#e3e7ec', btn='#eef1f5', btn_hover='#e1e6ee',
                  wave='#cfd6e0', glows=((.58, .66, .5, .5, '#bcdcfa', .85), (.4, .44, .42, .42, '#dbe8fb', .6))),
}


CHAT_EXAMPLES = [('⚔', 'Эпичная битва с боссом в замке'), ('☾', 'Спокойный фон для стрима, ночной город'),
                 ('☂', 'Грустная мелодия под дождь, с вокалом'), ('✸', 'Набор звуков для платформера'),
                 ('★', 'Короткий победный джингл'), ('✧', 'Загадочный космос, 2 минуты')]
EQ_BANDS = (2, 6, 14, 32, 80, 200)  # границы полос живого эквалайзера (бины БПФ на окне 2048)
GENRE_ICONS = {'Приключение': '⚑', 'Битва с боссом': '⚔', 'Экшен / погоня': '➹', 'Гонки': '⚐',
               'Подземелье / хоррор': '☠', 'Замок / готика': '♜', 'Деревня / уют': '⌂', 'Чилл / лоу-фай': '☕',
               'Синтвейв / ночной город': '☾', 'Космос': '☄', 'Подводный мир': '≈', 'Зима / праздник': '❄',
               'Грусть / дождь': '☂', 'Победа / фанфары': '★', 'Блюз / джаз / фанк': '♬',
               'Главное меню / титры': '▶', 'Магазин / мини-игра': '♦', 'Марш / армия': '⚜', 'Рок / метал': '⚡',
               'Танцевальная / диско': '✺', 'Сказка / магия': '✧', 'Тайна / детектив': '◎'}


class ChatStudio:
    """Чат-режим в духе нейросетевых ассистентов: запрос → модель Forge сочиняет музыку или звук."""
    FONTS = {'greet': ('Segoe UI Semilight', 30), 'input': ('Segoe UI', 12), 'msg': ('Segoe UI', 11),
             'msg_b': ('Segoe UI Semibold', 11), 'title': ('Segoe UI Semibold', 13), 'small': ('Segoe UI', 9),
             'small_b': ('Segoe UI Semibold', 9), 'btn': ('Segoe UI Semibold', 10), 'brand': ('Consolas', 13, 'bold'),
             'icon': ('Segoe UI Symbol', 13)}

    def __init__(self, win, shell, state=None):
        self.win, self.shell, self.k = win, shell, shell.k
        self.prefs = shell.prefs
        self.player = Player()
        self.tasks = TaskRunner(win)
        self.anim = Animator(win)
        self.msgs = []
        self.scroll, self._scroll_target, self.stick, self.content_h = 0.0, 0.0, True, 0
        self.area = (0, 0)
        self.playing = None  # (результат, t0, длительность)
        self.busy = False
        self._fonts, self._imgs = {}, {}
        self._bg_key = None
        self._job = None
        self._uid = 0
        self._popover, self._pop_closed, self._anchors, self._pop_up = None, None, {}, False
        self._lines, self._text_w, self._send, self._send_c, self._pill = 1, 400, None, None, None
        self._intro, self._focused, self._toast_state = True, False, None
        model = self.prefs.get('chat_model', 'auto')
        self.v_model = tk.StringVar(win, value=model if model in AI_MODELS else 'auto')
        self.v_dur, self.v_voc, self.v_genre = (tk.StringVar(win, value=AI_ANY) for _ in range(3))
        self.v_vowel = tk.StringVar(win, value='auto')
        self.v_autoplay = tk.BooleanVar(win, value=self.prefs.get('chat_autoplay', True))
        for v in (self.v_model, self.v_dur, self.v_voc, self.v_genre, self.v_vowel, self.v_autoplay):
            v.trace_add('write', lambda *a: self._on_option())
        win.title(T('{0} — ✦ Чат-студия').format(APP_NAME))
        shell.center(win, 1280, 840)
        win.minsize(int(720 * self.k), int(540 * self.k))
        self.cv = tk.Canvas(win, highlightthickness=0, bd=0)
        self.cv.pack(fill='both', expand=True)
        self.dust = PixelDust(self.cv)
        self.entry = tk.Text(self.cv, height=1, wrap='word', bd=0, highlightthickness=0, font=self.F('input'),
                             padx=0, pady=0, undo=True)
        self.entry.configure(insertwidth=max(2, round(2 * self.k)), insertofftime=500, insertontime=600)
        self.ph = tk.Label(self.entry, text=T('Опишите музыку или звук…'), bd=0, padx=0, pady=0, cursor='xterm',
                           font=self.F('input'))
        self._show_ph()
        self.ph.bind('<Button-1>', lambda e: self.entry.focus_set())
        self.entry.bind('<Return>', self._on_return)
        self.entry.bind('<KeyRelease>', lambda e: self._entry_changed())
        self.entry.bind('<<Paste>>', lambda e: self.win.after(1, self._entry_changed))
        self.entry.bind('<FocusIn>', lambda e: self._focus(True))
        self.entry.bind('<FocusOut>', lambda e: self._focus(False))
        self.cv.bind('<Configure>', lambda e: self._schedule())
        self.cv.bind('<MouseWheel>', self._on_wheel)
        win.bind('<Escape>', lambda e: self.stop_playback())
        win.protocol('WM_DELETE_WINDOW', shell.quit)
        if state is not None:
            self.import_state(state)
        self.apply_theme()
        self.entry.focus_set()

    # ── смена языка: окно строится заново, переписка и выбранные опции переносятся ──
    def export_state(self):
        return dict(msgs=self.msgs, text=self._text(), dur=self.v_dur.get(), voc=self.v_voc.get(),
                    genre=self.v_genre.get(), vowel=self.v_vowel.get())

    def import_state(self, st):
        for m in st['msgs']:  # убрать ссылки на элементы старого холста
            for key in [k for k in m if k.startswith('_') and k not in ('_in', '_grown')]:
                del m[key]
            for r in m.get('results', ()):
                for key in [k for k in r if k.startswith('_') and k != '_grown']:
                    del r[key]
        self.msgs = st['msgs']
        self._intro = not self.msgs
        for var, key in ((self.v_dur, 'dur'), (self.v_voc, 'voc'), (self.v_genre, 'genre'), (self.v_vowel, 'vowel')):
            var.set(st[key])
        if st['text']:
            self.entry.insert('1.0', st['text'])
            self.ph.place_forget()

    def dispose(self):
        """Закрыть окно без выхода из программы (при смене языка)."""
        self.stop_playback()
        self.anim.stop()
        if self._job:
            self.win.after_cancel(self._job)
        if self._popover:
            self._popover.close()
        try:
            self.player.cleanup()
        except Exception:  # noqa
            pass
        self.tasks.close()
        self.win.destroy()

    def toggle_language(self):
        self.shell.set_language('ru' if i18n.LANG == 'en' else 'en')

    # ── оформление ──
    def F(self, name):
        if name not in self._fonts:
            fam, size, *bold = self.FONTS[name]
            self._fonts[name] = tkfont.Font(root=self.win, family=fam, size=size, weight='bold' if bold else 'normal')
        return self._fonts[name]

    def apply_theme(self):
        self.theme = self.prefs.get('theme', 'dark')
        if self.theme not in CHAT_THEMES:
            self.theme = 'dark'
        c = dict(CHAT_THEMES[self.theme])
        acc = ACCENTS.get(self.prefs.get('accent'), '#00d9ff')
        c.update(accent=acc, accent_fg='#0b0b12', accent_hover=blend(acc, '#ffffff', .25),
                 accent_text=acc if self.theme == 'dark' else blend(acc, '#000000', .35))
        self.c = c
        self.cv.configure(bg=c['bg'])
        self.win.configure(bg=c['bg'])
        self.entry.configure(bg=c['pill'], fg=c['fg'], insertbackground=c['fg'], selectbackground=acc,
                             selectforeground='#0b0b12')
        self.ph.configure(bg=c['pill'], fg=c['muted'])
        self._bg_key = None
        self.relayout()

    def toggle_theme(self):
        self.shell.set_theme('light' if self.theme == 'dark' else 'dark')
        self.apply_theme()

    def _schedule(self):
        if self._job:
            self.win.after_cancel(self._job)
        self._job = self.win.after(40, self.relayout)

    def relayout(self):
        self._job = None
        if self._popover:  # окно перестроилось — старое положение меню больше не верно
            self._popover.close()
        cv, c, k = self.cv, self.c, self.k
        W, H = max(cv.winfo_width(), 300), max(cv.winfo_height(), 300)
        self.W, self.H = W, H
        if self._bg_key != (W, H, self.theme, c['accent']):
            glows = [(x, y, rx, ry, col or c['accent'], a) for x, y, rx, ry, col, a in c['glows']]
            self._bg_arr = _glow_image(W, H, c['bg'], glows)
            self._imgs['bg'] = _photo(self._bg_arr)
            self._bg_key = (W, H, self.theme, c['accent'])
        self._imgs = {'bg': self._imgs['bg']}
        cv.delete('all')
        cv.configure(cursor='')
        cv.create_image(0, 0, image=self._imgs['bg'], anchor='nw', tags=('bg',))
        self.colw = min(k * 820, W - k * 48)
        self.x0 = (W - self.colw) / 2
        self._draw_overlay()
        self._render_msgs()
        cv.tag_raise('overlay')
        self.dust.build(W, H, [c['accent'], '#6a5cff', c['muted']], c['bg'], k)
        self.anim.loop('dust', self.dust.step)
        self._draw_toast()
        if self._intro and not self.msgs and self.win.winfo_viewable():
            self._intro = False
            self._play_intro()

    def relayout_msgs(self):
        self.cv.delete('msg')
        self._render_msgs()
        self.cv.tag_raise('overlay')
        self.cv.tag_raise('toast')

    def _mask(self, x0, y0, x1, y1):
        """Кусок фона поверх сообщений — чтобы прокрученные сообщения уходили «под» шапку и поле ввода."""
        y0, y1 = int(clamp(y0, 0, self.H)), int(clamp(y1, 0, self.H))
        if y1 <= y0:
            return
        img = self._imgs[f'mask{y0}'] = _photo(self._bg_arr[y0:y1, int(x0):int(x1)])
        self.cv.create_image(x0, y0, image=img, anchor='nw', tags=('overlay',))

    # ── анимационные помощники ──
    def _bg_at(self, x, y):
        """Настоящий цвет градиентного фона в точке — в него элементы растворяются и из него проявляются."""
        arr = self._bg_arr
        r, g, b = arr[int(clamp(y, 0, arr.shape[0] - 1)), int(clamp(x, 0, arr.shape[1] - 1))]
        return '#%02x%02x%02x' % (r, g, b)

    def _bg_under(self, ids):
        out = {}
        for it in ids:
            bb = self.cv.bbox(it)
            if bb:
                out[it] = self._bg_at((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
        return out

    def _fade_in(self, tag, delay=0.0, dy=0.0, dur=.35, ease=ease_out):
        """Проявить элементы с тегом из фона, заодно подвинув их на место снизу (или сверху при dy < 0)."""
        cv = self.cv
        ids = cv.find_withtag(tag)
        if not ids:
            return
        cols = collect_colors(cv, ids)
        bg = self._bg_under(ids)
        tint(cv, cols, bg, 0)
        for it in ids:
            cv.move(it, 0, dy)
        st = {'off': dy}

        def fn(t):
            tint(cv, cols, bg, min(1.0, t))
            off = dy * (1 - t)
            if dy:
                for it in ids:
                    cv.move(it, 0, off - st['off'])
                st['off'] = off
        self.anim.tween(None, dur, fn, delay=delay, ease=ease)

    def _fade_out(self, tag, dur=.3, then=None):
        cv = self.cv
        ids = cv.find_withtag(tag)
        cols = collect_colors(cv, ids)
        bg = self._bg_under(ids)

        def done():
            for it in ids:
                cv.delete(it)
            if then:
                then()
        self.anim.tween(None, dur, lambda t: tint(cv, cols, bg, 1 - t), done=done)

    def _play_intro(self):
        """Стартовый экран: приветствие выплывает, опции и подсказки появляются по очереди."""
        k = self.k
        groups = ['hero_g', 'hero_c'] + [f'hero_s{i}' for i in range(len(CHAT_EXAMPLES))] + ['hero_f']
        for i, tag in enumerate(groups):
            self._fade_in(tag, delay=.05 + i * .07, dy=k * (18 if i == 0 else 12), dur=.55, ease=ease_back)

    def _focus(self, on):
        """Рамка поля ввода мягко подсвечивается акцентом, когда в нём курсор."""
        self._focused = on
        if self._pill is None:
            return
        c, pill = self.c, self._pill
        a, b = c['pill_border'], blend(c['pill_border'], c['accent'], .75)
        if not on:
            a, b = b, a
        self.anim.tween('focus', .25, lambda t: self.cv.itemconfigure(pill, outline=blend(a, b, t)))

    def _ripple(self):
        """Круги расходятся от кнопки отправки."""
        if not self._send_c:
            return
        cv, c, k = self.cv, self.c, self.k
        cx, cy, r0 = self._send_c
        under = self._bg_at(cx, cy - r0 * 2)
        for i in range(2):
            o = cv.create_oval(cx - r0, cy - r0, cx + r0, cy + r0, outline=c['accent'], width=2 * k,
                               tags=('overlay',))

            def fn(t, o=o):
                r = r0 * (1 + 1.6 * t)
                cv.coords(o, cx - r, cy - r, cx + r, cy + r)
                cv.itemconfigure(o, outline=blend(c['accent'], under, t))
            self.anim.tween(None, .6, fn, done=lambda o=o: cv.delete(o), delay=i * .14)

    def _toast(self, text, ok=True, ttl=2.8):
        """Всплывающее уведомление сверху: выезжает, висит, растворяется."""
        self._toast_state = dict(text=text, ok=ok, until=time.perf_counter() + ttl)
        self._draw_toast(animate=True)
        self.anim.tween('toast_life', ttl, lambda t: None, done=self._toast_out, ease=lambda t: t)

    def _draw_toast(self, animate=False):
        cv, c, k = self.cv, self.c, self.k
        cv.delete('toast')
        st = self._toast_state
        if not st or time.perf_counter() > st['until']:
            return
        f = self.F('btn')
        w, h = f.measure(st['text']) + k * 44, k * 38
        x0, y = (self.W - w) / 2, k * 72
        round_rect(cv, x0, y, x0 + w, y + h, h / 2, fill=c['card'], outline=c['accent'] if st['ok'] else '#ff5c7a',
                   width=1.5 * k, tags=('overlay', 'toast'))
        cv.create_text(self.W / 2, y + h / 2, text=st['text'], font=f, fill=c['fg'], tags=('overlay', 'toast'))
        cv.tag_raise('toast')
        if animate:
            self._fade_in('toast', dy=-k * 16, dur=.35, ease=ease_back)

    def _toast_out(self):
        self._toast_state = None
        self._fade_out('toast', .35)

    # ── элементы ──
    def _button(self, x, y, text, cmd, style='ghost', anchor='w', tags=('overlay',), font='btn'):
        cv, c, k = self.cv, self.c, self.k
        f = self.F(font)
        h = k * 32
        w = f.measure(text) + k * 28
        if anchor == 'e':
            x -= w
        elif anchor == 'center':
            x -= w / 2
        fill, fg, hover, outline = {
            'ghost': (c['btn'], c['fg'], c['btn_hover'], ''),
            'accent': (c['accent'], c['accent_fg'], c['accent_hover'], ''),
            'chip': (c['pill'], c['muted'], c['btn_hover'], c['pill_border']),
            'chip_on': (c['pill'], c['accent_text'], c['btn_hover'], c['accent']),
            'sugg': (c['pill'], c['fg'], c['btn_hover'], c['pill_border']),
        }[style]
        self._uid += 1
        bid = f'b{self._uid}'
        r = round_rect(cv, x, y - h / 2, x + w, y + h / 2, h / 2, fill=fill, outline=outline, tags=tags + (bid,))
        cv.create_text(x + w / 2, y, text=text, font=f, fill=fg, tags=tags + (bid,))

        def hover_to(on):
            cv.configure(cursor='hand2' if on else '')
            a, b = (fill, hover) if on else (hover, fill)
            self.anim.tween(('hov', bid), .14, lambda t: cv.itemconfigure(r, fill=blend(a, b, t)))
        cv.tag_bind(bid, '<Enter>', lambda e: hover_to(True))
        cv.tag_bind(bid, '<Leave>', lambda e: hover_to(False))
        cv.tag_bind(bid, '<Button-1>', lambda e: self.win.after_idle(cmd))
        return x, x + w

    def _text(self):
        return self.entry.get('1.0', 'end-1c')

    def _count_lines(self, width):
        f = self.F('input')
        n = sum(max(1, -(-f.measure(line) // max(1, int(width)))) for line in self._text().split('\n'))
        return int(clamp(n, 1, 6))

    def _draw_overlay(self):
        cv, c, k = self.cv, self.c, self.k
        W, H, x0, colw = self.W, self.H, self.x0, self.colw
        chat = bool(self.msgs)
        lh = self.F('input').metrics('linespace')
        name, short = AI_MODELS[self.v_model.get()]['name'].split(' ', 1)
        f_b, f_m = self.F('msg_b'), self.F('msg')
        mw = f_b.measure(name + ' ') + f_m.measure(short + '  ▾')
        self._text_w = colw - k * 60 - mw - k * 96
        self._lines = lines = self._count_lines(self._text_w)
        ph = max(k * 62, lines * lh + k * 32)
        if chat:
            chips_y = H - k * 30
            y1 = chips_y - k * 30
            y0 = y1 - ph
            self._mask(0, y0 - k * 20, W, H)
            self._mask(0, 0, W, k * 62)
            self.area = (k * 66, y0 - k * 20)
        else:
            y0 = H * .44 - k * 31
            y1 = y0 + ph
            chips_y = y1 + k * 32
        # шапка
        cv.create_text(k * 22, k * 31, text='▚▞ 8-BIT FORGE', font=self.F('brand'), fill=c['accent_text'], anchor='w',
                       tags=('overlay',))
        cv.create_text(k * 32 + self.F('brand').measure('▚▞ 8-BIT FORGE'), k * 32, text=T('Чат-студия'),
                       font=self.F('small_b'), fill=c['muted'], anchor='w', tags=('overlay',))
        x = W - k * 18
        for text, cmd in (('☀' if self.theme == 'dark' else '☾', self.toggle_theme),
                          ('EN ⇄ RU', self.toggle_language),
                          (T('⌂  Меню'), self.shell.show_launcher), (T('✎  Ручной режим'), self.shell.open_manual),
                          (T('+  Новый чат'), self.new_chat)):
            x = self._button(x, k * 31, text, cmd, anchor='e')[0] - k * 8
        # поле ввода — «пилюля» как у нейросетевых чатов
        x1 = x0 + colw
        rad = min(k * 31, ph / 2)
        if self.theme == 'light':
            round_rect(cv, x0, y0 + k * 3, x1, y1 + k * 4, rad, fill='#e4e9f1', outline='', tags=('overlay',))
        border = blend(c['pill_border'], c['accent'], .75) if self._focused else c['pill_border']
        self._pill = round_rect(cv, x0, y0, x1, y1, rad, fill=c['pill'], outline=border, width=1.5 * k,
                                tags=('overlay',))
        cy = y1 - k * 31
        self._pop_up = chat  # в чате поле внизу — меню открываются вверх, на стартовом экране — вниз
        self._anchors = {'plus': (x0 + k * 13, cy - k * 18, x0 + k * 49, cy + k * 18)}
        self._circle_btn(x0 + k * 31, cy, k * 18, '+', self._menu_plus, c['pill'], c['btn_hover'], c['fg'], 'title')
        ey = cy - lh / 2 if lines == 1 else y0 + k * 16
        self.entry.configure(height=lines)
        cv.create_window(x0 + k * 60, ey, window=self.entry, anchor='nw', width=self._text_w, height=lines * lh,
                         tags=('overlay',))
        mx = x1 - k * 74 - mw
        self._uid += 1
        tag = f'b{self._uid}'
        hr = round_rect(cv, mx - k * 12, cy - k * 17, mx + mw + k * 10, cy + k * 17, k * 17, fill=c['pill'], outline='',
                        tags=('overlay', tag))
        self._anchors['model'] = (mx - k * 12, cy - k * 17, mx + mw + k * 10, cy + k * 17)
        cv.create_text(mx, cy, text=name, font=f_b, fill=c['fg'], anchor='w', tags=('overlay', tag))
        cv.create_text(mx + f_b.measure(name + ' '), cy, text=short + '  ▾', font=f_m, fill=c['muted'], anchor='w',
                       tags=('overlay', tag))

        def hover_model(on):
            cv.configure(cursor='hand2' if on else '')
            a, b = (c['pill'], c['btn_hover']) if on else (c['btn_hover'], c['pill'])
            self.anim.tween(('hov', tag), .14, lambda t: cv.itemconfigure(hr, fill=blend(a, b, t)))
        cv.tag_bind(tag, '<Enter>', lambda e: hover_model(True))
        cv.tag_bind(tag, '<Leave>', lambda e: hover_model(False))
        cv.tag_bind(tag, '<Button-1>', lambda e: self.win.after_idle(self._menu_model))
        self._send_c = (x1 - k * 33, cy, k * 20)
        self._send = self._circle_btn(x1 - k * 33, cy, k * 20, '➤', self.send, *self._send_colors(), 'msg_b')
        # опции под полем: длительность, вокал, жанр
        x = x0 + k * 6
        for key, icon, label, var in (('dur', '◷', T('Длительность'), self.v_dur), ('voc', '♪', T('Вокал'), self.v_voc),
                                      ('genre', '♫', T('Жанр'), self.v_genre)):
            val = var.get()
            shown = T(val)
            if key == 'voc' and val != AI_ANY and val != 'Без вокала' and self.v_vowel.get() != 'auto':
                shown += ' · ' + T(VOWEL_NAMES[self.v_vowel.get()])
            text = f'{icon}  {label}: {T("по запросу") if val == AI_ANY else shown}  ▾'
            bx0, bx1 = self._button(x, chips_y, text, lambda k_=key: self._menu_option(k_),
                                    style='chip' if val == AI_ANY else 'chip_on', font='small_b',
                                    tags=('overlay', 'hero_c'))
            self._anchors[key] = (bx0, chips_y - k * 16, bx1, chips_y + k * 16)
            x = bx1 + k * 8
        if not chat:
            cv.create_text(W / 2, y0 - k * 54, text=T('С чего начнём?'), font=self.F('greet'), fill=c['fg'],
                           tags=('overlay', 'hero_g'))
            rows, row, rw = [], [], 0.0
            for i, (icon, text) in enumerate(CHAT_EXAMPLES):
                text = T(text)
                label = f'{icon}  {text}'
                bw = self.F('btn').measure(label) + k * 28
                if row and rw + bw > colw:
                    rows.append((row, rw))
                    row, rw = [], 0.0
                row.append((i, label, text, bw))
                rw += bw + k * 10
            if row:
                rows.append((row, rw))
            y = chips_y + k * 58
            for row, rw in rows:
                bx = W / 2 - (rw - k * 10) / 2
                for i, label, text, bw in row:
                    self._button(bx, y, label, lambda t=text: self.send(t), style='sugg',
                                 tags=('overlay', f'hero_s{i}'))
                    bx += bw + k * 10
                y += k * 44
            if y + k * 20 < H - k * 24:
                cv.create_text(W / 2, H - k * 22, text=T('Модели Forge сочиняют прямо на вашем компьютере — без интернета'),
                               font=self.F('small'), fill=c['muted'], tags=('overlay', 'hero_f'))

    def _send_colors(self):
        c = self.c
        if self._text().strip() and not self.busy:
            return c['accent'], c['accent_hover'], c['accent_fg']
        return c['btn'], c['btn_hover'], c['muted']

    def _circle_btn(self, cx, cy, r, text, cmd, fill, hover, fg, font):
        cv = self.cv
        self._uid += 1
        tag = f'b{self._uid}'
        o = cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline='', tags=('overlay', tag))
        t = cv.create_text(cx, cy, text=text, font=self.F(font), fill=fg, tags=('overlay', tag))
        state = {'fill': fill, 'hover': hover}

        def hover_to(on):
            cv.configure(cursor='hand2' if on else '')
            a, b = (state['fill'], state['hover']) if on else (state['hover'], state['fill'])
            self.anim.tween(('hov', tag), .14, lambda t_: cv.itemconfigure(o, fill=blend(a, b, t_)))
        cv.tag_bind(tag, '<Enter>', lambda e: hover_to(True))
        cv.tag_bind(tag, '<Leave>', lambda e: hover_to(False))
        cv.tag_bind(tag, '<Button-1>', lambda e: self.win.after_idle(cmd))
        return o, t, state

    def _update_send(self):
        if self._send:
            o, t, state = self._send
            fill, hover, fg = self._send_colors()
            old = state['fill']
            state.update(fill=fill, hover=hover)
            if old != fill:
                self.anim.tween('send', .2, lambda t_: self.cv.itemconfigure(o, fill=blend(old, fill, t_)))
            self.cv.itemconfigure(t, fill=fg)

    # ── сообщения ──
    def _render_msgs(self):
        if not self.msgs:
            self.content_h = 0
            return
        k = self.k
        top, bottom = self.area
        y = k * 8
        for m in self.msgs:
            if '_id' not in m:
                self._uid += 1
                m['_id'] = self._uid
            self._mt = ('msg', f'm{m["_id"]}')
            y = (self._draw_user(m, y) if m['role'] == 'user' else self._draw_bot(m, y)) + k * 26
        self.content_h = y
        mx = max(0, y - (bottom - top))
        if self.stick:
            self._scroll_target = mx
        self._scroll_target = clamp(self._scroll_target, 0, mx)
        self.scroll = clamp(self.scroll, 0, mx)
        self.cv.move('msg', 0, top - self.scroll)
        for m in self.msgs:  # новые сообщения выплывают снизу
            if not m.get('_in'):
                m['_in'] = True
                self._fade_in(f'm{m["_id"]}', delay=.06 if m['role'] == 'bot' else 0, dy=k * 18, dur=.4)
        if abs(self._scroll_target - self.scroll) > .5:
            self.anim.loop('scroll', self._scroll_step)

    def _draw_user(self, m, y):
        cv, c, k = self.cv, self.c, self.k
        t = cv.create_text(0, 0, text=m['text'], font=self.F('msg'), fill=c['fg'], anchor='nw',
                           width=self.colw * .72 - k * 36, tags=self._mt)
        bx0, by0, bx1, by1 = cv.bbox(t)
        x1 = self.x0 + self.colw
        x0 = x1 - (bx1 - bx0) - k * 36
        cv.coords(t, x0 + k * 18, y + k * 12)
        r = round_rect(cv, x0, y, x1, y + (by1 - by0) + k * 24, k * 20, fill=c['bubble'], outline='', tags=self._mt)
        cv.tag_lower(r, t)
        return y + (by1 - by0) + k * 24

    def _draw_bot(self, m, y):
        cv, c, k = self.cv, self.c, self.k
        mt = self._mt
        x = self.x0
        info = AI_MODELS.get(m.get('model'), AI_MODELS['auto'])
        thinking = bool(m.get('status'))
        ring = cv.create_oval(x, y, x + k * 30, y + k * 30, outline=c['accent'] if thinking else '', width=2 * k,
                              tags=mt)
        avatar = cv.create_oval(x, y, x + k * 30, y + k * 30, fill=c['accent'], outline='', tags=mt)
        icon = cv.create_text(x + k * 15, y + k * 15, text=info['icon'], font=self.F('icon'), fill=c['accent_fg'],
                              tags=mt)
        cv.create_text(x + k * 42, y + k * 15, text=info['name'], font=self.F('small_b'), fill=c['muted'], anchor='w',
                       tags=mt)
        tx, tw, ty = x + k * 42, self.colw - k * 42, y + k * 36
        if thinking:
            return self._draw_thinking(m, tx, ty, tw, dict(ring=ring, avatar=avatar, icon=icon))
        typing = m.get('_typing') is not None
        n = int(m.get('_typing') or 0)
        head, text = m.get('head', ''), m.get('text', '')
        m['_hid'] = m['_tid'] = None
        if head:
            t = cv.create_text(tx, ty, text=head, font=self.F('msg_b'), fill=c['fg'], anchor='nw', width=tw, tags=mt)
            ty = cv.bbox(t)[3] + k * 6
            m['_hid'] = t
        if text:
            t = cv.create_text(tx, ty, text=text, font=self.F('msg'), fill=c['fg'], anchor='nw', width=tw, tags=mt)
            ty = cv.bbox(t)[3] + k * 12
            m['_tid'] = t
        if typing:
            self._show_typed(m, n)
        for r in m.get('results', ()):
            ty = self._draw_card(m, r, tx, ty, tw, hidden=typing) + k * 10
        return ty

    def _draw_thinking(self, m, tx, ty, tw, th):
        """«Модель думает»: переливающийся статус, прыгающие точки и эквалайзер-заглушка будущего трека."""
        cv, c, k, mt = self.cv, self.c, self.k, self._mt
        f = self.F('msg')
        text = m['status']
        th['chars'] = [cv.create_text(tx + f.measure(text[:i]), ty, text=ch, font=f, fill=c['muted'], anchor='nw',
                                      tags=mt) for i, ch in enumerate(text)]
        dx = tx + f.measure(text) + k * 8
        th['dots'] = [cv.create_oval(dx + i * k * 9, ty + k * 10, dx + i * k * 9 + k * 5, ty + k * 15,
                                     fill=c['accent'], outline='', tags=mt) for i in range(3)]
        th['doff'] = [0.0, 0.0, 0.0]
        cy0, w, h = ty + k * 32, min(tw, k * 440), k * 78
        round_rect(cv, tx, cy0, tx + w, cy0 + h, k * 18, fill=c['card'], outline=c['card_border'], tags=mt)
        mid = cy0 + h / 2
        th['eq'] = [cv.create_rectangle(tx + k * 18 + i * k * 7, mid - k * 2, tx + k * 22 + i * k * 7, mid + k * 2,
                                        fill=c['wave'], outline='', tags=mt)
                    for i in range(int((w - k * 36) // (k * 7)))]
        m['_think'] = th
        return cy0 + h

    def _think_step(self, dt, now):
        if not self.busy:
            return False
        cv, c, k = self.cv, self.c, self.k
        hi = c['fg'] if self.theme == 'dark' else c['accent_text']
        for m in self.msgs:
            th = m.get('_think')
            if not m.get('status') or not th:
                continue
            cv.itemconfigure(th['icon'], angle=(now * 140) % 360)
            co = cv.coords(th['avatar'])
            if co:
                cx, cy, r0 = (co[0] + co[2]) / 2, (co[1] + co[3]) / 2, (co[2] - co[0]) / 2
                ph = (now * 1.2) % 1
                r = r0 + ph * k * 13
                cv.coords(th['ring'], cx - r, cy - r, cx + r, cy + r)
                cv.itemconfigure(th['ring'], outline=blend(c['accent'], self._bg_at(cx, cy - r), ph))
            n = len(th['chars'])
            pos = (now * 16) % (n + 10) - 5
            for i, cid in enumerate(th['chars']):
                cv.itemconfigure(cid, fill=blend(c['muted'], hi, max(0.0, 1 - abs(i - pos) / 3.5)))
            for i, d in enumerate(th['dots']):
                off = -abs(math.sin(now * 5.5 - i * .7)) * k * 6
                cv.move(d, 0, off - th['doff'][i])
                th['doff'][i] = off
            for i, b in enumerate(th['eq']):
                co = cv.coords(b)
                if not co:
                    continue
                mid = (co[1] + co[3]) / 2
                v = abs(math.sin(now * (2.6 + (i % 5) * .6) + i * .55) * math.sin(now * 1.1 + i * .23))
                h = (3 + 30 * v) * k
                cv.coords(b, co[0], mid - h / 2, co[2], mid + h / 2)
                cv.itemconfigure(b, fill=blend(c['wave'], c['accent'], .25 + .75 * v))
        return True

    def _show_typed(self, m, n):
        head, text = m.get('head', ''), m.get('text', '')
        caret = '▍'
        if m.get('_hid'):
            self.cv.itemconfigure(m['_hid'], text=head[:n] + (caret if n < len(head) else ''))
        if m.get('_tid'):
            j = n - len(head)
            self.cv.itemconfigure(m['_tid'], text=text[:j] + caret if j >= 0 else '')

    def _type_step(self, dt, now):
        """Ответ «печатается», как у нейросетевых чатов; потом проявляются карточки."""
        active = False
        for m in self.msgs:
            if m.get('_typing') is None:
                continue
            total = len(m.get('head', '')) + len(m.get('text', ''))
            m['_typing'] += dt * max(260.0, total / 1.4)
            if m['_typing'] >= total:
                m['_typing'] = None
                self._reveal(m)
                continue
            active = True
            self._show_typed(m, int(m['_typing']))
        return active

    def _reveal(self, m):
        self.relayout_msgs()
        for r in m.get('results', ()):
            self._fade_in(f'c{r["_cid"]}', dy=self.k * 12, dur=.45, ease=ease_back)
        if m.pop('_autoplay', False) and m.get('results') and m in self.msgs:
            self.play_result(m['results'][0])

    @staticmethod
    def _status_text(m):
        return m['status']

    def _progress(self, r):
        if not self.playing or self.playing[0] is not r:
            return None
        return clamp((time.perf_counter() - self.playing[1]) / self.playing[2], 0, 1)

    def _draw_card(self, m, r, x, y, w, hidden=False):
        cv, c, k = self.cv, self.c, self.k
        if '_cid' not in r:
            self._uid += 1
            r['_cid'] = self._uid
        ctag = f'c{r["_cid"]}'
        pad, tags = k * 16, self._mt + (ctag,)
        t = cv.create_text(x + pad, y + pad, text=r['title'], font=self.F('title'), fill=c['fg'], anchor='nw',
                           width=w - 2 * pad - k * 60, tags=tags)
        s = cv.create_text(x + pad, cv.bbox(t)[3] + k * 2, text=r['sub'], font=self.F('small'), fill=c['muted'],
                           anchor='nw', width=w - 2 * pad, tags=tags)
        yy = cv.bbox(s)[3] + k * 12
        wh, step = k * 36, k * 5
        nb = max(16, int((w - 2 * pad) // step))
        pk = r['peaks']
        prog = self._progress(r)
        playing = prog is not None
        upto = int(prog * nb) if playing else 0
        self._uid += 1
        wid = f'wf{self._uid}'
        bars, heights = [], []
        grow = not hidden and not r.get('_grown')
        for i in range(nb):
            bh = max(k * 2, pk[min(len(pk) - 1, int(i * len(pk) / nb))] * wh)
            heights.append(bh)
            h0 = k * 1 if grow else bh
            bx = x + pad + i * step
            bars.append(cv.create_rectangle(bx, yy + wh / 2 - h0 / 2, bx + k * 3, yy + wh / 2 + h0 / 2,
                                            fill=c['accent'] if i < upto else c['wave'], outline='',
                                            tags=tags + (wid,)))
        r['_bars'], r['_shown'] = bars, upto
        if grow:  # волна вырастает слева направо
            r['_grown'] = True

            def fn(tt, bars=bars, heights=heights):
                for i, (b, bh) in enumerate(zip(bars, heights)):
                    p = clamp(tt * 1.6 - i / len(bars) * .6, 0, 1)
                    co = cv.coords(b)
                    if co:
                        mid, h = (co[1] + co[3]) / 2, max(k, bh * ease_out(p))
                        cv.coords(b, co[0], mid - h / 2, co[2], mid + h / 2)
            self.anim.tween(None, .9, fn, ease=lambda q: q, delay=.1)
        r['_ph'] = r['_eq'] = None
        if playing:  # плейхед и живой эквалайзер у заголовка
            px = x + pad + prog * (nb * step)
            r['_ph'] = cv.create_line(px, yy - k * 4, px, yy + wh + k * 4, fill=c['accent'], width=2 * k, tags=tags)
            ex, ey = x + w - pad - k * 40, y + pad + k * 20
            r['_eq'] = [cv.create_rectangle(ex + i * k * 8, ey - k * 3, ex + i * k * 8 + k * 5, ey, fill=c['accent'],
                                            outline='', tags=tags) for i in range(len(EQ_BANDS) - 1)]
        cv.tag_bind(wid, '<Button-1>', lambda e: self.win.after_idle(lambda: self.play_result(r)))
        cv.tag_bind(wid, '<Enter>', lambda e: cv.configure(cursor='hand2'))
        cv.tag_bind(wid, '<Leave>', lambda e: cv.configure(cursor=''))
        btns = [(T('■  Стоп') if playing else T('▶  Слушать'), lambda: self.play_result(r), 'accent'),
                (T('⚄  Другой вариант') if r['kind'] == 'sfx' else T('⚄  Ещё вариант'), lambda: self.again(m, r), 'ghost'),
                ('⬇  WAV', lambda: self.save_result(r, '.wav'), 'ghost'),
                ('⬇  MP3', lambda: self.save_result(r, '.mp3'), 'ghost')]
        if r['kind'] == 'song':
            btns.append((T('✎  В редактор'), lambda: self.to_editor(r), 'ghost'))
        bx, by = x + pad, yy + wh + k * 30
        for text, cmd, style in btns:
            bw = self.F('btn').measure(text) + k * 28
            if bx + bw > x + w - pad and bx > x + pad:
                bx, by = x + pad, by + k * 40
            self._button(bx, by, text, cmd, style=style, tags=tags)
            bx += bw + k * 8
        bottom = by + k * 16 + pad
        r['_card'] = round_rect(cv, x, y, x + w, bottom, k * 18, fill=c['card'],
                                outline=blend(c['card_border'], c['accent'], .5) if playing else c['card_border'],
                                width=1.5 * k if playing else 1, tags=tags)
        cv.tag_lower(r['_card'], t)
        if hidden:
            cv.itemconfigure(ctag, state='hidden')
        return bottom

    def _play_step(self, dt, now):
        """Покадрово: закрашиваем пройденную волну, двигаем плейхед, качаем эквалайзер, пульсирует рамка."""
        if not self.playing:
            return False
        cv, c, k = self.cv, self.c, self.k
        r, t0, dur = self.playing
        p = (time.perf_counter() - t0) / dur
        if p >= 1:
            self.stop_playback()
            return False
        bars = r.get('_bars') or []
        upto = min(len(bars), int(p * len(bars)))
        for i in range(r.get('_shown', 0), upto):
            cv.itemconfigure(bars[i], fill=c['accent'])
        r['_shown'] = max(r.get('_shown', 0), upto)
        if r.get('_ph') and bars:
            a, b = cv.coords(bars[0]), cv.coords(bars[-1])
            co = cv.coords(r['_ph'])
            if a and b and co:
                px = a[0] + p * (b[2] - a[0])
                cv.coords(r['_ph'], px, co[1], px, co[3])
        if r.get('_eq'):
            audio = r['audio']
            i0 = int(p * len(audio))
            seg = audio[i0:i0 + 2048, 0]
            if len(seg) >= 256:
                spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
                vals = r.setdefault('_eqv', [0.0] * (len(EQ_BANDS) - 1))
                mx = r.setdefault('_eqmax', [1e-6] * (len(EQ_BANDS) - 1))
                for j, (lo, hi_) in enumerate(zip(EQ_BANDS, EQ_BANDS[1:])):
                    e = float(spec[lo:hi_].mean()) if hi_ <= len(spec) else 0.0
                    mx[j] = max(mx[j] * .995, e)
                    vals[j] = vals[j] * .55 + .45 * math.sqrt(e / mx[j])
                    co = cv.coords(r['_eq'][j])
                    if co:
                        cv.coords(r['_eq'][j], co[0], co[3] - k * (3 + 22 * vals[j]), co[2], co[3])
        if r.get('_card'):
            cv.itemconfigure(r['_card'], outline=blend(c['card_border'], c['accent'], .45 + .35 * math.sin(now * 4)))
        return True

    def _scroll_step(self, dt, now):
        d = self._scroll_target - self.scroll
        step = d if abs(d) < .5 else d * min(1.0, dt * 12)
        self.cv.move('msg', 0, -step)
        self.scroll += step
        return abs(d) >= .5

    def _on_wheel(self, e):
        if self.msgs:
            top, bottom = self.area
            mx = max(0, self.content_h - (bottom - top))
            self._scroll_target = clamp(self._scroll_target - e.delta / 120 * 90 * self.k, 0, mx)
            self.stick = self._scroll_target >= mx - 2
            self.anim.loop('scroll', self._scroll_step)
        return 'break'

    # ── ввод и запросы ──
    def _show_ph(self):
        """Подсказка в пустом поле — правее мигающего курсора, иначе она его закрывает."""
        self.ph.place(x=int(self.entry.cget('insertwidth')) + round(3 * self.k), y=0)

    def _entry_changed(self):
        if self._text():
            self.ph.place_forget()
        else:
            self._show_ph()
        if self._count_lines(self._text_w) != self._lines:
            self.relayout()
        else:
            self._update_send()

    def _on_return(self, e):
        if e.state & 0x1:  # Shift+Enter — новая строка
            return None
        self.send()
        return 'break'

    def _on_option(self):
        self.prefs['chat_model'] = self.v_model.get()
        self.prefs['chat_autoplay'] = self.v_autoplay.get()
        save_prefs(self.prefs)
        self._schedule()

    def _opts(self):
        v = self.v_vowel.get()
        return dict(model=self.v_model.get(), dur=self.v_dur.get(), voc=self.v_voc.get(), genre=self.v_genre.get(),
                    vowel=None if v == 'auto' else v)

    def send(self, text=None):
        if self.busy:
            return self._toast(T('Модель ещё сочиняет предыдущий запрос…'), ok=False)
        text = (self._text() if text is None else text).strip()
        if not text:
            return
        self.entry.delete('1.0', 'end')
        self._show_ph()
        self.msgs.append(dict(role='user', text=text))
        self._run(text, self._opts())
        self._ripple()

    def _run(self, text, opts, again=False):
        """Сочинение идёт в фоновом потоке — окно остаётся живым и анимированным."""
        bot = dict(role='bot', model=opts['model'], status=T('Думаю над запросом'), results=[], prompt=text,
                   opts=opts, again=again)
        self.msgs.append(bot)
        self.busy, self.stick = True, True
        self.dust.target = 1.0
        self.relayout()
        self.anim.loop('think', self._think_step)
        seed = random.randrange(1, 999999)
        def render(*a, **kw):  # синтез звука — в отдельном процессе, окно не подтормаживает
            return run_in_process(render_song, *a, **kw)
        self.tasks.submit(lambda report: ai_respond(text, opts, seed, lambda s: report(None, s), render),
                          done=lambda res: self._done(bot, res),
                          error=lambda ex: self._done(bot, None, f'{type(ex).__name__}: {ex}'),
                          progress=lambda _f, s: self._set_status(bot, s))

    def _set_status(self, bot, s):
        if bot.get('status') and bot['status'] != s:
            bot['status'] = s
            self.relayout_msgs()

    def _done(self, bot, res, err=None):
        self.busy = False
        self.dust.target = 0.0
        bot['status'] = None
        bot.pop('_think', None)
        if err:
            bot['head'] = T('Не получилось сочинить.')
            bot['text'] = T('Ошибка: {0}\nПопробуйте переформулировать запрос.').format(err)
        else:
            bot.update(model=res['model'], text=res['text'], results=res['results'],
                       head=res['head'].replace(T('Готово!'), T('Ещё вариант!')) if bot['again'] else res['head'])
            bot['_autoplay'] = bool(self.v_autoplay.get() and res['results'])
        bot['_typing'] = 0.0
        self.stick = True
        self.relayout_msgs()
        self._update_send()
        self.anim.loop('type', self._type_step)

    def again(self, m, r):
        if r['kind'] == 'sfx':  # звук перегенерируем на месте — это мгновенно
            r['seed'] = random.randrange(1, 999999)
            P, audio = ai_sfx_sound(r['sfx'], r['mods'], r['seed'], r['chip'])
            r['variant'] += 1
            r.update(audio=audio, peaks=_ai_peaks(audio), sub=_ai_sfx_desc(P, audio),
                     title=T('{0} · вариант {1}').format(T(AI_SFX[r["sfx"]][0]), r["variant"]))
            r['_grown'] = False
            self.player.stop()
            self.playing = None
            self.play_result(r)
        elif not self.busy:
            self._run(m['prompt'], m['opts'], again=True)

    def new_chat(self):
        self.stop_playback()
        self.msgs.clear()
        self.scroll = self._scroll_target = 0.0
        self.stick, self._intro = True, True
        self.relayout()
        self.entry.focus_set()

    def show_models(self):
        lines = [f'{info["icon"]}  {info["name"]} — {T(info["desc"])}' for info in AI_MODELS.values()]
        lines += ['', T('Пишите свободно: жанр или место (замок, космос, гонки), настроение (грустно, эпично), темп '
                      '(быстро, 140 bpm), длительность (30 секунд, 2 минуты), инструменты (флейта, гитара, '
                      'колокольчики), «с вокалом», «без барабанов», «ля минор», «Sega» или «Dendy».'),
                  T('Для звуков: «прыжок», «лазер с эхом», «низкая монетка», «набор звуков для шутера».')]
        self.msgs.append(dict(role='bot', model='auto', head=T('Модели Forge и что им можно писать'),
                              text='\n'.join(lines), results=[], _typing=0.0))
        self.stick = True
        self.relayout()
        self.anim.loop('type', self._type_step)

    # ── воспроизведение и файлы ──
    def play_result(self, r):
        if self.playing and self.playing[0] is r:
            return self.stop_playback()
        if self.shell.app:
            self.shell.app.stop()
        try:
            self.player.play(r['audio'], r['sr'])
        except Exception as ex:  # noqa
            return messagebox.showerror(APP_NAME, T('Не удалось воспроизвести звук:\n{0}').format(ex), parent=self.win)
        self.playing = (r, time.perf_counter(), len(r['audio']) / r['sr'])
        self.relayout_msgs()
        self.anim.loop('play', self._play_step)

    def stop_playback(self):
        self.player.stop()
        if self.playing:
            self.playing = None
            self.relayout_msgs()

    def save_result(self, r, ext):
        """Кодирование MP3 / запись WAV — в фоне: окно не зависает, по готовности всплывает уведомление."""
        if ext == '.mp3' and not find_ffmpeg():
            return messagebox.showinfo(APP_NAME, T(FFMPEG_HELP), parent=self.win)
        name = re.sub(r'[^\w\- ]+', '', r['title']).strip().replace(' ', '_') or 'forge'
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=ext, initialfile=name,
                                            filetypes=[(ext[1:].upper(), '*' + ext)],
                                            initialdir=self.prefs.get('dir') or os.path.expanduser('~'))
        if not path:
            return
        self.prefs['dir'] = os.path.dirname(path)
        save_prefs(self.prefs)
        audio, sr, kind, title = r['audio'], r['sr'], r['kind'], r['title']

        def work(_report):
            if ext == '.mp3':
                export_mp3(path, audio, sr, 256 if kind == 'song' else 192, title)
            else:
                write_wav(path, audio, sr)
            return path
        self._toast(T('⬇  Сохраняю {0}…').format(ext[1:].upper()), ttl=60)
        self.tasks.submit(work, done=lambda p: self._toast(T('✓  Сохранено: {0}').format(os.path.basename(p))),
                          error=lambda ex: (self._toast(T('Не удалось сохранить'), ok=False),
                                            messagebox.showerror(APP_NAME, T('Не удалось сохранить:\n{0}').format(ex),
                                                                 parent=self.win)))

    def to_editor(self, r):
        self.stop_playback()
        self.shell.open_manual(copy.deepcopy(r['song']), r['title'])

    # ── меню ──
    def _open_popover(self, key, sections, align='left', min_w=220):
        """Открыть карточку-меню у кнопки key; повторный клик по той же кнопке её закрывает."""
        last = self._pop_closed
        if self._popover:
            same = self._popover.key == key
            self._popover.close()
            if same:
                return
        elif last and last[0] == key and time.perf_counter() - last[1] < .3:
            return  # клик по кнопке уже закрыл это меню (фокус ушёл) — не открываем снова
        x0, y0, x1, y1 = self._anchors[key]
        rx, ry = self.cv.winfo_rootx(), self.cv.winfo_rooty()
        self._popover = Popover(self, key, (rx + x0, ry + y0, rx + x1, ry + y1), sections, up=self._pop_up,
                                align=align, min_w=min_w)

    @staticmethod
    def _choice(var, value, label, icon, desc='', after=None):
        def cmd():
            var.set(value)
            if after:
                after()
        return dict(label=label, icon=icon, desc=desc, checked=var.get() == value, cmd=cmd)

    def _menu_model(self):
        items = [self._choice(self.v_model, key, info['name'], info['icon'], T(info['desc']))
                 for key, info in AI_MODELS.items()]
        self._open_popover('model', [dict(title=T('Модель Forge'), items=items)], align='right', min_w=300)

    def _menu_option(self, which):
        V = self._choice
        if which == 'dur':
            items = [V(self.v_dur, AI_ANY, T(AI_ANY), '✦', T('модель поймёт из текста'))]
            secs = [dict(title=T('Длительность'), items=items),
                    dict(cols=2, items=[V(self.v_dur, k_, T(k_), '◷') for k_ in AI_DURATIONS if k_ != AI_ANY])]
        elif which == 'voc':
            def pick_vowel():
                if self.v_vowel.get() != 'auto' and self.v_voc.get() != 'С вокалом':
                    self.v_voc.set('С вокалом')
            secs = [dict(title=T('Вокал'), items=[
                        V(self.v_voc, AI_ANY, T(AI_ANY), '✦', T('по словам «с вокалом», «хор», «без голоса»')),
                        V(self.v_voc, 'С вокалом', T('С вокалом'), '♪', T('голос поёт тему припева')),
                        V(self.v_voc, 'Без вокала', T('Без вокала'), '⊘', T('только инструменты'))]),
                    dict(title=T('Тембр голоса'), cols=2, items=[V(self.v_vowel, 'auto', T('Авто — по настроению'), '✦')] +
                         [V(self.v_vowel, k_, T(name), '◉', after=pick_vowel) for k_, name in VOWEL_NAMES.items()])]
        else:
            secs = [dict(title=T('Жанр'), items=[V(self.v_genre, AI_ANY, T(AI_ANY), '✦', T('модель подберёт по описанию'))]),
                    dict(cols=3, items=[V(self.v_genre, g, T(g), GENRE_ICONS.get(g, '♫')) for g in AI_GENRES])]
        self._open_popover(which, secs)

    def _menu_plus(self):
        examples = [dict(label=T(text), icon=icon, cmd=lambda t=T(text): self.send(t)) for icon, text in CHAT_EXAMPLES]
        secs = [dict(title=T('Примеры запросов'), items=examples),
                dict(items=[dict(label=T('Что умеют модели?'), icon='ℹ', cmd=self.show_models),
                            dict(label=T('Сразу проигрывать результат'), icon='▶', checked=self.v_autoplay.get(),
                                 desc=T('сейчас: ') + (T('включено') if self.v_autoplay.get() else T('выключено')),
                                 cmd=lambda: self.v_autoplay.set(not self.v_autoplay.get())),
                            dict(label=T('Новый чат'), icon='+', cmd=self.new_chat)]),
                dict(title=T('Язык / Language'), cols=2, items=[
                    dict(label=name, icon='◉', checked=code == i18n.LANG,
                         cmd=lambda c=code: self.win.after_idle(lambda: self.shell.set_language(c)))
                    for code, name in LANGUAGES.items()])]
        self._open_popover('plus', secs, min_w=300)
