# -*- coding: utf-8 -*-
"""Connects the windows: start screen, chat studio and manual editor."""

import tkinter as tk
from tkinter import messagebox

from scripts.core.constants import APP_NAME
from scripts.core import i18n
from scripts.core.i18n import LANGUAGES, T
from scripts.core.prefs import load_prefs, save_prefs
from scripts.core.tasks import stop_processes, warm_up_processes
from scripts.ui.chat_studio import ChatStudio
from scripts.ui.editor.app import App
from scripts.ui.graphics import set_app_icon
from scripts.ui.launcher import Launcher


class Shell:
    """Connects the windows: start screen, chat studio and manual editor."""

    def __init__(self, root):
        self.root = root
        self.prefs = load_prefs()
        self.k = max(1.0, root.winfo_fpixels('1i') / 96.0)
        self.app = self.chat = None
        root.protocol('WM_DELETE_WINDOW', self.quit)
        set_app_icon(root)  # True inside — the icon is also given to all future windows
        self.launcher = Launcher(root, self)
        warm_up_processes()  # render processes start in advance while the user picks a mode

    def center(self, win, w, h):
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = min(int(w * self.k), sw - 40), min(int(h * self.k), sh - 80)
        win.geometry(f'{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}')

    def stop_all(self):
        if self.app:
            self.app.stop()
        if self.chat:
            self.chat.stop_playback()

    def _show(self, win):
        for w in (self.root, self.app and self.app.root, self.chat and self.chat.win):
            if w is not None and w is not win:
                w.withdraw()
        win.deiconify()
        win.lift()
        win.focus_force()

    def show_launcher(self):
        self.stop_all()
        self._show(self.root)
        self.launcher.draw()

    def open_chat(self):
        self.stop_all()
        if self.chat is None:
            self.chat = ChatStudio(tk.Toplevel(self.root), self)
        else:
            self.chat.apply_theme()
        self._show(self.chat.win)
        self.chat.entry.focus_set()

    def open_manual(self, song=None, label=None):
        self.stop_all()
        if self.app is None:
            self.app = App(tk.Toplevel(self.root), song=song, shell=self)
        elif song is not None:
            self.app.load_external_song(song, label)
        self._show(self.app.root)

    def import_track(self):
        """From the start screen: open the editor and immediately pick a file to import."""
        self.open_manual()
        self.app.root.after(50, self.app.import_track)

    def set_theme(self, name):
        self.prefs['theme'] = name
        save_prefs(self.prefs)
        if self.app:
            self.app.set_theme(name)

    def set_language(self, lang):
        """Switches the language on the fly: the windows are rebuilt, the song, history, cache and settings are carried over."""
        if lang == i18n.LANG or lang not in LANGUAGES:
            return False
        if sum(x.tasks.active for x in (self.app, self.chat) if x):
            messagebox.showinfo(APP_NAME, T('Дождитесь окончания экспорта или сочинения — потом смените язык.'))
            return False
        self.stop_all()
        i18n.set_lang(lang)
        self.prefs['lang'] = lang
        save_prefs(self.prefs)
        shown = next((name for name, w in (('app', self.app and self.app.root), ('chat', self.chat and self.chat.win))
                      if w is not None and w.winfo_viewable()), 'launcher')
        if self.app:
            app, self.app = self.app, None
            state, geo = app.export_state(), app.root.geometry()
            zoomed = app.root.state() == 'zoomed'
            app.dispose()
            self.app = App(tk.Toplevel(self.root), shell=self, state=state)
            self.app.root.geometry(geo)
            if zoomed:
                self.app.root.state('zoomed')
            if shown != 'app':
                self.app.root.withdraw()
        if self.chat:
            chat, self.chat = self.chat, None
            state, geo = chat.export_state(), chat.win.geometry()
            chat.dispose()
            self.chat = ChatStudio(tk.Toplevel(self.root), self, state=state)
            self.chat.win.geometry(geo)
            if shown != 'chat':
                self.chat.win.withdraw()
        self.launcher.retitle()
        if shown == 'launcher':
            self.launcher.draw()
        return True

    def quit(self):
        busy = sum(x.tasks.active for x in (self.app, self.chat) if x)
        if busy and not messagebox.askyesno(APP_NAME, T('Ещё идёт экспорт или сочинение в фоне.\n'
                                                      'Закрыть программу и прервать его?')):
            return
        for x in (self.app, self.chat):
            if x:
                try:
                    x.player.cleanup()
                except Exception:  # noqa
                    pass
        save_prefs(self.prefs)
        stop_processes()
        self.root.destroy()
