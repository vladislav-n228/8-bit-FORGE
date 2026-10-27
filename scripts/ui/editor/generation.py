# -*- coding: utf-8 -*-
"""Track generation from the settings, ♻ Recreate of a piece and the cache of old variants."""

import copy
import random
import time
from tkinter import messagebox

from scripts.core.constants import (
    APP_NAME, ARP_RATES, CHARACTER_KEYS, CHIPS, CHORD_RATES, NOTE_NAMES, RECREATE_MODES, STYLES)
from scripts.core.i18n import T
from scripts.core.theory import bb, clamp, fmt_time
from scripts.music.composer import Composer
from scripts.music.generator import build_song


class GenerationMixin:
    """Track generation from the settings, ♻ Recreate of a piece and the cache of old variants."""

    def collect_params(self):
        try:
            key = NOTE_NAMES.index(self.v_key.get())
        except ValueError:
            key = 0
        return dict(style=self.v_style.get(), key=key, scale=self.v_scale.get(), bpm=int(round(self.v_bpm.get())),
                    bars=int(self.v_bars.get()), chord_steps=CHORD_RATES.get(self.v_chord_rate.get(), 16),
                    density=self.v_density.get(), complexity=self.v_complexity.get(),
                    repetition=self.v_repetition.get(), drums=self.v_drums.get(), swing=self.v_swing.get(),
                    bass=self.v_bass.get(), arp=self.v_arp.get(), arp_rate=ARP_RATES.get(self.v_arp_rate.get(), 1),
                    harmony=self.v_harmony.get(), chip=CHIPS.get(self.v_chip.get(), 'nes'),
                    include=[v.get() for v in self.v_include],
                    exact_sec=self._num(self.v_exact_sec, 30, 3, 600) if self.v_exact.get() else None,
                    intro=self.v_intro.get(), outro=self.v_outro.get(),
                    drop_sec=self._num(self.v_drop_sec, 0, 0, 600))

    @staticmethod
    def _num(var, default, lo, hi):
        try:
            return clamp(float(str(var.get()).replace(',', '.').strip()), lo, hi)
        except ValueError:
            return default

    def new_seed(self):
        self.v_seed.set(str(random.randrange(1, 999999)))

    def generate(self, initial=False):
        params = self.collect_params()
        try:
            seed = int(self.v_seed.get())
        except ValueError:
            seed = 0
        if not self.v_lock.get() and not initial or seed <= 0:
            seed = random.randrange(1, 999999)
            self.v_seed.set(str(seed))
        if not initial:
            self.push_history(T('Генерация нового трека'))
        self.song = build_song(params, seed, self.song, self.v_keep_sounds.get())
        self.cursor = 0
        self.after_song_change()
        if not initial:
            self.zoom_fit()
        self.set_status(T('⚡ Сгенерировано: {0}, {1} {2}, seed {3}. Пробел — слушать.').format(T(params["style"]), NOTE_NAMES[params["key"]], T(params["scale"]), seed))

    def load_external_song(self, song, label=None):
        """A track from the chat studio → into the editor; the previous one stays available via "◀ Back"."""
        first = self.song is None
        if not first:
            self.stop()
            self.push_history(T('✦ Из чата: «{0}»').format(label) if label else T('✦ Трек из чата'))
        self.song = song
        self.cursor = 0
        self.sel_track = 0
        self._sync_generator_vars(song.params, song.seed)
        self.after_song_change()
        if not first:
            self.zoom_fit()
        self.set_status(T('✦ Трек из чата: «{0}» — {1}. Пробел — слушать.').format(song.params.get("title", T(song.style)), fmt_time(song.total_steps * song.step_dur)))

    def apply_style_preset(self):
        st = STYLES[self.v_style.get()]
        self.v_scale.set(random.choice(st['scales']))
        self.v_bpm.set(random.randint(*st['bpm']))
        for var, k in ((self.v_density, 'density'), (self.v_complexity, 'complexity'),
                       (self.v_repetition, 'repetition'), (self.v_drums, 'drums'), (self.v_swing, 'swing')):
            var.set(st[k])
        self.v_bass.set(st['bass'])
        self.v_arp.set(st['arp'])
        self.v_arp_rate.set(st['arp_rate'])
        self.v_harmony.set(st['harmony'])
        self.v_chord_rate.set(st['chords'])
        self.v_chip.set('Sega (FM)' if st['chip'] == 'sega' else 'Dendy (NES)')
        self.set_status(T('Пресет «{0}» применён — нажмите «Сгенерировать»').format(T(self.v_style.get())))

    def surprise(self):
        self.v_style.set(random.choice(list(STYLES)))
        self.apply_style_preset()
        self.v_key.set(random.choice(NOTE_NAMES))
        for var in (self.v_density, self.v_complexity, self.v_repetition, self.v_drums):
            var.set(clamp(var.get() + random.uniform(-.15, .15), 0, 1))
        self.v_bars.set(random.choice(['8', '12', '16', '16', '24', '32']))
        self.v_lock.set(False)
        self.generate()

    def _update_character(self):
        P = self.collect_params()
        self.song.params.update({k: P[k] for k in CHARACTER_KEYS})

    def get_region(self):
        if not self.song:
            return None
        if self.mode == 'edit' and self.sel_notes:
            s0 = self.snap_floor(min(n.s for n in self.sel_notes))
            s1 = self.snap_ceil(max(n.s + n.l for n in self.sel_notes))
            return [self.sel_track], s0, min(self.song.total_steps, max(s1, s0 + 1))
        if self.sel:
            return list(range(self.sel['t0'], self.sel['t1'] + 1)), self.sel['s0'], self.sel['s1']
        return None

    def recreate_selection(self):
        reg = self.get_region()
        if not reg:
            self.set_status(T('Сначала выделите область: зажмите ЛКМ на дорожках и протяните'))
            messagebox.showinfo(APP_NAME, T('Сначала выделите область:\nзажмите ЛКМ на дорожках и протяните мышь.\n\n'
                                          'Потом нажмите «♻ Recreate another piece».'))
            return
        self.recreate(*reg)

    def recreate_track(self):
        self.recreate([self.sel_track], 0, self.song.total_steps)
        self.sel = dict(t0=self.sel_track, t1=self.sel_track, s0=0, s1=self.song.total_steps)
        self.redraw_all()

    def recreate(self, tis, s0, s1, mode=None):
        sg = self.song
        if s1 <= s0 or not tis:
            return
        mode = mode or self.v_recreate_mode.get()
        names = ', '.join(T(sg.tracks[i].name) for i in tis)
        self.push_history(f'♻ {T(mode)}: {names} {bb(s0)}–{bb(s1)}')
        self._update_character()
        comp = Composer(sg, random.Random(random.randrange(1, 2 ** 31)))
        saved = {}
        for ti in sorted(tis):
            tr = sg.tracks[ti]
            old = [n for n in tr.notes if s0 <= n.s < s1]
            saved[ti] = [copy.copy(n) for n in old]
            keep = [n for n in tr.notes if not (s0 <= n.s < s1)]
            for n in keep:
                if n.s < s0 < n.s + n.l:
                    n.l = s0 - n.s
            tr.notes = keep
            new = comp.generate(tr, s0, s1) if mode == RECREATE_MODES[0] else comp.vary(tr, old, s0, s1, mode)
            tr.notes = sorted(keep + new, key=lambda n: (n.s, n.p))
        self.cache_seq += 1
        self.cache.insert(0, dict(id=self.cache_seq, time=time.strftime('%H:%M:%S'), tracks=sorted(tis),
                                  s0=s0, s1=s1, notes=saved, swaps=0))
        del self.cache[100:]
        if self.mode == 'arrange' or not self.sel_notes:
            self.sel = dict(t0=min(tis), t1=max(tis), s0=s0, s1=s1)
        self.after_song_change(keep_sel=True)
        self.set_status(T('♻ Кусок пересоздан ({0}). Старый вариант в кэше #{1}. R — ещё вариант, ◀ Назад — вернуть.').format(T(mode), self.cache_seq))

    def update_cache_ui(self):
        lb = self.lb_cache
        lb.delete(0, 'end')
        for e in self.cache:
            names = '+'.join(T(self.song.tracks[t].name) for t in e['tracks'] if t < len(self.song.tracks))
            cnt = sum(len(v) for v in e['notes'].values())
            swap = ' ⇄' if e['swaps'] else ''
            lb.insert('end', T(' #{0}{1}  {2}  {3} · {4}–{5} · {6} нот').format(e["id"], swap, e["time"], names, bb(e["s0"]), bb(e["s1"]), cnt))
        if not self.cache:
            lb.insert('end', T('  (пусто — используйте ♻ Recreate)'))
            lb.itemconfigure('end', foreground=self.c['muted'])
        self.update_info()

    def _cache_selected(self):
        sel = self.lb_cache.curselection()
        if not sel or not self.cache or sel[0] >= len(self.cache):
            self.set_status(T('Выберите кусок в списке кэша'))
            return None
        return sel[0]

    def cache_restore_sel(self):
        i = self._cache_selected()
        if i is None:
            return
        e = self.cache[i]
        sg = self.song
        s0, s1 = e['s0'], min(e['s1'], sg.total_steps)
        if s1 <= s0:
            self.set_status(T('Этот кусок вне текущей длины песни'))
            return
        self.push_history(T('⟲ Восстановление из кэша #{0}').format(e["id"]))
        cur = {}
        for ti in e['tracks']:
            if ti >= len(sg.tracks):
                continue
            tr = sg.tracks[ti]
            cur[ti] = [copy.copy(n) for n in tr.notes if s0 <= n.s < s1]
            tr.notes = sorted([n for n in tr.notes if not (s0 <= n.s < s1)] +
                              [copy.copy(n) for n in e['notes'].get(ti, []) if n.s < s1],
                              key=lambda n: (n.s, n.p))
        e['notes'], e['time'], e['swaps'] = cur, time.strftime('%H:%M:%S'), e['swaps'] + 1
        self.sel = dict(t0=min(e['tracks']), t1=max(e['tracks']), s0=s0, s1=s1)
        self.after_song_change(keep_sel=True)
        self.lb_cache.selection_set(i)
        self.set_status(T('⟲ Кусок #{0} восстановлен; текущий вариант теперь хранится на его месте в кэше').format(e["id"]))

    def cache_preview_sel(self):
        i = self._cache_selected()
        if i is None:
            return
        e = self.cache[i]
        tmp = copy.deepcopy(self.song)
        for ti, tr in enumerate(tmp.tracks):
            tr.notes = [copy.copy(n) for n in e['notes'].get(ti, [])]
            tr.mute = tr.solo = False
        self.play(e['s0'], min(e['s1'], tmp.total_steps), loop=False, song=tmp)
        self.set_status(T('▶ Прослушивание куска из кэша #{0}').format(e["id"]))

    def cache_delete_sel(self):
        i = self._cache_selected()
        if i is not None:
            del self.cache[i]
            self.update_cache_ui()

    def cache_clear(self):
        if self.cache and messagebox.askyesno(APP_NAME, T('Очистить весь кэш кусков?')):
            self.cache.clear()
            self.update_cache_ui()
