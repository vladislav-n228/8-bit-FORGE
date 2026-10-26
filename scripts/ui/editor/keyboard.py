# -*- coding: utf-8 -*-
"""Горячие клавиши."""

import sys
import tkinter as tk
from tkinter import ttk

from scripts.core.i18n import T
from scripts.core.theory import clamp


class KeyboardMixin:
    """Горячие клавиши."""

    def _bind_keys(self):
        self.root.bind('<KeyPress>', self._on_key)

    def _letter(self, e):
        if sys.platform == 'win32' and 65 <= e.keycode <= 90:
            return chr(e.keycode).lower()
        return e.keysym.lower() if len(e.keysym) == 1 else ''

    def _on_key(self, e):
        w = self.root.focus_get()
        typing = isinstance(w, (tk.Entry, ttk.Entry, tk.Text, tk.Listbox))
        ctrl, shift = bool(e.state & 0x4), bool(e.state & 0x1)
        ch, ks = self._letter(e), e.keysym
        if ctrl:
            if typing and ch in ('c', 'v', 'a', 'x', 'z', 'y'):
                return
            act = {'z': self.redo if shift else self.undo, 'y': self.redo, 's': self.save_project,
                   'o': self.open_project, 'e': self.export_wav, 'g': self.generate, 'c': self.op_copy,
                   'v': self.op_paste, 'd': self.op_duplicate, 'a': self.op_select_all,
                   'k': self.open_companion}.get(ch)
            if act:
                act()
                return 'break'
            return
        if typing:
            return
        if ks == 'space':
            self.toggle_play()
        elif ks in ('Delete', 'BackSpace'):
            self.op_clear()
        elif ks == 'Escape':
            self.clear_selection()
        elif ks == 'Home':
            self.to_start()
        elif ks in ('Up', 'Down'):
            self.op_transpose((12 if shift else 1) * (1 if ks == 'Up' else -1))
        elif ks in ('Left', 'Right'):
            d = self.snap * (1 if ks == 'Right' else -1)
            if self.mode == 'edit' and self.sel_notes:
                self.move_notes(d)
            else:
                self.cursor = int(clamp(self.cursor + d, 0, self.song.total_steps - 1))
                self._place_cursor()
        elif ks in ('plus', 'equal', 'KP_Add'):
            self.zoom(1.25)
        elif ks in ('minus', 'KP_Subtract'):
            self.zoom(0.8)
        elif ks in ('1', '2', '3', '4', '5', '6'):
            self.select_track(int(ks) - 1)
        elif ch == 'r':
            self.recreate_selection()
        elif ch == 'e':
            self.set_mode('edit' if self.mode == 'arrange' else 'arrange')
        elif ch == 'd':
            self.v_tool.set('draw')
        elif ch == 's':
            self.v_tool.set('select')
        elif ch == 'x':
            self.v_tool.set('erase')
        elif ch == 'l':
            self.v_loop.set(not self.v_loop.get())
            self.set_status(T('Петля ') + (T('включена') if self.v_loop.get() else T('выключена')))
        elif ch == 'f':
            self.zoom_fit()
        elif ch == 'm':
            self.tv_mute.set(not self.cur_track().mute)
            self._on_track_param('mute')
            self.load_track_panel()
        else:
            return
        return 'break'
