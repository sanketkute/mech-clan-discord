"""Live war board for Mech Clan Bot (2026-10-24): one message per war, edited in place every minute, instead of a
new card for every attack. Built with Discord's Components V2 layout (container, dividers, small grey subtext).

Layout (the owner's own design, trimmed after "a bit verbose"): a badge vs badge header, one score line, the last
3 attacks per side in "Our attacks" and "Enemy attacks" blocks, and one "N attacks left" line whose "Who's left"
button the bot answers privately with detail(). Every attack also goes into a thread under the board.
Every line has to fit on a phone without wrapping; phone_check.py checks that.

build_board() turns a Clash API war (regular or CWL, raw JSON) into the message's component list;
attack_log() gives every attack in order with the new stars it added."""
import re
from datetime import datetime, timezone

IS_COMPONENTS_V2 = 1 << 15  # message flag; such a message has no content or embeds, only components
GOLD, GREEN, RED, GREY = 0xE8B339, 0x2ECC71, 0xE74C3C, 0x99AAB5
LATEST = 3  # attacks shown per side on the board; the thread has all of them
NAME_MAX = 12  # longer player names are cut short so an attack still fits on one line on a phone


def unix(api_value):
    # The Clash API writes times like 20261023T210000.000Z.
    return int(datetime.strptime(api_value, '%Y%m%dT%H%M%S.%fZ').replace(tzinfo=timezone.utc).timestamp())


def text(content):
    return {'type': 10, 'content': content}


def divider():
    return {'type': 14, 'divider': True, 'spacing': 1}


def sides(war, clan_tag):
    """(us, them): in CWL our clan can be listed as either side."""
    return (war['clan'], war['opponent']) if war['clan']['tag'] == clan_tag else (war['opponent'], war['clan'])


def attacks_per_member(war):
    return war.get('attacksPerMember') or (1 if war.get('_cwl_tag') else 2)


def attack_log(us, them):
    """Every attack in order, with the stars it added on top of the best earlier attack on that base."""
    members = {m['tag']: m for m in us.get('members', []) + them.get('members', [])}
    ours = {m['tag'] for m in us.get('members', [])}
    attacks = sorted((a for side in (us, them) for m in side.get('members', []) for a in m.get('attacks', [])),
                     key=lambda a: a['order'])
    best, log = {}, []
    for a in attacks:
        before = best.get(a['defenderTag'], 0)
        best[a['defenderTag']] = max(before, a['stars'])
        log.append({'attack': a, 'ours': a['attackerTag'] in ours, 'attacker': members[a['attackerTag']],
                    'defender': members[a['defenderTag']], 'new_stars': max(0, a['stars'] - before)})
    return log


def short(name, limit=NAME_MAX):
    return name if len(name) <= limit else name[:limit - 1].rstrip() + '…'


def attack_line(entry, icon, in_thread=False):
    """Stars, destruction, attacker → base number, new stars: "★★★ 100%  sanket → #6  +3".
    On the board the block heading says whose attack it is. In the thread both sides are mixed, so a sword (ours)
    or shield (theirs) leads the line, and the name is cut a bit shorter to make room for it."""
    a = entry['attack']
    stars = icon('war_star', '★') * a['stars'] + icon('no_star', '☆') * (3 - a['stars'])
    target = f"#{entry['defender']['mapPosition']}"
    if in_thread:
        side = icon('sword', 'Us:') if entry['ours'] else icon('shield', 'Them:')
        new = f" +{entry['new_stars']}" if entry['new_stars'] else ''
        return (f"{side} {stars} {a['destructionPercentage']}% {short(entry['attacker']['name'], NAME_MAX - 2)} "
                f"→ {target}{new}")
    new = f" `+{entry['new_stars']}`" if entry['new_stars'] else ''
    return f"{stars} **{a['destructionPercentage']}%**  {short(entry['attacker']['name'])} → {target}{new}"


