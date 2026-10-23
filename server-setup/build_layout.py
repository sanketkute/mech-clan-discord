"""Build the new Mech Clan layout agreed with the owner on 2026-10-23: clean channel names, rank roles,
read-only info and log channels, a private leadership channel, and Discord's Community features.
Safe to re-run: existing roles and channels are found by name and reused."""
import re

from discord_api import call, get

GUILD = '1316103480644993116'
REASON = 'Mech Clan rebuild'

BIT = {name: 1 << n for name, n in {
    'KICK_MEMBERS': 1, 'ADMINISTRATOR': 3, 'VIEW_AUDIT_LOG': 7, 'VIEW_CHANNEL': 10, 'SEND_MESSAGES': 11,
    'MANAGE_MESSAGES': 13, 'MENTION_EVERYONE': 17, 'MUTE_MEMBERS': 22, 'MOVE_MEMBERS': 24, 'MANAGE_NICKNAMES': 27,
    'MANAGE_THREADS': 34, 'CREATE_PUBLIC_THREADS': 35, 'CREATE_PRIVATE_THREADS': 36, 'SEND_MESSAGES_IN_THREADS': 38,
    'MODERATE_MEMBERS': 40,
}.items()}


def bits(*names):
    total = 0
    for n in names:
        total |= BIT[n]
    return str(total)


# Highest first. Rank roles mirror the in-game rank (ClashPerk syncs them), so they carry no powers;
# moderation sits on Moderator, which the owner hands out manually.
ROLES = [
    ('Moderator', 0x1ABC9C, bits('KICK_MEMBERS', 'VIEW_AUDIT_LOG', 'MANAGE_MESSAGES', 'MENTION_EVERYONE', 'MUTE_MEMBERS',
                                 'MOVE_MEMBERS', 'MANAGE_NICKNAMES', 'MANAGE_THREADS', 'MODERATE_MEMBERS'), False),
    ('Leader', 0xE8B339, '0', True),
    ('Co-Leader', 0xE67E22, '0', True),
    ('Elder', 0x5865F2, '0', True),
    ('Member', 0x99AAB5, '0', True),
]

READ_ONLY = bits('SEND_MESSAGES', 'SEND_MESSAGES_IN_THREADS', 'CREATE_PUBLIC_THREADS', 'CREATE_PRIVATE_THREADS')

# (category, [(name, type, topic, access)]). type: 0 text, 2 voice, 5 announcement, 15 forum.
# access: 'open', 'read-only' (only leaders post), 'bots' (only bots post), 'leaders' (only leaders see it).
LAYOUT = [
    ('START HERE', [
        ('welcome', 0, 'Start here: who we are and how to join the clan.', 'read-only'),
        ('rules', 0, 'Clan rules and CWL rules.', 'read-only'),
        ('announcements', 5, 'Clan news from leadership.', 'read-only'),
    ]),
    ('CLAN', [
        ('chat', 0, 'General clan chat.', 'open'),
        ('cwl', 0, 'CWL sign-ups, roster and lineups.', 'open'),
        ('capital-raids', 0, 'Raid weekend coordination.', 'open'),
        ('bases', 15, 'One post per Town Hall. Open yours and use /layout post to share a base.', 'open'),
    ]),
    ('LOGS', [
        ('war-log', 0, 'Automatic war and CWL results and reminders.', 'bots'),
        ('clan-log', 0, 'Automatic joins, leaves and donations.', 'bots'),
    ]),
    ('LEADERSHIP', [
        ('leaders', 0, 'Leader and co-leader discussion.', 'leaders'),
    ]),
    ('VOICE', [
        ('Clan Voice', 2, None, 'open'),
    ]),
]
FORUM_TAGS = [f'TH{n}' for n in range(11, 19)]  # only used when creating #bases; bases_posts.py manages them after that


def ensure_roles():
    existing = {r['name']: r for r in get(f'/guilds/{GUILD}/roles')}
    for name, color, perms, hoist in ROLES:
        if name not in existing:
            existing[name] = call('POST', f'/guilds/{GUILD}/roles',
                                  {'name': name, 'color': color, 'permissions': perms, 'hoist': hoist, 'mentionable': True}, REASON)
            print(f'created role {name}')
        elif existing[name]['permissions'] != perms:
            call('PATCH', f'/guilds/{GUILD}/roles/{existing[name]["id"]}', {'permissions': perms}, REASON)
            print(f'updated permissions of {name}')
    # Bottom to top: TH roles (th_roles.py), rank roles, Moderator, the Clash bots (must sit above the roles they hand out), Owner.
    th = sorted((n for n in existing if re.fullmatch(r'TH\d+', n)), key=lambda n: int(n[2:]))
    stack = th + [name for name, _, _, _ in reversed(ROLES)] + [n for n in ('ClashPerk', 'ClashKing', 'Owner') if n in existing]
    try:
        call('PATCH', f'/guilds/{GUILD}/roles', [
            {'id': existing[name]['id'], 'position': pos} for pos, name in enumerate(stack, start=1)], REASON)
    except RuntimeError as e:
        # Happens when role positions are tied and there aren't enough slots under this bot's role.
        # Dragging any role in Server Settings > Roles renumbers them; then re-run.
        print(f'could not reorder roles, drag them in Discord instead: {e}')
    return {name: existing[name]['id'] for name in [n for n, _, _, _ in ROLES] + ['ClashPerk'] if name in existing}


