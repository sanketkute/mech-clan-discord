"""Save every message in the Mech Clan server to a JSON file before anything is deleted.

Usage (from the repo root): python server-setup/backup.py OUTPUT.json
"""
import json
import sys

from discord_api import get

GUILD = '1316103480644993116'


def all_messages(channel_id):
    out, before = [], None
    while True:
        batch = get(f'/channels/{channel_id}/messages?limit=100' + (f'&before={before}' if before else ''))
        if not batch:
            return out
        out += batch
        before = batch[-1]['id']


def main(path):
    channels = get(f'/guilds/{GUILD}/channels')
    names = {c['id']: c['name'] for c in channels}
    backup = {'guild': get(f'/guilds/{GUILD}'), 'channels': []}
    for ch in channels:
        entry = {'id': ch['id'], 'name': ch['name'], 'type': ch['type'], 'category': names.get(ch.get('parent_id')),
                 'topic': ch.get('topic'), 'permission_overwrites': ch.get('permission_overwrites')}
        if ch['type'] in (0, 2, 5):
            entry['messages'] = [{
                'id': m['id'], 'at': m['timestamp'], 'author': m['author']['username'], 'bot': m['author'].get('bot', False),
                'content': m['content'], 'embeds': m.get('embeds', []), 'attachments': [a['url'] for a in m.get('attachments', [])],
            } for m in reversed(all_messages(ch['id']))]
        backup['channels'].append(entry)
        print(f"#{ch['name']}: {len(entry.get('messages', []))} messages")
    with open(path, 'w') as f:
        json.dump(backup, f, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main(sys.argv[1])
