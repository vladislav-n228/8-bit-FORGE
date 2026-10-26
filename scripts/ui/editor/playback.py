# -*- coding: utf-8 -*-
"""Воспроизведение, плейхед, живое обновление и прослушивание звука трека."""

import copy
import dataclasses
import queue
import threading
import time
from tkinter import messagebox

import numpy as np
try:
    import winsound
except ImportError:
    winsound = None

from scripts.audio.synth import render_song
from scripts.core.i18n import T
from scripts.core.tasks import run_in_process
from scripts.core.constants import APP_NAME, RANGES
from scripts.core.model import Note, Song
from scripts.core.theory import clamp


class PlaybackMixin:
    """Воспроизведение, плейхед, живое обновление и прослушивание звука трека."""

    def play(self, s0=None, s1=None, loop=None, song=None, start=None):
        sg = song or self.song
        total = sg.total_steps
        if s0 is None:
            s0, s1 = 0, total
        s1 = min(s1, total)
        loop = self.v_loop.get() if loop is None else loop
        start = s0 if start is None else int(clamp(start, s0, s1 - 1))
        self.render_token += 1
        token = self.render_token
        snap, m = copy.deepcopy(sg), self.master_settings()
        live = song is None
        if not self.playing:
            self.pending = True
            self.btn_play.configure(text=T('…  Рендер'))

        def work():
            try:
                audio, sr = run_in_process(render_song, snap, m, s0 if loop else start, s1, loop=loop)
                self.jobs.put(lambda: self._begin(token, audio, sr, snap, s0, s1, start, loop, live))
            except Exception as ex:  # noqa
                err = ex
                self.jobs.put(lambda: self._render_failed(token, err))
        threading.Thread(target=work, daemon=True).start()

    def _render_failed(self, token, err):
        if token == self.render_token:
            self.stop()
            messagebox.showerror(APP_NAME, T('Ошибка рендера:\n{0}').format(err))

    def _begin(self, token, audio, sr, snap, s0, s1, start, loop, live):
        if token != self.render_token:
            return
        sd = snap.step_dur
        offset = 0.0
        if loop:
            off = int((start - s0) * sd * sr) % max(1, len(audio))
            if off:
                audio = np.roll(audio, -off, axis=0)
            offset = off / sr
            base = s0
        else:
            base = start
        try:
            self.player.play(audio, sr, loop)
        except Exception as ex:  # noqa
            self.stop()
            messagebox.showerror(APP_NAME, T('Не удалось воспроизвести звук:\n{0}').format(ex))
            return
        self.pstate = dict(t0=time.perf_counter(), dur=len(audio) / sr, base=base, s0=s0, s1=s1, loop=loop,
                           offset=offset, sd=sd, audio=audio, sr=sr, live=live)
        total = snap.total_steps
        solo = any(t.solo for t in snap.tracks)
        act = []
        for tr in snap.tracks:
            a = np.zeros(total + 1, bool)
            if not (tr.mute or (solo and not tr.solo)) or not live:
                for n in tr.notes:
                    a[n.s:n.s + max(1, n.l if tr.kind != 'drums' else 1)] = True
            act.append(a)
        self.play_active = act
        self.playing, self.pending = True, False
        self.btn_play.configure(text=T('■  Стоп'))
        self.set_status(T('▶ Воспроизведение') + (T(' (петля)') if loop else ''))

    def stop(self):
        self.render_token += 1
        self.pending = False
        self.player.stop()
        was = self.playing
        self.playing = False
        self.btn_play.configure(text=T('▶  Играть'))
        self.lanes.coords('playhead', -10, 0, -10, 1)
        self.ruler.coords('playhead', -10, 0, -10, 1)
        self.scope.coords(self.scope_line, 0, 22, 190, 22)
        if self.mode == 'arrange' and self.song:
            for i in range(len(self.song.tracks)):
                self.head.itemconfigure(f'led{i}', fill=self.c['grid_beat'])
        if was:
            self.set_status(T('■ Остановлено'))
        self.redraw_time()

    def toggle_play(self):
        if self.playing or self.pending:
            self.stop()
        else:
            self.play(0, self.song.total_steps, start=self.cursor)

    def play_selection(self):
        reg = self.get_region()
        if not reg:
            return self.set_status(T('Нет выделения — играю весь трек'))or self.toggle_play()
        self.play(reg[1], reg[2], start=reg[1])

    def to_start(self):
        self.cursor = 0
        self.lanes.xview_moveto(0)
        self._place_cursor()
        if self.playing:
            self.play(0, self.song.total_steps, start=0)

    def _on_loop_toggle(self):
        on = self.v_loop.get()
        self.chk_loop.configure(text=T('↻ Петля: вкл') if on else T('↻ Петля: выкл'))
        ps = self.pstate
        if self.playing and ps.get('live') and ps.get('loop') != on:
            # winsound не умеет менять режим на лету — перезапускаем с текущей позиции
            self.play(ps['s0'], ps['s1'], on, start=int(clamp(self.play_step, ps['s0'], ps['s1'] - 1)))

    def schedule_refresh(self):
        if not (self.playing and self.v_live.get() and self.pstate.get('live')):
            return
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
        self._refresh_job = self.root.after(350, self._do_refresh)

    def _do_refresh(self):
        self._refresh_job = None
        if not self.playing:
            return
        ps, total = self.pstate, self.song.total_steps
        s0, s1 = min(ps['s0'], total - 1), min(ps['s1'], total)
        if s1 <= s0:
            s0, s1 = 0, total
        self.play(s0, s1, ps['loop'], start=int(clamp(self.play_step, s0, s1 - 1)))

    def preview_note(self, tr, pitch, force=False):
        if self.playing or self.pending or not (self.v_preview.get() or force):
            return
        now = time.time()
        if self._last_preview[0] == pitch and now - self._last_preview[1] < 0.15:
            return
        self._last_preview = (pitch, now)
        t = dataclasses.replace(tr, notes=[Note(0, 2, pitch, .85)], mute=False, solo=False)
        tmp = Song(bpm=self.song.bpm, bars=1, tracks=[t], seed=self.song.seed)
        try:
            audio, sr = render_song(tmp, self.master_settings(), 0, 2)
            self.player.play(audio, sr)
        except Exception:  # noqa
            pass

    def preview_track_sound(self):
        if self.playing or self.pending:
            self.stop()
        tr = self.cur_track()
        if tr.kind == 'drums':
            notes = [Note(s, 1, p, .9) for s, p in ((0, 36), (2, 42), (4, 38), (6, 42), (8, 36), (9, 36),
                                                     (10, 46), (12, 38), (14, 45), (15, 45))]
        else:
            lo, hi = RANGES.get(tr.kind, (60, 84))
            root = 12 * ((lo + hi) // 24) + self.song.key
            notes = [Note(i * 2, 2, root + iv, .85) for i, iv in enumerate((0, 4, 7, 12, 7, 4))] + [Note(12, 4, root, .85)]
        t = dataclasses.replace(tr, notes=notes, mute=False, solo=False)
        tmp = Song(bpm=self.song.bpm, bars=1, tracks=[t], seed=self.song.seed)
        audio, sr = render_song(tmp, self.master_settings(), 0, 16)
        self.player.play(audio, sr)

    def _tick(self):
        if self._disposed:
            return
        try:
            while True:
                self.jobs.get_nowait()()
        except queue.Empty:
            pass
        if self.playing:
            ps = self.pstate
            el = time.perf_counter() - ps['t0']
            if el >= ps['dur']:
                if ps['loop']:
                    if not winsound:
                        self.player.replay()
                        ps['t0'] += ps['dur']
                        el -= ps['dur']
                else:
                    self.stop()
            if self.playing:
                if ps['loop']:
                    span = (ps['s1'] - ps['s0']) * ps['sd']
                    step = ps['s0'] + ((el + ps['offset']) % span) / ps['sd']
                else:
                    step = min(ps['s1'], ps['base'] + el / ps['sd'])
                self.play_step = step
                self._set_playhead(step)
                self.redraw_time()
                audio, sr = ps['audio'], ps['sr']
                i0 = int((el % ps['dur']) * sr)
                seg = audio[i0:i0 + 760, 0]
                if len(seg) > 8:
                    seg = seg[::4]
                    xs = np.linspace(0, 190, len(seg))
                    ys = 22 - seg * 20
                    self.scope.coords(self.scope_line, *np.column_stack([xs, ys]).ravel().tolist())
                if self.mode == 'arrange' and self.play_active and ps.get('live'):
                    si = int(step)
                    for i, a in enumerate(self.play_active):
                        on = si < len(a) and a[si]
                        col = self.song.tracks[i].color if (on and i < len(self.song.tracks)) else self.c['grid_beat']
                        self.head.itemconfigure(f'led{i}', fill=col)
        self.root.after(33, self._tick)
