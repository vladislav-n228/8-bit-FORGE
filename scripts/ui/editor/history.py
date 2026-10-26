# -*- coding: utf-8 -*-
"""История действий: ◀ Назад / Вперёд ▶."""

import copy
import time

from scripts.core.i18n import T
from scripts.core.theory import clamp


class HistoryMixin:
    """История действий: ◀ Назад / Вперёд ▶."""

    def push_history(self, label, pre=None):
        self.undo_stack.append((label, pre if pre is not None else copy.deepcopy(self.song)))
        if len(self.undo_stack) > 150:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._coalesce = (None, 0.0)
        self.update_history_ui()

    def push_history_coalesced(self, label, key):
        now = time.time()
        if self._coalesce[0] == key and now - self._coalesce[1] < 2.0 and self.undo_stack:
            self._coalesce = (key, now)
            return
        self.push_history(label)
        self._coalesce = (key, now)

    def undo(self):
        if not self.undo_stack:
            self.set_status(T('Назад: нечего отменять'))
            return
        label, snap = self.undo_stack.pop()
        self.redo_stack.append((label, copy.deepcopy(self.song)))
        self.song = snap
        self.after_song_change(keep_sel=True)
        self.set_status(T('◀ Отменено: {0}').format(label))

    def redo(self):
        if not self.redo_stack:
            self.set_status(T('Вперёд: нечего повторять'))
            return
        label, snap = self.redo_stack.pop()
        self.undo_stack.append((label, copy.deepcopy(self.song)))
        self.song = snap
        self.after_song_change(keep_sel=True)
        self.set_status(T('Вперёд ▶ Повторено: {0}').format(label))

    def history_jump(self, _e=None):
        sel = self.lb_hist.curselection()
        if not sel:
            return
        i, cur = sel[0], len(self.undo_stack)
        if i < cur:
            for _ in range(cur - i):
                self.undo()
        elif i > cur:
            for _ in range(i - cur):
                self.redo()

    def clear_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_history_ui()
        self.set_status(T('История очищена'))

    def update_history_ui(self):
        self.btn_undo.state(['!disabled'] if self.undo_stack else ['disabled'])
        self.btn_redo.state(['!disabled'] if self.redo_stack else ['disabled'])
        lb = self.lb_hist
        lb.delete(0, 'end')
        for i, (label, _) in enumerate(self.undo_stack):
            lb.insert('end', f'  {i + 1:>3}. {label}')
        lb.insert('end', T('  ●  Текущее состояние'))
        lb.itemconfigure('end', foreground=self.c['accent_text'])
        for label, _ in reversed(self.redo_stack):
            lb.insert('end', f'   ↷  {label}')
            lb.itemconfigure('end', foreground=self.c['muted'])
        lb.see(len(self.undo_stack))

    def after_song_change(self, keep_sel=False, keep_notes=False):
        sg = self.song
        total = sg.total_steps
        if keep_notes:
            live = {n for t in sg.tracks for n in t.notes}
            self.sel_notes &= live
        else:
            self.sel_notes = set()
        if not keep_sel:
            self.sel = None
        elif self.sel:
            s = self.sel
            s['s1'] = min(s['s1'], total)
            s['t1'] = min(s['t1'], len(sg.tracks) - 1)
            if s['s0'] >= s['s1']:
                self.sel = None
        self.cursor = int(clamp(self.cursor, 0, total - 1))
        self.sel_track = int(clamp(self.sel_track, 0, len(sg.tracks) - 1))
        self._loading = True
        try:
            self.v_bpm.set(sg.bpm)
            self.v_swing.set(sg.swing)
        finally:
            self._loading = False
        self.refresh_track_names()
        self.load_track_panel()
        self.redraw_all()
        self.update_history_ui()
        self.update_cache_ui()
        self.schedule_refresh()
