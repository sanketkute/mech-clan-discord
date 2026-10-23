"""Live war board for Mech Clan Bot (prototype 2026-10-24): one message per war, edited in place every minute,
instead of a new card for every attack. Built with Discord's Components V2 layout (container, sections,
dividers, small grey subtext), which classic embeds can't do.

build_board() turns a Clash API war (regular or CWL, raw JSON) into the message's component list;
attack_log() gives every attack in order with the new stars it added, for the board and its thread."""
from datetime import datetime, timezone

IS_COMPONENTS_V2 = 1 << 15  # message flag; such a message has no content or embeds, only components
GOLD, GREEN, RED, GREY = 0xE8B339, 0x2ECC71, 0xE74C3C, 0x99AAB5
LATEST = 3  # attacks shown per side on the board; the thread has all of them


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


def attack_line(entry, icon, with_order=False):
    a, att, dfn = entry['attack'], entry['attacker'], entry['defender']
    stars = icon('war_star', '★') * a['stars'] + icon('no_star', '☆') * (3 - a['stars'])
    step = '↑' if dfn['mapPosition'] < att['mapPosition'] else ('↓' if dfn['mapPosition'] > att['mapPosition'] else '')
    new = f"  `+{entry['new_stars']}`" if entry['new_stars'] else ''
    # In the thread both sides are mixed, so each line also says who attacked.
    order = f"`{a['order']:>2}` {'Us' if entry['ours'] else 'Enemy'} · " if with_order else ''
    target = f"#{dfn['mapPosition']}" if entry['ours'] else f"our #{dfn['mapPosition']}"
    th = dfn['townhallLevel']
    return (f"{order}{icon('sword' if entry['ours'] else 'shield')} **{att['name']}**  #{att['mapPosition']} → "
            f"{target}{step} {icon(f'th{th}', f'TH{th}')}  {stars} **{a['destructionPercentage']}%**{new}")


def bar(value, total, width=12):
    filled = round(width * value / total) if total else 0
    return '▰' * filled + '▱' * (width - filled)


