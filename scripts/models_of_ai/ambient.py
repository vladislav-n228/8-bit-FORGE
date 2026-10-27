# -*- coding: utf-8 -*-
"""The Forge Ambient model — background music, a seamless loop."""

from scripts.models_of_ai.base_composer import AIComposer


AMBIENT_INFO = dict(name='Forge Ambient', icon='☁', desc='фоновая музыка: спокойно, ненавязчиво, бесшовная петля')


class AmbientComposer(AIComposer):
    """Forge Ambient: calm sections without intro or ending, the melody "breathes", the end leads back to the start (loop)."""
    FORM = [('A', .3), ('B', .45), ('A', .35), ('C', .4)]
    AMBIENT = True
