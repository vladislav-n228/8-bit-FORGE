# -*- coding: utf-8 -*-
"""Chat studio history: each chat is a file in ~/.8bit_forge_chats, plus a shared list in index.json.

Sound is not saved (it's heavy) — only the song's notes and the sound parameters. When an old chat is opened,
the sound is rebuilt on first playback, so it is exactly the same as it was."""

import json
import os
import time

from scripts.core.constants import PREFS_PATH
from scripts.core.model import song_from_dict, song_to_dict

CHATS_DIR = os.path.join(os.path.dirname(PREFS_PATH), '.8bit_forge_chats')
_INDEX = os.path.join(CHATS_DIR, 'index.json')


def _write(path, data):
    os.makedirs(CHATS_DIR, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)  # the file won't get corrupted if the app is closed in the middle of writing


def _path(chat_id):
    return os.path.join(CHATS_DIR, f'{chat_id}.json')


def list_chats():
    """All saved chats, newest first: [dict(id, title, created, updated, count)]."""
    try:
        with open(_INDEX, 'r', encoding='utf-8') as f:
            items = json.load(f)
    except (OSError, ValueError):
        return []
    items = [it for it in items if isinstance(it, dict) and os.path.isfile(_path(it.get('id', '')))]
    return sorted(items, key=lambda it: it.get('updated', 0), reverse=True)


def new_chat_id():
    return time.strftime('%Y%m%d-%H%M%S') + f'-{int(time.time() * 1000) % 1000:03d}'


def _mod_index(fn):
    from scripts.models_of_ai.sfx import AI_SFX_MODS
    return next((i for i, (_, _, f) in enumerate(AI_SFX_MODS) if f is fn), None)


def _pack_result(r):
    out = {k: r[k] for k in ('kind', 'title', 'sub', 'sr') if k in r}
    out['peaks'] = [round(float(x), 3) for x in r.get('peaks', ())]
    if r['kind'] == 'song':
        out.update(song=song_to_dict(r['song']), loop=bool(r.get('loop')))
    else:
        out.update(sfx=r['sfx'], seed=r['seed'], chip=r['chip'], variant=r.get('variant', 1),
                   mods=[i for i in (_mod_index(fn) for fn in r.get('mods', ())) if i is not None])
    return out


def _unpack_result(d):
    r = dict(d, audio=None)
    if d['kind'] == 'song':
        r['song'] = song_from_dict(d['song'])
    else:
        from scripts.models_of_ai.sfx import AI_SFX_MODS
        r['mods'] = [AI_SFX_MODS[i][2] for i in d.get('mods', ()) if 0 <= i < len(AI_SFX_MODS)]
    return r


def pack_msgs(msgs):
    """Chat messages → something that can go into JSON (without sound and the canvas's service fields)."""
    out = []
    for m in msgs:
        if m.get('status'):  # the reply is still being composed — it will be saved when ready
            continue
        d = {k: v for k, v in m.items() if not k.startswith('_') and k != 'results'}
        if m['role'] == 'bot':
            d['results'] = [_pack_result(r) for r in m.get('results', ())]
        out.append(d)
    return out


def save_chat(chat_id, msgs, created=None):
    packed = pack_msgs(msgs)
    if not any(m['role'] == 'user' for m in packed):
        return False
    first = next(m['text'] for m in packed if m['role'] == 'user')
    title = ' '.join(first.split())
    title = title if len(title) <= 60 else title[:57].rstrip() + '…'
    now, items = time.time(), list_chats()
    old = next((it for it in items if it['id'] == chat_id), None)
    items = [it for it in items if it['id'] != chat_id]
    created = (old or {}).get('created') or created or now
    _write(_path(chat_id), dict(id=chat_id, title=title, created=created, updated=now, msgs=packed))
    items.append(dict(id=chat_id, title=title, created=created, updated=now,
                      count=sum(m['role'] == 'user' for m in packed)))
    _write(_INDEX, items)
    return True


def load_chat(chat_id):
    """→ a list of messages ready for ChatStudio (results have empty sound: audio=None)."""
    with open(_path(chat_id), 'r', encoding='utf-8') as f:
        data = json.load(f)
    msgs = []
    for m in data.get('msgs', []):
        if m.get('role') == 'bot':
            m['results'] = [_unpack_result(r) for r in m.get('results', [])]
        msgs.append(m)
    return msgs


def delete_chat(chat_id):
    try:
        os.remove(_path(chat_id))
    except OSError:
        pass
    _write(_INDEX, [it for it in list_chats() if it['id'] != chat_id])
