# -*- coding: utf-8 -*-
"""Реестр моделей Forge: описания для интерфейса и композиторы."""

from scripts.models_of_ai.action import ACTION_INFO, ActionComposer
from scripts.models_of_ai.ambient import AMBIENT_INFO, AmbientComposer
from scripts.models_of_ai.auto import AUTO_INFO
from scripts.models_of_ai.jingle import JINGLE_INFO
from scripts.models_of_ai.melody import MELODY_INFO, MelodyComposer
from scripts.models_of_ai.sfx import SFX_INFO


AI_MODELS = {'auto': AUTO_INFO, 'melody': MELODY_INFO, 'ambient': AMBIENT_INFO, 'action': ACTION_INFO,
             'jingle': JINGLE_INFO, 'sfx': SFX_INFO}


AI_COMPOSERS = {'melody': MelodyComposer, 'ambient': AmbientComposer, 'action': ActionComposer}
