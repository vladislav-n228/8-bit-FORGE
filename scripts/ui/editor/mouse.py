# -*- coding: utf-8 -*-
"""Мышь: выделение и рисование на дорожках, заголовки, линейка, колесо и масштаб."""

import copy
import tkinter as tk

from scripts.core.constants import DRUM_PITCHES, DRUM_ROWS, ROMAN
from scripts.core.i18n import T
from scripts.core.model import Note
from scripts.core.theory import chord_name, clamp
from scripts.ui.style import HEAD_W, LANE_H, PMAX, PMIN


class MouseMixin:
    """Мышь: выделение и рисование на дорожках, заголовки, линейка, колесо и масштаб."""

    def _ev_xy(self, e):
        return self.lanes.canvasx(e.x), self.lanes.canvasy(e.y)

    def on_lanes_press(self, e):
        if not self.song:
            return
        self.lanes.focus_set()
        x, y = self._ev_xy(e)
        if self.mode == 'arrange':
            ti = int(clamp(y // LANE_H, 0, len(self.song.tracks) - 1))
            if ti != self.sel_track:
                self.sel_track = ti
                self.refresh_track_names()
                self.load_track_panel()
            self.drag = dict(kind='asel', x0=x, step0=x / self.pps, t0=ti, moved=False)
        else:
            self._roll_press(x, y, 1, bool(e.state & 0x1))

    def on_lanes_motion(self, e):
        d = self.drag
        if not d:
            return
        x, y = self._ev_xy(e)
        total = self.song.total_steps
        if d['kind'] == 'asel':
            if abs(x - d['x0']) < 4 and not d['moved']:
                return
            d['moved'] = True
            ti = int(clamp(y // LANE_H, 0, len(self.song.tracks) - 1))
            a, b = d['step0'], clamp(x / self.pps, 0, total)
            lo, hi = min(a, b), max(a, b)
            s0, s1 = self.snap_floor(lo), min(total, self.snap_ceil(hi))
            if s1 <= s0:
                s1 = min(total, s0 + self.snap)
            self.sel = dict(t0=min(ti, d['t0']), t1=max(ti, d['t0']), s0=s0, s1=s1)
            self.redraw_lanes()
            self.redraw_ruler()
            self.update_sel_info()
        else:
            self._roll_motion(x, y)

    def on_lanes_release(self, e):
        d = self.drag
        if not d:
            return
        x, y = self._ev_xy(e)
        if d['kind'] == 'asel':
            if not d['moved']:
                self.sel = None
                self.cursor = int(clamp(self.snap_floor(x / self.pps), 0, self.song.total_steps - 1))
                self.redraw_all()
            else:
                self.set_status(T('Область выделена — нажмите «♻ Recreate another piece» (R), чтобы заменить кусок'))
                self.redraw_head()
            self.drag = None
        else:
            self._roll_release(x, y)

    def on_lanes_double(self, e):
        if self.mode == 'arrange':
            x, y = self._ev_xy(e)
            self.drag = None
            self.select_track(int(clamp(y // LANE_H, 0, len(self.song.tracks) - 1)))
            self.set_mode('edit')

    def on_lanes_right(self, e):
        if self.mode != 'edit':
            return
        x, y = self._ev_xy(e)
        tr = self.cur_track()
        hit = self._note_at(tr, x / self.pps, int(y // self.row_h()))
        if hit:
            self.push_history(T('Удаление ноты'))
            tr.notes.remove(hit)
            self.sel_notes.discard(hit)
            self.redraw_lanes()
            self.update_info()
            self.schedule_refresh()

    def on_lanes_hover(self, e):
        if self.mode != 'edit' or self.drag:
            return
        x, y = self._ev_xy(e)
        hit = self._note_at(self.cur_track(), x / self.pps, int(y // self.row_h()))
        edge = hit and x >= (hit.s + hit.l) * self.pps - max(4, min(8, self.pps * .4))
        self.lanes.configure(cursor='sb_h_double_arrow' if edge else ('fleur' if hit else ''))

    def _note_at(self, tr, step_f, row):
        for n in reversed(tr.notes):
            if self.pitch_to_row(n.p) == row and n.s <= step_f < n.s + n.l:
                return n
        return None

    def _roll_press(self, x, y, button, shift):
        tr = self.cur_track()
        total = self.song.total_steps
        step_f = x / self.pps
        row = int(y // self.row_h())
        if row >= self.roll_rows() or step_f >= total:
            return
        pitch = self.row_to_pitch(row)
        hit = self._note_at(tr, step_f, row)
        tool = self.v_tool.get()
        if tool == 'erase':
            self.drag = dict(kind='erase', pushed=False)
            self._erase_at(x, y)
            return
        if hit:
            if shift:
                self.sel_notes ^= {hit}
            elif hit not in self.sel_notes:
                self.sel_notes = {hit}
            edge = x >= (hit.s + hit.l) * self.pps - max(4, min(8, self.pps * .4))
            self.drag = dict(kind='resize' if edge else 'move', note=hit, pre=copy.deepcopy(self.song),
                             orig={n: (n.s, n.p, n.l) for n in self.sel_notes | {hit}},
                             step0=step_f, row0=row, x0=x, changed=False, last_dr=0)
            self.preview_note(tr, hit.p)
        elif tool == 'draw':
            s = self.snap_floor(step_f)
            ln = 1 if tr.kind == 'drums' else min(self.note_len, total - s)
            self.push_history(T('Новая нота'))
            n = Note(s, ln, pitch, 0.8)
            tr.notes.append(n)
            tr.notes.sort(key=lambda q: (q.s, q.p))
            self.sel_notes = {n}
            self.drag = dict(kind='resize' if tr.kind != 'drums' else 'none', note=n, orig={n: (n.s, n.p, n.l)},
                             step0=step_f, row0=row, x0=x, changed=True, new=True, last_dr=0)
            self.preview_note(tr, pitch)
        else:
            if not shift:
                self.sel_notes = set()
            self.drag = dict(kind='rubber', x0=x, y0=y)
        self.redraw_lanes()
        self.update_sel_info()

    def _erase_at(self, x, y):
        tr = self.cur_track()
        hit = self._note_at(tr, x / self.pps, int(y // self.row_h()))
        if hit:
            if not self.drag.get('pushed'):
                self.push_history(T('Стирание нот'))
                self.drag['pushed'] = True
            tr.notes.remove(hit)
            self.sel_notes.discard(hit)
            self.redraw_lanes()

    def _roll_motion(self, x, y):
        d = self.drag
        tr = self.cur_track()
        total = self.song.total_steps
        step_f = clamp(x / self.pps, 0, total)
        row = int(clamp(y // self.row_h(), 0, self.roll_rows() - 1))
        k = d['kind']
        if k == 'erase':
            self._erase_at(x, y)
            return
        if k == 'rubber':
            d['x1'], d['y1'] = x, y
        elif k == 'move':
            ds = int(round((step_f - d['step0']) / self.snap)) * self.snap
            dr = row - d['row0']
            for n, (s, p, l) in d['orig'].items():
                n.s = int(clamp(s + ds, 0, total - l))
                if tr.kind == 'drums':
                    n.p = DRUM_PITCHES[int(clamp(self.pitch_to_row(p) + dr, 0, len(DRUM_ROWS) - 1))]
                else:
                    n.p = int(clamp(p - dr, PMIN, PMAX))
            d['changed'] = d['changed'] or ds != 0 or dr != 0
            if dr != d['last_dr']:
                d['last_dr'] = dr
                self.preview_note(tr, d['note'].p)
        elif k == 'resize':
            if abs(x - d['x0']) < 3 and not d.get('resized'):
                return
            d['resized'] = True
            n = d['note']
            end = max(n.s + 1, self.snap_ceil(step_f))
            n.l = int(clamp(end - n.s, 1, total - n.s))
            d['changed'] = True
        else:
            return
        self.redraw_lanes()

    def _roll_release(self, x, y):
        d = self.drag
        self.drag = None
        if not d:
            return
        tr = self.cur_track()
        k = d['kind']
        if k in ('move', 'resize'):
            if d['changed'] and not d.get('new'):
                self.push_history(T('Перемещение нот') if k == 'move' else T('Длина ноты'), pre=d['pre'])
            tr.notes.sort(key=lambda q: (q.s, q.p))
            if d['changed']:
                self.schedule_refresh()
        elif k == 'rubber':
            x0, x1 = sorted((d['x0'], x))
            y0, y1 = sorted((d['y0'], y))
            if x1 - x0 < 4 and y1 - y0 < 4:
                self.sel = None
                self.cursor = int(clamp(self.snap_floor(x / self.pps), 0, self.song.total_steps - 1))
            else:
                s_lo, s_hi = x0 / self.pps, x1 / self.pps
                r_lo, r_hi = int(y0 // self.row_h()), int(y1 // self.row_h())
                for n in tr.notes:
                    if n.s < s_hi and n.s + n.l > s_lo and r_lo <= self.pitch_to_row(n.p) <= r_hi:
                        self.sel_notes.add(n)
                total = self.song.total_steps
                self.sel = dict(t0=self.sel_track, t1=self.sel_track, s0=self.snap_floor(s_lo),
                                s1=min(total, max(self.snap_floor(s_lo) + self.snap, self.snap_ceil(s_hi))))
        elif k in ('none', 'erase'):
            if d.get('pushed') or d.get('new'):
                self.schedule_refresh()
        self.redraw_all()

    def on_head_press(self, e):
        y = self.head.canvasy(e.y)
        x = e.x
        if self.mode == 'edit':
            r = int(y // self.row_h())
            if 0 <= r < self.roll_rows():
                self.preview_note(self.cur_track(), self.row_to_pitch(r), force=True)
            return
        i = int(y // LANE_H)
        if not (0 <= i < len(self.song.tracks)):
            return
        tr = self.song.tracks[i]
        ly = y - i * LANE_H
        if 6 <= ly <= 24 and HEAD_W - 58 <= x <= HEAD_W - 6:
            attr = 'mute' if x < HEAD_W - 32 else 'solo'
            self.push_history(f'{"Mute" if attr == "mute" else "Solo"} «{T(tr.name)}»')
            setattr(tr, attr, not getattr(tr, attr))
            self.sel_track = i
            self.refresh_track_names()
            self.load_track_panel()
            self.redraw_head()
            self.redraw_lanes()
            self.schedule_refresh()
            return
        if ly >= LANE_H - 19 and 10 <= x <= HEAD_W - 6:
            self.push_history(T('Громкость «{0}»').format(T(tr.name)))
            self.drag = dict(kind='vol', i=i)
            self.on_head_motion(e)
            return
        self.select_track(i)

    def on_head_motion(self, e):
        d = self.drag
        if not d or d.get('kind') != 'vol':
            return
        tr = self.song.tracks[d['i']]
        tr.volume = round(clamp((e.x - 14) / (HEAD_W - 24), 0, 1), 3)
        if d['i'] == self.sel_track:
            self.load_track_panel()
        self.redraw_head()
        self.set_status(T('Громкость «{0}»: {1:.0f}%').format(T(tr.name), tr.volume * 100))
        self.schedule_refresh()

    def on_head_double(self, e):
        if self.mode == 'arrange':
            self.rename_track()

    def on_ruler_press(self, e):
        x, y = self.ruler.canvasx(e.x), e.y
        if y >= 24:
            slot = int(x / self.pps // self.song.chord_steps)
            if 0 <= slot < len(self.song.chords):
                self.chord_menu(slot, e)
            return
        self.on_ruler_motion(e)

    def on_ruler_motion(self, e):
        if e.y >= 24 and str(e.type) == 'ButtonPress':
            return
        x = self.ruler.canvasx(e.x)
        self.cursor = int(clamp(self.snap_floor(x / self.pps), 0, self.song.total_steps - 1))
        self._place_cursor()

    def on_ruler_right(self, e):
        slot = int(self.ruler.canvasx(e.x) / self.pps // self.song.chord_steps)
        if 0 <= slot < len(self.song.chords):
            self.chord_menu(slot, e)

    def chord_menu(self, slot, e):
        sg = self.song
        m = tk.Menu(self.root, tearoff=0)
        self.apply_theme_menu(m)
        m.add_command(label=T('Аккорд №{0} (сейчас {1})').format(slot + 1, chord_name(sg, sg.chords[slot])), state='disabled')
        m.add_separator()
        for d in range(7):
            m.add_command(label=f'{ROMAN[d]:>4}   {chord_name(sg, d)}', command=lambda d=d: self.set_chord(slot, d))
        m.add_separator()
        cs = sg.chord_steps
        m.add_command(label=T('♻ Пересоздать все треки под этим аккордом'),
                      command=lambda: self.recreate(list(range(len(sg.tracks))), slot * cs,
                                                    min(sg.total_steps, (slot + 1) * cs)))
        m.tk_popup(e.x_root, e.y_root)

    def apply_theme_menu(self, m):
        c = self.c
        m.configure(bg=c['panel'], fg=c['fg'], activebackground=c['accent'], activeforeground=c['accent_fg'],
                    disabledforeground=c['muted'])

    def _on_wheel(self, e):
        w = self.root.winfo_containing(e.x_root, e.y_root)
        if w is None:
            return
        units = -1 if e.delta > 0 else 1
        if w in (self.lanes, self.head, self.ruler):
            if e.state & 0x4:
                self.zoom(1.25 if e.delta > 0 else 0.8, anchor_x=e.x if w is self.lanes else None)
                return 'break'
            fits = self._content_height() <= self.lanes.winfo_height()
            if e.state & 0x1 or w is self.ruler or (self.mode == 'arrange' and fits):
                self.lanes.xview_scroll(units * 3, 'units')
            else:
                self.lanes.yview_scroll(units * 2, 'units')
            return 'break'
        path = str(w)
        for sf in self.scrollframes:
            if path.startswith(str(sf)) and sf.winfo_ismapped():
                sf.scroll(units * 2)
                return

    def zoom(self, factor, anchor_x=None):
        old = self.pps
        new = clamp(old * factor, 2.0, 60.0)
        if abs(new - old) < 1e-6:
            return
        ax = anchor_x if anchor_x is not None else self.lanes.winfo_width() / 2
        step_at = self.lanes.canvasx(ax) / old
        self.pps = new
        self.redraw_all()
        W = self.song.total_steps * new + 60
        self.lanes.xview_moveto(max(0.0, (step_at * new - ax) / W))

    def zoom_fit(self):
        if not self.song:
            return
        vis = max(200, self.lanes.winfo_width() - 30)
        self.pps = clamp(vis / self.song.total_steps, 2.0, 60.0)
        self.redraw_all()
        self.lanes.xview_moveto(0)