def attacks_left(us, per_member):
    return {m['name']: per_member - len(m.get('attacks', []))
            for m in sorted(us.get('members', []), key=lambda m: m['mapPosition'])}


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def build_board(war, clan_tag, icon, kind='War', now=None, opponent_icon=None, war_id=None):
    """Components for the board. icon(name, fallback) returns a bot emoji or the fallback.
    opponent_icon is the opponent's badge as a bot emoji (uploaded per war). With it, the header is a
    "badge mech clan vs Dark Star badge" line; without it, their badge sits in the corner instead.
    war_id adds the "Who's left" / "Who missed" button (custom id wb:<left|missed>:<war_id>)."""
    us, them = sides(war, clan_tag)
    state, size = war['state'], war['teamSize']
    per_member = attacks_per_member(war)
    total = per_member * size
    log = attack_log(us, them)
    score =(us.get('stars', 0), us.get('destructionPercentage', 0)), (them.get('stars', 0), them.get('destructionPercentage', 0))
    won, tied = score[0] > score[1], score[0] == score[1]
    left = attacks_left(us, per_member)

    opponent = short(them['name'])  # a 15-character name would push the header onto two lines on a phone
    versus = (f"{icon('mech_badge')} {us['name']} vs {opponent} {opponent_icon}" if opponent_icon
              else f"{us['name']} vs {opponent}")
    if state == 'preparation':
        title, status, accent = versus, f"{kind} · starts <t:{unix(war['startTime'])}:R>", GOLD
    elif state == 'inWar':
        title, status, accent = versus, f"{kind} · ends <t:{unix(war['endTime'])}:R>", GOLD
    else:
        # A headline that reads as English ("We beat Dark Star"), not a label like "Defeat vs Dark Star".
        # "We" rather than "mech clan" keeps "drew with" plus a long name on one line; our badge says who we are.
        verb = 'drew with' if tied else ('beat' if won else 'lost to')
        title = (f"{icon('mech_badge')} We {verb} {opponent} {opponent_icon}" if opponent_icon
                 else f"We {verb} {opponent}")
        status = f"{kind} · ended <t:{unix(war['endTime'])}:R>"
        accent = GREY if tied else (GREEN if won else RED)

    header = [text(f'### {title}'), text(f'-# {status} · {size} vs {size}')]
    parts = header if opponent_icon else [{'type': 9, 'components': header, 'accessory': {
        'type': 11, 'media': {'url': (them.get('badgeUrls') or {}).get('medium', '')}}}]

    if state == 'preparation':
        counts = {}
        for m in us.get('members', []):
            counts[m['townhallLevel']] = counts.get(m['townhallLevel'], 0) + 1
        items = [f"{icon(f'th{th}', f'TH{th}')} {n}" for th, n in sorted(counts.items(), reverse=True)]
        # Four Town Halls per row, so a mixed lineup doesn't wrap mid-row on a phone.
        rows = '\n'.join('   '.join(items[i:i + 4]) for i in range(0, len(items), 4))
        parts.append(text(f'**Our lineup**\n{rows}'))
    else:
        parts.append(text(f"{icon('war_star', '★')} **{score[0][0]}** – {score[1][0]}  ·  "
                          f"**{score[0][1]:.1f}%** – {score[1][1]:.1f}%"))
        parts.append(divider())
        # Our attacks and theirs in separate blocks, newest first, so nobody has to tell them apart by icon.
        for ours, heading in ((True, 'Our attacks'), (False, 'Enemy attacks')):
            side = [e for e in log if e['ours'] == ours]
            lines = '\n'.join(attack_line(e, icon) for e in reversed(side[-LATEST:])) or '-# None yet.'
            parts.append(text(f"**{heading}** · {len(side)} of {total}\n{lines}"))
        parts.append(divider())

        remaining = sum(k for k in left.values() if k > 0)
        players = sum(1 for k in left.values() if k > 0)
        if state == 'inWar':
            line = (f"**{plural(remaining, 'attack')} left**\n-# {plural(players, 'player')} still to attack"
                    if remaining else f"{icon('tick')} Every attack is used")
            action = ('left', "Who's left")
        else:
            ours = [e for e in log if e['ours']]
            mvp_name, mvp = max(((n, [e for e in ours if e['attacker']['name'] == n]) for n in left),
                                key=lambda p: (sum(e['new_stars'] for e in p[1]),
                                               sum(e['attack']['destructionPercentage'] for e in p[1])),
                                default=(None, []))
            # Best defence: the base held to the fewest stars, and of those the one attacked most often.
            members = sorted(us.get('members', []), key=lambda m: m['mapPosition'])
            hits_on = {m['tag']: [e for e in log if not e['ours'] and e['defender']['tag'] == m['tag']] for m in members}
            held = [(m, hits_on[m['tag']]) for m in members if hits_on[m['tag']]]
            best_def = max(held, key=lambda p: (-max(e['attack']['stars'] for e in p[1]), len(p[1])), default=None)
            summary = []
            if mvp:
                summary.append(f"**MVP** · {short(mvp_name)} · {plural(sum(e['new_stars'] for e in mvp), 'new star')}")
            if best_def:
                m, hits = best_def
                summary.append(f"**Best defence** · {short(m['name'], NAME_MAX - 2)} · "
                               f"{max(e['attack']['stars'] for e in hits)}{icon('war_star', '★')} in "
                               f"{plural(len(hits), 'hit')}")
            if summary:
                # On its own, not beside the button, which would leave these lines too little room on a phone.
                parts.append(text('\n'.join(summary)))
            line = (f"**{plural(remaining, 'attack')} missed**\n-# by {plural(players, 'player')}" if remaining
                    else f"{icon('tick')} Every attack was used")
            action = ('missed', 'Who missed')
        if war_id and remaining:
            parts.append({'type': 9, 'components': [text(line)], 'accessory': {
                'type': 2, 'style': 2, 'label': action[1], 'custom_id': f'wb:{action[0]}:{war_id}'}})
        else:
            parts.append(text(line))

    parts.append(text(f"-# Updated <t:{int((now or datetime.now(timezone.utc)).timestamp())}:R>"))
    return [{'type': 17, 'accent_color': accent, 'components': parts}]


def detail(war, clan_tag, what, icon):
    """(title, text) for a board button: 'left' or 'missed' (and 'ours' / 'enemy', from the earlier layout)."""
    us, them = sides(war, clan_tag)
    log = attack_log(us, them)
    if what in ('ours', 'enemy'):
        side = [e for e in log if e['ours'] == (what == 'ours')]
        title = f"Our attacks on {them['name']}" if what == 'ours' else f"{them['name']}'s attacks on us"
        lines = [attack_line(e, icon) for e in reversed(side)]  # newest first
        return f'{title} ({len(side)})', '\n'.join(lines)[:4000] or 'None yet.'
    left = attacks_left(us, attacks_per_member(war))
    groups = [f"**{n} left:** " + ', '.join(name for name, k in left.items() if k == n)
              for n in range(attacks_per_member(war), 0, -1) if any(k == n for k in left.values())]
    if what == 'missed':
        return 'Missed attacks', '\n'.join(g.replace(' left:', ' missed:') for g in groups) or 'None, every attack was used.'
    return 'Attacks left', '\n'.join(groups) or 'None, every attack is used.'
