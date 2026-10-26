# -*- coding: utf-8 -*-
"""Модель Forge Melody — песни и темы с запоминающейся мелодией."""

from scripts.models_of_ai.base_composer import AIComposer


MELODY_INFO = dict(name='Forge Melody', icon='♫', desc='песни и темы с запоминающейся мелодией: куплет, припев, бридж')


class MelodyComposer(AIComposer):
    """Forge Melody: куплет → припев → куплет → припев → бридж → финальный припев, тема с развитием."""
    FORM = [('A', .5), ('B', .8), ('A', .55), ('B', .88), ('C', .45), ('B', .95)]
