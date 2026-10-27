# -*- coding: utf-8 -*-
"""Note editing (copy, transpose, quantize…) and the track's sound parameters."""

import random
import tkinter as tk
from tkinter import simpledialog, colorchooser

from scripts.core.constants import (
    APP_NAME, DUTY_VALUES, NOTE_NAMES, SOUND_FIELDS, SOUND_PRESETS, VOWEL_KEYS, WAVE_KEYS)
from scripts.core.i18n import T
from scripts.core.model import default_tracks, Note
from scripts.core.theory import bb, chord_name, clamp
from scripts.music.composer import Composer
from scripts.ui.style import PMAX, PMIN


class EditingMixin:
    """Note editing (copy, transpose, quantize…) and the track's sound parameters."""

    def target_notes(self):
        if self.mode == 'edit' and self.sel_notes:
            return [(self.cur_track(), n) for n in self.sel_notes]
        reg = self.get_region()
        if not reg:
            return []
        tis, s0, s1 = reg
        return [(self.song.tracks[ti], n) for ti in tis for n in self.song.tracks[ti].notes if s0 <= n.s < s1]

    def _need_targets(self):
        t = self.target_notes()
        if not t:
            self.set_status(T('Нет нот в выделении'))
        return t

    def _finish_edit(self, msg):
        for tr in self.song.tracks:
            tr.notes.sort(key=lambda n: (n.s, n.p))
        self.after_song_change(keep_sel=True, keep_notes=True)
        self.set_status(msg)

    def op_clear(self):
        if self.mode == 'edit' and self.sel_notes:
            self.push_history(T('Удаление нот'))
            tr = self.cur_track()
            tr.notes = [n for n in tr.notes if n not in self.sel_notes]
            self.sel_notes = set()
            return self._finish_edit(T('Ноты удалены'))
        reg = self.get_region()
        if not reg:
            return self.set_status(T('Нечего очищать — выделите область'))
        tis, s0, s1 = reg
        self.push_history(T('Очистка {0}–{1}').format(bb(s0), bb(s1)))
        for ti in tis:
            tr = self.song.tracks[ti]
            tr.notes = [n for n in tr.notes if not (s0 <= n.s < s1)]
        self._finish_edit(T('Область очищена'))

    def op_transpose(self, k):
        t = self._need_targets()
        if not t:
            return
        self.push_history(T('Транспонирование {0:+d}').format(k))
        for tr, n in t:
            if tr.kind != 'drums':
                n.p = int(clamp(n.p + k, PMIN, PMAX))
        self._finish_edit(T('Транспонировано на {0:+d} пт').format(k))

    def op_reverse(self):
        reg = self.get_region()
        t = self._need_targets()
        if not t or not reg:
            return
        _, s0, s1 = reg
        self.push_history(T('Реверс'))
        for tr, n in t:
            n.s = int(clamp(s0 + s1 - (n.s + n.l), s0, s1 - 1))
        self._finish_edit(T('Кусок развёрнут задом наперёд'))

    def op_quantize(self):
        t = self._need_targets()
        if not t:
            return
        q, total = self.snap, self.song.total_steps
        self.push_history(T('Квантование'))
        for tr, n in t:
            n.s = int(clamp(round(n.s / q) * q, 0, total - 1))
            if tr.kind != 'drums':
                n.l = int(clamp(max(q, round(n.l / q) * q), 1, total - n.s))
        self._finish_edit(T('Квантовано по сетке {0}').format(self.v_snap.get()))

    def op_humanize(self):
        t = self._need_targets()
        if not t:
            return
        self.push_history(T('Хьюманайз'))
        for _, n in t:
            n.v = round(clamp(n.v + random.uniform(-.18, .18), .2, 1), 3)
        self._finish_edit(T('Громкость нот слегка «оживлена»'))

    def op_velocity(self, d):
        t = self._need_targets()
        if not t:
            return
        self.push_history(T('Громкость нот'))
        for _, n in t:
            n.v = round(clamp(n.v + d, .1, 1), 3)
        self._finish_edit(T('Громкость нот изменена'))

    def op_copy(self):
        reg = self.get_region()
        if not reg:
            return self.set_status(T('Нечего копировать — выделите область'))
        tis, s0, s1 = reg
        if self.mode == 'edit' and self.sel_notes:
            data = {self.sel_track: [(n.s - s0, n.l, n.p, n.v) for n in self.sel_notes]}
        else:
            data = {ti: [(n.s - s0, n.l, n.p, n.v) for n in self.song.tracks[ti].notes if s0 <= n.s < s1] for ti in tis}
        self.clipboard = dict(span=s1 - s0, data=data)
        self.set_status(T('⧉ Скопировано {0} нот. Вставка — в позицию курсора (Ctrl+V)').format(sum(len(v) for v in data.values())))

    def op_paste(self, at=None):
        cb = self.clipboard
        if not cb:
            return self.set_status(T('Буфер пуст — сначала скопируйте (Ctrl+C)'))
        sg = self.song
        total = sg.total_steps
        at = self.snap_floor(self.cursor) if at is None else at
        if at >= total:
            return
        self.push_history(T('Вставка в {0}').format(bb(at)))
        dests = []
        for ti, items in cb['data'].items():
            dest = self.sel_track if (self.mode == 'edit' and len(cb['data']) == 1) else ti
            tr = sg.tracks[dest]
            if (tr.kind == 'drums') != (sg.tracks[ti].kind == 'drums'):
                continue
            dests.append(dest)
            if self.mode == 'arrange':
                tr.notes = [n for n in tr.notes if not (at <= n.s < at + cb['span'])]
            for ds, ln, p, v in items:
                s = at + ds
                if s < total:
                    tr.notes.append(Note(s, min(ln, total - s), p, v))
        if dests:
            self.sel = dict(t0=min(dests), t1=max(dests), s0=at, s1=min(total, at + cb['span']))
        self.sel_notes = set()
        self._finish_edit(T('⎘ Вставлено в такт {0}').format(bb(at)))

    def op_duplicate(self):
        reg = self.get_region()
        if not reg:
            return self.set_status(T('Выделите область для дублирования'))
        self.op_copy()
        self.sel_notes = set()
        self.op_paste(at=reg[2])
        self.cursor = min(self.song.total_steps - 1, reg[2])
        self._place_cursor()

    def op_select_all(self):
        if self.mode == 'edit':
            self.sel_notes = set(self.cur_track().notes)
        else:
            self.sel = dict(t0=0, t1=len(self.song.tracks) - 1, s0=0, s1=self.song.total_steps)
        self.redraw_all()

    def clear_selection(self):
        self.sel = None
        self.sel_notes = set()
        self.redraw_all()

    def move_notes(self, ds):
        if not self.sel_notes:
            return
        total = self.song.total_steps
        self.push_history_coalesced(T('Сдвиг нот'), ('move',))
        for n in self.sel_notes:
            n.s = int(clamp(n.s + ds, 0, total - n.l))
        self._finish_edit(T('Ноты сдвинуты'))

    def set_chord(self, slot, d):
        self.push_history(T('Аккорд №{0} → {1}').format(slot + 1, chord_name(self.song, d)))
        self.song.chords[slot] = d
        self.after_song_change(keep_sel=True)
        self.set_status(T('Аккорд изменён. Чтобы партии подстроились — пересоздайте этот кусок (ПКМ по аккорду)'))

    def transpose_song(self, k):
        sg = self.song
        self.push_history(T('Транспонирование песни {0:+d}').format(k))
        sg.key = (sg.key + k) % 12
        for tr in sg.tracks:
            if tr.kind != 'drums':
                for n in tr.notes:
                    n.p = int(clamp(n.p + k, 0, 127))
        self.v_key.set(NOTE_NAMES[sg.key])
        self.after_song_change(keep_sel=True)
        self.set_status(T('Песня теперь в тональности {0}').format(NOTE_NAMES[sg.key]))

    def append_bars(self, n=4):
        sg = self.song
        if sg.bars + n > 128:
            return self.set_status(T('Максимум 128 тактов'))
        self.push_history(T('+{0} тактов').format(n))
        old_total = sg.total_steps
        base = sg.chords[:] or [0]
        sg.bars += n
        while len(sg.chords) < max(1, sg.total_steps // sg.chord_steps):
            sg.chords.append(base[len(sg.chords) % len(base)])
        self._update_character()
        comp = Composer(sg, random.Random(random.randrange(1, 2 ** 31)))
        for i, tr in enumerate(sg.tracks):
            if tr.notes or (i < len(self.v_include) and self.v_include[i].get()):
                tr.notes += comp.generate(tr, old_total, sg.total_steps, allow_repeat=True)
        self.after_song_change(keep_sel=True)
        self.zoom_fit()
        self.set_status(T('Добавлено {0} такта — теперь {1}').format(n, sg.bars))

    def remove_bars(self, n=4):
        sg = self.song
        if sg.bars - n < 2:
            return self.set_status(T('Песня и так короткая'))
        self.push_history(T('−{0} тактов').format(n))
        sg.bars -= n
        total = sg.total_steps
        for tr in sg.tracks:
            tr.notes = [q for q in tr.notes if q.s < total]
            for q in tr.notes:
                q.l = min(q.l, total - q.s)
        del sg.chords[max(1, total // sg.chord_steps):]
        self.after_song_change(keep_sel=True)
        self.zoom_fit()

    def _on_track_param(self, fname):
        if self._loading or not self.song:
            return
        tr = self.cur_track()
        try:
            if fname == 'wave':
                val = WAVE_KEYS.get(self.tv_wave.get(), tr.wave)
            elif fname == 'duty':
                val = DUTY_VALUES.get(self.tv_duty.get(), tr.duty)
            elif fname == 'octave':
                val = int(self.tv_octave.get().replace('+', ''))
            elif fname == 'kit':
                val = self.tv_kit.get()
            elif fname == 'vowel':
                val = VOWEL_KEYS.get(self.tv_vowel.get(), tr.vowel)
            elif fname == 'mute':
                val = bool(self.tv_mute.get())
            elif fname == 'solo':
                val = bool(self.tv_solo.get())
            else:
                val = round(float(self.tv[fname].get()), 4)
        except (tk.TclError, ValueError):
            return
        if getattr(tr, fname) == val:
            return
        self.push_history_coalesced(T('Звук «{0}»: {1}').format(T(tr.name), fname), ('tp', self.sel_track, fname))
        setattr(tr, fname, val)
        if fname in ('mute', 'solo', 'wave', 'kit', 'volume'):
            self.redraw_head()
            if fname in ('mute', 'solo'):
                self.redraw_lanes()
        self.schedule_refresh()

    def apply_preset(self):
        name = self.tv_preset.get()
        if name not in SOUND_PRESETS:
            return
        tr = self.cur_track()
        self.push_history(T('Пресет «{0}» → {1}').format(T(name), T(tr.name)))
        for k, v in SOUND_PRESETS[name].items():
            if tr.kind == 'drums' and k == 'wave':
                continue
            setattr(tr, k, v)
        self.load_track_panel()
        self.redraw_head()
        self.schedule_refresh()
        self.set_status(T('Пресет «{0}» применён к треку «{1}»').format(T(name), T(tr.name)))
        self.preview_track_sound()

    def reset_sound(self):
        tr = self.cur_track()
        refs = default_tracks(self.song.params.get('chip', 'nes'))
        ref = next((r for r in refs if r.kind == tr.kind), refs[0])
        self.push_history(T('Сброс звука «{0}»').format(T(tr.name)))
        for f in SOUND_FIELDS:
            setattr(tr, f, getattr(ref, f))
        self.load_track_panel()
        self.redraw_head()
        self.schedule_refresh()

    def clear_track(self):
        tr = self.cur_track()
        if not tr.notes:
            return
        self.push_history(T('Очистка трека «{0}»').format(T(tr.name)))
        tr.notes = []
        self.after_song_change(keep_sel=True)

    def pick_color(self):
        tr = self.cur_track()
        res = colorchooser.askcolor(tr.color, title=T('Цвет трека «{0}»').format(T(tr.name)))
        if res and res[1]:
            self.push_history(T('Цвет «{0}»').format(T(tr.name)))
            tr.color = res[1]
            self.load_track_panel()
            self.redraw_all()

    def rename_track(self):
        tr = self.cur_track()
        name = simpledialog.askstring(APP_NAME, T('Новое имя трека:'), initialvalue=T(tr.name), parent=self.root)
        if name and name.strip():
            self.push_history(T('Переименование «{0}»').format(T(tr.name)))
            tr.name = name.strip()[:24]
            self.refresh_track_names()
            self.load_track_panel()
            self.redraw_all()

    def _on_bpm(self):
        if self._loading or not self.song:
            return
        b = int(round(self.v_bpm.get()))
        if b == round(self.song.bpm):
            return
        self.push_history_coalesced(T('Темп'), ('bpm',))
        self.song.bpm = b
        self.update_info()
        self.redraw_time()
        self.schedule_refresh()

    def _on_swing(self):
        if self._loading or not self.song:
            return
        s = round(self.v_swing.get(), 3)
        if s == self.song.swing:
            return
        self.push_history_coalesced(T('Свинг'), ('swing',))
        self.song.swing = s
        self.schedule_refresh()

    def _on_master_change(self):
        self.schedule_refresh()

    def master_settings(self):
        return dict(volume=self.v_mvol.get(), sr=int(self.v_sr.get()), bits=int(self.v_bits.get()),
                    downsample=int(round(self.v_down.get())), smooth=int(round(self.v_smooth.get())),
                    nes_env=self.v_nes_env.get(), normalize=self.v_norm.get())
