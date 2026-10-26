# -*- coding: utf-8 -*-
"""Модель Forge Ambient — фоновая музыка, бесшовная петля."""

from scripts.models_of_ai.base_composer import AIComposer


AMBIENT_INFO = dict(name='Forge Ambient', icon='☁', desc='фоновая музыка: спокойно, ненавязчиво, бесшовная петля')


class AmbientComposer(AIComposer):
    """Forge Ambient: спокойные части без вступления и концовки, мелодия «дышит», конец ведёт в начало (петля)."""
    FORM = [('A', .3), ('B', .45), ('A', .35), ('C', .4)]
    AMBIENT = True
