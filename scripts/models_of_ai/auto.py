# -*- coding: utf-8 -*-
"""The Forge Auto model — picks the right model for the request by itself."""

AUTO_INFO = dict(name='Forge Auto', icon='✦', desc='сам выберет подходящую модель по запросу')


def choose_model(votes):
    """Forge Auto: the model the request "voted" for wins; on a tie — by order."""
    order = ['melody', 'jingle', 'sfx', 'ambient', 'action']
    return max(order, key=lambda m: (votes[m], -order.index(m)))
