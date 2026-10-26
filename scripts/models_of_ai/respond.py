# -*- coding: utf-8 -*-
"""Ответ модели: запрос → готовый трек / звуки + текст для чата."""

import random

from scripts.audio.synth import render_song
from scripts.core.constants import TRACK_DEFS, VOWEL_NAMES
from scripts.core.i18n import T
from scripts.core.theory import fmt_time
from scripts.models_of_ai.common import _ai_peaks, AI_MASTER, key_text
from scripts.models_of_ai.jingle import _ai_jingle
from scripts.models_of_ai.music_theory import (
    AI_AMBIENT_NAMES, AI_BASS_NAMES, AI_GROOVE_NAMES, AI_HARM_NAMES, AI_SECTION_NAMES)
from scripts.models_of_ai.registry import AI_COMPOSERS, AI_MODELS
from scripts.models_of_ai.sfx import _ai_sfx_reply
from scripts.models_of_ai.understanding import ai_understand
from scripts.music.structure import fmt_bpm


def _ai_music_reply(plan, song, secs, audio, sr):
    P = plan
    dur = len(audio) / sr
    jingle = P['model'] == 'jingle'
    what = {'melody': T('трек с запоминающейся темой'), 'ambient': T('фоновую композицию — она бесшовно зацикливается'),
            'action': T('энергичный экшен-трек'), 'jingle': T('короткий джингл')}[P['model']]
    head = T('Готово! Сочинил {0}: «{1}».').format(what, P["title"])
    lines = []
    if P['tags']:
        lines.append(T('Что я услышал в запросе: ') + ', '.join(T(x) for x in P['tags']) + '.')
    chip = 'Dendy / NES' if P['chip'] == 'nes' else 'Sega / FM'
    lines.append(T('• {0}: {1} · звучание {2}').format(T("Тип") if jingle else T("Жанр"), P["title"] if jingle else T(P["genre"]), chip))
    lines.append(T('• Тональность: {0} · темп {1} BPM · длительность {2}').format(key_text(song.key, song.scale), fmt_bpm(song.bpm), fmt_time(dur)))
    by = {t.kind: t for t in song.tracks}
    if secs:
        names = AI_AMBIENT_NAMES if P['model'] == 'ambient' else {}
        parts = []
        for s in secs:
            nm = T(names.get(s['name']) or AI_SECTION_NAMES[s['name']])
            if not parts or parts[-1] != nm:
                parts.append(nm)
        lines.append(T('• Форма: ') + ' → '.join(parts) + (T(' → (по кругу)') if P['loop'] else ''))
        if P['model'] == 'ambient':
            lines.append(T('• Мелодия: редкие фразы с паузами, в паузах отвечает арпеджио — фон не утомляет '
                         'и не спорит с голосом или видео.'))
        else:
            lines.append(T('• Мелодия: короткий мотив повторяется и развивается в 4-тактовые фразы, фразы '
                         'завершаются каденциями; припев звучит выше и ярче куплета.'))
        arr = [T('лид — «{0}»').format(T(P["sounds"][0])),
               T('гармония — {0}').format(T(AI_HARM_NAMES[P["harm"][0]])) +
               (T(' / в припеве {0}').format(T(AI_HARM_NAMES[P["harm"][1]])) if P['harm'][1] != P['harm'][0] else ''),
               T('бас — {0}').format(T(AI_BASS_NAMES[P["bass"]]))]
        if by['arp'].notes:
            arr.append(T('арпеджио'))
        arr.append(T('ударные — {0}').format(T(AI_GROOVE_NAMES[P["groove"]])) if by['drums'].notes else T('без ударных'))
        lines.append(T('• Аранжировка: ') + ', '.join(arr))
        lines.append(T('• Вокал: {0} — поёт тему припева и подпевает').format(T(VOWEL_NAMES.get(P["vowel"], P["vowel"])))
                     if by['voice'].notes else T('• Без вокала'))
    else:
        lines.append(T('• Мелодия: законченная фраза с ясным финалом — подходит как звуковая «подпись» события.'))
    lines += [f'• {n[0].upper() + n[1:]}' for n in P['notes']]
    if P['exclude']:
        names = dict(TRACK_DEFS)
        lines.append(T('• Убрал по просьбе: ') + ', '.join(T(names[k]).lower() for k in P['exclude'] if k in names))
    lines.append('')
    lines.append(T('«✎ В редактор» — доработать вручную, «⚄ Ещё вариант» — другой трек по тому же запросу.'))
    sub = (f'{AI_MODELS[P["model"]]["name"]} · {"" if jingle else T(P["genre"]) + " · "}'
           f'{key_text(song.key, song.scale)} · {fmt_bpm(song.bpm)} BPM · {fmt_time(dur)}')
    return head, '\n'.join(lines), sub


def ai_respond(text, opts, seed, status=None, render=render_song):
    """Главная точка входа чата: запрос → ответ модели с готовым звуком."""
    status = status or (lambda s: None)
    status(T('Разбираю запрос'))
    plan = ai_understand(text, opts, random.Random(seed))
    if plan['model'] == 'sfx':
        status(T('Синтезирую звуки'))
        return _ai_sfx_reply(plan, seed)
    if plan['model'] == 'jingle':
        status(T('Сочиняю джингл'))
        song, secs = _ai_jingle(plan, seed), None
    else:
        status(T('Сочиняю мелодию и гармонию'))
        comp = AI_COMPOSERS[plan['model']](plan, seed)
        song, secs = comp.compose(), comp.secs
    status(T('Свожу дорожки'))
    audio, sr = render(song, AI_MASTER, loop=plan['loop'])  # render можно подменить (например, рендер в процессе)
    head, body, sub = _ai_music_reply(plan, song, secs, audio, sr)
    res = dict(kind='song', title=plan['title'], sub=sub, song=song, audio=audio, sr=sr, peaks=_ai_peaks(audio))
    return dict(model=plan['model'], head=head, text=body, results=[res])
