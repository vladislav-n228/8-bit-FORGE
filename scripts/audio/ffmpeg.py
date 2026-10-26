# -*- coding: utf-8 -*-
"""Поиск ffmpeg и экспорт MP3."""

import os
import shutil
import subprocess
import sys
import tempfile

from scripts.audio.synth import write_wav
from scripts.core.constants import APP_NAME
from scripts.core.i18n import T


_FFMPEG = {}


def _bundled_ffmpeg():
    """ffmpeg, положенный рядом с программой: внутрь собранного .exe, рядом с .exe или с Generator_of_music.py."""
    name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for d in (getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
              else None, here):
        if d and os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    return None


def find_ffmpeg():
    if 'exe' not in _FFMPEG:
        exe = _bundled_ffmpeg() or shutil.which('ffmpeg')
        if not exe:
            try:
                import imageio_ffmpeg
                exe = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:  # noqa
                exe = None
        _FFMPEG['exe'] = exe
    return _FFMPEG['exe']


def ffmpeg_encoders():
    if 'enc' not in _FFMPEG:
        names = set()
        exe = find_ffmpeg()
        if exe:
            try:
                out = subprocess.run([exe, '-hide_banner', '-encoders'], capture_output=True, text=True,
                                     timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and len(parts[0]) == 6:
                        names.add(parts[1])
            except (OSError, subprocess.SubprocessError):
                pass
        _FFMPEG['enc'] = names
    return _FFMPEG['enc']


FFMPEG_HELP = ('Для MP3 и видео нужна бесплатная программа ffmpeg.\n\n'
               'Установить проще всего одной командой в терминале:\n'
               '    winget install ffmpeg\n'
               'или:\n'
               '    pip install imageio-ffmpeg\n\n'
               'После установки перезапустите программу.')


def _run_ffmpeg(args):
    exe = find_ffmpeg()
    if not exe:
        raise RuntimeError(T(FFMPEG_HELP))
    r = subprocess.run([exe, '-hide_banner', '-loglevel', 'error', '-y'] + args, capture_output=True, text=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode != 0:
        raise RuntimeError('ffmpeg: ' + (r.stderr.strip()[-600:] or T('неизвестная ошибка')))


def export_mp3(path, audio, sr, kbps=256, title=''):
    enc = 'libmp3lame' if 'libmp3lame' in ffmpeg_encoders() or not ffmpeg_encoders() else 'mp3_mf'
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp.close()
    try:
        write_wav(tmp.name, audio, sr)
        _run_ffmpeg(['-i', tmp.name, '-codec:a', enc, '-b:a', f'{kbps}k', '-metadata', f'title={title}',
                     '-metadata', f'comment=Made with {APP_NAME}', path])
    finally:
        os.unlink(tmp.name)
