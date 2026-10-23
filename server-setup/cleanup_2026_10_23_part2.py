"""Second half of the approved 2026-10-23 cleanup, run after the owner moved Mech Clan Bot's role to the top:
remove the 5 old bots and delete the 20 old roles."""
from cleanup_2026_10_23 import GUILD, OLD_BOTS, OLD_ROLES, REASON, attempt
from discord_api import call, get


def main():
    integrations = {i['account']['id']: i for i in get(f'/guilds/{GUILD}/integrations') if i['name'] in OLD_BOTS}
    for m in get(f'/guilds/{GUILD}/members?limit=1000'):
        user = m['user']
        if not user.get('bot') or user['username'] not in OLD_BOTS:
            continue
        integration = integrations.get(user['id'])
        try:
            if not integration:
                raise RuntimeError('no integration found')
            call('DELETE', f'/guilds/{GUILD}/integrations/{integration["id"]}', reason=REASON)
            print(f'ok    remove bot {user["username"]} (integration)')
        except RuntimeError as e:
            print(f'      integration removal failed for {user["username"]} ({str(e)[-60:]}), kicking instead')
            attempt(f'kick bot {user["username"]}', 'DELETE', f'/guilds/{GUILD}/members/{user["id"]}')

    for role in get(f'/guilds/{GUILD}/roles'):
        if role['name'] in OLD_ROLES and not role['managed']:
            attempt(f'delete role {role["name"]}', 'DELETE', f'/guilds/{GUILD}/roles/{role["id"]}')


if __name__ == '__main__':
    main()
