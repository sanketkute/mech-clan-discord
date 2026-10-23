"""Create the Town Hall roles TH1-TH19 under Member, for ClashPerk's /autorole town-hall and onboarding.
The owner asked for all levels on 2026-10-23 (TH19 comes out in November 2026).
Safe to re-run: existing roles are found by name and reused."""
from discord_api import call, get

GUILD = '1316103480644993116'
REASON = 'Town Hall roles'
LEVELS = range(1, 20)


def main():
    existing = {r['name']: r for r in get(f'/guilds/{GUILD}/roles')}
    # Highest level first: new roles land tied at the bottom, and Discord shows the older of two tied roles higher.
    for n in reversed(LEVELS):
        name = f'TH{n}'
        if name not in existing:
            existing[name] = call('POST', f'/guilds/{GUILD}/roles',
                                  {'name': name, 'permissions': '0', 'hoist': False, 'mentionable': False}, REASON)
            print(f'created role {name}')
    # Bottom to top: TH1..TH19, then everything that was above them, in its current order.
    th_ids = {existing[f'TH{n}']['id'] for n in LEVELS}
    others = [r for r in sorted(get(f'/guilds/{GUILD}/roles'), key=lambda r: (r['position'], -int(r['id'])))
              if r['id'] not in th_ids and r['id'] != GUILD]
    stack = [existing[f'TH{n}']['id'] for n in LEVELS] + [r['id'] for r in others]
    try:
        call('PATCH', f'/guilds/{GUILD}/roles', [{'id': rid, 'position': pos} for pos, rid in enumerate(stack, start=1)], REASON)
    except RuntimeError as e:
        # This bot can't move its own role, so a full renumber can fail; moving one role makes Discord renumber the rest.
        print(f'full reorder failed ({e}), renumbering via TH1')
        call('PATCH', f'/guilds/{GUILD}/roles', [{'id': existing['TH1']['id'], 'position': 1}], REASON)


if __name__ == '__main__':
    main()
