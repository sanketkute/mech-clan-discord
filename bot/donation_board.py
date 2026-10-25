"""Daily donation board for Mech Clan Bot (the owner's pick, 2026-10-24): one message per day in #clan-log, posted
silently and edited whenever someone donates, instead of a card for every donation. Same Components V2 layout as
the war board. The date is in the title, so an old board still reads right the next day.
Every line has to fit on a phone without wrapping; phone_check.py checks that."""
from war_board import divider, plural, short, text

BLUE = 0x3498DB  # mech_bot's color for donations
TOP = 8  # donors listed by name
MEDALS = ['🥇', '🥈', '🥉']


def build_donation_board(rows, season_total, icon, day, updated):
    """Components for one day's board. rows: (name, given, received) for the day; only donors get a line, most
    given first, with what they received beside it. day is a date, updated a Unix time."""
    donors = sorted((row for row in rows if row[1]), key=lambda row: (-row[1], -row[2]))
    lines = [f"{MEDALS[i] if i < len(MEDALS) else f'`{i + 1:>2}`'} **{short(name)}**  {icon('troop', '↑')} {given:,}"
             + (f"  {icon('clan_castle', '↓')} {received:,}" if received else '')
             for i, (name, given, received) in enumerate(donors[:TOP])]
    if len(donors) > TOP:
        lines.append(f'-# and {len(donors) - TOP} more')
    return [{'type': 17, 'accent_color': BLUE, 'components': [
        text(f"### {icon('troop')} Donations · {day:%a %d %b}"),
        text(f"-# {sum(row[1] for row in donors):,} troops by {plural(len(donors), 'member')}"),
        divider(),
        text('\n'.join(lines) or '-# Nobody has donated yet.'),
        divider(),
        text(f'-# Season: {season_total:,} troops · Updated <t:{updated}:R>')]}]
