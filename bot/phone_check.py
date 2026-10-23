"""Checks that the war board fits on a phone before it goes out. The owner's rule (2026-10-24): always check how
a card looks on a small screen, not just on a desktop.

It estimates each line's width in units: a letter, digit, space or sign is 1 and an emoji (custom or Unicode) is 4.5.
Bold is a bit wider, ### headings are bigger and -# subtext is smaller. On the owner's phone, a board line of about
47 units still fit and 49.5 wrapped, so lines over LIMIT get flagged. That leaves some room for narrower phones.
A button beside text (a section) takes about its label plus 6 units.
This is only an estimate; a phone screenshot is still the real check.

Run: python bot/phone_check.py  (sample boards in every war state, with made-up 15-character names)"""
import re
import sys
from datetime import datetime, timezone

import war_board as wb

LIMIT = 44
EMOJI = 4.5
CUSTOM_EMOJI = re.compile(r'<a?:\w+:\d+>')
TIMESTAMP = re.compile(r'<t:\d+:R>')


def units(line):
    scale = 1.0
    for prefix, size in (('### ', 1.2), ('## ', 1.35), ('# ', 1.6), ('-# ', 0.9)):
        if line.startswith(prefix):
            line, scale = line[len(prefix):], size
            break
    line = CUSTOM_EMOJI.sub('\0', line)  # one placeholder per emoji
    line = TIMESTAMP.sub('45 minutes ago', line)  # about the longest a relative time gets
    total, bold = 0.0, False
    for i, part in enumerate(re.split(r'(`[^`]*`)', line)):
        if i % 2:  # inline code: wider monospace letters plus the pill's padding
            total += len(part.strip('`')) * 1.2 + 1
            continue
        for piece in re.split(r'(\*\*)', part):
            if piece == '**':
                bold = not bold
                continue
            for ch in piece:
                width = EMOJI if ch == '\0' or ord(ch) >= 0x1F000 else 1
                total += width * (1.1 if bold else 1)
    return round(total * scale, 1)


def texts(components, room=0.0):
    """(text, units taken by things beside it) for every text display, including inside sections."""
    for c in components:
        if c['type'] == 10:
            yield c['content'], room
        elif c['type'] == 9:
            accessory = c.get('accessory', {})
            beside = len(accessory.get('label', '')) + 6 if accessory.get('type') == 2 else 12  # button or thumbnail
            yield from texts(c['components'], room + beside)
        elif c.get('components'):
            yield from texts(c['components'], room)


def check(components, label, show=False):
    """Print lines over LIMIT (every line with show=True). Returns how many lines would wrap."""
    wraps = 0
    for content, room in texts(components):
        for line in content.split('\n'):
            width = units(line) + room
            over = width > LIMIT
            wraps += over
            if over or show:
                print(f"  {'WRAPS' if over else 'ok   '} {width:5.1f}  {line}")
    print(f"{label}: {'fits' if not wraps else f'{wraps} line(s) would wrap'}")
    return wraps


def sample_war(state):
    """A 15 vs 15 war with made-up names, several at the 15-character maximum."""
    names = ['DarkKnightRider', 'xX_Thunder_Xx', 'Phoenix', 'ShadowHunter777', 'Lia', 'Mighty Barbarian',
             'Kai', 'Dragon Queen 99', 'Bob', 'TheLastAirbende', 'Zed', 'Valkyrie_Fury', 'Ana', 'Golem Grinder',
             'Max']
    members = lambda side, prefix: [{'tag': f'#{prefix}{i}', 'name': names[(i + side) % 15][:15],  # noqa: E731
                                     'mapPosition': i + 1, 'townhallLevel': 18 - i // 2} for i in range(15)]
    ours, theirs = members(0, 'A'), members(7, 'B')
    order = 0
    for i in range(12):
        attacker, defender = (ours[i], theirs[(i + 10) % 15]) if i % 2 == 0 else (theirs[i], ours[(i + 9) % 15])
        order += 1
        attacker.setdefault('attacks', []).append({'attackerTag': attacker['tag'], 'defenderTag': defender['tag'],
                                                   'stars': i % 4, 'destructionPercentage': 100 - i * 7,
                                                   'order': order})
    return {'state': state, 'teamSize': 15, 'attacksPerMember': 2,
            'startTime': '20261024T200000.000Z', 'endTime': '20261025T200000.000Z',
            'clan': {'tag': '#OURS', 'name': 'mech clan', 'stars': 14, 'destructionPercentage': 41.33,
                     'members': ours},
            'opponent': {'tag': '#THEIRS', 'name': 'Longest Name 15', 'stars': 9, 'destructionPercentage': 100.0,
                         'members': theirs}}


def main():
    icon = lambda name, fallback='': f'<:{name}:1>'  # noqa: E731  (every icon as a custom emoji)
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    wraps = 0
    for state in ('preparation', 'inWar', 'warEnded'):
        war = sample_war(state)
        board = wb.build_board(war, '#OURS', icon, kind='CWL round 7', now=now, opponent_icon='<:opp:1>',
                               war_id='x')
        wraps += check(board, f'board, {state}', show='-v' in sys.argv)
    log = wb.attack_log(war['clan'], war['opponent'])
    wraps += check([wb.text('\n'.join(wb.attack_line(e, icon, in_thread=True) for e in log))], 'thread lines',
                   show='-v' in sys.argv)
    sys.exit(1 if wraps else 0)


if __name__ == '__main__':
    main()
