#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8-BIT FORGE — бесплатный генератор 8/16-битной музыки в духе Dendy (NES) и Sega Mega Drive.

Запуск:  python Generator_of_music.py
Нужно:   Python 3.9+, numpy (pip install numpy). tkinter входит в стандартный Python.

Возможности:
  • стартовый экран: «Чат-промпт» или «Ручное создание»;
  • чат-студия: запрос словами → модели Forge (Melody, Ambient, Action, Jingle, SFX) сочиняют трек
    с формой, гармонией и развитием мотива, джингл или звуковой эффект; выбор длительности, вокала, жанра;
  • генерация трека по стилю, тональности, ладу, темпу, плотности, сложности и т.д.;
  • 5 каналов: лид, гармония, бас, арпеджио, ударные;
  • выделение области зажатой ЛКМ + «♻ Recreate another piece» — пересоздание куска,
    старый кусок уходит в кэш, его можно вернуть; ◀ Назад / Вперёд ▶ (undo / redo);
  • режим редактора (пиано-ролл): рисование, перемещение, растяжение, удаление нот;
  • звук каждого трека: волна, скважность, ШИМ, ADSR, вибрато, FM, расстройка, эхо, пресеты;
  • мастер: биткраш, понижение частоты, сглаживание, 4-битная громкость как у NES;
  • экспорт WAV (весь трек / выделение / стемы), MIDI, сохранение и загрузка проекта;
  • тёмная (по умолчанию) и светлая темы, несколько акцентных цветов.

Код разложен по модулям в папке scripts/ рядом с этим файлом.
"""

import multiprocessing
import tkinter as tk
from tkinter import messagebox

def main():
    multiprocessing.freeze_support()  # рендер звука идёт в отдельных процессах — нужно и для сборки в .exe
    try:
        import numpy  # noqa: F401
    except ImportError:  # pragma: no cover
        from scripts.core.i18n import T
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showerror('8-BIT FORGE', T('Нужна библиотека numpy.\n\nУстановите:  pip install numpy'))
        raise SystemExit(1)
    # интерфейс импортируем здесь, а не наверху: процессы рендера заново читают этот файл,
    # и им не нужно тянуть за собой окна
    from scripts.ui.shell import Shell
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa
        pass
    root = tk.Tk()
    Shell(root)
    root.mainloop()


if __name__ == '__main__':
    main()
