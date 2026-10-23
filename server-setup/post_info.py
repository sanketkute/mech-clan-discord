"""Post posts/welcome.md to #welcome and posts/rules.md to #rules, approved by the owner on 2026-10-23.
{channel} placeholders become channel mentions. Safe to re-run: Mech Clan Bot edits its own earlier post
in the channel instead of posting again, so this is also how to publish later edits to the drafts."""
import re
from pathlib import Path

from discord_api import call, get

GUILD = '1316103480644993116'
POSTS = {'welcome': 'welcome.md', 'rules': 'rules.md'}
SUPPRESS_EMBEDS = 1 << 2  # no link preview for the in-game clan link


def main():
    channels = {c['name']: c['id'] for c in get(f'/guilds/{GUILD}/channels')}
    me = get('/users/@me')['id']
    for channel, file in POSTS.items():
        text = (Path(__file__).parent.parent / 'posts' / file).read_text(encoding='utf-8').strip()
        text = re.sub(r'\{([a-z-]+)\}', lambda m: f'<#{channels[m.group(1)]}>', text)
        if len(text) > 2000:
            raise SystemExit(f'{file} is {len(text)} characters; Discord allows 2000')
        body = {'content': text, 'flags': SUPPRESS_EMBEDS, 'allowed_mentions': {'parse': []}}
        mine = [m for m in get(f'/channels/{channels[channel]}/messages?limit=50') if m['author']['id'] == me]
        if mine:
            call('PATCH', f'/channels/{channels[channel]}/messages/{mine[-1]["id"]}', body)
            print(f'updated the post in #{channel}')
        else:
            call('POST', f'/channels/{channels[channel]}/messages', body)
            print(f'posted in #{channel}')


if __name__ == '__main__':
    main()
