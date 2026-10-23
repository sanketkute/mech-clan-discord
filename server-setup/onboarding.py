"""Turn on Discord onboarding as agreed with the owner on 2026-10-23: every channel except #leaders is a default
channel, and one required question asks new members their Town Hall level (several answers allowed, for alts).
Linking stays optional; ClashPerk corrects the TH role of members who link.
Safe to re-run: the whole onboarding config is replaced, and the question keeps its id."""
import time

from discord_api import call, get

GUILD = '1316103480644993116'
REASON = 'Onboarding with Town Hall question'
HIDDEN = {'leaders'}
DISCORD_EPOCH_MS = 1420070400000
QUESTION = "What's your Town Hall level? Pick one for each account you play."


def new_id(n):
    # Discord wants snowflake ids for new questions and options; any unused one works.
    return str(((int(time.time() * 1000) - DISCORD_EPOCH_MS) << 22) + n)


def main():
    channels = [c for c in get(f'/guilds/{GUILD}/channels') if c['type'] != 4 and c['name'] not in HIDDEN]
    roles = {r['name']: r['id'] for r in get(f'/guilds/{GUILD}/roles')}
    current = {p['title']: p for p in get(f'/guilds/{GUILD}/onboarding')['prompts']}
    old = current.get(QUESTION)
    old_options = {o['title']: o['id'] for o in old['options']} if old else {}
    options = [{'id': old_options.get(f'TH{n}') or new_id(n), 'title': f'TH{n}', 'role_ids': [roles[f'TH{n}']], 'channel_ids': []}
               for n in range(19, 0, -1)]
    prompt = {'id': old['id'] if old else new_id(0), 'type': 1, 'title': QUESTION, 'options': options,
              'single_select': False, 'required': True, 'in_onboarding': True}
    result = call('PUT', f'/guilds/{GUILD}/onboarding', {
        'prompts': [prompt], 'default_channel_ids': [c['id'] for c in channels], 'enabled': True, 'mode': 0}, REASON)
    print(f'onboarding enabled={result["enabled"]}, {len(result["default_channel_ids"])} default channels, '
          f'{len(result["prompts"])} question(s)')


if __name__ == '__main__':
    main()
