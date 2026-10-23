"""Dump the Mech Clan server's structure and message history to a JSON file for review.

Usage (from the repo root): python server-setup/audit.py OUTPUT.json
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from discord_api import get

GUILD = '1316103480644993116'
MAX_MESSAGES = 1000
CHANNEL_TYPES = {0: 'text', 2: 'voice', 4: 'category', 5: 'announcement', 13: 'stage', 15: 'forum', 16: 'media'}
PERMS = {'ADMINISTRATOR': 3, 'MANAGE_CHANNELS': 4, 'MANAGE_GUILD': 5, 'VIEW_CHANNEL': 10, 'SEND_MESSAGES': 11,
         'MANAGE_MESSAGES': 13, 'MENTION_EVERYONE': 17, 'MANAGE_ROLES': 28, 'MANAGE_WEBHOOKS': 29}


def snowflake_time(sid):
    return datetime.fromtimestamp(((int(sid) >> 22) + 1420070400000) / 1000, timezone.utc).isoformat()[:16]


def perm_names(bits):
    bits = int(bits)
    return [name for name, bit in PERMS.items() if bits & (1 << bit)]


def try_get(path):
    try:
        return get(path)
    except RuntimeError as e:
        return {'error': str(e)}


def messages(channel_id):
    out, before = [], None
    while len(out) < MAX_MESSAGES:
        batch = get(f'/channels/{channel_id}/messages?limit=100' + (f'&before={before}' if before else ''))
        if not batch:
            break
        out += batch
        before = batch[-1]['id']
    return out


def main(path):
    guild = get(f'/guilds/{GUILD}?with_counts=true')
    roles = {r['id']: r for r in guild['roles']}
    members = get(f'/guilds/{GUILD}/members?limit=1000')
    role_counts = Counter(rid for m in members for rid in m['roles'])

    channels = []
    for ch in sorted(get(f'/guilds/{GUILD}/channels'), key=lambda c: (c['type'] != 4, c.get('position', 0))):
        info = {
            'id': ch['id'], 'name': ch['name'], 'type': CHANNEL_TYPES.get(ch['type'], ch['type']),
            'parent': ch.get('parent_id'), 'position': ch.get('position'), 'topic': ch.get('topic'),
            'created': snowflake_time(ch['id']), 'slowmode': ch.get('rate_limit_per_user'),
            'overwrites': [{
                'target': roles[o['id']]['name'] if o['id'] in roles else f'member {o["id"]}',
                'allow': perm_names(o['allow']), 'deny': perm_names(o['deny']),
            } for o in ch.get('permission_overwrites', [])],
        }
        if ch['type'] in (0, 2, 5, 13):
            try:
                msgs = messages(ch['id'])
            except RuntimeError as e:
                msgs, info['error'] = [], str(e)
            info['message_count'] = len(msgs) if len(msgs) < MAX_MESSAGES else f'{MAX_MESSAGES}+'
            if msgs:
                info['first_message'] = msgs[-1]['timestamp'][:16]
                info['last_message'] = msgs[0]['timestamp'][:16]
                info['authors'] = Counter(
                    m['author']['username'] + (' [bot]' if m['author'].get('bot') else '') for m in msgs).most_common(8)
                info['recent'] = [{
                    'at': m['timestamp'][:16], 'author': m['author']['username'],
                    'text': m['content'][:300], 'embeds': [e.get('title') or e.get('description', '')[:80] for e in m.get('embeds', [])],
                    'attachments': len(m.get('attachments', [])),
                } for m in msgs[:15]]
            pins = try_get(f'/channels/{ch["id"]}/pins')
            info['pins'] = [p['content'][:200] for p in pins] if isinstance(pins, list) else pins
        channels.append(info)

    audit = {
        'guild': {
            'name': guild['name'], 'created': snowflake_time(guild['id']), 'description': guild.get('description'),
            'members': guild.get('approximate_member_count'), 'online': guild.get('approximate_presence_count'),
            'verification_level': guild['verification_level'], 'features': guild['features'],
            'boost_tier': guild['premium_tier'], 'boosts': guild.get('premium_subscription_count'),
            'system_channel': guild.get('system_channel_id'), 'rules_channel': guild.get('rules_channel_id'),
            'afk_channel': guild.get('afk_channel_id'), 'emojis': [e['name'] for e in guild['emojis']],
            'stickers': [s['name'] for s in guild.get('stickers', [])],
        },
        'roles': [{
            'name': r['name'], 'position': r['position'], 'color': f'#{r["color"]:06x}', 'hoist': r['hoist'],
            'managed': r['managed'], 'mentionable': r['mentionable'], 'members': role_counts.get(r['id'], 0),
            'key_perms': perm_names(r['permissions']),
        } for r in sorted(guild['roles'], key=lambda r: -r['position'])],
        'members': [{
            'name': m['user']['username'], 'nick': m.get('nick'), 'bot': m['user'].get('bot', False),
            'joined': m['joined_at'][:10], 'roles': [roles[r]['name'] for r in m['roles'] if r in roles],
        } for m in members],
        'channels': channels,
        'active_threads': [t['name'] for t in try_get(f'/guilds/{GUILD}/threads/active').get('threads', [])],
        'integrations': [{'name': i['name'], 'type': i['type'], 'account': i.get('account', {}).get('name')}
                         for i in try_get(f'/guilds/{GUILD}/integrations') or []],
        'webhooks': [{'name': w.get('name'), 'channel': w['channel_id'], 'type': w['type']}
                     for w in try_get(f'/guilds/{GUILD}/webhooks') or []],
        'invites': [{'code': i['code'], 'channel': i['channel']['name'], 'uses': i.get('uses'), 'max_age': i.get('max_age'),
                     'inviter': i.get('inviter', {}).get('username')} for i in try_get(f'/guilds/{GUILD}/invites') or []],
        'automod_rules': [r['name'] for r in try_get(f'/guilds/{GUILD}/auto-moderation/rules') or []],
        'scheduled_events': [e['name'] for e in try_get(f'/guilds/{GUILD}/scheduled-events') or []],
    }
    with open(path, 'w') as f:
        json.dump(audit, f, indent=1, ensure_ascii=False)
    print(f'{len(channels)} channels, {len(members)} members, {len(guild["roles"])} roles -> {path}')


if __name__ == '__main__':
    main(sys.argv[1])
