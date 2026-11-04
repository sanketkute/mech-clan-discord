"""CWL group card for Mech Clan Bot (prototype, 2026-11-04; the owner liked a Town Hall table from Reddit): the
8 clans of our CWL group, ranked by stars so far, each with its badge, its attacks this round and the Town Halls
of its lineup. Buttons 1-7 under it work like tabs: each shows that round's results privately (round_view).
Text, not a picture, so it stays sharp on a phone; every line has to fit one (phone_check.py).

build_cwl_group() and round_view() take the raw CWL group JSON and the group's wars."""
from war_board import divider, short, text

PURPLE = 0x9B59B6
PLACES = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣']
SHOWN_LEVELS = 3  # Town Hall levels listed per lineup; the rest are summed up as "+N"


def standings(group, wars):
    """Clan tag -> [stars, destruction] so far. A won war adds 10 stars once it has ended, as in the game."""
    table = {clan['tag']: [0, 0.0] for clan in group['clans']}
    for war in wars:
        if war['state'] not in ('inWar', 'warEnded'):
            continue
        for side, other in ((war['clan'], war['opponent']), (war['opponent'], war['clan'])):
            row = table.get(side['tag'])
            if row is None:
                continue
            row[0] += side.get('stars', 0)
            row[1] += side.get('destructionPercentage', 0) * war['teamSize']
            if war['state'] == 'warEnded' and winner(war) is side:
                row[0] += 10
    return table


def winner(war):
    """The side ahead on stars, then destruction, or None on a tie."""
    a, b = war['clan'], war['opponent']
    key = lambda side: (side.get('stars', 0), side.get('destructionPercentage', 0))  # noqa: E731
    return a if key(a) > key(b) else b if key(b) > key(a) else None


def sides(round_wars):
    """Clan tag -> its side (lineup, attacks) in the given wars."""
    return {side['tag']: side for war in round_wars for side in (war['clan'], war['opponent'])}


def attacked(side):
    members = side.get('members', [])
    return sum(1 for m in members if m.get('attacks')), len(members)


def lineup_line(side, icon):
    counts = {}
    for member in side.get('members', []):
        counts[member['townhallLevel']] = counts.get(member['townhallLevel'], 0) + 1
    ordered = sorted(counts.items(), reverse=True)
    rest = sum(n for _, n in ordered[SHOWN_LEVELS:])
    return '  '.join(f"{icon(f'th{th}', f'TH{th}')} {n}" for th, n in ordered[:SHOWN_LEVELS]) + \
        (f'  +{rest}' if rest else '') or '-# No lineup yet'


def build_cwl_group(group, wars, clan_tag, icon, league_name, league_icon, round_number, updated=None):
    """Components for the live card. wars: the group's started wars, rounds in order. round_number: the round
    being fought (1-7), whose attacks and lineups are shown. updated: a Unix time for the footer."""
    table = standings(group, wars)
    current = sides(w for w in wars if w.get('_round') == round_number)
    ranked = sorted(group['clans'], key=lambda clan: (-table[clan['tag']][0], -table[clan['tag']][1]))
    rows = []
    for i, clan in enumerate(ranked):
        side = current.get(clan['tag'], {})
        done, size = attacked(side)
        # ‎ keeps a right-to-left name from pulling what follows to the wrong side.
        lines = (f"{PLACES[i]} **{short(clan['name'])}**‎{'  `us`' if clan['tag'] == clan_tag else ''}\n"
                 f"{icon('war_star', '★')} **{table[clan['tag']][0]}**    {icon('sword', '⚔')} {done}/{size}\n"
                 f"{lineup_line(side, icon)}")
        rows.append({'type': 9, 'components': [text(lines)], 'accessory': {
            'type': 11, 'media': {'url': (clan.get('badgeUrls') or {}).get('medium', '')}}})
    rounds = len(group.get('rounds', []))
    played = {w.get('_round') for w in wars}
    buttons = [{'type': 2, 'label': str(n), 'custom_id': f'cwl:round:{n}',
                'style': 1 if n == round_number else 2, 'disabled': n not in played} for n in range(1, rounds + 1)]
    updated_text = f' · updated <t:{updated}:R>' if updated else ''
    return [{'type': 17, 'accent_color': PURPLE, 'components': [
        text(f'### {league_icon} CWL · {league_name}'),
        text(f'-# Round {round_number} of {rounds} · {icon("war_star", "★")} stars · '
             f'{icon("sword", "⚔")} attacked'),
        divider(), *rows, divider(),
        text(f"-# This round's lineups{updated_text}\n-# Tap a round to see its results"),
        {'type': 1, 'components': buttons[:4]}, {'type': 1, 'components': buttons[4:]}]}]


def round_view(group, wars, number, clan_tag, icon):
    """Components for one round's results, sent privately when its button is tapped."""
    names = {clan['tag']: clan['name'] for clan in group['clans']}
    blocks = []
    for war in (w for w in wars if w.get('_round') == number):
        top = winner(war) if war['state'] == 'warEnded' else None
        lines = []
        for side in sorted((war['clan'], war['opponent']), key=lambda s: s['tag'] != clan_tag):
            done, size = attacked(side)
            name = short(names.get(side['tag'], side['name']))
            lines.append(f"{f'**{name}**' if side is top else name}‎  {icon('war_star', '★')} "
                         f"{side.get('stars', 0)}  {side.get('destructionPercentage', 0):.0f}%  "
                         f"{icon('sword', '⚔')} {done}/{size}")
        blocks.append('\n'.join(lines))
    state = next((w['state'] for w in wars if w.get('_round') == number), 'warEnded')
    parts = [text(f'### Round {number} · ' + ('battle day' if state == 'inWar' else 'ended')),
             text('-# Each war: stars, destruction, attacks used' + ('' if state == 'inWar' else '\n-# Winners in bold'))]
    for block in blocks:
        parts += [divider(), text(block)]
    return [{'type': 17, 'accent_color': PURPLE, 'components': parts}]
