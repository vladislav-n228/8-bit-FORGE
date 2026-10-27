# -*- coding: utf-8 -*-
"""Shared widgets."""

import tkinter as tk
from tkinter import ttk

from scripts.core.i18n import T


def translate_combo(cb, var, values, on_select=None):
    """The list shows the translation, while var holds the internal value (the one that goes into the project and settings)."""
    labels = [T(v) for v in values]
    back = dict(zip(labels, values))
    shown = tk.StringVar(cb)

    def sync(*_):
        try:
            shown.set(T(var.get()))
        except tk.TclError:
            pass
    var.trace_add('write', sync)
    sync()
    cb.configure(textvariable=shown, values=labels)

    def picked(_e):
        var.set(back.get(shown.get(), shown.get()))
        if on_select:
            on_select()
    cb.bind('<<ComboboxSelected>>', picked)
    return cb


class ScrollFrame(ttk.Frame):
    def __init__(self, master, width=None):
        super().__init__(master, style='Bg.TFrame')
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, width=width or 10)
        self.vsb = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style='Bg.TFrame')
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.vsb.pack(side='right', fill='y')

    def scroll(self, units):
        first, last = self.canvas.yview()
        if first <= 0 and last >= 1:
            return
        self.canvas.yview_scroll(units, 'units')
