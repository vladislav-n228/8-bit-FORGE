# -*- coding: utf-8 -*-
"""Модель Forge Action — битвы, боссы, погони и гонки."""

from scripts.models_of_ai.base_composer import AIComposer


ACTION_INFO = dict(name='Forge Action', icon='⚡', desc='битвы, боссы, погони и гонки — быстро и мощно')


class ActionComposer(AIComposer):
    """Forge Action: напор с первых тактов, припев на максимуме, брейкдаун перед финальным припевом."""
    FORM = [('A', .75), ('B', .95), ('C', .55), ('B', 1.0)]
