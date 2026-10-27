#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds 8-BIT FORGE into a Windows program (.exe) with PyInstaller.

Run (from this folder):
    python build.py              — single file:  dist/8-BIT FORGE.exe
    python build.py --folder     — folder:       dist/8-BIT FORGE/8-BIT FORGE.exe (starts faster)
    python build.py --ffmpeg     — bundle ffmpeg inside: MP3 and video will work on any computer
    python build.py --console    — with a console window (errors are visible — handy for debugging)

Requires: Python 3.9+, numpy, pyinstaller (if it's missing, the script offers to install it).
Pillow is optional: with it the app gets its own icon and video export works.
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(ROOT, 'Generator_of_music.py')
BUILD = os.path.join(ROOT, 'build')
DIST = os.path.join(ROOT, 'dist')
APP_NAME = '8-BIT FORGE'
VERSION = (1, 0, 0, 0)

# Packages that may be installed in Python but the app doesn't need — without them the .exe is several times smaller
EXCLUDES = ['matplotlib', 'cv2', 'pygame', 'scipy', 'pandas', 'IPython', 'jupyter', 'notebook', 'PyQt5', 'PyQt6',
            'PySide2', 'PySide6', 'torch', 'tensorflow', 'sympy', 'numba', 'pytest', 'setuptools', 'pip',
            'tkinter.test', 'pydoc_data', 'lib2to3', 'imageio_ffmpeg']


def say(text):
    print(f'» {text}', flush=True)


def ensure_pyinstaller():
    if importlib.util.find_spec('PyInstaller'):
        return
    answer = input('PyInstaller не установлен. Поставить его сейчас (pip install pyinstaller)? [Y/n] ').strip().lower()
    if answer not in ('', 'y', 'yes', 'д', 'да'):
        sys.exit('Без PyInstaller собрать .exe нельзя.')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])


def check_requirements():
    if sys.platform != 'win32':
        say('Внимание: собирается под текущую систему — для .exe под Windows запускайте сборку на Windows.')
    if not importlib.util.find_spec('numpy'):
        sys.exit('Нужна библиотека numpy:  pip install numpy')
    ensure_pyinstaller()


def make_icon():
    """The same pixel icon as the app's windows — as an .ico with several sizes at once."""
    try:
        from PIL import Image
    except ImportError:
        say('Pillow не найден — собираю со стандартной иконкой (pip install pillow — будет своя).')
        return None
    sys.path.insert(0, ROOT)
    from scripts.ui.graphics import ICON_COLORS, ICON_PIXELS
    img = Image.new('RGBA', (16, 16))
    for y, row in enumerate(ICON_PIXELS):
        for x, ch in enumerate(row):
            img.putpixel((x, y), tuple(int(ICON_COLORS[ch][i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    big = img.resize((256, 256), Image.NEAREST)  # big crisp pixels, no blur
    path = os.path.join(BUILD, 'forge.ico')
    big.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def make_version_file():
    """File properties in Explorer: name, version, description."""
    v = ', '.join(map(str, VERSION))
    vs = '.'.join(map(str, VERSION))
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041904B0', [
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('FileDescription', '{APP_NAME} — генератор 8-битной музыки'),
      StringStruct('FileVersion', '{vs}'),
      StringStruct('ProductVersion', '{vs}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('InternalName', '{APP_NAME}')])]),
    VarFileInfo([VarStruct('Translation', [0x0419, 1200])])
  ]
)
"""
    path = os.path.join(BUILD, 'version_info.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return path


def find_ffmpeg_exe():
    exe = shutil.which('ffmpeg')
    if not exe:
        sys.exit('ffmpeg не найден в PATH — установите его (например: winget install ffmpeg) или соберите без --ffmpeg.')
    return exe


def build(args):
    os.makedirs(BUILD, exist_ok=True)
    icon = make_icon()
    sep = os.pathsep  # "source;folder" separator for --add-binary
    cmd = [sys.executable, '-m', 'PyInstaller', ENTRY,
           '--name', APP_NAME,
           '--onedir' if args.folder else '--onefile',
           '--console' if args.console else '--windowed',
           '--noconfirm', '--clean',
           '--workpath', BUILD, '--distpath', DIST, '--specpath', BUILD,
           '--paths', ROOT,
           '--collect-submodules', 'scripts',  # all of the app's modules, even those loaded on the fly
           '--version-file', make_version_file()]
    if icon:
        cmd += ['--icon', icon]
    for mod in EXCLUDES:
        cmd += ['--exclude-module', mod]
    if args.ffmpeg:
        exe = find_ffmpeg_exe()
        say(f'Кладу внутрь ffmpeg: {exe}')
        cmd += ['--add-binary', f'{exe}{sep}.']
    say('Собираю (это займёт 1–3 минуты)…')
    subprocess.check_call(cmd, cwd=ROOT)
    out = os.path.join(DIST, APP_NAME, APP_NAME + '.exe') if args.folder else os.path.join(DIST, APP_NAME + '.exe')
    if not os.path.isfile(out):
        sys.exit('Сборка завершилась, но .exe не найден — смотрите сообщения PyInstaller выше.')
    size = (sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(os.path.dirname(out)) for f in fs)
            if args.folder else os.path.getsize(out))
    print()
    say(f'Готово: {out}')
    say(f'Размер: {size / 1024 / 1024:.0f} МБ' + (' (вся папка — её и нужно копировать целиком)' if args.folder else ''))
    if not args.ffmpeg:
        say('MP3 и видео в .exe работают, если на компьютере установлен ffmpeg '
            '(или положите ffmpeg.exe рядом с программой; либо соберите с --ffmpeg).')


def main():
    p = argparse.ArgumentParser(description=f'Сборка {APP_NAME} в .exe')
    p.add_argument('--folder', action='store_true', help='собрать в папку (запуск быстрее), а не в один файл')
    p.add_argument('--console', action='store_true', help='оставить окно консоли — для отладки')
    p.add_argument('--ffmpeg', action='store_true', help='положить ffmpeg внутрь (MP3 и видео без установки)')
    args = p.parse_args()
    check_requirements()
    build(args)


if __name__ == '__main__':
    main()
