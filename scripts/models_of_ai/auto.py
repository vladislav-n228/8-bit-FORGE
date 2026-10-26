# -*- coding: utf-8 -*-
"""Модель Forge Auto — сама выбирает подходящую модель по запросу."""

AUTO_INFO = dict(name='Forge Auto', icon='✦', desc='сам выберет подходящую модель по запросу')


def choose_model(votes):
    """Forge Auto: побеждает модель, за которую «проголосовал» запрос; при равенстве — по порядку."""
    order = ['melody', 'jingle', 'sfx', 'ambient', 'action']
    return max(order, key=lambda m: (votes[m], -order.index(m)))
