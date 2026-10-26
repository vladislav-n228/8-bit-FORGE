# -*- coding: utf-8 -*-
"""Для видео: метки битов, ролик MP4 с визуализацией, окно звуковых эффектов."""

import copy
import os
import random
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from scripts.audio.ffmpeg import export_mp3, FFMPEG_HELP, find_ffmpeg
from scripts.audio.sfx import render_sfx, SFX_TYPES
from scripts.audio.synth import write_wav
from scripts.core.constants import APP_NAME, CHIPS
from scripts.core.i18n import T
from scripts.core.prefs import save_prefs
from scripts.core.theory import fmt_time
from scripts.export.markers import beat_markers, MARKER_FORMATS, MARKER_KINDS, write_markers
from scripts.export.video import render_video, RenderCancelled, VIDEO_SIZES, VIDEO_STYLES, VideoRenderer
from scripts.ui.style import FONT_B, HELP_TEXT, THEMES


class MediaMixin:
    """Для видео: метки битов, ролик MP4 с визуализацией, окно звуковых эффектов."""

    MARKER_HINTS = {
        'edl': 'DaVinci Resolve: Timeline → Import → Timeline Markers from EDL.\nТрек положите в самое начало '
               'таймлайна (01:00:00:00), частота кадров таймлайна должна совпадать с выбранной.',
        'audacity': 'Audacity: Файл → Импорт → Метки. Удобно, чтобы видеть биты прямо на волне.',
        'csv': 'Открывается в Excel / Google Таблицах. Premiere не импортирует маркеры из CSV сам — '
               'используйте таблицу как шпаргалку (время, такт, доля).',
        'txt': 'CapCut и мобильные редакторы не импортируют метки — держите список рядом при монтаже.\n'
               'Подсказка: в CapCut у аудио есть функция «Ритм / Beat» — с нашим треком она работает отлично.',
    }

    def open_markers_dialog(self):
        w, f = self._dialog(T('метки битов'), '560x470')
        v_kind = tk.StringVar(value='Такты')
        v_fmt = tk.StringVar(value='DaVinci Resolve (.edl)')
        v_fps = tk.StringVar(value='30')
        ttk.Label(f, text=T('⌖ Метки битов для монтажа'), style='Section.TLabel').pack(anchor='w')
        ttk.Label(f, text=T('Файл с временем каждого такта / удара — по нему удобно ставить склейки видео ровно в бит.'),
                  style='Muted.TLabel', wraplength=510).pack(anchor='w', pady=(2, 10))
        self._combo(f, T('Что отмечать'), v_kind, list(MARKER_KINDS), width=30)
        self._combo(f, T('Формат'), v_fmt, list(MARKER_FORMATS), width=30, cmd=lambda: upd())
        self._combo(f, T('Кадров/с (для EDL)'), v_fps, ['24', '25', '30', '50', '60'], width=6)
        hint = ttk.Label(f, style='Muted.TLabel', wraplength=510, justify='left')
        hint.pack(anchor='w', pady=(10, 6))
        info = ttk.Label(f, style='Muted.TLabel', wraplength=510, justify='left')
        info.pack(anchor='w')

        def upd():
            hint.configure(text=T(self.MARKER_HINTS[MARKER_FORMATS[v_fmt.get()][0]]))
            n = len(beat_markers(self.song, MARKER_KINDS[v_kind.get()]))
            info.configure(text=T('Будет меток: {0} · длина трека {1}').format(n, fmt_time(self.song.total_steps * self.song.step_dur)))
        v_kind.trace_add('write', lambda *a: upd())
        upd()

        def save():
            fmt, ext = MARKER_FORMATS[v_fmt.get()]
            kind = MARKER_KINDS[v_kind.get()]
            path = self._ask_save(ext, [(v_fmt.get(), '*' + ext)], f'{self._slug()}_markers_{kind}')
            if not path:
                return
            try:
                n = write_markers(path, self.song, kind, fmt, int(v_fps.get()))
                self.set_status(T('⌖ Сохранено меток: {0} → {1}').format(n, path))
                w.destroy()
            except Exception as ex:  # noqa
                messagebox.showerror(APP_NAME, T('Не удалось сохранить метки:\n{0}').format(ex), parent=w)
        row = ttk.Frame(f)
        row.pack(fill='x', side='bottom')
        self._btn(row, T('⌖  Сохранить метки'), save, style='Accent.TButton').pack(side='left', fill='x', expand=True)
        self._btn(row, T('Закрыть'), w.destroy).pack(side='left', padx=(6, 0))

    def open_video_dialog(self):
        if not find_ffmpeg():
            return messagebox.showinfo(APP_NAME, T(FFMPEG_HELP))
        try:
            from PIL import Image, ImageTk  # noqa
        except ImportError:
            return messagebox.showinfo(APP_NAME, T('Для видео нужна библиотека Pillow:\n\npip install pillow'))
        w, f = self._dialog(T('видео'), '720x820')
        V = dict(size=tk.StringVar(value=list(VIDEO_SIZES)[0]), style=tk.StringVar(value=VIDEO_STYLES[0]),
                 fps=tk.StringVar(value='30'), title=tk.StringVar(value=self._title_text()),
                 sub=tk.StringVar(value=f'Made with {APP_NAME}'), stars=tk.BooleanVar(value=True),
                 crt=tk.BooleanVar(value=True), prog=tk.BooleanVar(value=True),
                 sel=tk.BooleanVar(value=False), bg=THEMES['dark']['bg'], img=None)
        ttk.Label(f, text=T('▶ Видео с визуализацией'), style='Section.TLabel').pack(anchor='w')
        ttk.Label(f, text=T('Готовый ролик MP4: трек + бегущие ноты / эквалайзер, название, фон. '
                          'Звук берётся с настройками громкости из «Мастер».'),
                  style='Muted.TLabel', wraplength=670).pack(anchor='w', pady=(2, 8))
        self._combo(f, T('Формат'), V['size'], list(VIDEO_SIZES), width=36, cmd=lambda: preview())
        self._combo(f, T('Визуализация'), V['style'], VIDEO_STYLES, width=36, cmd=lambda: preview())
        self._combo(f, T('Кадров в секунду'), V['fps'], ['30', '60'], width=6)
        for label, key in ((T('Заголовок'), 'title'), (T('Подзаголовок'), 'sub')):
            row = ttk.Frame(f)
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=label).pack(side='left')
            ttk.Entry(row, textvariable=V[key], width=46).pack(side='right')
        row = ttk.Frame(f)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=T('Фон')).pack(side='left')
        bg_lbl = ttk.Label(row, text='', style='Muted.TLabel')

        def pick_bg():
            res = colorchooser.askcolor(V['bg'], parent=w)
            if res and res[1]:
                V['bg'], V['img'] = res[1], None
                preview()

        def pick_img():
            p = filedialog.askopenfilename(parent=w, filetypes=[(T('Картинки'), '*.png *.jpg *.jpeg *.bmp *.webp')])
            if p:
                V['img'] = p
                preview()
        self._btn(row, T('Картинка…'), pick_img, style='Small.TButton').pack(side='right')
        self._btn(row, T('Цвет…'), pick_bg, style='Small.TButton').pack(side='right', padx=4)
        bg_lbl.pack(side='right', padx=6)
        checks = ttk.Frame(f)
        checks.pack(fill='x', pady=(4, 0))
        for i, (text, key) in enumerate(((T('Пиксельные звёзды'), 'stars'), (T('CRT-полоски (как старый ТВ)'), 'crt'),
                                         (T('Полоса прогресса'), 'prog'), (T('Только выделенный кусок'), 'sel'))):
            self._check(checks, text, V[key], lambda k=key: (state.__setitem__('audio', None) if k == 'sel' else None,
                                                             preview())).grid(row=i // 2, column=i % 2, sticky='w', padx=(0, 16))
        pv = ttk.Label(f, anchor='center')
        pv.pack(fill='both', expand=True, pady=(10, 6))
        prog = ttk.Progressbar(f, mode='determinate', maximum=1.0)
        status = ttk.Label(f, style='Muted.TLabel', text=T('Превью — кадр из середины трека.'))
        prog.pack(fill='x')
        status.pack(anchor='w', pady=(4, 0))
        btns = ttk.Frame(f)
        btns.pack(fill='x', pady=(8, 0))
        state = {'cancel': None, 'audio': None, 'pv': 0}

        def audio_job():
            """Снимок настроек звука (в главном потоке); сам рендер потом идёт в фоне."""
            return self._export_job('selection' if V['sel'].get() and self.get_region() else 'song')

        def snapshot():
            """Все настройки читаем в главном потоке — фоновому потоку трогать Tk нельзя."""
            return dict(song=copy.deepcopy(self.song), size=VIDEO_SIZES[V['size'].get()], fps=int(V['fps'].get()),
                        style=V['style'].get(), title=V['title'].get(), sub=V['sub'].get(), bg=V['bg'], img=V['img'],
                        crt=V['crt'].get(), stars=V['stars'].get(), prog=V['prog'].get(), accent=self.c['accent'])

        def make_renderer(audio, sr, o, scale=1.0, fps=None):
            W, H = o['size']
            W, H = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
            return VideoRenderer(o['song'], audio, sr, W, H, fps or o['fps'], o['style'], o['title'], o['sub'], o['bg'],
                                 o['accent'], o['img'], o['crt'], o['stars'], o['prog'])

        def preview():
            """Кадр-превью строится в фоне: на длинном треке окно не замирает."""
            bg_lbl.configure(text=os.path.basename(V['img']) if V['img'] else V['bg'])
            state['pv'] += 1
            token, cached, o = state['pv'], state['audio'], snapshot()
            job = None if cached else audio_job()
            W, H = o['size']
            scale = min(640 / W, 330 / H)
            status.configure(text=T('Строю превью…'))

            def work(_report):
                audio_sr = cached or self._render_job(job)[:2]
                R = make_renderer(*audio_sr, o, scale, fps=4)
                return audio_sr, R.frame(R.n_frames // 2)

            def done(res):
                if token != state['pv'] or not w.winfo_exists():
                    return
                from PIL import Image, ImageTk
                state['audio'] = res[0]
                pv.image = ImageTk.PhotoImage(Image.fromarray(res[1]))
                pv.configure(image=pv.image)
                status.configure(text=T('Превью — кадр из середины трека.'))

            def fail(ex):
                if token == state['pv'] and w.winfo_exists():
                    status.configure(text=T('Не удалось построить превью: {0}').format(ex))
            self.tasks.submit(work, done, fail)

        def start():
            path = self._ask_save('.mp4', [(T('Видео MP4'), '*.mp4')], self._slug())
            if not path:
                return
            ev = threading.Event()
            state['cancel'] = ev
            go.state(['disabled'])
            status.configure(text=T('Готовлю звук и анализирую спектр…'))
            job = audio_job()
            tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            tmp.close()
            opts = snapshot()
            t0 = time.time()

            def ui(fn):
                self.jobs.put(lambda: fn() if w.winfo_exists() else None)

            def work():
                try:
                    audio, sr, _ = self._render_job(job)  # звук тоже готовим в фоне
                    write_wav(tmp.name, audio, sr)
                    R = make_renderer(audio, sr, opts)

                    def progress(x):
                        el = time.time() - t0
                        left = el / max(x, 1e-3) * (1 - x) if x > .02 else 0
                        ui(lambda: (prog.configure(value=x),
                                    status.configure(text=T('Рендер видео: {0:.0f}%').format(x * 100) +
                                                     (T(' · осталось ~{0:.0f} с').format(left) if left else ''))))
                    render_video(path, R, tmp.name, progress, ev)
                    ui(lambda: done(None))
                except RenderCancelled:
                    ui(lambda: done('cancel'))
                except Exception as ex:  # noqa
                    err = ex
                    ui(lambda: done(err))
                finally:
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass

            def done(err):
                go.state(['!disabled'])
                state['cancel'] = None
                if err == 'cancel':
                    prog.configure(value=0)
                    status.configure(text=T('Рендер отменён.'))
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                elif err:
                    status.configure(text=T('Ошибка рендера.'))
                    messagebox.showerror(APP_NAME, T('Не удалось сделать видео:\n{0}').format(err), parent=w)
                else:
                    prog.configure(value=1)
                    status.configure(text=T('Готово за {0:.0f} с: {1}').format(time.time() - t0, path))
                    self.set_status(T('▶ Видео сохранено: {0}').format(path))
                    if messagebox.askyesno(APP_NAME, T('Видео готово! Открыть папку с файлом?'), parent=w):
                        try:
                            os.startfile(os.path.dirname(path))
                        except (OSError, AttributeError):
                            pass
            threading.Thread(target=work, daemon=True).start()

        def cancel():
            if state['cancel']:
                state['cancel'].set()
            else:
                w.destroy()
        go = self._btn(btns, T('▶  Сделать видео'), start, style='Accent.TButton')
        go.pack(side='left', fill='x', expand=True)
        self._btn(btns, T('⟳ Превью'), preview).pack(side='left', padx=6)
        self._btn(btns, T('Отмена / Закрыть'), cancel).pack(side='left')
        w.protocol('WM_DELETE_WINDOW', cancel)
        w.after(50, preview)

    def open_sfx(self):
        w, f = self._dialog(T('звуковые эффекты'), '640x600')
        S = dict(kind=None, seed=1, audio=None, pitch=tk.DoubleVar(value=1.0), length=tk.DoubleVar(value=1.0),
                 chip=tk.StringVar(value='Dendy (NES)'), crush=tk.BooleanVar(value=True))
        ttk.Label(f, text=T('♪ 8-битные звуковые эффекты'), style='Section.TLabel').pack(anchor='w')
        ttk.Label(f, text=T('Клик по кнопке — новый вариант звука (каждый раз немного другой). '
                          'Понравился — сохраняйте в WAV или MP3 и кладите в видео.'),
                  style='Muted.TLabel', wraplength=590).pack(anchor='w', pady=(2, 8))
        grid = ttk.Frame(f)
        grid.pack(fill='x')
        cur = ttk.Label(f, text=T('Выберите звук'), font=FONT_B)

        def render():
            S['audio'] = render_sfx(S['kind'], S['seed'], S['pitch'].get(), S['length'].get(),
                                    CHIPS.get(S['chip'].get(), 'nes'), S['crush'].get())
            cur.configure(text=T('{0}  · вариант #{1} · {2:.2f} с').format(T(S["kind"]), S["seed"], len(S["audio"]) / 44100))

        def play():
            if not S['kind']:
                return
            if self.playing or self.pending:
                self.stop()
            render()
            self.player.play(S['audio'], 44100)

        def pick(kind):
            S['kind'], S['seed'] = kind, random.randrange(1, 99999)
            play()

        def again():
            if S['kind']:
                S['seed'] = random.randrange(1, 99999)
                play()
        for i, kind in enumerate(SFX_TYPES):
            self._btn(grid, T(kind), lambda k=kind: pick(k), style='Small.TButton').grid(
                row=i // 4, column=i % 4, sticky='ew', padx=2, pady=2)
        for i in range(4):
            grid.columnconfigure(i, weight=1)
        opts = ttk.Frame(f)
        opts.pack(fill='x', pady=(10, 0))
        self._slider(opts, T('Высота'), S['pitch'], .5, 2, lambda v: f'×{v:.2f}')
        self._slider(opts, T('Длина'), S['length'], .5, 2.5, lambda v: f'×{v:.2f}')
        self._combo(opts, T('Звучание'), S['chip'], list(CHIPS), width=14)
        self._check(opts, T('Ретро-хруст (4 бита, низкая частота)'), S['crush']).pack(anchor='w', pady=(4, 0))
        cur.pack(anchor='w', pady=(10, 4))

        def save(ext):
            if not S['kind']:
                return messagebox.showinfo(APP_NAME, T('Сначала выберите звук.'), parent=w)
            if ext == '.mp3' and not find_ffmpeg():
                return messagebox.showinfo(APP_NAME, T(FFMPEG_HELP), parent=w)
            render()
            name = f'sfx_{T(S["kind"]).split()[0].lower()}_{S["seed"]}'
            path = self._ask_save(ext, [(ext.upper()[1:], '*' + ext)], name)
            if not path:
                return
            audio, kind = S['audio'], T(S['kind'])

            def work(_report):
                if ext == '.mp3':
                    export_mp3(path, audio, 44100, 192, kind)
                else:
                    write_wav(path, audio, 44100)
            self.run_bg(T('Сохранение звука'), work, lambda _r: self.set_status(T('♪ Звук сохранён: {0}').format(path)),
                        T('Не удалось сохранить звук'))

        def save_pack():
            folder = filedialog.askdirectory(parent=w, title=T('Папка для набора звуков'), initialdir=self.prefs.get('dir'))
            if not folder:
                return
            chip, pitch, length, crush = CHIPS.get(S['chip'].get(), 'nes'), S['pitch'].get(), S['length'].get(), \
                S['crush'].get()
            todo = [(kind, v) for kind in SFX_TYPES for v in range(1, 4)]

            def work(report):
                for i, (kind, v) in enumerate(todo):
                    a = render_sfx(kind, v * 101, pitch, length, chip, crush)
                    write_wav(os.path.join(folder, f'{T(kind).split()[0].lower()}_{v}.wav'), a, 44100)
                    report((i + 1) / len(todo), T(kind))
                return len(todo)

            def done(n):
                self.set_status(T('♪ Набор из {0} звуков сохранён в {1}').format(n, folder))
                if w.winfo_exists():
                    messagebox.showinfo(APP_NAME, T('Готово: {0} звуков ({1} типов × 3 варианта).').format(n, len(SFX_TYPES)), parent=w)
            self.run_bg(T('Набор звуков'), work, done, T('Не удалось сохранить набор'))
        row = ttk.Frame(f)
        row.pack(fill='x', pady=(6, 0))
        self._btn(row, T('▶ Ещё раз'), play).pack(side='left')
        self._btn(row, T('⚄ Другой вариант'), again).pack(side='left', padx=4)
        self._btn(row, T('Сохранить WAV…'), lambda: save('.wav'), style='Accent.TButton').pack(side='left', padx=4)
        self._btn(row, 'MP3…', lambda: save('.mp3')).pack(side='left')
        self._btn(f, T('Сохранить весь набор (все звуки × 3 варианта) в папку…'), save_pack).pack(fill='x', pady=(8, 0))

    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title(T('{0} — справка').format(APP_NAME))
        win.configure(bg=self.c['panel'])
        win.transient(self.root)
        txt = tk.Text(win, width=78, height=34, bg=self.c['panel'], fg=self.c['fg'], bd=0, padx=18, pady=14,
                      font=('Consolas', 10), wrap='word', highlightthickness=0)
        txt.insert('1.0', T(HELP_TEXT))
        txt.configure(state='disabled')
        txt.pack(fill='both', expand=True)
        self._btn(win, T('Понятно'), win.destroy, style='Accent.TButton').pack(pady=(0, 12))

    def on_close(self):
        if self.shell:
            return self.shell.quit()
        self.stop()
        self.player.cleanup()
        save_prefs(self.prefs)
        self.root.destroy()
