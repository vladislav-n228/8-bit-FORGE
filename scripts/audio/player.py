# -*- coding: utf-8 -*-
"""Воспроизведение через winsound (Windows) или системный плеер."""

import os
import shutil
import subprocess
import tempfile

try:
    import winsound
except ImportError:
    winsound = None

from scripts.audio.synth import write_wav


class Player:
    """Воспроизведение через winsound (Windows) или системный плеер."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix='8bitforge_')
        self.n = 0
        self.proc = None
        self.path = None

    def play(self, audio, sr, loop=False):
        self.stop()
        self.n += 1
        self.path = os.path.join(self.dir, f'play_{self.n % 6}.wav')
        write_wav(self.path, audio, sr)
        self._start(loop)

    def _start(self, loop=False):
        if winsound:
            flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
            if loop:
                flags |= winsound.SND_LOOP
            winsound.PlaySound(self.path, flags)
            return
        for cmd in (['afplay'], ['paplay'], ['aplay', '-q'], ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet']):
            if shutil.which(cmd[0]):
                self.proc = subprocess.Popen(cmd + [self.path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break

    def replay(self):
        if self.path and not winsound:
            self.stop()
            self._start()

    def stop(self):
        if winsound:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass
        if self.proc:
            try:
                self.proc.terminate()
            except OSError:
                pass
            self.proc = None

    def cleanup(self):
        self.stop()
        shutil.rmtree(self.dir, ignore_errors=True)