def build_board(war, clan_tag, icon, kind='War', thread_hint=True, now=None, opponent_icon=None):
    """Components for the board. icon(name, fallback) returns a bot emoji or the fallback.
    opponent_icon is the opponent's badge as a bot emoji (uploaded per war). With it, the header is a
    "badge mech clan vs Dark Star badge" line; without it, their badge sits in the corner instead."""
    us, them = sides(war, clan_tag)
    state, size = war['state'], war['teamSize']
    per_member = war.get('attacksPerMember') or (1 if kind != 'War' else 2)
    total_attacks, max_stars = per_member * size, 3 * size
    log = attack_log(us, them)
    used = {side: sum(1 for e in log if e['ours'] == (side == 'us')) for side in ('us', 'them')}
    score = (us.get('stars', 0), us.get('destructionPercentage', 0)), (them.get('stars', 0), them.get('destructionPercentage', 0))
    won, tied = score[0] > score[1], score[0] == score[1]

    versus = (f"{icon('mech_badge')} {us['name']}   vs   {them['name']} {opponent_icon}" if opponent_icon
              else f"{us['name']}  vs  {them['name']}")
    if state == 'preparation':
        title, status, accent = versus, f"{kind} · preparation · battle day <t:{unix(war['startTime'])}:R>", GOLD
    elif state == 'inWar':
        title, status, accent = versus, f"{kind} · battle day · ends <t:{unix(war['endTime'])}:R>", GOLD
    else:
        # A headline that reads as English ("mech clan beat Dark Star"), not a label like "Defeat vs Dark Star".
        verb = 'drew with' if tied else ('beat' if won else 'lost to')
        title = (f"{icon('mech_badge')} {us['name']} {verb} {them['name']} {opponent_icon}" if opponent_icon
                 else f"{us['name']} {verb} {them['name']}")
        status = f"{kind} over · ended <t:{unix(war['endTime'])}:R>"
        accent = GREY if tied else (GREEN if won else RED)

    lines = [text(f'### {title}'), text(f'-# {status}  ·  {size} vs {size}')]
    if opponent_icon:
        parts = lines
    else:
        parts = [{'type': 9, 'components': lines,
                  'accessory': {'type': 11, 'media': {'url': (them.get('badgeUrls') or {}).get('medium', '')}}}]

    if state != 'preparation':
        parts.append(text(
            f"{icon('war_star', '★')} **{score[0][0]}** – {score[1][0]}   ·   **{score[0][1]:.1f}%** – {score[1][1]:.1f}%"
            f"   ·   {icon('sword', '⚔')} **{used['us']}**/{total_attacks} – {used['them']}/{total_attacks}\n"
            f"-# {bar(score[0][0], max_stars)}  {score[0][0]} of {max_stars} stars"))
        parts.append(divider())
        # Our attacks and theirs in separate blocks, newest first, so nobody has to tell them apart by icon.
        for ours, heading in ((True, 'Our attacks'), (False, 'Enemy attacks')):
            side = [e for e in log if e['ours'] == ours]
            lines = '\n'.join(attack_line(e, icon) for e in reversed(side[-LATEST:])) or '-# None yet.'
            more = f"\n-# +{len(side) - LATEST} more in the thread below" if thread_hint and len(side) > LATEST else ''
            parts.append(text(f'**{heading}**\n{lines}{more}'))
        parts.append(divider())

    members = sorted(us.get('members', []), key=lambda m: m['mapPosition'])
    left = {m['name']: per_member - len(m.get('attacks', [])) for m in members}
    if state == 'preparation':
        ths = {}
        for m in members:
            ths[m['townhallLevel']] = ths.get(m['townhallLevel'], 0) + 1
        lineup = '  '.join(f"{icon(f'th{th}', f'TH{th}')} {n}" for th, n in sorted(ths.items(), reverse=True))
        parts.append(text(f'**Our lineup**\n{lineup}'))
    elif state == 'inWar':
        groups = [f"**{n} left:** " + ', '.join(name for name, k in left.items() if k == n)
                  for n in range(per_member, 0, -1) if any(k == n for k in left.values())]
        parts.append(text('**Attacks left**\n' + ('\n'.join(groups) or f"{icon('tick')} Every attack is used.")))
    else:
        ours = [e for e in log if e['ours']]
        mvp_name, mvp = max(((n, [e for e in ours if e['attacker']['name'] == n]) for n in left),
                            key=lambda p: (sum(e['new_stars'] for e in p[1]),
                                           sum(e['attack']['destructionPercentage'] for e in p[1])), default=(None, []))
        # Best defence: the base held to the fewest stars, and of those the one attacked most often.
        hits_on = {m['tag']: [e for e in log if not e['ours'] and e['defender']['tag'] == m['tag']] for m in members}
        held = [(m, hits_on[m['tag']]) for m in members if hits_on[m['tag']]]
        best_def = max(held, key=lambda p: (-max(e['attack']['stars'] for e in p[1]), len(p[1])), default=None)
        lines = []
        if mvp:
            lines.append(f"**MVP** · {mvp_name}: {sum(e['new_stars'] for e in mvp)} new stars in {len(mvp)} "
                         f"attack{'s' if len(mvp) != 1 else ''}")
        if best_def:
            m, hits = best_def
            most = max(e['attack']['stars'] for e in hits)
            lines.append(f"**Best defence** · {m['name']} (#{m['mapPosition']}): held to {most} "
                         f"{'star' if most == 1 else 'stars'} in {len(hits)} attack{'s' if len(hits) != 1 else ''}")
        missed = [f"{name} ({k})" for name, k in left.items() if k > 0]
        lines.append(f"**Missed** · {', '.join(missed)}" if missed else f"{icon('tick')} Every attack was used.")
        parts.append(text('\n'.join(lines)))

    parts.append(text(f"-# Updated <t:{int((now or datetime.now(timezone.utc)).timestamp())}:R>"))
    return [{'type': 17, 'accent_color': accent, 'components': parts}]
