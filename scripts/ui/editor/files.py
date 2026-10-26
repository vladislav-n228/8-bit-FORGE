# -*- coding: utf-8 -*-
"""Экспорт WAV / MP3 / стемов / MIDI / петли, сохранение и открытие проекта."""

import copy
import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

from scripts.audio.ffmpeg import export_mp3, FFMPEG_HELP, find_ffmpeg
from scripts.audio.loudness import LOUDNESS_TARGETS, normalize_loudness
from scripts.audio.synth import fade_out, render_song, write_midi, write_wav
from scripts.core.constants import APP_NAME, NOTE_NAMES, SCALES, STYLES
from scripts.core.i18n import T
from scripts.core.model import song_from_dict, song_to_dict
from scripts.core.prefs import save_prefs
from scripts.core.tasks import parallel_map, run_in_process
from scripts.core.theory import fmt_time
from scripts.music.structure import PLATFORM_PRESETS


def render_export(o):
    """Готовый к выкладке звук: повторы, затухание, громкость для соцсетей. Без Tk — можно в потоке или процессе.
    → (audio, sr, lufs)"""
    sg, m, s0, s1 = o['song'], o['m'], o['s0'], o['s1']
    if o['loop']:
        audio, sr = render_song(sg, m, s0, s1, loop=True)
    elif o['which'] == 'selection':
        audio, sr = render_song(sg, m, s0, s1)
    elif o['loops'] > 1:
        base, sr = render_song(sg, m, 0, sg.total_steps, loop=True)
        audio = np.tile(base, (o['loops'], 1))
    else:
        audio, sr = render_song(sg, m)
    if o['fade'] and not o['loop']:
        audio = fade_out(audio.copy(), sr)
    audio, lufs = normalize_loudness(audio, sr, o['lufs'])
    return audio, sr, lufs


