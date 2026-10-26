# -*- coding: utf-8 -*-
"""Фоновые задачи: тяжёлая работа (рендер, экспорт, кодирование) идёт в отдельных потоках,
а окно продолжает отвечать.

Правило: рабочая функция не трогает Tk. Всё, что нужно показать в окне, попадает в главный поток
через колбэки done / error / progress или через TaskRunner.post()."""

import os
import pickle
import queue
import threading
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures.process import BrokenProcessPool


class TaskRunner:
    """Запускает задачи в фоновых потоках и доставляет их результаты в главный поток Tk."""

    def __init__(self, widget, poll_ms=30):
        self.widget = widget
        self.poll_ms = poll_ms
        self.q = queue.Queue()
        self.active = 0
        self._closed = False
        self._poll()

    def submit(self, work, done=None, error=None, progress=None):
        """work(report) выполняется в фоне. report(доля 0..1 или None, текст) — сообщить о прогрессе.
        done(результат) / error(исключение) / progress(доля, текст) вызываются уже в главном потоке."""
        self.active += 1

        def report(frac=None, text=None):
            if progress:
                self.post(lambda: progress(frac, text))

        def run():
            try:
                res = work(report)
            except BaseException as ex:  # noqa
                self.post(lambda err=ex: self._finish(error, err, failed=True))
            else:
                self.post(lambda: self._finish(done, res))
        threading.Thread(target=run, daemon=True, name='forge-task').start()

    def post(self, fn):
        """Выполнить fn в главном потоке (можно вызывать из любого потока)."""
        self.q.put(fn)

    def _finish(self, cb, val, failed=False):
        self.active -= 1
        if cb:
            cb(val)
        elif failed:
            traceback.print_exception(type(val), val, val.__traceback__)

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                fn = self.q.get_nowait()
                try:
                    fn()
                except Exception:  # noqa
                    traceback.print_exc()
        except queue.Empty:
            pass
        try:
            self.widget.after(self.poll_ms, self._poll)
        except Exception:  # noqa — окно уже закрыто
            self._closed = True

    def close(self):
        self._closed = True


def parallel_map(fn, items, workers=None):
    """Параллельно применить fn к элементам (внутри фоновой задачи)."""
    items = list(items)
    if len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers or min(4, os.cpu_count() or 2)) as ex:
        return list(ex.map(fn, items))


# ── отдельные процессы для самого тяжёлого (рендер звука) ──
# У каждого процесса свой GIL: рендер идёт параллельно на разных ядрах и совсем не отнимает время
# у окна — анимации и интерфейс не подтормаживают даже при нескольких экспортах сразу.
_PROC = None
_PROC_LOCK = threading.Lock()
_PROC_OK = True


def _noop():
    return True


def _pool():
    global _PROC
    with _PROC_LOCK:
        if _PROC is None:
            _PROC = ProcessPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2) - 1)))
        return _PROC


def run_in_process(fn, *args, **kwargs):
    """Выполнить fn(*args, **kwargs) в отдельном процессе и вернуть результат (вызывать из фонового потока).
    fn и аргументы должны «упаковываться» (pickle). Если процессы недоступны — считаем здесь же, в потоке."""
    global _PROC_OK
    if _PROC_OK:
        try:
            return _pool().submit(fn, *args, **kwargs).result()
        except (BrokenProcessPool, pickle.PicklingError, OSError, RuntimeError):
            _PROC_OK = False
    return fn(*args, **kwargs)


def warm_up_processes():
    """Заранее запустить процессы (импорт numpy занимает время), чтобы первый экспорт начался сразу."""
    def go():
        try:
            pool = _pool()
            for f in [pool.submit(_noop) for _ in range(pool._max_workers)]:
                f.result()
        except Exception:  # noqa
            pass
    threading.Thread(target=go, daemon=True).start()


def stop_processes():
    """При выходе: прервать недосчитанное, чтобы программа закрылась сразу."""
    global _PROC
    with _PROC_LOCK:
        pool, _PROC = _PROC, None
    if pool is None:
        return
    for p in list(getattr(pool, '_processes', {}).values()):
        try:
            p.terminate()
        except Exception:  # noqa
            pass
    pool.shutdown(wait=False, cancel_futures=True)
