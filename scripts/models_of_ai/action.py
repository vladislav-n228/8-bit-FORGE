# -*- coding: utf-8 -*-
"""The Forge Action model — battles, bosses, chases and races."""

from scripts.models_of_ai.base_composer import AIComposer


ACTION_INFO = dict(name='Forge Action', icon='⚡', desc='битвы, боссы, погони и гонки — быстро и мощно')


class ActionComposer(AIComposer):
    """Forge Action: drive from the first bars, the chorus at full power, a breakdown before the final chorus."""
    FORM = [('A', .75), ('B', .95), ('C', .55), ('B', 1.0)]