def overwrites(access, roles):
    leaders = [roles['Leader'], roles['Co-Leader'], roles['Moderator']]
    if access == 'read-only':
        return [{'id': GUILD, 'type': 0, 'allow': '0', 'deny': READ_ONLY},
                {'id': roles['Moderator'], 'type': 0, 'allow': READ_ONLY, 'deny': '0'}]
    if access == 'bots':
        # ClashPerk has no Administrator and checks Send Messages before it posts a log.
        clash_bot = [{'id': roles['ClashPerk'], 'type': 0, 'allow': bits('SEND_MESSAGES'), 'deny': '0'}] if 'ClashPerk' in roles else []
        return [{'id': GUILD, 'type': 0, 'allow': '0', 'deny': READ_ONLY}] + clash_bot
    if access == 'leaders':
        return [{'id': GUILD, 'type': 0, 'allow': '0', 'deny': bits('VIEW_CHANNEL')}] + [
            {'id': r, 'type': 0, 'allow': bits('VIEW_CHANNEL'), 'deny': '0'} for r in leaders]
    return []


def ensure_channel(existing, name, ch_type, parent, topic, access, roles, position):
    body = {'name': name, 'type': ch_type, 'parent_id': parent, 'position': position,
            'permission_overwrites': overwrites(access, roles)}
    if topic:
        body['topic'] = topic
    if ch_type == 15:
        body['available_tags'] = [{'name': t} for t in FORUM_TAGS]
    match = existing.get((name, parent)) or existing.get((name, None))
    if match:
        body.pop('type')
        body.pop('available_tags', None)
        ch = call('PATCH', f'/channels/{match["id"]}', body, REASON)
        print(f'updated #{name}')
    else:
        ch = call('POST', f'/guilds/{GUILD}/channels', body, REASON)
        print(f'created #{name}')
    existing[(name, parent)] = ch
    return ch


def main():
    roles = ensure_roles()
    channels = get(f'/guilds/{GUILD}/channels')
    # Reuse the fresh #general as #chat so its history (the join messages) stays.
    for c in channels:
        if c['name'] == 'general' and c['type'] == 0:
            c['name'] = 'chat'
    existing = {(c['name'], c.get('parent_id')): c for c in channels}

    guild = get(f'/guilds/{GUILD}')
    community = 'COMMUNITY' in guild['features']
    built = {}
    for cat_pos, (cat_name, items) in enumerate(LAYOUT):
        cat_body = {'name': cat_name, 'type': 4, 'position': cat_pos,
                    'permission_overwrites': overwrites('leaders', roles) if cat_name == 'LEADERSHIP' else []}
        if (cat_name, None) in existing:
            cat_body.pop('type')
            cat = call('PATCH', f'/channels/{existing[(cat_name, None)]["id"]}', cat_body, REASON)
        else:
            cat = call('POST', f'/guilds/{GUILD}/channels', cat_body, REASON)
        existing[(cat_name, None)] = cat
        for pos, (name, ch_type, topic, access) in enumerate(items):
            if ch_type in (5, 15) and not community:
                continue  # announcement and forum channels come after Community is on
            built[name] = ensure_channel(existing, name, ch_type, cat['id'], topic, access, roles, pos)

    if not community:
        call('PATCH', f'/guilds/{GUILD}', {
            'features': guild['features'] + ['COMMUNITY'],
            'rules_channel_id': built['rules']['id'],
            'public_updates_channel_id': built['leaders']['id'],
            'explicit_content_filter': 2,
            'verification_level': max(guild['verification_level'], 1),
            'preferred_locale': 'en-US',
        }, REASON)
        print('enabled Community')
        for cat_name, items in LAYOUT:
            cat = existing[(cat_name, None)]
            for pos, (name, ch_type, topic, access) in enumerate(items):
                if ch_type in (5, 15):
                    built[name] = ensure_channel(existing, name, ch_type, cat['id'], topic, access, roles, pos)

    call('PATCH', f'/guilds/{GUILD}', {
        'system_channel_id': built['chat']['id'],  # join messages; #welcome stays an info page (owner, 2026-10-24)
        'system_channel_flags': (1 << 2) | (1 << 3),  # hide Discord's setup tips and sticker-reply prompts
        'default_message_notifications': 1,  # only @mentions notify by default
    }, REASON)
    call('PUT', f'/guilds/{GUILD}/members/{guild["owner_id"]}/roles/{roles["Moderator"]}', reason=REASON)
    print('server settings applied, owner given Moderator')


if __name__ == '__main__':
    main()
