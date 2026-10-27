# -*- coding: utf-8 -*-
"""Main window of manual mode: variables, theme, building the interface."""

import os
import queue
import random
import tkinter as tk
from tkinter import ttk, messagebox

from scripts.audio.loudness import LOUDNESS_TARGETS
from scripts.audio.player import Player
from scripts.core.constants import (
    APP_NAME, ARP_PATTERNS, ARP_RATES, BAR_CHOICES, BASS_PATTERNS, CHIPS, CHORD_RATES, DUTY_NAMES, HARMONY_MODES,
    KITS, NOTE_NAMES, RECREATE_MODES, SCALES, SOUND_PRESETS, STYLES, TRACK_DEFS, VOWEL_NAMES, WAVE_NAMES)
from scripts.core import i18n
from scripts.core.i18n import LANGUAGES, T
from scripts.core.prefs import load_prefs, save_prefs
from scripts.core.tasks import TaskRunner
from scripts.core.theory import blend
from scripts.music.structure import PLATFORM_PRESETS
from scripts.ui.editor.canvas import CanvasMixin
from scripts.ui.editor.companion import CompanionMixin
from scripts.ui.editor.editing import EditingMixin
from scripts.ui.editor.files import FilesMixin
from scripts.ui.editor.generation import GenerationMixin
from scripts.ui.editor.history import HistoryMixin
from scripts.ui.editor.keyboard import KeyboardMixin
from scripts.ui.editor.media import MediaMixin
from scripts.ui.editor.mouse import MouseMixin
from scripts.ui.editor.playback import PlaybackMixin
from scripts.ui.style import (
    ACCENTS, FONT, FONT_B, FONT_MONO, FONT_S, FONT_SB, FONT_TITLE, HEAD_W, pct, RULER_H, SNAPS, THEMES,
    TRACK_SLIDERS)
from scripts.ui.widgets import ScrollFrame, translate_combo


