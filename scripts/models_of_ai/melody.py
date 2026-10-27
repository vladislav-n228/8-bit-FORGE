# -*- coding: utf-8 -*-
"""The Forge Melody model — songs and themes with a catchy melody."""

from scripts.models_of_ai.base_composer import AIComposer


MELODY_INFO = dict(name='Forge Melody', icon='♫', desc='песни и темы с запоминающейся мелодией: куплет, припев, бридж')


class MelodyComposer(AIComposer):
    """Forge Melody: verse → chorus → verse → chorus → bridge → final chorus, a theme with development."""
    FORM = [('A', .5), ('B', .8), ('A', .55), ('B', .88), ('C', .45), ('B', .95)]
