# -*- coding: utf-8 -*-
"""Beat markers for video editing (DaVinci, Audacity, CSV, list)."""

from scripts.core.constants import APP_NAME
from scripts.core.i18n import T
from scripts.core.theory import chord_name


MARKER_KINDS = {'Такты': 'bars', 'Доли (каждый бит)': 'beats', 'Удары бочки и малого': 'hits',
                'Смена аккордов': 'chords', 'Части трека (фразы, дроп, концовка)': 'sections'}


MARKER_FORMATS = {'DaVinci Resolve (.edl)': ('edl', '.edl'), 'Audacity (метки .txt)': ('audacity', '.txt'),
                  'Таблица CSV (Excel, Premiere)': ('csv', '.csv'), 'Простой список (CapCut и др.)': ('txt', '.txt')}


def fmt_time_ms(sec):
    m = int(sec // 60)
    return f'{m}:{sec - m * 60:06.3f}'


def beat_markers(song, kind):
    sd, total = song.step_dur, song.total_steps

    def tm(s):
        return s * sd + (song.swing * sd * .5 if s % 2 else 0)
    if kind == 'bars':
        return [(s * sd, T('Такт {0}').format(s // 16 + 1), 'bar') for s in range(0, total, 16)]
    if kind == 'beats':
        return [(s * sd, f'{s // 16 + 1}.{(s % 16) // 4 + 1}', 'bar' if s % 16 == 0 else 'beat') for s in range(0, total, 4)]
    if kind == 'hits':
        drums = next((t for t in song.tracks if t.kind == 'drums'), None)
        hits = sorted({(n.s, n.p) for n in (drums.notes if drums else []) if n.p in (36, 38) and n.v >= .45})
        return [(tm(s), T('Бочка') if p == 36 else T('Малый'), 'kick' if p == 36 else 'snare') for s, p in hits]
    if kind == 'chords':
        cs = song.chord_steps
        return [(i * cs * sd, T('Аккорд {0}').format(chord_name(song, d)), 'chord') for i, d in enumerate(song.chords) if i * cs < total]
    out = [(s * sd, T('Фраза {0}').format(s // 64 + 1), 'section') for s in range(0, total, 64)]
    if song.params.get('intro') and song.bars >= 6:
        out.append(((2 if song.bars >= 16 else 1) * 16 * sd, T('Конец вступления'), 'section'))
    if song.params.get('drop_step'):
        out.append((song.params['drop_step'] * sd, T('ДРОП'), 'drop'))
    if song.params.get('outro') and song.bars >= 4:
        out.append(((total - 16) * sd, T('Концовка'), 'section'))
    out.append((total * sd, T('Конец трека'), 'section'))
    return sorted(out)


def write_markers(path, song, kind, fmt, fps=30):
    m = beat_markers(song, kind)
    enc = 'utf-8'
    if fmt == 'audacity':
        lines = [f'{t:.6f}\t{t:.6f}\t{label}' for t, label, _ in m]
    elif fmt == 'csv':
        enc = 'utf-8-sig'
        lines = ['time_sec;time;bar;beat;type;label']
        for t, label, typ in m:
            step = int(round(t / song.step_dur))
            lines.append(f'{t:.3f};{fmt_time_ms(t)};{step // 16 + 1};{(step % 16) // 4 + 1};{typ};{label}')
    elif fmt == 'edl':
        colors = {'bar': 'ResolveColorBlue', 'beat': 'ResolveColorCyan', 'kick': 'ResolveColorRed',
                  'snare': 'ResolveColorYellow', 'chord': 'ResolveColorPurple', 'drop': 'ResolveColorPink',
                  'section': 'ResolveColorGreen'}

        def tc(sec):
            fr = int(round(sec * fps))
            return f'{1 + fr // (3600 * fps):02d}:{(fr // (60 * fps)) % 60:02d}:{(fr // fps) % 60:02d}:{fr % fps:02d}'
        lines = [f'TITLE: {APP_NAME} markers', 'FCM: NON-DROP FRAME', '']
        for i, (t, label, typ) in enumerate(m, 1):
            a, b = tc(t), tc(t + 1.0 / fps)
            lines += [f'{i:03d}  001      V     C        {a} {b} {a} {b}  ',
                      f' |C:{colors.get(typ, "ResolveColorBlue")} |M:{label} |D:1', '']
    else:
        lines = [f'{fmt_time_ms(t):>10}  —  {label}' for t, label, _ in m]
    with open(path, 'w', encoding=enc, newline='\r\n' if fmt == 'edl' else None) as f:
        f.write('\n'.join(lines) + '\n')
    return len(m)
