# -*- coding: utf-8 -*-
"""Interface language: English (default) or Russian.

Texts in the code are written in Russian; T('…') returns their translation into the current language.
Internal keys (names of styles, scales, presets) stay in Russian — they are stored in projects
and settings and are translated only when shown on screen. That's why T() is called at display time
rather than at import: the language can be switched on the fly, the windows are simply rebuilt."""

import json

from scripts.core.constants import PREFS_PATH


LANGUAGES = {'en': 'English', 'ru': 'Русский'}


DEFAULT_LANG = 'en'


def _initial_lang():
    try:
        with open(PREFS_PATH, 'r', encoding='utf-8') as f:
            lang = json.load(f).get('lang')
    except (OSError, ValueError, AttributeError):
        lang = None
    return lang if lang in LANGUAGES else DEFAULT_LANG


LANG = _initial_lang()


_EN = None


def _table():
    global _EN
    if _EN is None:
        from scripts.core.lang_en import EN
        _EN = EN
    return _EN


def set_lang(lang):
    global LANG
    LANG = lang if lang in LANGUAGES else DEFAULT_LANG


def T(text):
    """Translates an interface string into the current language. Unknown strings (user track names, etc.)
    are returned as is."""
    if LANG == 'ru' or not isinstance(text, str):
        return text
    return _table().get(text, text)


def Tn(n, one, few, many):
    """A number with the right word form: Tn(5, 'звук', 'звука', 'звуков') → «звуков» / «sounds»."""
    if LANG != 'ru':
        return T(one) if n == 1 else T(many)
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many
