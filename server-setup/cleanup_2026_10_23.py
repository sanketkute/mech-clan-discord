"""One-off cleanup approved by the owner on 2026-10-23: remove old bots, channels and roles,
then create a fresh #general and apply the two safety settings."""
from discord_api import call, get

GUILD = '1316103480644993116'
REASON = 'Server rebuild approved by owner'
OLD_BOTS = {'ClashKing', 'ClashPerk', 'Dyno', 'Custom Command', 'CLASH CLIFFS'}
OLD_ROLES = {f'Town Hall {n}' for n in range(1, 18)} | {'Bots', 'Leadership', 'Member'}
MENTION_EVERYONE = 1 << 17
VERIFICATION_LOW = 1


def attempt(label, method, path, body=None):
    try:
        result = call(method, path, body, reason=REASON)
        print(f'ok    {label}')
        return result
    except RuntimeError as e:
        print(f'FAIL  {label}: {e}')


def main():
    for i in get(f'/guilds/{GUILD}/integrations'):
        if i['name'] in OLD_BOTS:
            attempt(f'remove bot {i["name"]}', 'DELETE', f'/guilds/{GUILD}/integrations/{i["id"]}')

    channels = get(f'/guilds/{GUILD}/channels')
    for ch in sorted(channels, key=lambda c: c['type'] == 4):  # channels first, categories last
        attempt(f'delete channel #{ch["name"]}', 'DELETE', f'/channels/{ch["id"]}')

    for role in get(f'/guilds/{GUILD}/roles'):
        if role['name'] in OLD_ROLES and not role['managed']:
            attempt(f'delete role {role["name"]}', 'DELETE', f'/guilds/{GUILD}/roles/{role["id"]}')

    general = attempt('create #general', 'POST', f'/guilds/{GUILD}/channels', {'name': 'general', 'type': 0})
    settings = {'verification_level': VERIFICATION_LOW}
    if general:
        settings['system_channel_id'] = general['id']
    attempt('set verification Low + join messages to #general', 'PATCH', f'/guilds/{GUILD}', settings)

    everyone = next(r for r in get(f'/guilds/{GUILD}/roles') if r['id'] == GUILD)
    perms = int(everyone['permissions']) & ~MENTION_EVERYONE
    attempt('stop @everyone from pinging everyone', 'PATCH', f'/guilds/{GUILD}/roles/{GUILD}', {'permissions': str(perms)})


if __name__ == '__main__':
    main()
