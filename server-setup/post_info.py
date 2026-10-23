"""Post the #welcome and #rules cards, approved by the owner on 2026-10-23 (as cards with game icons since 2026-10-24).

The text lives in posts/welcome.md and posts/rules.md: '# ' is the card title, the first paragraph its intro,
each '## ' or '### ' heading a section, and a '> ' line the footer note. {channel} placeholders become channel
mentions and {:icon} placeholders become Mech Clan Bot's game-icon emojis.
Safe to re-run: Mech Clan Bot edits its own earlier post in the channel instead of posting again, so this is also
how to publish later edits to the .md files.

Usage (from the repo root): python server-setup/post_info.py [--preview CHANNEL]
--preview posts fresh copies in that channel instead, for review."""
import re
import sys
from pathlib import Path

from discord_api import call, get

GUILD = '1316103480644993116'
APP = '1563174332744728659'  # Mech Clan Bot, which owns the game-icon emojis
POSTS = {'welcome': 'welcome.md', 'rules': 'rules.md'}
CLAN_LINK = 'https://link.clashofclans.com/en?action=OpenClanProfile&tag=YU9YY8UV'
BADGE = 'https://api-assets.clashofclans.com/badges/{}/sGyFKAT-ZNxGz5CmtQ8hdI1oTjTOrZGClEGFO0YeIJs.png'
GOLD = 0xE8B339
SECTION_ICONS = {'Clan': 'trophy', 'Get started': 'tick', 'Where things are': 'people', 'Server': 'shield',
                 'Clan Wars': 'sword', 'CWL': 'cwl_medal', 'Raid Weekend': 'raid_medal', 'Activity': 'clock'}
# Per card (after the owner's and a reviewer's "too cramped" feedback, 2026-10-24): the welcome card shows the big
# badge and a title linking to the clan, without the small "mech clan" header; the rules card drops the badge,
# whose column made most rules wrap, especially on phones.
CARD_STYLE = {'welcome': {'author': False, 'thumbnail': True, 'url': CLAN_LINK},
              'rules': {'author': True, 'thumbnail': False}}
SPACER = '\n​'  # a zero-width-space line: Discord drops trailing blank lines, so this adds the gap


def build_card(text, channels, icons, author=True, thumbnail=True, url=None):
    def fill(s):
        s = re.sub(r'\{:([a-z0-9_]+)\}', lambda m: icons.get(m.group(1), ''), s)
        return re.sub(r'\{([a-z-]+)\}', lambda m: f'<#{channels[m.group(1)]}>', s)

    embed = {'color': GOLD, 'fields': []}
    if thumbnail:
        embed['thumbnail'] = {'url': BADGE.format(200)}
    if author:
        embed['author'] = {'name': 'mech clan', 'url': CLAN_LINK, 'icon_url': BADGE.format(70)}
    if url:
        embed['url'] = url
    intro, field = [], None
    for line in text.strip().splitlines():
        if line.startswith('# '):
            embed['title'] = line[2:].strip()
        elif re.match(r'#{2,3} ', line):
            name = line.lstrip('#').strip()
            field = {'name': f"{icons.get(SECTION_ICONS.get(name, ''), '')} {name}".strip(), 'value': '', 'inline': False}
            embed['fields'].append(field)
        elif line.startswith('> '):
            embed['footer'] = {'text': fill(line[2:].strip())}
        elif field is not None:
            field['value'] += line + '\n'
        else:
            intro.append(line)
    if '\n'.join(intro).strip():
        embed['description'] = fill('\n'.join(intro).strip())
    for i, field in enumerate(embed['fields']):
        field['value'] = fill(field['value'].strip()) + (SPACER if i < len(embed['fields']) - 1 else '')
        if len(field['value']) > 1024:
            raise SystemExit(f"section {field['name']!r} is {len(field['value'])} characters; Discord allows 1024")
    return embed


def buttons(channel, channels, icons):
    if channel != 'welcome':
        return []

    def emoji(name):
        found = re.match(r'<:(\w+):(\d+)>', icons.get(name, ''))
        return {'emoji': {'name': found.group(1), 'id': found.group(2)}} if found else {}

    return [{'type': 1, 'components': [
        {'type': 2, 'style': 5, 'label': 'Open the clan in game', 'url': CLAN_LINK, **emoji('clan_castle')},
        {'type': 2, 'style': 5, 'label': 'Read the rules',
         'url': f"https://discord.com/channels/{GUILD}/{channels['rules']}", **emoji('shield')},
    ]}]


def main():
    preview = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--preview' else None
    channels = {c['name']: c['id'] for c in get(f'/guilds/{GUILD}/channels')}
    icons = {e['name']: f"<:{e['name']}:{e['id']}>" for e in get(f'/applications/{APP}/emojis')['items']}
    me = get('/users/@me')['id']
    for channel, file in POSTS.items():
        text = (Path(__file__).parent.parent / 'posts' / file).read_text(encoding='utf-8')
        # flags 0 clears the old "no link preview" flag, which would hide the card.
        # The welcome title links to the clan: link buttons can only be grey, a linked title is blue.
        card = build_card(text, channels, icons, **CARD_STYLE.get(channel, {}))
        body = {'content': '', 'embeds': [card],
                'components': buttons(channel, channels, icons), 'flags': 0, 'allowed_mentions': {'parse': []}}
        if preview:
            message = call('POST', f'/channels/{channels[preview]}/messages', body)
            print(f'preview of #{channel} posted in #{preview}: {message["id"]}')
            continue
        mine = [m for m in get(f'/channels/{channels[channel]}/messages?limit=50') if m['author']['id'] == me]
        if mine:
            call('PATCH', f'/channels/{channels[channel]}/messages/{mine[-1]["id"]}', body)
            print(f'updated the post in #{channel}')
        else:
            call('POST', f'/channels/{channels[channel]}/messages', body)
            print(f'posted in #{channel}')


if __name__ == '__main__':
    main()
