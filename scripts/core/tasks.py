# -*- coding: utf-8 -*-
"""Background tasks: heavy work (rendering, export, encoding) runs in separate threads,
and the window stays responsive.

Rule: the work function doesn't touch Tk. Everything that has to be shown in the window reaches the main thread
through the done / error / progress callbacks or through TaskRunner.post()."""

import os
import pickle
import queue
import threading
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures.process import BrokenProcessPool


class TaskRunner:
    """Runs tasks in background threads and delivers their results to the Tk main thread."""

    def __init__(self, widget, poll_ms=30):
        self.widget = widget
        self.poll_ms = poll_ms
        self.q = queue.Queue()
        self.active = 0
        self._closed = False
        self._poll()

    def submit(self, work, done=None, error=None, progress=None):
        """work(report) runs in the background. report(fraction 0..1 or None, text) — reports progress.
        done(result) / error(exception) / progress(fraction, text) are called in the main thread."""
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
        """Runs fn in the main thread (may be called from any thread)."""
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
        except Exception:  # noqa — the window is already closed
            self._closed = True

    def close(self):
        self._closed = True


def parallel_map(fn, items, workers=None):
    """Applies fn to the items in parallel (inside a background task)."""
    items = list(items)
    if len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers or min(4, os.cpu_count() or 2)) as ex:
        return list(ex.map(fn, items))


# ── separate processes for the heaviest work (sound rendering) ──
# Each process has its own GIL: rendering runs in parallel on different cores and takes no time at all
# from the window — animations and the UI don't stutter even with several exports at once.
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
    """Runs fn(*args, **kwargs) in a separate process and returns the result (call from a background thread).
    fn and its arguments must be picklable. If processes are unavailable, it computes right here, in the thread."""
    global _PROC_OK
    if _PROC_OK:
        try:
            return _pool().submit(fn, *args, **kwargs).result()
        except (BrokenProcessPool, pickle.PicklingError, OSError, RuntimeError):
            _PROC_OK = False
    return fn(*args, **kwargs)


def warm_up_processes():
    """Starts the processes in advance (importing numpy takes time) so the first export begins immediately."""
    def go():
        try:
            pool = _pool()
            for f in [pool.submit(_noop) for _ in range(pool._max_workers)]:
                f.result()
        except Exception:  # noqa
            pass
    threading.Thread(target=go, daemon=True).start()


def stop_processes():
    """On exit: abort unfinished work so the app closes right away."""
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
