# -*- coding: utf-8 -*-
"""Настройки программы (~/.8bit_forge_prefs.json)."""

import json

from scripts.core.constants import PREFS_PATH


def load_prefs():
    try:
        with open(PREFS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_prefs(p):
    try:
        with open(PREFS_PATH, 'w', encoding='utf-8') as f:
            json.dump(p, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
