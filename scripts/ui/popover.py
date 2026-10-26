# -*- coding: utf-8 -*-
"""Всплывающие меню чат-студии: скруглённая карточка с мягкой тенью, заголовки разделов,
пункты с иконками, описаниями и галочкой, плавная подсветка, появление с затуханием и сдвигом.
Управление мышью и клавиатурой (↑ ↓ Enter Esc), закрывается кликом мимо."""

import time
import tkinter as tk

from scripts.core.theory import blend
from scripts.ui.anim import ease_out
from scripts.ui.graphics import round_rect

KEY = '#010203'  # «прозрачный» цвет окна: всё, что им залито, не видно — так получаются скруглённые углы


class Popover:
    """sections: [dict(title=None|str, cols=1, items=[dict(label, icon='', desc='', checked=False, cmd)])]."""

    def __init__(self, chat, key, anchor, sections, up=True, align='left', min_w=220):
        self.chat, self.key, self.k = chat, key, chat.k
        self.closing = False
        c, k = chat.c, chat.k
        self.c = c
        win = self.win = tk.Toplevel(chat.win)
        win.overrideredirect(True)  # без transient(): на Windows окно без рамки с ним просто не рисуется
        win.configure(bg=KEY)
        for attr, val in (('-transparentcolor', KEY), ('-alpha', 0.0)):
            try:
                win.attributes(attr, val)
            except tk.TclError:
                pass
        cv = self.cv = tk.Canvas(win, bg=KEY, highlightthickness=0, bd=0)
        cv.pack(fill='both', expand=True)
        self.rows = []  # (x0, y0, x1, y1, пункт, id подсветки, базовый цвет)
        self.card = blend(c['pill'], c['fg'], .03) if chat.theme == 'dark' else c['pill']
        W, H = self._layout(sections, min_w)
        # положение: над / под якорем, по левому или правому краю
        ax0, ay0, ax1, ay1 = anchor
        m, gap = self.m, k * 8
        rx, ry = chat.win.winfo_rootx(), chat.win.winfo_rooty()
        room_up, room_down = ay0 - ry, ry + chat.win.winfo_height() - ay1
        need = H - 2 * m + gap
        if up and room_up < need and room_down > room_up:  # не влезает — открываем в другую сторону
            up = False
        elif not up and room_down < need and room_up > room_down:
            up = True
        x = ax0 - m if align == 'left' else ax1 - W + m
        y = ay0 - H + m - gap if up else ay1 - m + gap
        x = max(rx - m, min(x, rx + chat.win.winfo_width() - W + m))
        y = max(ry - m, min(y, ry + chat.win.winfo_height() - H + m))
        self.x, self.y = int(x), int(y)
        self._draw(W, H)
        win.geometry(f'{W}x{H}+{self.x}+{self.y + int(k * (10 if up else -10))}')
        cv.bind('<Motion>', self._on_motion)
        cv.bind('<Leave>', lambda e: self._set_hover(None))
        cv.bind('<Button-1>', self._on_click)
        for seq, fn in (('<Escape>', lambda e: self.close()), ('<Up>', lambda e: self._step(-1)),
                        ('<Down>', lambda e: self._step(1)), ('<Return>', lambda e: self._activate(self.hover)),
                        ('<FocusOut>', lambda e: self.win.after(10, self._check_focus))):
            win.bind(seq, fn)
        self.hover = None
        win.update_idletasks()
        win.lift()
        win.focus_force()
        dy = k * (10 if up else -10)
        chat.anim.tween(('pop', id(self)), .18, lambda t: self._place(t, dy))

    # ── раскладка ──
    def _layout(self, sections, min_w):
        k, F = self.k, self.chat.F
        self.m, self.p = k * 10, k * 8  # поле под тень и внутренний отступ
        self.secs = []
        content_w, h = min_w * k, 0
        for si, sec in enumerate(sections):
            cols = max(1, sec.get('cols', 1))
            items = sec['items']
            iw = 0
            for it in items:
                tw = max(F('msg').measure(it['label']), F('small').measure(it.get('desc', '')))
                iw = max(iw, k * 12 + k * 26 + tw + k * 14 + k * 22 + k * 10)
            ih = k * (52 if any(it.get('desc') for it in items) else 38)
            nrows = -(-len(items) // cols)
            th = k * 28 if sec.get('title') else 0
            sep = k * 9 if si else 0
            self.secs.append(dict(sec=sec, cols=cols, iw=iw, ih=ih, nrows=nrows, th=th, sep=sep))
            content_w = max(content_w, iw * cols)
            h += sep + th + nrows * ih
        self.content_w = content_w
        return int(content_w + 2 * (self.m + self.p)), int(h + 2 * (self.m + self.p))

    def _draw(self, W, H):
        cv, c, k, m = self.cv, self.c, self.k, self.m
        chat = self.chat
        under = chat._bg_at(self.x - chat.win.winfo_rootx() + W / 2, self.y - chat.win.winfo_rooty() + H / 2)
        shade = '#000000' if chat.theme == 'dark' else '#8090a8'
        r = k * 16
        for grow, a in ((k * 6, .10), (k * 4, .18), (k * 2, .28)):  # мягкая тень в несколько слоёв
            round_rect(cv, m - grow, m - grow + k * 3, W - m + grow, H - m + grow + k * 3, r + grow,
                       fill=blend(under, shade, a), outline='')
        round_rect(cv, m, m, W - m, H - m, r, fill=self.card, outline=c['pill_border'])
        y, x0 = m + self.p, m + self.p
        for s in self.secs:
            if s['sep']:
                cv.create_line(x0 + k * 10, y + s['sep'] / 2, x0 + self.content_w - k * 10, y + s['sep'] / 2,
                               fill=c['pill_border'])
                y += s['sep']
            if s['th']:
                cv.create_text(x0 + k * 12, y + s['th'] / 2 + k * 2, text=s['sec']['title'], anchor='w',
                               font=self.chat.F('small_b'), fill=c['muted'])
                y += s['th']
            iw = self.content_w / s['cols']
            for i, it in enumerate(s['sec']['items']):
                col, row = divmod(i, s['nrows'])
                ix, iy = x0 + col * iw, y + row * s['ih']
                self._draw_item(it, ix, iy, iw, s['ih'])
            y += s['nrows'] * s['ih']

    def _draw_item(self, it, x, y, w, h):
        cv, c, k, F = self.cv, self.c, self.k, self.chat.F
        on = it.get('checked')
        base = blend(self.card, c['accent'], .14) if on else self.card
        hl = round_rect(cv, x + k * 2, y + k * 2, x + w - k * 2, y + h - k * 2, k * 10, fill=base, outline='')
        cy = y + h / 2
        cv.create_text(x + k * 25, cy, text=it.get('icon', ''), font=F('icon'),
                       fill=c['accent_text'] if on else c['muted'])
        tx = x + k * 44
        if it.get('desc'):
            cv.create_text(tx, cy - k * 9, text=it['label'], font=F('msg_b' if on else 'msg'), fill=c['fg'],
                           anchor='w')
            cv.create_text(tx, cy + k * 10, text=it['desc'], font=F('small'), fill=c['muted'], anchor='w')
        else:
            cv.create_text(tx, cy, text=it['label'], font=F('msg_b' if on else 'msg'), fill=c['fg'], anchor='w')
        if on:
            cv.create_text(x + w - k * 20, cy, text='✓', font=F('msg_b'), fill=c['accent_text'])
        self.rows.append((x, y, x + w, y + h, it, hl, base))

    # ── поведение ──
    def _place(self, t, dy):
        if self.closing or not self.win.winfo_exists():
            return
        try:
            self.win.attributes('-alpha', min(1.0, t))
        except tk.TclError:
            pass
        self.win.geometry(f'+{self.x}+{int(self.y + dy * (1 - ease_out(min(1.0, t))))}')

    def _row_at(self, x, y):
        return next((i for i, r in enumerate(self.rows) if r[0] <= x <= r[2] and r[1] <= y <= r[3]), None)

    def _on_motion(self, e):
        self._set_hover(self._row_at(e.x, e.y))

    def _set_hover(self, i):
        if i == self.hover:
            return
        for j, on in ((self.hover, False), (i, True)):
            if j is None:
                continue
            _, _, _, _, _, hl, base = self.rows[j]
            a, b = (base, self.c['btn_hover']) if on else (self.c['btn_hover'], base)
            self.chat.anim.tween(('pophl', id(self), j), .12, lambda t, hl=hl, a=a, b=b: self.cv.itemconfigure(
                hl, fill=blend(a, b, t)))
        self.hover = i
        self.cv.configure(cursor='hand2' if i is not None else '')

    def _step(self, d):
        n = len(self.rows)
        if n:
            self._set_hover((0 if d > 0 else n - 1) if self.hover is None else (self.hover + d) % n)

    def _on_click(self, e):
        i = self._row_at(e.x, e.y)
        if i is not None:
            self._activate(i)

    def _activate(self, i):
        if i is None or self.closing:
            return
        it = self.rows[i][4]
        self.close()
        if it.get('cmd'):
            self.chat.win.after_idle(it['cmd'])

    def _check_focus(self):
        try:
            f = self.win.focus_get()
        except (tk.TclError, KeyError):
            f = None
        if f is None or not str(f).startswith(str(self.win)):
            self.close()

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.chat._pop_closed = (self.key, time.perf_counter())
        if self.chat._popover is self:
            self.chat._popover = None
        win = self.win

        def fade(t):
            if win.winfo_exists():
                win.attributes('-alpha', max(0.0, 1 - t))

        def done():
            if win.winfo_exists():
                win.destroy()
        self.chat.anim.tween(('popout', id(self)), .12, fade, done=done)
