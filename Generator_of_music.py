#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8-BIT FORGE — a free 8/16-bit music generator in the spirit of the Dendy (NES) and Sega Mega Drive.

Run:       python Generator_of_music.py
Requires:  Python 3.9+, numpy (pip install numpy). tkinter ships with standard Python.

Features:
  • start screen: "Chat prompt" or "Manual creation";
  • chat studio: a request in words → Forge models (Melody, Ambient, Action, Jingle, SFX) compose a track
    with form, harmony and motif development, a jingle or a sound effect; choice of duration, vocals, genre;
  • track generation by style, key, scale, tempo, density, complexity, etc.;
  • 5 channels: lead, harmony, bass, arpeggio, drums;
  • select a region by dragging with the left mouse button + "♻ Recreate another piece" — regenerates the piece,
    the old piece goes to the cache and can be restored; ◀ Back / Forward ▶ (undo / redo);
  • editor mode (piano roll): draw, move, stretch and delete notes;
  • sound of each track: waveform, duty cycle, PWM, ADSR, vibrato, FM, detune, echo, presets;
  • master: bitcrush, sample-rate reduction, smoothing, NES-style 4-bit volume;
  • export WAV (whole track / selection / stems), MIDI, save and load projects;
  • dark (default) and light themes, several accent colors.

The code is split into modules in the scripts/ folder next to this file.
"""

import multiprocessing
import tkinter as tk
from tkinter import messagebox

def main():
    multiprocessing.freeze_support()  # sound is rendered in separate processes — also needed for the .exe build
    try:
        import numpy  # noqa: F401
    except ImportError:  # pragma: no cover
        from scripts.core.i18n import T
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showerror('8-BIT FORGE', T('Нужна библиотека numpy.\n\nУстановите:  pip install numpy'))
        raise SystemExit(1)
    # the UI is imported here rather than at the top: render processes re-read this file,
    # and they don't need to drag the windows along
    from scripts.ui.shell import Shell
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa
        pass
    root = tk.Tk()
    Shell(root)
    root.mainloop()


if __name__ == '__main__':
    main()