class App(CanvasMixin, MouseMixin, HistoryMixin, GenerationMixin, EditingMixin, PlaybackMixin, FilesMixin, CompanionMixin, MediaMixin, KeyboardMixin):
    """Manual mode: style generator, arrangement, piano roll, track sound, export.
    The methods are split into mixins in the neighbouring files of this folder."""

    def __init__(self, root, song=None, shell=None, state=None):
        self.root = root
        self.shell = shell
        self._disposed = False
        root.title(T('{0} — генератор 8-битной музыки').format(APP_NAME))
        root.geometry('1460x900')
        root.minsize(1120, 700)
        self.prefs = shell.prefs if shell else load_prefs()
        self.theme = self.prefs.get('theme', 'dark')
        self.accent = self.prefs.get('accent', 'Неоновый циан')
        if self.accent not in ACCENTS:
            self.accent = 'Неоновый циан'
        self.style = ttk.Style(root)
        self.c = self._palette()
        self.player = Player()
        self.song = None
        self.project_path = None
        self.undo_stack, self.redo_stack = [], []
        self._coalesce = (None, 0.0)
        self.cache, self.cache_seq = [], 0
        self.clipboard = None
        self.mode = 'arrange'
        self.sel_track = 0
        self.sel = None
        self.sel_notes = set()
        self.cursor = 0
        self.pps = 12.0
        self.drag = None
        self.playing = False
        self.pending = False
        self.pstate = {}
        self.play_step = 0.0
        self.play_active = None
        self.render_token = 0
        self.jobs = queue.Queue()
        self.tasks = TaskRunner(root)  # export and other heavy work — in background threads
        self._bg = {}
        self._bg_seq = 0
        self._loading = False
        self._refresh_job = None
        self._last_preview = (None, 0.0)
        self.scrollframes, self.tk_canvases, self.listboxes, self.menus, self.combos = [], [], [], [], []
        self.cb_tracks = []
        self._init_vars()
        self._build_ui()
        self.apply_theme()
        self._bind_keys()
        if state is not None:
            self.import_state(state)
        elif song is not None:
            self.load_external_song(song)
        else:
            self.generate(initial=True)
        if state is None:
            self.root.after(250, self.zoom_fit)
        self.root.after(33, self._tick)
        root.protocol('WM_DELETE_WINDOW', self.on_close)

    # ── variables ──
    def _init_vars(self):
        D, S, B = tk.DoubleVar, tk.StringVar, tk.BooleanVar
        first = next(iter(STYLES))
        st = STYLES[first]
        self.v_style = S(value=first)
        self.v_key = S(value='C')
        self.v_scale = S(value=st['scales'][0])
        self.v_bpm = D(value=140)
        self.v_bars = S(value='16')
        self.v_chord_rate = S(value=st['chords'])
        self.v_chip = S(value='Dendy (NES)')
        self.v_seed = S(value=str(random.randrange(1, 999999)))
        self.v_lock = B(value=False)
        self.v_density = D(value=st['density'])
        self.v_complexity = D(value=st['complexity'])
        self.v_repetition = D(value=st['repetition'])
        self.v_drums = D(value=st['drums'])
        self.v_swing = D(value=0.0)
        self.v_bass = S(value=st['bass'])
        self.v_arp = S(value=st['arp'])
        self.v_arp_rate = S(value=st['arp_rate'])
        self.v_harmony = S(value=st['harmony'])
        self.v_include = [B(value=kind != 'voice') for kind, _ in TRACK_DEFS]
        self.v_keep_sounds = B(value=False)
        self.v_recreate_mode = S(value=RECREATE_MODES[0])
        self.v_loop = B(value=False)
        self.v_follow = B(value=True)
        self.v_preview = B(value=True)
        self.v_ghost = B(value=True)
        self.v_show_scale = B(value=True)
        self.v_live = B(value=True)
        self.v_snap = S(value='1/4')
        self.v_note_len = S(value='1/8')
        self.v_tool = S(value='draw')
        self.v_mode = S(value='arrange')
        self.v_edit_track = S()
        self.v_mvol = D(value=.8)
        self.v_sr = S(value='44100')
        self.v_bits = S(value='16')
        self.v_down = D(value=1)
        self.v_smooth = D(value=0)
        self.v_nes_env = B(value=True)
        self.v_norm = B(value=True)
        self.v_loops = D(value=1)
        self.v_fade = B(value=False)
        self.v_wav8 = B(value=False)
        self.v_theme = S(value=self.theme)
        self.v_accent = S(value=self.accent)
        self.v_lang = S(value=i18n.LANG)
        self.v_lang_name = S(value=LANGUAGES[i18n.LANG])
        self.tv = {f: D(value=0) for f, *_ in TRACK_SLIDERS}
        self.tv_wave, self.tv_duty, self.tv_octave, self.tv_kit, self.tv_vowel = S(), S(), S(), S(), S()
        self.c_genre = S(value='Авто (по описанию)')
        self.c_duration = S(value='45 секунд')
        self.c_voice = B(value=False)
        self.c_voice_type = S(value=VOWEL_NAMES['а'])
        self.c_autoplay = B(value=True)
        self.c_exact = B(value=True)
        self.c_drop = S(value='0')
        self.v_platform = S(value='Своя длительность')
        self.v_exact = B(value=False)
        self.v_exact_sec = S(value='30')
        self.v_intro = B(value=False)
        self.v_outro = B(value=False)
        self.v_drop_sec = S(value='0')
        self.v_lufs = S(value='-14 LUFS — YouTube / Spotify')
        self.v_mp3_kbps = S(value='256')
        self.extra_windows = []
        self.comp_win = None
        self.comp_last = None
        self.comp_history = list(self.prefs.get('companion_history', []))[:15]
        self.tv_mute, self.tv_solo, self.tv_preset = B(), B(), S()
        self.v_bpm.trace_add('write', lambda *a: self._on_bpm())
        self.v_swing.trace_add('write', lambda *a: self._on_swing())

    # ── theme ──
    def _palette(self):
        c = dict(THEMES[self.theme])
        acc = ACCENTS.get(self.accent, '#00d9ff')
        c['accent'] = acc
        c['accent_text'] = acc if self.theme == 'dark' else blend(acc, '#000000', .4)
        c['accent_hover'] = blend(acc, '#ffffff', .25)
        c['accent_fg'] = '#0b0b12'
        return c

    def apply_theme(self):
        self.c = c = self._palette()
        st = self.style
        st.theme_use('clam')
        st.configure('.', background=c['panel'], foreground=c['fg'], fieldbackground=c['field'],
                     bordercolor=c['border'], lightcolor=c['panel'], darkcolor=c['panel'], troughcolor=c['panel2'],
                     focuscolor=c['panel'], selectbackground=c['accent'], selectforeground=c['accent_fg'],
                     insertcolor=c['fg'], font=FONT, arrowcolor=c['fg'])
        st.configure('TFrame', background=c['panel'])
        st.configure('Bg.TFrame', background=c['bg'])
        st.configure('TLabel', background=c['panel'], foreground=c['fg'])
        st.configure('Muted.TLabel', foreground=c['muted'])
        st.configure('Value.TLabel', foreground=c['accent_text'], font=FONT_SB)
        st.configure('Section.TLabel', foreground=c['accent_text'], font=('Segoe UI Semibold', 11))
        st.configure('Title.TLabel', foreground=c['accent_text'], font=FONT_TITLE)
        st.configure('Time.TLabel', foreground=c['fg'], font=FONT_MONO)
        st.configure('Status.TLabel', background=c['bg'], foreground=c['muted'], font=FONT_S)
        flat = dict(background=c['panel2'], foreground=c['fg'], bordercolor=c['border'], lightcolor=c['panel2'],
                    darkcolor=c['panel2'], padding=(9, 5), focusthickness=0)
        st.configure('TButton', **flat)
        st.map('TButton', background=[('disabled', c['panel']), ('pressed', c['accent']), ('active', c['hover'])],
               foreground=[('disabled', c['muted']), ('pressed', c['accent_fg'])],
               lightcolor=[('active', c['hover'])], darkcolor=[('active', c['hover'])])
        st.configure('Accent.TButton', background=c['accent'], foreground=c['accent_fg'], lightcolor=c['accent'],
                     darkcolor=c['accent'], bordercolor=c['accent'], font=('Segoe UI Semibold', 11), padding=(12, 7))
        st.map('Accent.TButton', background=[('pressed', c['accent_hover']), ('active', c['accent_hover'])],
               lightcolor=[('active', c['accent_hover'])], darkcolor=[('active', c['accent_hover'])],
               foreground=[('active', c['accent_fg']), ('pressed', c['accent_fg'])])
        st.configure('Small.TButton', padding=(6, 3), font=FONT_S)
        st.configure('Toolbutton', anchor='center', **flat)
        st.map('Toolbutton', background=[('selected', c['accent']), ('active', c['hover'])],
               foreground=[('selected', c['accent_fg'])], lightcolor=[('selected', c['accent'])],
               darkcolor=[('selected', c['accent'])])
        for cls in ('TCheckbutton', 'TRadiobutton'):
            st.configure(cls, background=c['panel'], foreground=c['fg'], indicatorbackground=c['field'],
                         indicatorforeground=c['accent_fg'], upperbordercolor=c['border'], lowerbordercolor=c['border'])
            st.map(cls, background=[('active', c['panel'])],
                   indicatorbackground=[('selected', c['accent']), ('active', c['hover'])])
        st.configure('TCombobox', fieldbackground=c['field'], background=c['panel2'], foreground=c['fg'],
                     arrowcolor=c['fg'], bordercolor=c['border'], lightcolor=c['field'], darkcolor=c['field'], padding=3)
        st.map('TCombobox', fieldbackground=[('readonly', c['field'])], foreground=[('readonly', c['fg'])],
               selectbackground=[('readonly', c['field'])], selectforeground=[('readonly', c['fg'])],
               background=[('active', c['hover'])], bordercolor=[('focus', c['accent'])])
        st.configure('TEntry', fieldbackground=c['field'], foreground=c['fg'], bordercolor=c['border'],
                     lightcolor=c['field'], darkcolor=c['field'], padding=3)
        st.configure('Horizontal.TScale', background=c['accent'], troughcolor=c['panel2'], bordercolor=c['panel'],
                     lightcolor=c['accent'], darkcolor=c['accent'])
        st.configure('TNotebook', background=c['bg'], bordercolor=c['bg'], lightcolor=c['bg'], darkcolor=c['bg'],
                     tabmargins=(0, 0, 0, 0))
        st.configure('TNotebook.Tab', background=c['panel2'], foreground=c['muted'], padding=(11, 6),
                     bordercolor=c['border'], lightcolor=c['panel2'])
        st.map('TNotebook.Tab', background=[('selected', c['panel'])], foreground=[('selected', c['accent_text'])],
               lightcolor=[('selected', c['panel'])])
        st.configure('TScrollbar', background=c['panel2'], troughcolor=c['bg'], bordercolor=c['bg'],
                     arrowcolor=c['muted'], lightcolor=c['panel2'], darkcolor=c['panel2'], gripcount=0)
        st.map('TScrollbar', background=[('active', c['hover'])])
        st.configure('TMenubutton', **flat)
        st.map('TMenubutton', background=[('active', c['hover'])])
        st.configure('TSeparator', background=c['border'])
        st.configure('Horizontal.TProgressbar', background=c['accent'], troughcolor=c['panel2'], bordercolor=c['border'],
                     lightcolor=c['accent'], darkcolor=c['accent'])
        self.extra_windows = [w for w in self.extra_windows if w.winfo_exists()]
        for w in self.extra_windows:
            w.configure(bg=c['panel'])
        self.root.configure(bg=c['bg'])
        lb_opts = dict(background=c['field'], foreground=c['fg'], selectbackground=c['accent'],
                       selectforeground=c['accent_fg'])
        for k, v in lb_opts.items():
            self.root.option_add(f'*TCombobox*Listbox.{k}', v)
        for cb in self.combos:
            try:
                pd = self.root.tk.call('ttk::combobox::PopdownWindow', str(cb))
                self.root.tk.call(f'{pd}.f.l', 'configure', '-background', c['field'], '-foreground', c['fg'],
                                  '-selectbackground', c['accent'], '-selectforeground', c['accent_fg'])
            except tk.TclError:
                pass
        for w, key in self.tk_canvases:
            w.configure(bg=c[key])
        self.scope.configure(highlightbackground=c['border'])
        self.scope.itemconfigure(self.scope_line, fill=c['accent'])
        for lb in self.listboxes:
            lb.configure(bg=c['field'], fg=c['fg'], selectbackground=c['accent'], selectforeground=c['accent_fg'],
                         highlightthickness=0, bd=0)
        for m in self.menus:
            m.configure(bg=c['panel'], fg=c['fg'], activebackground=c['accent'], activeforeground=c['accent_fg'],
                        bd=0)
        self.btn_theme.configure(text=T('☀  Светлая') if self.theme == 'dark' else T('☾  Тёмная'))
        if self.comp_win and self.comp_win.winfo_exists():
            self._theme_companion()
        if self.song:
            self.load_track_panel()
            self.redraw_all()

    def set_theme(self, name):
        self.theme = name
        self.v_theme.set(name)
        self.prefs['theme'] = name
        save_prefs(self.prefs)
        self.apply_theme()

    def toggle_theme(self):
        self.set_theme('light' if self.theme == 'dark' else 'dark')

    def set_accent(self):
        self.accent = self.v_accent.get()
        self.prefs['accent'] = self.accent
        save_prefs(self.prefs)
        self.apply_theme()

    def set_language(self, lang):
        if self.shell:
            if not self.shell.set_language(lang):  # not switched (an export is running) — put the choice back
                self.v_lang.set(i18n.LANG)
                self.v_lang_name.set(LANGUAGES[i18n.LANG])
            return
        self.prefs['lang'] = lang
        save_prefs(self.prefs)
        messagebox.showinfo(APP_NAME, T('Язык сменится при следующем запуске программы.'))

    # ── language change: the window is rebuilt, and the song, history, cache and settings are carried over ──
    _STATE_ATTRS = ('song', 'project_path', 'undo_stack', 'redo_stack', 'cache', 'cache_seq', 'clipboard',
                    'sel_track', 'cursor', 'pps', 'comp_last', 'comp_history')

    def export_state(self):
        st = {a: getattr(self, a) for a in self._STATE_ATTRS}
        st['vars'] = {k: v.get() for k, v in vars(self).items()
                      if isinstance(v, tk.Variable) and k not in ('v_lang', 'v_lang_name')}
        st['include'] = [v.get() for v in self.v_include]
        st['mode'] = self.mode
        return st

    def import_state(self, st):
        self._loading = True
        try:
            for k, val in st['vars'].items():
                var = getattr(self, k, None)
                if isinstance(var, tk.Variable):
                    var.set(val)
            for var, val in zip(self.v_include, st['include']):
                var.set(val)
        finally:
            self._loading = False
        for a in self._STATE_ATTRS:
            setattr(self, a, st[a])
        if self.project_path:
            self.root.title(f'{APP_NAME} — {os.path.basename(self.project_path)}')
        self.after_song_change()
        self.set_mode(st['mode'])

    def dispose(self):
        """Closes the window without quitting the app (on language change)."""
        self._disposed = True
        self.stop()
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
        try:
            self.player.cleanup()
        except Exception:  # noqa
            pass
        self.tasks.close()
        self.root.destroy()

    # ── widget helpers ──
    def _btn(self, parent, text, cmd, style='TButton', **kw):
        return ttk.Button(parent, text=text, command=cmd, style=style, takefocus=False, **kw)

    def _check(self, parent, text, var, cmd=None, style='TCheckbutton'):
        return ttk.Checkbutton(parent, text=text, variable=var, command=cmd, style=style, takefocus=False)

    def _combo(self, parent, label, var, values, cmd=None, width=18):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=label).pack(side='left')
        cb = ttk.Combobox(row, state='readonly', width=width, takefocus=False)
        cb.pack(side='right')
        translate_combo(cb, var, values, lambda: (cmd() if cmd else None, self.lanes.focus_set()))
        self.combos.append(cb)
        return cb

    def _slider(self, parent, label, var, lo, hi, fmt, on_change=None):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=(5, 0))
        ttk.Label(row, text=label).pack(side='left')
        val = ttk.Label(row, style='Value.TLabel')
        val.pack(side='right')
        sc = ttk.Scale(parent, from_=lo, to=hi, variable=var, orient='horizontal', takefocus=False)
        sc.pack(fill='x', pady=(1, 0))

        def upd(*_):
            try:
                val.configure(text=fmt(var.get()))
            except (tk.TclError, ValueError):
                pass
            if on_change:
                on_change()
        var.trace_add('write', upd)
        try:
            val.configure(text=fmt(var.get()))
        except (tk.TclError, ValueError):
            pass
        return sc

    def _section(self, parent, title, subtitle=None):
        f = ttk.Frame(parent, padding=(12, 10))
        f.pack(fill='x', pady=(0, 8))
        ttk.Label(f, text=title, style='Section.TLabel').pack(anchor='w')
        if subtitle:
            ttk.Label(f, text=subtitle, style='Muted.TLabel', font=FONT_S, wraplength=255,
                      justify='left').pack(anchor='w', pady=(0, 4))
        return f

    def _menu(self, parent):
        m = tk.Menu(parent, tearoff=0)
        self.menus.append(m)
        return m

    # ── building the window ──
    def _build_ui(self):
        self._build_menubar()
        self._build_topbar()
        status = ttk.Frame(self.root, style='Bg.TFrame', padding=(12, 2, 12, 6))
        status.pack(side='bottom', fill='x')
        self.lbl_status = ttk.Label(status, style='Status.TLabel', text=T('Готово'))
        self.lbl_status.pack(side='left')
        self.lbl_info = ttk.Label(status, style='Status.TLabel')
        self.lbl_info.pack(side='right')
        # background task indicator (export, etc.) — shown only while something is being computed
        self.bg_box = ttk.Frame(status, style='Bg.TFrame')
        self.lbl_bg = ttk.Label(self.bg_box, style='Status.TLabel')
        self.lbl_bg.pack(side='left', padx=(0, 6))
        self.bg_bar = ttk.Progressbar(self.bg_box, length=150, mode='determinate', maximum=1.0)
        self.bg_bar.pack(side='left')
        body = ttk.Frame(self.root, style='Bg.TFrame', padding=(10, 8))
        body.pack(fill='both', expand=True)
        left = ScrollFrame(body, width=292)
        left.pack(side='left', fill='y')
        self.scrollframes.append(left)
        self.tk_canvases.append((left.canvas, 'bg'))
        right = ttk.Frame(body, style='Bg.TFrame', width=340)
        right.pack(side='right', fill='y', padx=(10, 0))
        right.pack_propagate(False)
        center = ttk.Frame(body, style='Bg.TFrame')
        center.pack(side='left', fill='both', expand=True, padx=(10, 0))
        self._build_generator_panel(left.inner)
        self._build_center(center)
        self._build_right(right)
        self.root.unbind_class('TCombobox', '<MouseWheel>')
        self.root.bind_all('<MouseWheel>', self._on_wheel)

    def _build_menubar(self):
        mb = self._menu(self.root)
        f = self._menu(mb)
        f.add_command(label=T('✦ Компаньон: трек по описанию…   Ctrl+K'), command=self.open_companion)
        f.add_command(label=T('Сгенерировать новый трек   Ctrl+G'), command=self.generate)
        f.add_command(label=T('Открыть проект…   Ctrl+O'), command=self.open_project)
        f.add_command(label=T('⬆ Импорт трека (MIDI, Dendy, Sega)…   Ctrl+I'), command=self.import_track)
        f.add_command(label=T('Сохранить проект   Ctrl+S'), command=self.save_project)
        f.add_command(label=T('Сохранить проект как…'), command=lambda: self.save_project(as_new=True))
        f.add_separator()
        f.add_command(label=T('Экспорт WAV (весь трек)…   Ctrl+E'), command=self.export_wav)
        f.add_command(label=T('Экспорт WAV (выделение)…'), command=lambda: self.export_wav('selection'))
        f.add_command(label=T('Экспорт стемов (WAV на каждый трек)…'), command=self.export_stems)
        f.add_command(label=T('Экспорт MIDI…'), command=self.export_midi)
        f.add_separator()
        f.add_command(label=T('Выход'), command=self.on_close)
        mb.add_cascade(label=T('Файл'), menu=f)
        e = self._menu(mb)
        e.add_command(label=T('◀ Назад (отменить)   Ctrl+Z'), command=self.undo)
        e.add_command(label=T('Вперёд ▶ (повторить)   Ctrl+Y'), command=self.redo)
        e.add_separator()
        e.add_command(label='♻ Recreate another piece   R', command=self.recreate_selection)
        e.add_command(label=T('Копировать   Ctrl+C'), command=self.op_copy)
        e.add_command(label=T('Вставить   Ctrl+V'), command=self.op_paste)
        e.add_command(label=T('Дублировать   Ctrl+D'), command=self.op_duplicate)
        e.add_command(label=T('Очистить / удалить   Del'), command=self.op_clear)
        e.add_command(label=T('Выделить всё   Ctrl+A'), command=self.op_select_all)
        e.add_separator()
        e.add_command(label=T('Песня: +1 полутон'), command=lambda: self.transpose_song(1))
        e.add_command(label=T('Песня: −1 полутон'), command=lambda: self.transpose_song(-1))
        e.add_command(label=T('Добавить 4 такта'), command=lambda: self.append_bars(4))
        e.add_command(label=T('Убрать 4 такта'), command=lambda: self.remove_bars(4))
        mb.add_cascade(label=T('Правка'), menu=e)
        vid = self._menu(mb)
        vid.add_command(label=T('▶ Видео MP4 с визуализацией…'), command=self.open_video_dialog)
        vid.add_command(label=T('⌖ Метки битов для монтажа…'), command=self.open_markers_dialog)
        vid.add_command(label=T('♪ Звуковые эффекты (SFX)…'), command=self.open_sfx)
        vid.add_command(label=T('↻ Бесшовная петля для фона…'), command=self.export_loop)
        vid.add_command(label=T('MP3 для соцсетей…'), command=self.export_mp3_file)
        mb.add_cascade(label=T('Для видео'), menu=vid)
        v = self._menu(mb)
        v.add_radiobutton(label=T('Тёмная тема'), variable=self.v_theme, value='dark', command=lambda: self.set_theme('dark'))
        v.add_radiobutton(label=T('Светлая тема'), variable=self.v_theme, value='light', command=lambda: self.set_theme('light'))
        acc = self._menu(v)
        for name in ACCENTS:
            acc.add_radiobutton(label=T(name), variable=self.v_accent, value=name, command=self.set_accent)
        v.add_cascade(label=T('Акцентный цвет'), menu=acc)
        lang = self._menu(v)
        for code, name in LANGUAGES.items():
            lang.add_radiobutton(label=name, variable=self.v_lang, value=code,
                                 command=lambda c=code: self.set_language(c))
        v.add_cascade(label=T('Язык / Language'), menu=lang)
        v.add_separator()
        v.add_command(label=T('Аранжировка / Редактор   E'), command=lambda: self.set_mode('edit' if self.mode == 'arrange' else 'arrange'))
        v.add_command(label=T('Вписать в окно   F'), command=self.zoom_fit)
        v.add_command(label=T('Приблизить   +'), command=lambda: self.zoom(1.25))
        v.add_command(label=T('Отдалить   −'), command=lambda: self.zoom(0.8))
        mb.add_cascade(label=T('Вид'), menu=v)
        h = self._menu(mb)
        h.add_command(label=T('Горячие клавиши и подсказки'), command=self.show_help)
        h.add_command(label=T('О программе'), command=lambda: messagebox.showinfo(
            APP_NAME, T('{0}\nБесплатный генератор 8-битной музыки в духе Dendy и Sega.\nВсё звучание синтезируется прямо в программе — без сэмплов.').format(APP_NAME)))
        mb.add_cascade(label=T('Справка'), menu=h)
        if self.shell:
            md = self._menu(mb)
            md.add_command(label=T('✦ Чат-студия — создание по запросу'), command=self.shell.open_chat)
            md.add_command(label=T('⌂ Главное меню — выбор режима'), command=self.shell.show_launcher)
            mb.add_cascade(label=T('Режим'), menu=md)
        self.root.configure(menu=mb)

    def _build_topbar(self):
        top = ttk.Frame(self.root, padding=(14, 9))
        top.pack(side='top', fill='x')
        brand = ttk.Frame(top)
        brand.pack(side='left')
        ttk.Label(brand, text='▚▞ 8-BIT FORGE', style='Title.TLabel').pack(anchor='w')
        ttk.Label(brand, text='Dendy · Sega chiptune generator', style='Muted.TLabel', font=FONT_S).pack(anchor='w')
        trans = ttk.Frame(top)
        trans.pack(side='left', padx=(26, 0))
        self._btn(trans, '⏮', self.to_start, width=3).pack(side='left')
        self.btn_play = self._btn(trans, T('▶  Играть'), self.toggle_play, style='Accent.TButton', width=11)
        self.btn_play.pack(side='left', padx=4)
        self._btn(trans, T('■  Стоп'), self.stop).pack(side='left')
        self._btn(trans, T('▶ Выделение'), self.play_selection).pack(side='left', padx=4)
        self.chk_loop = self._check(trans, T('↻ Петля: выкл'), self.v_loop, style='Toolbutton')
        self.chk_loop.pack(side='left')
        self.v_loop.trace_add('write', lambda *a: self._on_loop_toggle())
        hist = ttk.Frame(top)
        hist.pack(side='left', padx=(20, 0))
        self.btn_undo = self._btn(hist, T('◀  Назад'), self.undo)
        self.btn_undo.pack(side='left')
        self.btn_redo = self._btn(hist, T('Вперёд  ▶'), self.redo)
        self.btn_redo.pack(side='left', padx=4)
        tbox = ttk.Frame(top)
        tbox.pack(side='left', padx=(20, 10))
        self.lbl_time = ttk.Label(tbox, text='00:00.0 / 00:00.0', style='Time.TLabel')
        self.lbl_time.pack(anchor='w')
        self.lbl_pos = ttk.Label(tbox, text=T('Такт 1 · доля 1'), style='Muted.TLabel', font=FONT_S)
        self.lbl_pos.pack(anchor='w')
        self.scope = tk.Canvas(top, width=190, height=44, highlightthickness=1, bd=0)
        self.scope.pack(side='left')
        self.scope_line = self.scope.create_line(0, 22, 190, 22, width=2)
        self.tk_canvases.append((self.scope, 'field'))
        self.btn_theme = self._btn(top, T('☀  Светлая'), self.toggle_theme)
        self.btn_theme.pack(side='right')
        self._btn(top, '?', self.show_help, width=3).pack(side='right', padx=4)
        if self.shell:
            self._btn(top, '⌂', self.shell.show_launcher, width=3).pack(side='right')
        mbtn = ttk.Menubutton(top, text=T('⬇  Экспорт'), takefocus=False)
        m = self._menu(mbtn)
        m.add_command(label=T('WAV — весь трек…'), command=self.export_wav)
        m.add_command(label=T('MP3 — весь трек…'), command=self.export_mp3_file)
        m.add_command(label=T('WAV — только выделение…'), command=lambda: self.export_wav('selection'))
        m.add_command(label=T('MP3 — только выделение…'), command=lambda: self.export_mp3_file('selection'))
        m.add_command(label=T('WAV — стемы (каждый трек отдельно)…'), command=self.export_stems)
        m.add_command(label='MIDI (.mid)…', command=self.export_midi)
        m.add_separator()
        m.add_command(label=T('▶ Видео MP4 с визуализацией…'), command=self.open_video_dialog)
        m.add_command(label=T('⌖ Метки битов для монтажа…'), command=self.open_markers_dialog)
        m.add_command(label=T('↻ Бесшовная петля для фона…'), command=self.export_loop)
        m.add_command(label=T('♪ Звуковые эффекты (SFX)…'), command=self.open_sfx)
        m.add_separator()
        m.add_command(label=T('Сохранить проект (.json)…'), command=lambda: self.save_project(as_new=True))
        m.add_command(label=T('Открыть проект…'), command=self.open_project)
        mbtn['menu'] = m
        mbtn.pack(side='right', padx=4)
        ibtn = ttk.Menubutton(top, text=T('⬆  Импорт'), takefocus=False)
        im = self._menu(ibtn)
        im.add_command(label=T('Импорт трека…   Ctrl+I'), command=self.import_track)
        im.add_separator()
        im.add_command(label=T('Проект 8-BIT FORGE (.json)…'), command=self.open_project)
        im.add_command(label=T('MIDI (.mid) — и экспорт этой программы…'), command=self.import_track)
        im.add_command(label=T('Dendy / NES — NSF, VGM…'), command=self.import_track)
        im.add_command(label=T('Sega Mega Drive / Master System — VGM, VGZ…'), command=self.import_track)
        ibtn['menu'] = im
        ibtn.pack(side='right')
        self._btn(top, T('Сохранить'), self.save_project).pack(side='right')
        self._btn(top, T('✦  Компаньон'), self.open_companion, style='Accent.TButton').pack(side='right', padx=(0, 8))

    def _build_generator_panel(self, p):
        s = self._section(p, T('⚡ Генератор'), T('Выберите стиль и нажмите «Сгенерировать». Пресет стиля подставит '
                                            'подходящие настройки — их можно менять.'))
        self._combo(s, T('Стиль'), self.v_style, list(STYLES), cmd=self.apply_style_preset, width=21)
        self._combo(s, T('Звучание'), self.v_chip, list(CHIPS), width=16)
        self._combo(s, T('Тональность'), self.v_key, NOTE_NAMES, width=16)
        self._combo(s, T('Лад'), self.v_scale, list(SCALES), width=19)
        self._combo(s, T('Длина (тактов)'), self.v_bars, BAR_CHOICES, width=8)
        self._combo(s, T('Смена аккордов'), self.v_chord_rate, list(CHORD_RATES), width=15)
        self._slider(s, T('Темп'), self.v_bpm, 60, 220, lambda v: f'{v:.0f} BPM')
        row = ttk.Frame(s)
        row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text='Seed').pack(side='left')
        ttk.Entry(row, textvariable=self.v_seed, width=10).pack(side='left', padx=6)
        self._btn(row, '⚄', self.new_seed, style='Small.TButton', width=3).pack(side='left')
        self._check(row, T('фикс.'), self.v_lock).pack(side='right')

        s = self._section(p, T('≋ Характер'))
        self._slider(s, T('Плотность мелодии'), self.v_density, 0, 1, pct)
        self._slider(s, T('Сложность / скачки'), self.v_complexity, 0, 1, pct)
        self._slider(s, T('Повторяемость фраз'), self.v_repetition, 0, 1, pct)
        self._slider(s, T('Интенсивность ударных'), self.v_drums, 0, 1, pct)
        self._slider(s, T('Свинг (сразу в треке)'), self.v_swing, 0, .6, pct)

        s = self._section(p, T('♫ Партии'))
        self._combo(s, T('Бас'), self.v_bass, BASS_PATTERNS, width=19)
        self._combo(s, T('Арпеджио'), self.v_arp, ARP_PATTERNS, width=12)
        self._combo(s, T('Скорость арп.'), self.v_arp_rate, list(ARP_RATES), width=8)
        self._combo(s, T('Гармония'), self.v_harmony, HARMONY_MODES, width=21)
        grid = ttk.Frame(s)
        grid.pack(fill='x', pady=(6, 0))
        for i, ((kind, name), var) in enumerate(zip(TRACK_DEFS, self.v_include)):
            self._check(grid, T(name), var).grid(row=i // 3, column=i % 3, sticky='w', padx=(0, 8), pady=1)
        self._check(s, T('Сохранять звук треков при генерации'), self.v_keep_sounds).pack(anchor='w', pady=(6, 0))

        s = self._section(p, T('▣ Для видео и клипов'), T('Применяется при «Сгенерировать». Точная длина подстраивает '
                                                    'темп, чтобы трек кончился ровно в нужную секунду.'))
        self._combo(s, T('Платформа'), self.v_platform, list(PLATFORM_PRESETS), cmd=self._apply_platform, width=21)
        row = ttk.Frame(s)
        row.pack(fill='x', pady=3)
        self._check(row, T('Точная длина, секунд:'), self.v_exact).pack(side='left')
        ttk.Entry(row, textvariable=self.v_exact_sec, width=6).pack(side='right')
        self._check(s, T('Вступление (нарастание)'), self.v_intro).pack(anchor='w')
        self._check(s, T('Концовка (финальный аккорд)'), self.v_outro).pack(anchor='w')
        row = ttk.Frame(s)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=T('Дроп / акцент на секунде')).pack(side='left')
        ttk.Entry(row, textvariable=self.v_drop_sec, width=6).pack(side='right')
        ttk.Label(s, text=T('0 — без дропа. Перед дропом музыка нарастает, в нём — взрыв.'), style='Muted.TLabel',
                  font=FONT_S).pack(anchor='w')
        g = ttk.Frame(s)
        g.pack(fill='x', pady=(6, 0))
        for i, (text, cmd) in enumerate(((T('▶ Видео MP4…'), self.open_video_dialog), (T('⌖ Метки битов…'), self.open_markers_dialog),
                                         (T('♪ Звуки SFX…'), self.open_sfx), (T('↻ Петля для фона…'), self.export_loop))):
            self._btn(g, text, cmd, style='Small.TButton').grid(row=i // 2, column=i % 2, sticky='ew', padx=2, pady=2)
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)

        s = ttk.Frame(p, padding=(12, 10))
        s.pack(fill='x', pady=(0, 8))
        self._btn(s, T('⚡  СГЕНЕРИРОВАТЬ'), self.generate, style='Accent.TButton').pack(fill='x')
        row = ttk.Frame(s)
        row.pack(fill='x', pady=(6, 0))
        self._btn(row, T('⚄ Удиви меня'), self.surprise).pack(side='left', fill='x', expand=True)
        self._btn(row, T('+4 такта'), lambda: self.append_bars(4)).pack(side='left', padx=(6, 0))

        s = self._section(p, T('♻ Пересоздание куска'),
                          T('Зажмите ЛКМ на дорожках и протяните — выделится область. Затем нажмите кнопку ниже '
                          '(или R). Старый кусок уйдёт в кэш. Используются текущие настройки «Характер» и «Партии».'))
        self._combo(s, T('Режим'), self.v_recreate_mode, RECREATE_MODES, width=17)
        self._btn(s, '♻  Recreate another piece', self.recreate_selection, style='Accent.TButton').pack(fill='x', pady=(6, 0))
        self._btn(s, T('Пересоздать весь выбранный трек'), self.recreate_track).pack(fill='x', pady=(6, 0))

    def _build_center(self, center):
        tb = ttk.Frame(center, padding=(8, 6))
        tb.pack(fill='x')
        for text, val in ((T('▦ Аранжировка'), 'arrange'), (T('✎ Редактор'), 'edit')):
            ttk.Radiobutton(tb, text=text, value=val, variable=self.v_mode, style='Toolbutton', takefocus=False,
                            command=lambda: self.set_mode(self.v_mode.get())).pack(side='left', padx=(0, 2))
        ttk.Label(tb, text=T('Трек')).pack(side='left', padx=(14, 4))
        cb = ttk.Combobox(tb, textvariable=self.v_edit_track, state='readonly', width=13, takefocus=False)
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e, w=cb: (self.select_track(w.current()), self.lanes.focus_set()))
        self.cb_tracks.append(cb)
        self.combos.append(cb)
        ttk.Label(tb, text='').pack(side='left', padx=6)
        for text, val in ((T('✎ Рисовать'), 'draw'), (T('⬚ Выделить'), 'select'), (T('⌫ Стереть'), 'erase')):
            ttk.Radiobutton(tb, text=text, value=val, variable=self.v_tool, style='Toolbutton',
                            takefocus=False).pack(side='left', padx=(0, 2))
        ttk.Label(tb, text=T('Сетка')).pack(side='left', padx=(12, 4))
        c1 = ttk.Combobox(tb, state='readonly', width=6, takefocus=False)
        c1.pack(side='left')
        translate_combo(c1, self.v_snap, list(SNAPS), lambda: self.lanes.focus_set())
        ttk.Label(tb, text=T('Нота')).pack(side='left', padx=(8, 4))
        c2 = ttk.Combobox(tb, state='readonly', width=6, takefocus=False)
        c2.pack(side='left')
        translate_combo(c2, self.v_note_len, list(SNAPS), lambda: self.lanes.focus_set())
        self.combos += [c1, c2]
        self._btn(tb, '⤢', self.zoom_fit, style='Small.TButton', width=3).pack(side='right')
        self._btn(tb, '+', lambda: self.zoom(1.25), style='Small.TButton', width=3).pack(side='right', padx=2)
        self._btn(tb, '−', lambda: self.zoom(0.8), style='Small.TButton', width=3).pack(side='right')
        self._check(tb, T('Следовать'), self.v_follow).pack(side='right', padx=8)
        self.lbl_hint = ttk.Label(center, style='Status.TLabel', padding=(4, 4, 0, 0))
        self.lbl_hint.pack(fill='x')

        area = ttk.Frame(center, style='Bg.TFrame')
        area.pack(fill='both', expand=True, pady=(4, 0))
        self.corner = tk.Canvas(area, width=HEAD_W, height=RULER_H, highlightthickness=0, bd=0)
        self.ruler = tk.Canvas(area, height=RULER_H, highlightthickness=0, bd=0)
        self.head = tk.Canvas(area, width=HEAD_W, highlightthickness=0, bd=0)
        self.lanes = tk.Canvas(area, highlightthickness=0, bd=0, takefocus=1)
        self.vbar = ttk.Scrollbar(area, orient='vertical', command=self.lanes.yview)
        self.hbar = ttk.Scrollbar(area, orient='horizontal', command=self.lanes.xview)
        self.corner.grid(row=0, column=0, sticky='nsew')
        self.ruler.grid(row=0, column=1, sticky='nsew')
        self.head.grid(row=1, column=0, sticky='nsew')
        self.lanes.grid(row=1, column=1, sticky='nsew')
        self.vbar.grid(row=1, column=2, sticky='ns')
        self.hbar.grid(row=2, column=1, sticky='ew')
        area.rowconfigure(1, weight=1)
        area.columnconfigure(1, weight=1)
        self.lanes.configure(xscrollcommand=self._xscroll, yscrollcommand=self._yscroll)
        for w, k in ((self.corner, 'panel'), (self.ruler, 'panel'), (self.head, 'panel'), (self.lanes, 'lane')):
            self.tk_canvases.append((w, k))
        self.lanes.bind('<ButtonPress-1>', self.on_lanes_press)
        self.lanes.bind('<B1-Motion>', self.on_lanes_motion)
        self.lanes.bind('<ButtonRelease-1>', self.on_lanes_release)
        self.lanes.bind('<Double-Button-1>', self.on_lanes_double)
        self.lanes.bind('<ButtonPress-3>', self.on_lanes_right)
        self.lanes.bind('<B3-Motion>', self.on_lanes_right)
        self.lanes.bind('<Motion>', self.on_lanes_hover)
        self.head.bind('<ButtonPress-1>', self.on_head_press)
        self.head.bind('<B1-Motion>', self.on_head_motion)
        self.head.bind('<Double-Button-1>', self.on_head_double)
        self.ruler.bind('<ButtonPress-1>', self.on_ruler_press)
        self.ruler.bind('<B1-Motion>', self.on_ruler_motion)
        self.ruler.bind('<ButtonPress-3>', self.on_ruler_right)

        sb = ttk.Frame(center, padding=(10, 8))
        sb.pack(fill='x', pady=(6, 0))
        r1 = ttk.Frame(sb)
        r1.pack(fill='x')
        self.lbl_sel = ttk.Label(r1, text='', font=FONT_B)
        self.lbl_sel.pack(side='left')
        self._btn(r1, '♻  Recreate another piece', self.recreate_selection, style='Accent.TButton').pack(side='right')
        cbm = ttk.Combobox(r1, state='readonly', width=16, takefocus=False)
        cbm.pack(side='right', padx=8)
        translate_combo(cbm, self.v_recreate_mode, RECREATE_MODES, lambda: self.lanes.focus_set())
        self.combos.append(cbm)
        r2 = ttk.Frame(sb)
        r2.pack(fill='x', pady=(6, 0))
        for text, cmd in ((T('✂ Очистить'), self.op_clear), (T('⧉ Копировать'), self.op_copy),
                          (T('⎘ Вставить'), self.op_paste), (T('⇉ Дублировать'), self.op_duplicate),
                          ('↑ +1', lambda: self.op_transpose(1)), ('↓ −1', lambda: self.op_transpose(-1)),
                          (T('⇑ Окт'), lambda: self.op_transpose(12)), (T('⇓ Окт'), lambda: self.op_transpose(-12)),
                          (T('⇆ Реверс'), self.op_reverse), (T('⌗ Квантовать'), self.op_quantize),
                          (T('≈ Хьюманайз'), self.op_humanize), (T('Громче'), lambda: self.op_velocity(.1)),
                          (T('Тише'), lambda: self.op_velocity(-.1)), (T('✖ Снять'), self.clear_selection)):
            self._btn(r2, text, cmd, style='Small.TButton').pack(side='left', padx=(0, 3))

    def _build_right(self, right):
        nb = ttk.Notebook(right, takefocus=False)
        nb.pack(fill='both', expand=True)
        tsf = ScrollFrame(nb)
        msf = ScrollFrame(nb)
        for sf in (tsf, msf):
            self.scrollframes.append(sf)
            self.tk_canvases.append((sf.canvas, 'bg'))
        cache_f = ttk.Frame(nb, padding=10)
        hist_f = ttk.Frame(nb, padding=10)
        nb.add(tsf, text=T('Трек'))
        nb.add(cache_f, text=T('Кэш'))
        nb.add(hist_f, text=T('История'))
        nb.add(msf, text=T('Мастер / Вид'))
        self._build_track_tab(tsf.inner)
        self._build_cache_tab(cache_f)
        self._build_history_tab(hist_f)
        self._build_master_tab(msf.inner)

    def _build_track_tab(self, p):
        s = ttk.Frame(p, padding=(12, 10))
        s.pack(fill='x', pady=(0, 8))
        self.track_title = ttk.Label(s, text=T('Трек'), style='Section.TLabel')
        self.track_title.pack(anchor='w')
        row = ttk.Frame(s)
        row.pack(fill='x', pady=4)
        cb = ttk.Combobox(row, textvariable=self.v_edit_track, state='readonly', width=16, takefocus=False)
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e, w=cb: (self.select_track(w.current()), self.lanes.focus_set()))
        self.cb_tracks.append(cb)
        self.combos.append(cb)
        self._check(row, 'S', self.tv_solo, lambda: self._on_track_param('solo'), style='Toolbutton').pack(side='right')
        self._check(row, 'M', self.tv_mute, lambda: self._on_track_param('mute'), style='Toolbutton').pack(side='right', padx=4)
        self._combo(s, T('Пресет'), self.tv_preset, list(SOUND_PRESETS), cmd=self.apply_preset, width=20)
        self._combo(s, T('Волна'), self.tv_wave, list(WAVE_NAMES.values()), cmd=lambda: self._on_track_param('wave'), width=16)
        self._combo(s, T('Скважность'), self.tv_duty, list(DUTY_NAMES.values()), cmd=lambda: self._on_track_param('duty'), width=8)
        self._combo(s, T('Октава'), self.tv_octave, ['-3', '-2', '-1', '0', '+1', '+2', '+3'],
                    cmd=lambda: self._on_track_param('octave'), width=8)
        self._combo(s, T('Набор ударных'), self.tv_kit, KITS, cmd=lambda: self._on_track_param('kit'), width=8)
        self._combo(s, T('Гласная (голос)'), self.tv_vowel, list(VOWEL_NAMES.values()),
                    cmd=lambda: self._on_track_param('vowel'), width=17)
        s2 = self._section(p, T('Огибающая и эффекты'))
        for fname, label, lo, hi, fmt in TRACK_SLIDERS:
            self._slider(s2, T(label), self.tv[fname], lo, hi, fmt, on_change=lambda f=fname: self._on_track_param(f))
        s3 = self._section(p, T('Действия с треком'))
        g = ttk.Frame(s3)
        g.pack(fill='x')
        for i, (text, cmd) in enumerate(((T('▶ Прослушать звук'), self.preview_track_sound),
                                         (T('⟲ Сбросить звук'), self.reset_sound),
                                         (T('♻ Пересоздать трек'), self.recreate_track),
                                         (T('✖ Очистить трек'), self.clear_track),
                                         (T('◐ Цвет…'), self.pick_color), (T('✎ Переименовать'), self.rename_track))):
            self._btn(g, text, cmd, style='Small.TButton').grid(row=i // 2, column=i % 2, sticky='ew', padx=2, pady=2)
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)

    def _build_cache_tab(self, f):
        ttk.Label(f, text=T('Кэш заменённых кусков'), style='Section.TLabel').pack(anchor='w')
        ttk.Label(f, text=T('Каждый раз при «Recreate» старый кусок попадает сюда. «Восстановить» меняет местами '
                          'текущий и сохранённый кусок — так можно сравнивать варианты.'),
                  style='Muted.TLabel', font=FONT_S, wraplength=300, justify='left').pack(anchor='w', pady=(0, 6))
        self.lb_cache = tk.Listbox(f, activestyle='none', font=FONT_S, exportselection=False)
        self.lb_cache.pack(fill='both', expand=True)
        self.lb_cache.bind('<Double-Button-1>', lambda e: self.cache_restore_sel())
        self.listboxes.append(self.lb_cache)
        g = ttk.Frame(f)
        g.pack(fill='x', pady=(6, 0))
        for i, (text, cmd) in enumerate(((T('⟲ Восстановить'), self.cache_restore_sel), (T('▶ Прослушать'), self.cache_preview_sel),
                                         (T('✖ Удалить'), self.cache_delete_sel), (T('Очистить всё'), self.cache_clear))):
            self._btn(g, text, cmd, style='Small.TButton').grid(row=i // 2, column=i % 2, sticky='ew', padx=2, pady=2)
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)

    def _build_history_tab(self, f):
        ttk.Label(f, text=T('История действий'), style='Section.TLabel').pack(anchor='w')
        ttk.Label(f, text=T('Кликните по шагу, чтобы перейти к нему. ● — текущее состояние.'),
                  style='Muted.TLabel', font=FONT_S, wraplength=300).pack(anchor='w', pady=(0, 6))
        self.lb_hist = tk.Listbox(f, activestyle='none', font=FONT_S, exportselection=False)
        self.lb_hist.pack(fill='both', expand=True)
        self.lb_hist.bind('<<ListboxSelect>>', self.history_jump)
        self.listboxes.append(self.lb_hist)
        row = ttk.Frame(f)
        row.pack(fill='x', pady=(6, 0))
        self._btn(row, T('◀ Назад'), self.undo, style='Small.TButton').pack(side='left', fill='x', expand=True)
        self._btn(row, T('Вперёд ▶'), self.redo, style='Small.TButton').pack(side='left', fill='x', expand=True, padx=4)
        self._btn(row, T('Очистить'), self.clear_history, style='Small.TButton').pack(side='left', fill='x', expand=True)

    def _build_master_tab(self, p):
        mc = self._on_master_change
        s = self._section(p, T('Мастер-канал'), T('Ретро-обработка всего звука. Применяется при следующем '
                                             'воспроизведении (или сразу, если включено живое обновление).'))
        self._slider(s, T('Громкость'), self.v_mvol, 0, 1, pct, mc)
        self._combo(s, T('Частота (Гц)'), self.v_sr, ['22050', '32000', '44100', '48000'], cmd=mc, width=8)
        self._combo(s, T('Разрядность (биткраш)'), self.v_bits, ['16', '12', '10', '8', '6', '4'], cmd=mc, width=5)
        self._slider(s, T('Понижение частоты ×'), self.v_down, 1, 8, lambda v: f'×{int(round(v))}', mc)
        self._slider(s, T('Сглаживание (мягче)'), self.v_smooth, 0, 6, lambda v: f'{int(round(v))}', mc)
        self._check(s, T('4-битная громкость (как у NES)'), self.v_nes_env, mc).pack(anchor='w', pady=(6, 0))
        self._check(s, T('Нормализация громкости'), self.v_norm, mc).pack(anchor='w')
        self._check(s, T('Живое обновление во время игры'), self.v_live).pack(anchor='w')
        s = self._section(p, T('Экспорт'))
        self._slider(s, T('Повторов трека в файле'), self.v_loops, 1, 8, lambda v: f'{int(round(v))}')
        self._check(s, T('Плавное затухание в конце'), self.v_fade).pack(anchor='w', pady=(6, 0))
        self._check(s, T('8-битный WAV (ещё ретро)'), self.v_wav8).pack(anchor='w')
        self._combo(s, T('Громкость'), self.v_lufs, list(LOUDNESS_TARGETS), width=25)
        self._combo(s, T('MP3, кбит/с'), self.v_mp3_kbps, ['128', '192', '256', '320'], width=6)
        g = ttk.Frame(s)
        g.pack(fill='x', pady=(6, 0))
        for i, (text, cmd) in enumerate((('WAV', self.export_wav), ('MP3', self.export_mp3_file),
                                         (T('Выделение'), lambda: self.export_wav('selection')), (T('Стемы'), self.export_stems),
                                         ('MIDI', self.export_midi), (T('Видео'), self.open_video_dialog))):
            self._btn(g, text, cmd, style='Small.TButton').grid(row=i // 3, column=i % 3, sticky='ew', padx=2, pady=2)
        for i in range(3):
            g.columnconfigure(i, weight=1)
        s = self._section(p, T('Песня'))
        g = ttk.Frame(s)
        g.pack(fill='x')
        for i, (text, cmd) in enumerate(((T('♯ +1 полутон'), lambda: self.transpose_song(1)),
                                         (T('♭ −1 полутон'), lambda: self.transpose_song(-1)),
                                         (T('+4 такта'), lambda: self.append_bars(4)),
                                         (T('−4 такта'), lambda: self.remove_bars(4)))):
            self._btn(g, text, cmd, style='Small.TButton').grid(row=i // 2, column=i % 2, sticky='ew', padx=2, pady=2)
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)
        s = self._section(p, T('Вид'))
        row = ttk.Frame(s)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=T('Тема')).pack(side='left')
        for text, val in ((T('Светлая'), 'light'), (T('Тёмная'), 'dark')):
            ttk.Radiobutton(row, text=text, value=val, variable=self.v_theme, style='Toolbutton', takefocus=False,
                            command=lambda: self.set_theme(self.v_theme.get())).pack(side='right', padx=2)
        self._combo(s, T('Акцент'), self.v_accent, list(ACCENTS), cmd=self.set_accent, width=16)
        self._combo(s, T('Язык / Language'), self.v_lang_name, list(LANGUAGES.values()), width=16,
                    cmd=lambda: self.set_language(next(c for c, n in LANGUAGES.items() if n == self.v_lang_name.get())))
        redraw = lambda: self.redraw_all()
        self._check(s, T('Показывать другие треки в редакторе'), self.v_ghost, redraw).pack(anchor='w', pady=(6, 0))
        self._check(s, T('Подсвечивать ноты лада'), self.v_show_scale, redraw).pack(anchor='w')
        self._check(s, T('Прослушивать ноты при рисовании'), self.v_preview).pack(anchor='w')
        self._check(s, T('Следовать за воспроизведением'), self.v_follow).pack(anchor='w')
