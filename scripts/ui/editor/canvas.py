# -*- coding: utf-8 -*-
"""Геометрия и отрисовка дорожек, пиано-ролла и линейки; режимы и выбор трека."""

import math

from scripts.core.constants import DRUM_PITCHES, DRUM_ROWS, DUTY_NAMES, NOTE_NAMES, SCALES, VOWEL_NAMES, WAVE_NAMES
from scripts.core.i18n import T
from scripts.core.theory import bb, blend, chord_at, chord_name, clamp, fmt_time, midi_name
from scripts.music.structure import fmt_bpm
from scripts.ui.style import FONT_B, FONT_S, FONT_SB, HEAD_W, LANE_H, PMAX, PMIN, RULER_H, SNAPS


class CanvasMixin:
    """Геометрия и отрисовка дорожек, пиано-ролла и линейки; режимы и выбор трека."""

    def cur_track(self):
        return self.song.tracks[self.sel_track]

    @property
    def snap(self):
        return SNAPS.get(self.v_snap.get(), 4)

    @property
    def note_len(self):
        return SNAPS.get(self.v_note_len.get(), 2)

    def snap_floor(self, x):
        return int(x // self.snap) * self.snap

    def snap_ceil(self, x):
        return int(math.ceil(x / self.snap - 1e-9)) * self.snap

    def is_drum_roll(self):
        return self.cur_track().kind == 'drums'

    def roll_rows(self):
        return len(DRUM_ROWS) if self.is_drum_roll() else PMAX - PMIN + 1

    def row_h(self):
        return 30 if self.is_drum_roll() else 13

    def pitch_to_row(self, p):
        if self.is_drum_roll():
            return DRUM_PITCHES.index(p) if p in DRUM_PITCHES else 2
        return PMAX - p

    def row_to_pitch(self, r):
        if self.is_drum_roll():
            return DRUM_PITCHES[int(clamp(r, 0, len(DRUM_ROWS) - 1))]
        return int(clamp(PMAX - r, PMIN, PMAX))

    def _content_height(self):
        if self.mode == 'arrange':
            return len(self.song.tracks) * LANE_H
        return self.roll_rows() * self.row_h()

    def _xscroll(self, first, last):
        self.hbar.set(first, last)
        self.ruler.xview_moveto(first)

    def _yscroll(self, first, last):
        self.vbar.set(first, last)
        self.head.yview_moveto(first)

    def redraw_all(self):
        if not self.song:
            return
        self.redraw_ruler()
        self.redraw_head()
        self.redraw_lanes()
        self.update_sel_info()
        self.update_info()
        self.redraw_time()

    def redraw_ruler(self):
        r, c, sg, pps = self.ruler, self.c, self.song, self.pps
        r.delete('all')
        W = sg.total_steps * pps
        r.configure(scrollregion=(0, 0, W + 60, RULER_H))
        r.create_rectangle(0, 0, W, RULER_H, fill=c['panel'], outline='')
        reg = self.get_region()
        if reg:
            r.create_rectangle(reg[1] * pps, 0, reg[2] * pps, 22, fill=blend(c['panel'], c['accent'], .35), outline='')
        for bar in range(sg.bars):
            x = bar * 16 * pps
            r.create_line(x, 0, x, RULER_H, fill=c['grid_bar'])
            if pps * 16 >= 18 or bar % 4 == 0:
                r.create_text(x + 4, 11, text=str(bar + 1), anchor='w', fill=c['fg'], font=FONT_SB)
            for b in (1, 2, 3):
                xb = x + b * 4 * pps
                r.create_line(xb, 16, xb, 22, fill=c['grid_bar'])
        cs = sg.chord_steps
        for i, deg in enumerate(sg.chords):
            x0, x1 = i * cs * pps, (i + 1) * cs * pps
            r.create_rectangle(x0 + 1, 24, x1 - 1, RULER_H - 2, fill=c['panel2'], outline=c['border'])
            if x1 - x0 > 26:
                r.create_text((x0 + x1) / 2, 34, text=chord_name(sg, deg), fill=c['accent_text'], font=FONT_SB)
        ds = sg.params.get('drop_step')
        if ds and ds < sg.total_steps:
            r.create_rectangle(ds * pps, 0, ds * pps + 40, 14, fill='#ff3d8b', outline='')
            r.create_text(ds * pps + 4, 7, text=T('ДРОП'), anchor='w', fill='#0b0b12', font=FONT_SB)
        x = self.cursor * pps
        r.create_polygon(x - 6, 0, x + 6, 0, x, 9, fill=c['accent'], outline='', tags='cursor')
        r.create_line(-10, 0, -10, RULER_H, fill=c['fg'], width=2, tags='playhead')
        self.corner.delete('all')
        self.corner.create_rectangle(0, 0, HEAD_W, RULER_H, fill=c['panel'], outline='')
        title = T('ДОРОЖКИ') if self.mode == 'arrange' else f'✎ {T(self.cur_track().name)}'
        self.corner.create_text(12, 14, text=title, anchor='w', fill=c['accent_text'], font=FONT_B)
        self.corner.create_text(12, 33, text=T('такты / аккорды  →'), anchor='w', fill=c['muted'], font=FONT_S)

    def redraw_head(self):
        h, c, sg = self.head, self.c, self.song
        h.delete('all')
        H = self._content_height()
        h.configure(scrollregion=(0, 0, HEAD_W, H))
        if self.mode == 'arrange':
            for i, tr in enumerate(sg.tracks):
                y0 = i * LANE_H
                h.create_rectangle(0, y0, HEAD_W, y0 + LANE_H, fill=c['panel2'] if i == self.sel_track else c['panel'],
                                   outline=c['border'])
                h.create_rectangle(0, y0, 5, y0 + LANE_H, fill=tr.color, outline='')
                h.create_text(14, y0 + 15, anchor='w', text=f'{i + 1}. {T(tr.name)}', font=FONT_B, fill=c['fg'])
                sub = T('ударные · {0}').format(tr.kit) if tr.kind == 'drums' else T(WAVE_NAMES.get(tr.wave, tr.wave))
                h.create_text(14, y0 + 33, anchor='w', text=sub, font=FONT_S, fill=c['muted'])
                for j, (lbl, on, col) in enumerate((('M', tr.mute, '#ff9f1c'), ('S', tr.solo, '#ffd23d'))):
                    x0 = HEAD_W - 58 + j * 28
                    h.create_rectangle(x0, y0 + 6, x0 + 24, y0 + 24, fill=col if on else c['panel2'], outline=c['border'])
                    h.create_text(x0 + 12, y0 + 15, text=lbl, font=FONT_SB, fill=c['accent_fg'] if on else c['muted'])
                h.create_oval(HEAD_W - 26, y0 + 30, HEAD_W - 16, y0 + 40, fill=c['grid_beat'], outline='', tags=f'led{i}')
                yb = y0 + LANE_H - 15
                h.create_rectangle(14, yb, HEAD_W - 10, yb + 6, fill=c['panel2'], outline=c['border'])
                h.create_rectangle(14, yb, 14 + (HEAD_W - 24) * clamp(tr.volume, 0, 1), yb + 6, fill=tr.color, outline='')
        else:
            rh = self.row_h()
            if self.is_drum_roll():
                for r, (p, name) in enumerate(DRUM_ROWS):
                    y = r * rh
                    h.create_rectangle(0, y, HEAD_W, y + rh, fill=c['panel2'] if r % 2 else c['panel'], outline=c['border'])
                    h.create_text(14, y + rh / 2, anchor='w', text=T(name), fill=c['fg'], font=FONT_B)
            else:
                for r in range(self.roll_rows()):
                    p, y = PMAX - r, r * rh
                    black = p % 12 in (1, 3, 6, 8, 10)
                    h.create_rectangle(HEAD_W - 70 if black else HEAD_W - 110, y, HEAD_W, y + rh,
                                       fill=c['key_black'] if black else c['key_white'], outline=c['border'])
                    if p % 12 == 0:
                        h.create_text(HEAD_W - 116, y + rh / 2, anchor='e', text=midi_name(p), fill=c['muted'], font=FONT_S)

    def _draw_grid(self, cv, W, H):
        c, pps, total = self.c, self.pps, self.song.total_steps
        if pps >= 4:
            for s in range(total + 1):
                if s % 16 == 0 or (s % 4 and pps < 9):
                    continue
                x = s * pps
                cv.create_line(x, 0, x, H, fill=c['grid_beat'] if s % 4 == 0 else c['grid'])
        for s in range(0, total + 1, 16):
            cv.create_line(s * pps, 0, s * pps, H, fill=c['grid_bar'])

    def redraw_lanes(self):
        cv, c = self.lanes, self.c
        cv.delete('all')
        W = self.song.total_steps * self.pps
        H = self._content_height()
        cv.configure(scrollregion=(0, 0, W + 60, H))
        if self.mode == 'arrange':
            self._draw_arrange(cv, W, H)
        else:
            self._draw_roll(cv, W, H)
        x = self.cursor * self.pps
        cv.create_line(x, 0, x, H, fill=c['accent'], dash=(4, 3), tags='cursor')
        cv.create_line(-10, 0, -10, H, fill=c['fg'], width=2, tags='playhead')
        if self.playing:
            self._set_playhead(self.play_step)

    def _draw_arrange(self, cv, W, H):
        c, sg, pps = self.c, self.song, self.pps
        solo = any(t.solo for t in sg.tracks)
        for i, tr in enumerate(sg.tracks):
            y0 = i * LANE_H
            bg = c['lane_alt'] if i % 2 else c['lane']
            if i == self.sel_track:
                bg = blend(bg, tr.color, .07)
            cv.create_rectangle(0, y0, W, y0 + LANE_H, fill=bg, outline='')
        self._draw_grid(cv, W, H)
        for i, tr in enumerate(sg.tracks):
            y0 = i * LANE_H
            cv.create_line(0, y0 + LANE_H, W, y0 + LANE_H, fill=c['border'])
            lane = c['lane_alt'] if i % 2 else c['lane']
            active = not (tr.mute or (solo and not tr.solo))
            base = tr.color if active else blend(tr.color, lane, .7)
            if not tr.notes:
                cv.create_text(10, y0 + LANE_H / 2, anchor='w', fill=c['muted'], font=FONT_S,
                               text=T('пусто — выделите область и нажмите ♻ Recreate another piece'))
                continue
            if tr.kind == 'drums':
                rh = (LANE_H - 12) / len(DRUM_ROWS)
                for n in tr.notes:
                    r = DRUM_PITCHES.index(n.p) if n.p in DRUM_PITCHES else 2
                    y, x = y0 + 6 + r * rh, n.s * pps
                    cv.create_rectangle(x + 1, y + 1, x + max(pps - 1, 2), y + rh - 1,
                                        fill=blend(base, lane, (1 - n.v) * .5), outline='')
            else:
                lo, hi = min(n.p for n in tr.notes) - 1, max(n.p for n in tr.notes) + 1
                if hi - lo < 14:
                    mid = (hi + lo) / 2
                    lo, hi = mid - 7, mid + 7
                span = LANE_H - 18
                nh = clamp(span / (hi - lo + 1), 3, 7)
                for n in tr.notes:
                    y = y0 + 9 + (hi - n.p) / (hi - lo) * span - nh / 2
                    x0 = n.s * pps
                    x1 = max(x0 + 2, (n.s + n.l) * pps - 1)
                    cv.create_rectangle(x0 + 1, y, x1, y + nh, fill=blend(base, lane, (1 - n.v) * .45), outline='')
        if self.sel:
            s = self.sel
            x0, x1 = s['s0'] * pps, s['s1'] * pps
            ya, yb = s['t0'] * LANE_H, (s['t1'] + 1) * LANE_H
            cv.create_rectangle(x0, ya, x1, yb, fill=c['accent'], stipple='gray25', outline='')
            cv.create_rectangle(x0, ya + 1, x1, yb - 1, outline=c['accent'], width=2)
            cv.create_text(x0 + 6, ya + 5, anchor='nw', text=T('♻ R — пересоздать'), fill=c['accent_text'], font=FONT_SB)

    def _draw_roll(self, cv, W, H):
        c, sg, pps = self.c, self.song, self.pps
        tr = self.cur_track()
        rh = self.row_h()
        drums = tr.kind == 'drums'
        scale_pcs = {(sg.key + i) % 12 for i in SCALES[sg.scale]}
        for r in range(self.roll_rows()):
            y = r * rh
            if drums:
                fill = c['lane_alt'] if r % 2 else c['lane']
            else:
                p = PMAX - r
                fill = c['row_black'] if p % 12 in (1, 3, 6, 8, 10) else c['lane']
                if self.v_show_scale.get() and p % 12 in scale_pcs:
                    fill = blend(fill, c['accent'], .07)
            cv.create_rectangle(0, y, W, y + rh, fill=fill, outline='')
        self._draw_grid(cv, W, H)
        if not drums:
            for r in range(self.roll_rows()):
                if (PMAX - r) % 12 == 0:
                    cv.create_line(0, (r + 1) * rh, W, (r + 1) * rh, fill=c['grid_bar'])
        reg = self.get_region()
        if reg and self.sel_track in reg[0]:
            cv.create_rectangle(reg[1] * pps, 0, reg[2] * pps, H, fill=c['accent'], stipple='gray12', outline=c['accent'])
        if self.v_ghost.get() and not drums:
            for o in sg.tracks:
                if o is tr or o.kind == 'drums':
                    continue
                gc = blend(o.color, c['lane'], .55)
                for n in o.notes:
                    if PMIN <= n.p <= PMAX:
                        y = (PMAX - n.p) * rh
                        cv.create_rectangle(n.s * pps + 1, y + 2, (n.s + n.l) * pps - 1, y + rh - 2, outline=gc)
        dark = blend(tr.color, '#000000', .4)
        for n in tr.notes:
            r = self.pitch_to_row(n.p)
            if not drums and not (PMIN <= n.p <= PMAX):
                continue
            y = r * rh
            x0, x1 = n.s * pps, max(n.s * pps + 3, (n.s + n.l) * pps - 1)
            sel = n in self.sel_notes
            cv.create_rectangle(x0 + 1, y + 1, x1, y + rh - 1, fill=blend(tr.color, c['lane'], (1 - n.v) * .45),
                                outline=c['fg'] if sel else dark, width=2 if sel else 1)
            if not drums and x1 - x0 > 28:
                cv.create_text(x0 + 4, y + rh / 2, anchor='w', text=midi_name(n.p), fill=c['note_text'], font=FONT_S)
        d = self.drag
        if d and d.get('kind') == 'rubber' and 'x1' in d:
            cv.create_rectangle(d['x0'], d['y0'], d['x1'], d['y1'], outline=c['accent'], dash=(3, 2), width=2)

    def _place_cursor(self):
        x = self.cursor * self.pps
        H = self._content_height()
        self.lanes.coords('cursor', x, 0, x, H)
        self.ruler.coords('cursor', x - 6, 0, x + 6, 0, x, 9)
        self.redraw_time()

    def _set_playhead(self, step):
        x = step * self.pps
        self.lanes.coords('playhead', x, 0, x, self._content_height())
        self.ruler.coords('playhead', x, 0, x, RULER_H)
        if self.v_follow.get():
            W = self.song.total_steps * self.pps + 60
            left, right = self.lanes.canvasx(0), self.lanes.canvasx(self.lanes.winfo_width())
            if x < left or x > right - 30:
                self.lanes.xview_moveto(max(0.0, (x - 40) / W))

    def redraw_time(self):
        if not self.song:
            return
        sg = self.song
        step = self.play_step if self.playing else self.cursor
        self.lbl_time.configure(text=f'{fmt_time(step * sg.step_dur)} / {fmt_time(sg.total_steps * sg.step_dur)}')
        s = int(step)
        self.lbl_pos.configure(text=T('Такт {0} · доля {1} · {2}').format(s // 16 + 1, (s % 16) // 4 + 1, chord_name(sg, chord_at(sg, s))))

    def update_sel_info(self):
        reg = self.get_region()
        if not reg:
            self.lbl_sel.configure(text=T('Нет выделения — зажмите ЛКМ на дорожках и протяните'))
        else:
            tis, s0, s1 = reg
            names = ', '.join(T(self.song.tracks[i].name) for i in tis)
            extra = T(' · нот выбрано: {0}').format(len(self.sel_notes)) if self.mode == 'edit' and self.sel_notes else ''
            self.lbl_sel.configure(text=T('Выделено: {0} · такт {1} → {2} ({3} шагов){4}').format(names, bb(s0), bb(s1), s1 - s0, extra))
        self.lbl_hint.configure(text=(
            T('ЛКМ + протянуть — выделить область · клик — курсор · двойной клик — трек в редактор · '
            'Ctrl+колесо — масштаб · M/S — заглушить/соло · полоска внизу — громкость')
            if self.mode == 'arrange' else
            T('ЛКМ — нарисовать / взять ноту · за правый край — длина · ПКМ — удалить · Shift+клик — добавить к выбору · '
            '«Выделить» — рамкой · ↑↓ — высота')))

    def update_info(self):
        sg = self.song
        nn = sum(len(t.notes) for t in sg.tracks)
        dur = sg.total_steps * sg.step_dur
        self.lbl_info.configure(text=T('{0} · {1} {2} · {3} BPM · {4} тактов · {5} · нот: {6} · seed {7} · кэш: {8}').format(T(sg.style), NOTE_NAMES[sg.key], T(sg.scale), fmt_bpm(sg.bpm), sg.bars, fmt_time(dur), nn, sg.seed, len(self.cache)))

    def set_status(self, text):
        self.lbl_status.configure(text=text)

    def set_mode(self, mode):
        self.mode = mode
        self.v_mode.set(mode)
        self.sel_notes.clear()
        self.drag = None
        self.redraw_all()
        if mode == 'edit':
            self.center_roll()
        else:
            self.lanes.yview_moveto(0)

    def center_roll(self):
        tr = self.cur_track()
        if tr.kind == 'drums' or not tr.notes:
            self.lanes.yview_moveto(0 if tr.kind == 'drums' else 0.4)
            return
        mid = sum(n.p for n in tr.notes) / len(tr.notes)
        H = self._content_height()
        y = (PMAX - mid) * self.row_h() - self.lanes.winfo_height() / 2
        self.lanes.yview_moveto(clamp(y / H, 0, 1))

    def refresh_track_names(self):
        vals = [f'{i + 1} · {T(t.name)}' for i, t in enumerate(self.song.tracks)]
        for cb in self.cb_tracks:
            cb.configure(values=vals)
        self.v_edit_track.set(vals[self.sel_track])

    def select_track(self, i):
        if i is None or i < 0 or i >= len(self.song.tracks):
            return
        changed = i != self.sel_track
        self.sel_track = i
        self.refresh_track_names()
        self.load_track_panel()
        if changed:
            self.sel_notes.clear()
        self.redraw_all()
        if self.mode == 'edit' and changed:
            self.center_roll()

    def load_track_panel(self):
        tr = self.cur_track()
        self._loading = True
        try:
            for f in self.tv:
                self.tv[f].set(getattr(tr, f))
            self.tv_wave.set(WAVE_NAMES.get(tr.wave, tr.wave))
            self.tv_duty.set(DUTY_NAMES.get(tr.duty, min(DUTY_NAMES.items(), key=lambda kv: abs(kv[0] - tr.duty))[1]))
            self.tv_octave.set(f'{tr.octave:+d}' if tr.octave else '0')
            self.tv_kit.set(tr.kit)
            self.tv_vowel.set(VOWEL_NAMES.get(tr.vowel, tr.vowel))
            self.tv_mute.set(tr.mute)
            self.tv_solo.set(tr.solo)
            self.tv_preset.set('')
        finally:
            self._loading = False
        self.track_title.configure(text=f'{self.sel_track + 1}. {T(tr.name)}', foreground=tr.color)