class FilesMixin:
    """Экспорт WAV / MP3 / стемов / MIDI / петли, сохранение и открытие проекта."""

    def _ask_save(self, ext, types, name):
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=types, initialfile=name,
                                            initialdir=self.prefs.get('dir') or os.path.expanduser('~'))
        if path:
            self.prefs['dir'] = os.path.dirname(path)
            save_prefs(self.prefs)
        return path

    def _slug(self):
        sg = self.song
        st = T(sg.style).split('·')[-1].strip().replace(' ', '_').replace('!', '') or 'track'
        return f'8bitforge_{st}_{sg.seed}'

    # ── фоновые задачи: окно не зависает, внизу крутится индикатор ──
    def run_bg(self, label, work, done=None, fail=None):
        """work(report) выполняется в фоновом потоке и не трогает Tk; done(результат) — уже в главном потоке."""
        self._bg_seq += 1
        key = self._bg_seq
        self._bg[key] = dict(label=label, frac=None, note='', t0=time.time())
        self._bg_show()

        def finish():
            self._bg.pop(key, None)
            self._bg_show()

        def ok(res):
            finish()
            if done:
                done(res)

        def bad(ex):
            finish()
            self.set_status(f'⚠ {fail or T("Не удалось выполнить")}')
            messagebox.showerror(APP_NAME, f'{fail}:\n{ex}', parent=self.root)

        def progress(frac, note):
            st = self._bg.get(key)
            if st:
                if frac is not None:
                    st['frac'] = frac
                if note:
                    st['note'] = note
        self.tasks.submit(work, ok, bad, progress)

    def _bg_show(self):
        if not self._bg:
            self.bg_box.pack_forget()
            return
        if not self.bg_box.winfo_ismapped():
            self.bg_box.pack(side='right', padx=(0, 18), before=self.lbl_status)  # место — раньше длинного статуса
            self._bg_anim()

    def _bg_anim(self):
        if not self._bg:
            return
        st = list(self._bg.values())[-1]
        spin = '◐◓◑◒'[int(time.time() * 8) % 4]
        more = T(' (+ ещё {0})').format(len(self._bg) - 1) if len(self._bg) > 1 else ''
        note = f' · {st["note"]}' if st['note'] else ''
        pct_ = f' · {st["frac"] * 100:.0f}%' if st['frac'] is not None else ''
        self.lbl_bg.configure(text=T('{0} {1}{2}{3}{4} · {5:.0f} с').format(spin, st["label"], more, note, pct_, time.time() - st["t0"]))
        if st['frac'] is None:
            self.bg_bar.configure(mode='indeterminate')
            self.bg_bar.step(.04)
        else:
            self.bg_bar.configure(mode='determinate', value=st['frac'])
        self.root.after(100, self._bg_anim)

    def _export_job(self, which='song', loop=False):
        """Снимок всего, что нужно для рендера. Читается в главном потоке — фоновым потокам трогать Tk нельзя."""
        reg = self.get_region()
        s0, s1 = (reg[1], reg[2]) if which == 'selection' and reg else (0, self.song.total_steps)
        return dict(song=copy.deepcopy(self.song), m=self.master_settings(), s0=s0, s1=s1, which=which, loop=loop,
                    loops=int(round(self.v_loops.get())), fade=self.v_fade.get(),
                    lufs=LOUDNESS_TARGETS.get(self.v_lufs.get()))

    @staticmethod
    def _render_job(o):
        """Рендер экспорта в отдельном процессе (вызывать из фонового потока). → (audio, sr, lufs)"""
        return run_in_process(render_export, o)

    def render_for_export(self, which='song', loop=False):
        return render_export(self._export_job(which, loop))

    @staticmethod
    def _lufs_note(lufs):
        return T(' · громкость {0:.1f} LUFS').format(lufs) if lufs is not None else ''

    def export_wav(self, which='song'):
        if which == 'selection' and not self.get_region():
            return messagebox.showinfo(APP_NAME, T('Сначала выделите область (зажмите ЛКМ и протяните).'))
        path = self._ask_save('.wav', [(T('WAV аудио'), '*.wav')], self._slug() + ('_part' if which == 'selection' else ''))
        if not path:
            return
        o, bits8 = self._export_job(which), self.v_wav8.get()

        def work(report):
            report(None, T('рендер звука'))
            audio, sr, lufs = self._render_job(o)
            report(None, T('запись файла'))
            write_wav(path, audio, sr, bits8=bits8)
            return len(audio) / sr, lufs
        self.run_bg(T('Экспорт WAV'), work, lambda r: self.set_status(
            T('⬇ Экспортировано: {0}  ({1}){2}').format(path, fmt_time(r[0]), self._lufs_note(r[1]))), T('Не удалось экспортировать'))

    def export_mp3_file(self, which='song'):
        if not find_ffmpeg():
            return messagebox.showinfo(APP_NAME, T(FFMPEG_HELP))
        if which == 'selection' and not self.get_region():
            return messagebox.showinfo(APP_NAME, T('Сначала выделите область (зажмите ЛКМ и протяните).'))
        path = self._ask_save('.mp3', [(T('MP3 аудио'), '*.mp3')], self._slug() + ('_part' if which == 'selection' else ''))
        if not path:
            return
        o, kbps, title = self._export_job(which), int(self.v_mp3_kbps.get()), self._title_text()

        def work(report):
            report(None, T('рендер звука'))
            audio, sr, lufs = self._render_job(o)
            report(None, T('кодирование MP3'))
            export_mp3(path, audio, sr, kbps, title)
            return len(audio) / sr, lufs
        self.run_bg(T('Экспорт MP3'), work, lambda r: self.set_status(
            T('⬇ MP3 сохранён: {0}  ({1}){2}').format(path, fmt_time(r[0]), self._lufs_note(r[1]))), T('Не удалось сохранить MP3'))

    def export_loop(self):
        reg = self.get_region()
        what = T('выделенный кусок') if reg else T('весь трек')
        path = self._ask_save('.wav', [(T('WAV аудио'), '*.wav')], self._slug() + '_loop')
        if not path:
            return
        o, bits8 = self._export_job('selection' if reg else 'song', loop=True), self.v_wav8.get()

        def work(report):
            report(None, T('рендер петли'))
            audio, sr, lufs = self._render_job(o)
            write_wav(path, audio, sr, bits8=bits8)
            return len(audio) / sr, lufs

        def done(r):
            self.set_status(T('↻ Бесшовная петля ({0}, {1}) сохранена: {2}{3}').format(what, fmt_time(r[0]), path, self._lufs_note(r[1])))
            messagebox.showinfo(APP_NAME, T('Петля сохранена ({0}).\n\nЕё можно ставить в видео по кругу сколько угодно раз — стык не слышен: «хвосты» нот в конце перенесены в начало.\n\nСовет: для петель используйте WAV — MP3 добавляет тишину на стыке.').format(what),
                                parent=self.root)
        self.run_bg(T('Бесшовная петля'), work, done, T('Не удалось сохранить петлю'))

    def _title_text(self):
        sg = self.song
        prompt = sg.params.get('prompt')
        if prompt:
            return prompt[:1].upper() + prompt[1:60]
        return T(sg.style).split('·')[-1].strip() or APP_NAME

    def _apply_platform(self):
        sec = PLATFORM_PRESETS.get(self.v_platform.get())
        if sec:
            self.v_exact.set(True)
            self.v_exact_sec.set(str(sec))
            self.v_outro.set(True)
            if sec >= 15:
                self.v_intro.set(True)
            self.set_status(T('Платформа: {0} — длина {1} с. Нажмите «Сгенерировать».').format(T(self.v_platform.get()), sec))

    def _dialog(self, title, size):
        w = tk.Toplevel(self.root)
        w.title(f'{APP_NAME} — {title}')
        w.geometry(size)
        w.transient(self.root)
        w.configure(bg=self.c['panel'])
        self.extra_windows.append(w)
        f = ttk.Frame(w, padding=(18, 14))
        f.pack(fill='both', expand=True)
        return w, f

    def export_stems(self):
        folder = filedialog.askdirectory(title=T('Папка для стемов'), initialdir=self.prefs.get('dir'))
        if not folder:
            return
        song, slug, bits8 = copy.deepcopy(self.song), self._slug(), self.v_wav8.get()
        m = dict(self.master_settings(), normalize=False)
        idx = [i for i, tr in enumerate(song.tracks) if tr.notes]

        def work(report):
            lock, count = threading.Lock(), [0]

            def one(i):  # дорожки считаются параллельно — каждая в своём процессе
                audio, sr = run_in_process(render_song, song, m, only=[i])
                write_wav(os.path.join(folder, f'{slug}_{i + 1:02d}_{T(song.tracks[i].name)}.wav'), audio, sr, bits8=bits8)
                with lock:
                    count[0] += 1
                    report(count[0] / len(idx), T('дорожка {0} из {1}').format(count[0], len(idx)))
            parallel_map(one, idx)
            return len(idx)
        self.run_bg(T('Экспорт стемов'), work, lambda n: self.set_status(T('⬇ Стемы сохранены ({0} шт.) в {1}').format(n, folder)),
                    T('Не удалось экспортировать стемы'))

    def export_midi(self):
        path = self._ask_save('.mid', [('MIDI', '*.mid')], self._slug())
        if path:
            try:
                write_midi(path, self.song)
                self.set_status(T('⬇ MIDI сохранён: {0}').format(path))
            except Exception as ex:  # noqa
                messagebox.showerror(APP_NAME, T('Не удалось сохранить MIDI:\n{0}').format(ex))

    def save_project(self, as_new=False):
        path = self.project_path
        if as_new or not path:
            path = self._ask_save('.json', [(T('Проект 8-BIT FORGE'), '*.json')], self._slug())
            if not path:
                return
        data = dict(format='8bitforge', version=1, song=song_to_dict(self.song), master=self.master_settings(),
                    generator=self.collect_params())
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            self.project_path = path
            self.root.title(f'{APP_NAME} — {os.path.basename(path)}')
            self.set_status(T('Проект сохранён: {0}').format(path))
        except OSError as ex:
            messagebox.showerror(APP_NAME, T('Не удалось сохранить:\n{0}').format(ex))

    def open_project(self):
        path = filedialog.askopenfilename(filetypes=[(T('Проект 8-BIT FORGE'), '*.json'), (T('Все файлы'), '*.*')],
                                          initialdir=self.prefs.get('dir'))
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            song = song_from_dict(data['song'])
        except (OSError, ValueError, KeyError, TypeError) as ex:
            return messagebox.showerror(APP_NAME, T('Не удалось открыть проект:\n{0}').format(ex))
        self.stop()
        self.push_history(T('Открытие проекта'))
        self.song = song
        m = data.get('master', {})
        for var, k in ((self.v_mvol, 'volume'), (self.v_down, 'downsample'), (self.v_smooth, 'smooth'),
                       (self.v_nes_env, 'nes_env'), (self.v_norm, 'normalize')):
            if k in m:
                var.set(m[k])
        if 'sr' in m:
            self.v_sr.set(str(m['sr']))
        if 'bits' in m:
            self.v_bits.set(str(m['bits']))
        self.v_key.set(NOTE_NAMES[song.key])
        if song.scale in SCALES:
            self.v_scale.set(song.scale)
        if song.style in STYLES:
            self.v_style.set(song.style)
        self.v_seed.set(str(song.seed))
        self.project_path = path
        self.root.title(f'{APP_NAME} — {os.path.basename(path)}')
        self.sel_track = 0
        self.after_song_change()
        self.zoom_fit()
        self.set_status(T('Проект открыт: {0}').format(path))
