# -*- coding: utf-8 -*-
"""The "✦ Companion" window: a track from a description by keywords (the old assistant)."""

import random
import tkinter as tk
from tkinter import ttk

from scripts.core.constants import APP_NAME, ARP_RATES, CHIPS, CHORD_RATES, NOTE_NAMES, VOWEL_KEYS, VOWEL_NAMES
from scripts.core.i18n import T
from scripts.core.prefs import save_prefs
from scripts.core.theory import fmt_time
from scripts.music.companion import (
    apply_companion_sound, COMPANION_DURATIONS, COMPANION_EXAMPLES, COMPANION_GENRES, interpret_prompt)
from scripts.music.generator import build_song
from scripts.music.structure import fmt_bpm, PLATFORM_PRESETS
from scripts.ui.style import FONT_B, FONT_S
from scripts.ui.widgets import translate_combo


class CompanionMixin:
    """The "✦ Companion" window: a track from a description by keywords (the old assistant)."""

    def open_companion(self):
        if self.comp_win and self.comp_win.winfo_exists():
            self.comp_win.deiconify()
            self.comp_win.lift()
            self.comp_text.focus_set()
            return
        w = self.comp_win = tk.Toplevel(self.root)
        w.title(T('{0} — ✦ Компаньон').format(APP_NAME))
        w.geometry('640x760')
        w.minsize(560, 620)
        w.transient(self.root)
        f = ttk.Frame(w, padding=(18, 14))
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=T('✦ Компаньон'), style='Title.TLabel').pack(anchor='w')
        ttk.Label(f, text=T('Опиши словами, какой трек нужен — я сочиню его, а дальше его можно редактировать как '
                          'обычно: Recreate, редактор нот, звук треков, экспорт.'),
                  style='Muted.TLabel', wraplength=590, justify='left').pack(anchor='w', pady=(2, 10))
        ttk.Label(f, text=T('Описание трека'), font=FONT_B).pack(anchor='w')
        self.comp_text = tk.Text(f, height=4, wrap='word', font=('Segoe UI', 11), bd=0, padx=10, pady=8,
                                 highlightthickness=1)
        self.comp_text.pack(fill='x', pady=(4, 6))
        self.comp_text.bind('<Control-Return>', lambda e: (self.companion_generate(), 'break')[1])
        ttk.Label(f, text=T('Примеры (клик — подставить):'), style='Muted.TLabel', font=FONT_S).pack(anchor='w')
        grid = ttk.Frame(f)
        grid.pack(fill='x', pady=(2, 8))
        for i, text in enumerate(COMPANION_EXAMPLES):
            self._btn(grid, T(text), lambda t=T(text): self._comp_set_text(t), style='Small.TButton').grid(
                row=i // 2, column=i % 2, sticky='ew', padx=2, pady=2)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        opts = ttk.Frame(f)
        opts.pack(fill='x', pady=(4, 6))
        self._combo(opts, T('Длительность'), self.c_duration,
                    list(COMPANION_DURATIONS) + [k for k, v in PLATFORM_PRESETS.items() if v], width=26)
        self._combo(opts, T('Жанр'), self.c_genre, list(COMPANION_GENRES), width=26)
        row = ttk.Frame(opts)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=T('Голос')).pack(side='left')
        cbv = ttk.Combobox(row, state='readonly', width=20, takefocus=False)
        cbv.pack(side='right')
        translate_combo(cbv, self.c_voice_type, list(VOWEL_NAMES.values()), lambda: self.c_voice.set(True))
        self.combos.append(cbv)
        for text, val in ((T('С голосом'), True), (T('Без голоса'), False)):
            ttk.Radiobutton(row, text=text, value=val, variable=self.c_voice, style='Toolbutton',
                            takefocus=False).pack(side='right', padx=2)
        row = ttk.Frame(opts)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=T('Дроп / акцент на секунде (0 — нет)')).pack(side='left')
        ttk.Entry(row, textvariable=self.c_drop, width=6).pack(side='right')
        self._check(opts, T('Для видео: ровно в секунду + вступление и концовка'), self.c_exact).pack(anchor='w', pady=(4, 0))
        self._check(opts, T('Сразу включить воспроизведение'), self.c_autoplay).pack(anchor='w')
        btns = ttk.Frame(f)
        btns.pack(fill='x', pady=(8, 6))
        self._btn(btns, T('✦  Сочинить трек'), self.companion_generate, style='Accent.TButton').pack(
            side='left', fill='x', expand=True)
        self._btn(btns, T('⚄ Ещё вариант'), self.companion_again).pack(side='left', padx=6)
        self._btn(btns, T('✎ В редактор'), self.companion_to_editor).pack(side='left')
        ttk.Label(f, text=T('Как я понял запрос'), font=FONT_B).pack(anchor='w', pady=(6, 2))
        self.comp_reply = tk.Text(f, height=9, wrap='word', font=('Segoe UI', 10), bd=0, padx=10, pady=8,
                                  highlightthickness=0, state='disabled')
        self.comp_reply.pack(fill='both', expand=True)
        ttk.Label(f, text=T('Недавние запросы (двойной клик — повторить)'), style='Muted.TLabel',
                  font=FONT_S).pack(anchor='w', pady=(8, 2))
        self.comp_list = tk.Listbox(f, height=4, activestyle='none', font=FONT_S, exportselection=False, bd=0,
                                    highlightthickness=0)
        self.comp_list.pack(fill='x')
        self.comp_list.bind('<Double-Button-1>', self._comp_pick_history)
        for p in self.comp_history:
            self.comp_list.insert('end', p)
        w.protocol('WM_DELETE_WINDOW', self._comp_close)
        self._theme_companion()
        self._comp_reply_set(T('Напиши описание и нажми «Сочинить трек» (или Ctrl+Enter).\n\n'
                             'Что можно указывать:\n'
                             '• жанр или место — замок, космос, гонки, деревня, пещера, ночной город;\n'
                             '• настроение — грустно, весело, эпично, жутко, загадочно;\n'
                             '• темп — быстро, медленно, «140 bpm»;\n'
                             '• длительность — «2 минуты», «30 секунд», «1:30» (иначе берётся из списка);\n'
                             '• «с голосом», «без барабанов», «без баса», «Sega» или «Dendy», «ля минор».'))
        self.comp_text.focus_set()

    def _theme_companion(self):
        c = self.c
        self.comp_win.configure(bg=c['panel'])
        for t in (self.comp_text, self.comp_reply):
            t.configure(bg=c['field'], fg=c['fg'], insertbackground=c['fg'], highlightbackground=c['border'],
                        highlightcolor=c['accent'], selectbackground=c['accent'], selectforeground=c['accent_fg'])
        self.comp_list.configure(bg=c['field'], fg=c['fg'], selectbackground=c['accent'],
                                 selectforeground=c['accent_fg'])

    def _comp_close(self):
        self.comp_win.destroy()
        self.comp_win = None

    def _comp_set_text(self, text):
        self.comp_text.delete('1.0', 'end')
        self.comp_text.insert('1.0', text)
        self.comp_text.focus_set()

    def _comp_reply_set(self, text):
        self.comp_reply.configure(state='normal')
        self.comp_reply.delete('1.0', 'end')
        self.comp_reply.insert('1.0', text)
        self.comp_reply.configure(state='disabled')

    def _comp_pick_history(self, _e=None):
        sel = self.comp_list.curselection()
        if sel:
            self._comp_set_text(self.comp_history[sel[0]])
            self.companion_generate()

    def companion_generate(self, prompt=None):
        text = (prompt if prompt is not None else self.comp_text.get('1.0', 'end')).strip()
        if not text:
            self._comp_reply_set(T('Сначала напиши, какой трек нужен. Например: «весёлое приключение в лесу, 1 минута».'))
            return
        res = interpret_prompt(text, self.c_genre.get(), self.c_duration.get(), self.c_voice.get(),
                               VOWEL_KEYS.get(self.c_voice_type.get(), 'а'), random.Random())
        self.comp_last = (text, res)
        self._companion_build(text, res)
        if text in self.comp_history:
            self.comp_history.remove(text)
        self.comp_history.insert(0, text)
        del self.comp_history[15:]
        self.prefs['companion_history'] = self.comp_history
        save_prefs(self.prefs)
        if self.comp_win and self.comp_win.winfo_exists():
            self.comp_list.delete(0, 'end')
            for p in self.comp_history:
                self.comp_list.insert('end', p)

    def companion_again(self):
        if not self.comp_last:
            return self.companion_generate()
        self._companion_build(*self.comp_last, again=True)

    def _companion_build(self, text, res, again=False):
        self.stop()
        seed = random.randrange(1, 999999)
        short = text if len(text) <= 40 else text[:38] + '…'
        self.push_history(T('✦ Компаньон: «{0}»').format(short) + (T(' — ещё вариант') if again else ''))
        params = dict(res['params'])
        drop = res.get('drop_sec') or self._num(self.c_drop, 0, 0, 600)
        if self.c_exact.get():
            params.update(exact_sec=res['seconds'], intro=True, outro=True)
        params['drop_sec'] = drop
        song = build_song(params, seed)
        apply_companion_sound(song, res)
        song.params['prompt'] = text
        self.song = song
        self.cursor = 0
        self.sel_track = 0
        self._sync_generator_vars(params, seed)
        self.after_song_change()
        self.zoom_fit()
        total = song.total_steps * song.step_dur
        final = T('Итог: {0} · {1} тактов · {2} BPM').format(fmt_time(total), song.bars, fmt_bpm(song.bpm))
        if params.get('exact_sec'):
            final += T(' · ровно в секунду, со вступлением и концовкой')
        if drop:
            ds = song.params.get('drop_step')
            final += (T(' · дроп на {0}').format(fmt_time(ds * song.step_dur)) if ds else
                      T(' · дроп на {0:g} с не поместился (нужно ≥ 2 такта до него и 1 после)').format(drop))
        lines = res['summary'] + [final, f'Seed: {seed}', '',
                                  T('Трек уже в главном окне. Его можно редактировать: выдели кусок и нажми '
                                  '♻ Recreate, открой ✎ Редактор или поменяй звук во вкладке «Трек». '
                                  '«◀ Назад» вернёт предыдущий трек, «⚄ Ещё вариант» — сочинит другой по тому же запросу.')]
        if self.comp_win and self.comp_win.winfo_exists():
            self._comp_reply_set('\n'.join(lines))
        self.set_status(T('✦ Компаньон сочинил трек: {0} · {1}').format(T(song.style), fmt_time(song.total_steps * song.step_dur)))
        if self.c_autoplay.get():
            self.play(0, self.song.total_steps, start=0)

    def _sync_generator_vars(self, p, seed):
        """The left panel shows the settings the track was composed with — "Generate" will continue in the same spirit."""
        self.v_style.set(p['style'])
        self.v_key.set(NOTE_NAMES[p['key']])
        self.v_scale.set(p['scale'])
        self.v_bars.set(str(p['bars']))
        self.v_chord_rate.set(next((k for k, v in CHORD_RATES.items() if v == p['chord_steps']), 'Каждый такт'))
        self.v_chip.set(next((k for k, v in CHIPS.items() if v == p['chip']), 'Dendy (NES)'))
        for var, k in ((self.v_density, 'density'), (self.v_complexity, 'complexity'),
                       (self.v_repetition, 'repetition'), (self.v_drums, 'drums')):
            var.set(p[k])
        self.v_bass.set(p['bass'])
        self.v_arp.set(p['arp'])
        self.v_arp_rate.set(next((k for k, v in ARP_RATES.items() if v == p['arp_rate']), '1/16'))
        self.v_harmony.set(p['harmony'])
        for var, inc in zip(self.v_include, p['include']):
            var.set(inc)
        self.v_seed.set(str(seed))
        self.v_exact.set(bool(p.get('exact_sec')))
        if p.get('exact_sec'):
            self.v_exact_sec.set(f'{p["exact_sec"]:g}')
        self.v_intro.set(bool(p.get('intro')))
        self.v_outro.set(bool(p.get('outro')))
        self.v_drop_sec.set(f'{p.get("drop_sec") or 0:g}')

    def companion_to_editor(self):
        self.root.lift()
        self.root.focus_force()
        self.select_track(0)
        self.set_mode('edit')
