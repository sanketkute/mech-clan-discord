"""Mech Clan Bot, run on the owner's laptop (set up 2026-10-23).

Checks mech clan through the official Clash API every minute and posts joins, leaves, promotions and Town Hall
upgrades to #clan-log, plus one live donation board a day (DONATION_LOG), and war and CWL attacks to #war-log.
Town Hall levels come from each member's profile, which updates sooner than the clan's member list.
ClashPerk takes up to an hour for the same logs right now. Also adds the slash commands /cwl-medals, /bases and
/rules.

Needs DISCORD_TOKEN, COC_EMAIL and COC_PASSWORD in .env (COC_* is the developer.clashofclans.com login; coc.py
makes a new API key whenever the laptop's IP changes). What the bot has already seen is kept in bot_state.json,
so a restart neither reposts nor misses anything.
Run from the repo root: .venv\\Scripts\\pythonw.exe bot\\mech_bot.py   (output goes to bot.log in the repo root)"""
import asyncio
import json
import logging
import re
import socket
import urllib.request
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import coc
import discord
from discord import app_commands
from discord.ext import tasks
from discord.http import Route

from donation_board import build_donation_board
from war_board import IS_COMPONENTS_V2, attack_line, attack_log, build_board, detail

ROOT = Path(__file__).parent.parent  # the repo root, which holds .env, posts/ and the bot's local files
GUILD = discord.Object(id=1316103480644993116)
CLAN = '#YU9YY8UV'
STATE_FILE = ROOT / 'bot_state.json'
RULES_FILE = ROOT / 'posts' / 'rules.md'

ROLES = {'member': 'Member', 'admin': 'Elder', 'coLeader': 'Co-Leader', 'leader': 'Leader'}
RANK = list(ROLES)
# Game art comes from ClashKing Assets (assets.clashk.ing, credited in the bot's About Me). Small icons were
# uploaded as the bot's own emojis on 2026-10-23 (th1-th18, bk, aq, gw, rc, mp, dd, xp, war_star, no_star, ...);
# bigger pictures are linked straight from the asset site.
# The live war board (war_board.py) is on trial in #leaders since 2026-10-24; the per-attack cards in #war-log
# keep running until the owner moves the board there.
BOARD_CHANNEL = 'leaders'
BADGE_HOST = 'https://api-assets.clashofclans.com/'  # opponent badges are only fetched from Supercell's server
SUPPRESS_NOTIFICATIONS = 1 << 12  # message flag, the same as starting a message with @silent
# The live daily donation board in #clan-log (donation_board.py, the owner's pick on 2026-10-24). Donations are
# counted even while it's off, so turning it back on picks up from then instead of posting everything at once.
DONATION_LOG = True
HERO_ICONS = {'Barbarian King': 'bk', 'Archer Queen': 'aq', 'Grand Warden': 'gw', 'Royal Champion': 'rc',
              'Minion Prince': 'mp', 'Dragon Duke': 'dd'}
TH_IMAGE = 'https://assets.clashk.ing/buildings/home-village/town_hall/level_{}.webp'
CWL_ICON = 'https://assets.clashk.ing/bot/cwl/War{}.png'  # Bronze III to Champion I only, e.g. WarCrystalI
CWL_MEDAL_IMAGE = 'https://assets.clashk.ing/bot/icons/cwl_medal.png'
# The same CWL league badges are bot emojis named cwl_bronze3 ... cwl_champion1 (uploaded 2026-10-23).
BADGE_TIERS = ('Bronze', 'Silver', 'Gold', 'Crystal', 'Master', 'Champion')
ROMAN = {'I': 1, 'II': 2, 'III': 3}
ALL_LEAGUES = 0
# Colors: join and win green, leave and loss red, war gold, battle day orange, rank changes amber, donations blue.
GREEN, RED, GOLD, ORANGE, AMBER, BLUE, PURPLE, GREY = (0x2ECC71, 0xE74C3C, 0xE8B339, 0xE67E22, 0xF1C40F,
                                                        0x3498DB, 0x9B59B6, 0x99AAB5)
PLACES = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th']

# CWL medals, from ClashPerk's src/util/constants.ts: league id -> (name, medals for places 1-8 with 8+ stars,
# bonus medals for 15v15 and 30v30). Fewer stars pay less: 0 stars 20%, then +10% per star up to 8.
CWL_LEAGUES = {
    48000001: ('Bronze League III', [46, 44, 42, 40, 38, 36, 34, 32], (1, 2)),
    48000002: ('Bronze League II', [58, 56, 54, 52, 50, 48, 46, 44], (1, 2)),
    48000003: ('Bronze League I', [70, 68, 66, 64, 62, 60, 58, 56], (1, 2)),
    48000004: ('Silver League III', [88, 85, 82, 79, 76, 73, 70, 67], (1, 2)),
    48000005: ('Silver League II', [106, 103, 100, 97, 94, 91, 88, 85], (1, 2)),
    48000006: ('Silver League I', [124, 121, 118, 115, 112, 109, 106, 103], (1, 2)),
    48000007: ('Gold League III', [148, 144, 140, 136, 132, 128, 124, 120], (2, 4)),
    48000008: ('Gold League II', [172, 168, 164, 160, 156, 152, 148, 144], (2, 4)),
    48000009: ('Gold League I', [196, 192, 188, 184, 180, 176, 172, 168], (2, 4)),
    48000010: ('Crystal League III', [220, 216, 212, 208, 204, 200, 196, 192], (2, 4)),
    48000011: ('Crystal League II', [244, 240, 236, 232, 228, 224, 220, 216], (2, 4)),
    48000012: ('Crystal League I', [274, 269, 264, 259, 254, 249, 244, 239], (2, 4)),
    48000013: ('Master League III', [304, 299, 294, 289, 284, 279, 274, 269], (3, 6)),
    48000014: ('Master League II', [334, 329, 324, 319, 314, 309, 304, 299], (3, 6)),
    48000015: ('Master League I', [364, 359, 354, 349, 344, 339, 334, 329], (3, 6)),
    48000016: ('Champion League III', [388, 384, 380, 376, 372, 368, 364, 360], (4, 0)),
    48000017: ('Champion League II', [412, 408, 404, 400, 396, 392, 388, 384], (4, 0)),
    48000018: ('Champion League I', [436, 432, 428, 424, 420, 416, 412, 408], (4, 0)),
    48000019: ('Titan League III', [454, 451, 448, 445, 442, 439, 436, 433], (5, 0)),
    48000020: ('Titan League II', [472, 469, 466, 463, 460, 457, 454, 451], (5, 0)),
    48000021: ('Titan League I', [490, 487, 484, 481, 478, 475, 472, 469], (5, 0)),
    48000022: ('Legend League', [508, 505, 502, 499, 496, 493, 490, 487], (6, 0)),
}

log = logging.getLogger('mech_bot')


def load_env():
    env = {}
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    return env


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def save_state(state):
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=1), encoding='utf-8')
    tmp.replace(STATE_FILE)


def api_time(value):
    # The Clash API writes times like 20261023T210000.000Z.
    return datetime.strptime(value, '%Y%m%dT%H%M%S.%fZ').replace(tzinfo=timezone.utc)


def stamp(value, style='R'):
    return f'<t:{int(api_time(value).timestamp())}:{style}>'


def game_link(action, tag):
    return f'https://link.clashofclans.com/en?action={action}&tag={tag.lstrip("#")}'


def cwl_icon(league_name):
    words = league_name.split()  # 'Crystal League I' -> WarCrystalI
    return CWL_ICON.format(words[0] + words[-1]) if words[0] in ('Bronze', 'Silver', 'Gold', 'Crystal', 'Master',
                                                                 'Champion') else None


def badge(side, size='medium'):
    return (side.get('badgeUrls') or {}).get(size)


def rules_sections():
    """'### Title' sections of posts/rules.md, with {channel} placeholders left in."""
    parts = re.split(r'^### +(.+)$', RULES_FILE.read_text(encoding='utf-8'), flags=re.M)
    return {title.strip(): body.strip() for title, body in zip(parts[1::2], parts[2::2])}


class MechClanBot(discord.Client):
    def __init__(self, env):
        super().__init__(intents=discord.Intents.default())
        self.env = env
        self.tree = app_commands.CommandTree(self)
        self.coc = None
        self.state = load_state()
        self.icons = {}
        self.live_wars = {}  # war id -> latest war JSON, for the board's buttons

    async def setup_hook(self):
        await self.tree.sync(guild=GUILD)
        try:
            self.icons = {emoji.name: str(emoji) for emoji in await self.fetch_application_emojis()}
        except Exception:
            log.exception('could not load the bot emojis, so cards fall back to text')
        if not (self.env.get('COC_EMAIL') and self.env.get('COC_PASSWORD')):
            log.warning('COC_EMAIL or COC_PASSWORD missing from .env, so the clan and war logs are off')
            return
        try:
            self.coc = coc.Client(key_names='Mech Clan Bot', key_count=1,
                                  load_game_data=coc.LoadGameData(never=True))
            await self.coc.login(self.env['COC_EMAIL'], self.env['COC_PASSWORD'])
        except Exception:
            log.exception('Clash API login failed, so the clan and war logs are off')
            self.coc = None
            return
        self.poll.start()

    async def on_ready(self):
        log.info('logged in as %s', self.user)

    async def on_interaction(self, interaction):
        """The war board's buttons (custom id wb:<what>:<war id>): answer privately with the details."""
        custom_id = (interaction.data or {}).get('custom_id', '')
        if interaction.type != discord.InteractionType.component or not custom_id.startswith('wb:'):
            return
        _, what, war_id = custom_id.split(':', 2)
        war = self.live_wars.get(war_id)
        if war is None:
            await interaction.response.send_message('The bot is still loading this war, or it is too old. '
                                                    'Try again in a minute.', ephemeral=True)
            return
        title, body = detail(war, CLAN, what, self.icon)
        await interaction.response.send_message(embed=self.card(BLUE, title, body), ephemeral=True)

    def channel(self, name):
        return discord.utils.get(self.get_guild(GUILD.id).channels, name=name)

    def icon(self, name, fallback=''):
        return self.icons.get(name, fallback)

    def th(self, level):
        return self.icon(f'th{level}', f'TH{level}')

    def card(self, color, title=None, description=None, url=None):
        """An embed with the clan's badge and name on top and the time at the bottom.
        A phone notification shows the title and description as plain text ("title: description"), with bot
        emojis, bold and <t:> timestamps left raw. So both stay plain words; icons go in fields and pictures."""
        embed = discord.Embed(color=color, title=title, description=description, url=url,
                              timestamp=discord.utils.utcnow())
        embed.set_author(name='mech clan', url=game_link('OpenClanProfile', CLAN), icon_url=self.state.get('badge'))
        return embed

    @tasks.loop(seconds=60)
    async def poll(self):
        for check in (self.check_clan, self.check_war):
            try:
                await check()
            except coc.Maintenance:
                log.info('Clash API maintenance, skipping %s', check.__name__)
            except Exception:
                log.exception('%s failed', check.__name__)
        save_state(self.state)

    @poll.before_loop
    async def before_poll(self):
        await self.wait_until_ready()

    async def check_clan(self):
        data = await self.coc.http.get_clan(CLAN)
        self.state['war_league_id'] = (data.get('warLeague') or {}).get('id')
        self.state['badge'] = badge(data, 'small')
        before = self.state.get('members')
        profiles = await self.profiles([m['tag'] for m in data['memberList']])
        now = {m['tag']: {'name': m['name'], 'role': m['role'],
                          # A Town Hall never goes down, so the highest of profile, clan list and last value is
                          # right even when a profile fails to load and the clan list is behind.
                          'th': max((profiles.get(m['tag'], {}).get('townHallLevel') or 0, m.get('townHallLevel') or 0,
                                     ((before or {}).get(m['tag']) or {}).get('th') or 0)) or None,
                          'given': m['donations'], 'received': m['donationsReceived']} for m in data['memberList']}
        self.state['members'] = now
        if before is None:
            return  # first run: remember the clan, post nothing
        channel = self.channel('clan-log')
        size = f'{len(now)}/50'
        for tag in now.keys() - before.keys():
            await channel.send(embed=await self.player_card(tag, now[tag], True, size))
        for tag in before.keys() - now.keys():
            await channel.send(embed=await self.player_card(tag, before[tag], False, size))

        ranks, upgrades, donations = [], [], []
        for tag in now.keys() & before.keys():
            new, old = now[tag], before[tag]
            if new['role'] != old['role']:
                up = RANK.index(new['role']) > RANK.index(old['role'])
                ranks.append(f"{new['name']} {'promoted' if up else 'demoted'} to {ROLES[new['role']]}")
            if new['th'] and old['th'] and new['th'] > old['th']:
                upgrades.append((old['th'], new['th'], new['name']))
            # Both counters drop back to 0 when the season ends, which gives a negative difference. A member saved
            # without counters (by an older version) counts as no change.
            given = new['given'] - old.get('given', new['given'])
            received = new['received'] - old.get('received', new['received'])
            if DONATION_LOG and (given > 0 or received > 0):
                donations.append((tag, max(given, 0), max(received, 0)))
        if ranks:
            await channel.send(embed=self.card(AMBER, 'Rank change' if len(ranks) == 1 else 'Rank changes',
                                               '\n'.join(ranks)))
        if upgrades:
            embed = self.card(PURPLE, 'Town Hall upgrade' if len(upgrades) == 1 else 'Town Hall upgrades',
                              '\n'.join(f"{name} is now Town Hall {new}" for old, new, name in upgrades))
            embed.add_field(name='Town Hall', value='\n'.join(
                f"{self.th(old)} ➜ {self.th(new)}" + (f"  {name}" if len(upgrades) > 1 else '')
                for old, new, name in upgrades)[:1024])
            if len(upgrades) == 1:
                embed.set_thumbnail(url=TH_IMAGE.format(upgrades[0][1]))
            await channel.send(embed=embed)
        if donations:
            await self.update_donation_board(donations, now)

    async def profiles(self, tags):
        """Each member's own profile. Its Town Hall updates sooner than the clan's member list: on 2026-10-24
        Yuki's TH12 reached the list an hour after ClashPerk, which reads profiles, had posted it. One request per
        member every minute; a profile that fails to load is left out."""
        results = await asyncio.gather(*(self.coc.http.get_player(tag) for tag in tags), return_exceptions=True)
        for tag, result in zip(tags, results):
            if isinstance(result, Exception):
                log.warning('could not load profile %s: %r', tag, result)
        return {tag: result for tag, result in zip(tags, results) if isinstance(result, dict)}

    async def update_donation_board(self, donations, members):
        """Add this minute's donations (tag, given, received) to today's board in #clan-log. The first donation of
        the day (laptop time) posts a new board, silently; after that it is edited."""
        today = datetime.now().astimezone()
        board = self.state.get('donation_board')
        if not board or board['date'] != today.date().isoformat():
            board = self.state['donation_board'] = {'date': today.date().isoformat(), 'members': {}}
        for tag, given, received in donations:
            row = board['members'].setdefault(tag, {'given': 0, 'received': 0})
            row['name'] = members[tag]['name']
            row['given'] += given
            row['received'] += received
        rows = [(row['name'], row['given'], row['received']) for row in board['members'].values()]
        body = {'flags': IS_COMPONENTS_V2, 'allowed_mentions': {'parse': []},
                'components': build_donation_board(rows, sum(m['given'] for m in members.values()), self.icon,
                                                   today, int(today.timestamp()))}
        if board.get('message'):
            try:
                await self.http.request(Route('PATCH', '/channels/{channel_id}/messages/{message_id}',
                                              channel_id=board['channel'], message_id=board['message']), json=body)
                return
            except discord.NotFound:
                log.warning('donation board %s was deleted, posting a new one', board['message'])
        channel = self.channel('clan-log')
        message = await self.http.request(Route('POST', '/channels/{channel_id}/messages', channel_id=channel.id),
                                          json={**body, 'flags': IS_COMPONENTS_V2 | SUPPRESS_NOTIFICATIONS})
        board['channel'], board['message'] = str(channel.id), message['id']

    async def player_card(self, tag, member, joined, size):
        try:
            player = await self.coc.http.get_player(tag)
        except Exception:
            log.exception('could not load player %s', tag)
            player = {}
        town_hall = player.get('townHallLevel') or member['th']
        embed = self.card(GREEN if joined else RED, member['name'], url=game_link('OpenPlayerProfile', tag),
                          description=f"{'Joined' if joined else 'Left'} the clan · {size}")
        new_clan = player.get('clan') or {}
        if not joined and new_clan.get('tag') not in (None, CLAN):
            embed.description += f"\nNow in {new_clan['name']}"
        if town_hall:
            embed.set_thumbnail(url=TH_IMAGE.format(town_hall))
        embed.add_field(name='Town Hall', value=f"{self.th(town_hall)} **{town_hall}**")
        if player:
            embed.add_field(name='Level', value=f"{self.icon('xp')} **{player['expLevel']}**")
            embed.add_field(name='War stars', value=f"{self.icon('war_star')} **{player['warStars']:,}**")
            heroes = '   '.join(f"{self.icon(HERO_ICONS.get(h['name'], ''), h['name'])} **{h['level']}**"
                                 for h in player.get('heroes', []) if h.get('village') == 'home')
            if heroes:
                embed.add_field(name='Heroes', value=heroes, inline=False)
            if player.get('warPreference'):
                opted_in = player['warPreference'] == 'in'
                embed.add_field(name='War preference', value=f"{self.icon('opt_in' if opted_in else 'opt_out')} "
                                                             f"{'In' if opted_in else 'Out'}")
        league = player.get('leagueTier') or {}
        footer = tag + (f" · was {ROLES.get(member['role'], member['role'])}" if not joined else '')
        embed.set_footer(text=f"{footer} · {league['name']}" if league.get('name') else footer,
                         icon_url=(league.get('iconUrls') or {}).get('small'))
        return embed

    async def current_wars(self):
        """Our regular war, or our CWL wars that haven't been reported as ended yet."""
        try:
            war = await self.coc.http.get_clan_current_war(CLAN)
        except coc.PrivateWarLog:
            log.warning('the war log is private, so war logs are off')
            return []
        if war.get('state') != 'notInWar':
            return [war]
        try:
            group = await self.coc.http.get_clan_war_league_group(CLAN)
        except coc.NotFound:
            return []
        cwl = self.state.setdefault('cwl', {})
        if cwl.get('season') != group.get('season'):
            cwl.clear()
            cwl.update(season=group.get('season'), ours={}, done=[])
        wars = []
        for number, round_ in enumerate(group.get('rounds', []), start=1):
            tag = cwl['ours'].get(str(number))
            if tag in cwl['done']:
                continue
            if tag:
                war = await self.coc.http.get_cwl_wars(tag)
            else:
                for war_tag in round_['warTags']:
                    if war_tag == '#0':
                        continue  # the round isn't drawn yet
                    war = await self.coc.http.get_cwl_wars(war_tag)
                    if CLAN in (war['clan']['tag'], war['opponent']['tag']):
                        cwl['ours'][str(number)] = tag = war_tag
                        break
                else:
                    continue
            war.update(_cwl_tag=tag, _round=number)
            wars.append(war)
        return wars

    async def check_war(self):
        first_run = 'wars' not in self.state
        seen_wars = self.state.setdefault('wars', {})
        for war in await self.current_wars():
            if war.get('state') in (None, 'notInWar'):
                continue
            us, them = ((war['clan'], war['opponent']) if war['clan']['tag'] == CLAN
                        else (war['opponent'], war['clan']))
            war_id = f"{war['preparationStartTime']}{them['tag']}"
            self.live_wars[war_id] = war
            attacks = sorted(
                [(a, True) for m in us.get('members', []) for a in m.get('attacks', [])]
                + [(a, False) for m in them.get('members', []) for a in m.get('attacks', [])],
                key=lambda pair: pair[0]['order'])
            seen = seen_wars.get(war_id)
            if seen is None:
                # On the very first run, don't replay attacks that happened before the bot existed.
                seen = seen_wars[war_id] = {'state': war['state'] if first_run else None,
                                            'order': attacks[-1][0]['order'] if first_run and attacks else 0}
            await self.report_war(war, us, them, seen, attacks)
            try:
                await self.update_board(war, us, them, war_id)
            except Exception:
                log.exception('war board update failed for %s', war_id)
            if war['state'] == 'warEnded' and war.get('_cwl_tag'):
                self.state['cwl']['done'].append(war['_cwl_tag'])
        # Forget wars that started more than two weeks ago. A war id starts with its 20-character start time.
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        for war_id in [w for w in seen_wars if api_time(w[:20]) < cutoff]:
            del seen_wars[war_id]
        boards = self.state.get('boards', {})
        for war_id in [w for w in boards if api_time(w[:20]) < cutoff]:
            await self.remove_opponent_badge(boards.pop(war_id).get('emoji'))

    async def update_board(self, war, us, them, war_id):
        """Create or edit the war's board in BOARD_CHANNEL, and post new attacks to the board's thread."""
        boards = self.state.setdefault('boards', {})
        board = boards.get(war_id)
        if board and board.get('final'):
            return
        emoji = 'opp_' + them['tag'].lstrip('#').lower()
        if emoji not in self.icons:
            await self.add_opponent_badge(emoji, them)
        kind = f"CWL round {war['_round']}" if war.get('_cwl_tag') else 'War'
        body = {'flags': IS_COMPONENTS_V2, 'allowed_mentions': {'parse': []},
                'components': build_board(war, CLAN, self.icon, kind=kind, opponent_icon=self.icons.get(emoji),
                                          war_id=war_id)}
        if board is not None:
            try:
                await self.http.request(Route('PATCH', '/channels/{channel_id}/messages/{message_id}',
                                              channel_id=board['channel'], message_id=board['message']), json=body)
            except discord.NotFound:
                log.warning('war board %s was deleted, posting a new one', board['message'])
                board = None
        if board is None:
            channel = self.channel(BOARD_CHANNEL)
            # Posted silently: the War declared, Battle day and result cards carry the notifications, with plain
            # text. Only a new message can be silent, so the edits keep just the Components V2 flag.
            message = await self.http.request(Route('POST', '/channels/{channel_id}/messages', channel_id=channel.id),
                                              json={**body, 'flags': IS_COMPONENTS_V2 | SUPPRESS_NOTIFICATIONS})
            thread = await self.http.request(
                Route('POST', '/channels/{channel_id}/messages/{message_id}/threads',
                      channel_id=channel.id, message_id=message['id']),
                json={'name': f"Attack log vs {them['name']}"[:100], 'auto_archive_duration': 10080})
            board = boards[war_id] = {'channel': str(channel.id), 'message': message['id'], 'thread': thread['id'],
                                      'order': 0, 'emoji': emoji}
        new = [e for e in attack_log(us, them) if e['attack']['order'] > board['order']]
        chunk = ''
        for line in [attack_line(e, self.icon, in_thread=True) for e in new] + [None]:
            if line is None or len(chunk) + len(line) > 1900:
                if chunk:
                    await self.http.request(Route('POST', '/channels/{channel_id}/messages', channel_id=board['thread']),
                                            json={'content': chunk, 'allowed_mentions': {'parse': []}})
                chunk = ''
            if line:
                chunk += line + '\n'
        if new:
            board['order'] = new[-1]['attack']['order']
        board['final'] = war['state'] == 'warEnded'

    async def add_opponent_badge(self, name, them):
        """Upload the opponent's badge as a bot emoji for the board's "vs" header."""
        url = (them.get('badgeUrls') or {}).get('medium', '')
        if not url.startswith(BADGE_HOST):
            return
        try:
            data = await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=20).read())
            if data[:8] != b'\x89PNG\r\n\x1a\n' or len(data) > 256 * 1024:
                log.warning('opponent badge %s is not a small PNG, skipping', url)
                return
            self.icons[name] = str(await self.create_application_emoji(name=name, image=data))
        except Exception:
            log.exception('could not add the opponent badge %s', name)

    async def remove_opponent_badge(self, name):
        """Delete an old opponent badge emoji once no remaining board uses it."""
        if not name or any(b.get('emoji') == name for b in self.state.get('boards', {}).values()):
            return
        for emoji in await self.fetch_application_emojis():
            if emoji.name == name:
                await emoji.delete()
        self.icons.pop(name, None)

    async def report_war(self, war, us, them, seen, attacks):
        channel = self.channel('war-log')
        cwl = war.get('_cwl_tag')
        kind = f"CWL round {war['_round']}" if cwl else 'War'
        size = f"{war['teamSize']} vs {war['teamSize']}"
        score = (f"{us['name']} {us.get('stars', 0)}⭐ {us.get('destructionPercentage', 0):.1f}%  —  "
                 f"{them['name']} {them.get('stars', 0)}⭐ {them.get('destructionPercentage', 0):.1f}%")
        opponent = f"[{them['name']}]({game_link('OpenClanProfile', them['tag'])}) · level {them.get('clanLevel', '?')}"
        members = {m['tag']: m for m in us.get('members', []) + them.get('members', [])}
        changed = war['state'] != seen['state']
        seen['state'] = war['state']

        # Order in the channel: war or battle day announced, then attacks, then the result.
        if changed and war['state'] in ('preparation', 'inWar'):
            if war['state'] == 'preparation':
                embed = self.card(GOLD, f'{kind} declared', f"Against {them['name']} · {size}")
                embed.add_field(name='Opponent', value=opponent, inline=False)
                embed.add_field(name='Battle day', value=f"{self.icon('clock')} {stamp(war['startTime'])} · "
                                                         f"{stamp(war['startTime'], 't')}")
                embed.set_footer(text='Preparation day: set up your war base')
            else:
                embed = self.card(ORANGE, 'Battle day' + (f' · {kind}' if cwl else ''),
                                  f"Against {them['name']} · use {'your attack' if cwl else 'both attacks'}")
                embed.add_field(name='Opponent', value=opponent, inline=False)
                embed.add_field(name='Size', value=f"{self.icon('people')} {size}")
                embed.add_field(name='Ends', value=f"{self.icon('clock')} {stamp(war['endTime'])} · "
                                                   f"{stamp(war['endTime'], 't')}")
                embed.set_footer(text=score)
            if badge(them):
                embed.set_thumbnail(url=badge(them))
            await channel.send(embed=embed)

        new = [pair for pair in attacks if pair[0]['order'] > seen['order']]
        if new:
            for ours, title, color in ((True, 'Our attacks', GREEN), (False, 'Enemy attacks', RED)):
                lines = []
                for attack, side in new:
                    if side != ours:
                        continue
                    # Plain text with standard stars, which a phone notification shows as they are.
                    a, d = members[attack['attackerTag']], members[attack['defenderTag']]
                    lines.append(f"{a['name']} #{a['mapPosition']} ➜ #{d['mapPosition']} · "
                                 f"{'★' * attack['stars']}{'☆' * (3 - attack['stars'])} "
                                 f"{attack['destructionPercentage']}%")
                if lines:
                    embed = self.card(color, title, '\n'.join(lines)[:4000])
                    embed.set_footer(text=score)
                    await channel.send(embed=embed)
            seen['order'] = new[-1][0]['order']

        if changed and war['state'] == 'warEnded':
            ours, theirs = ((side.get('stars', 0), side.get('destructionPercentage', 0)) for side in (us, them))
            won, tied = ours > theirs, ours == theirs
            verb = 'drew with' if tied else ('beat' if won else 'lost to')  # the same headline as the war board
            per_member = war.get('attacksPerMember') or (1 if cwl else 2)
            used = sum(len(m.get('attacks', [])) for m in us.get('members', []))
            missed = [f"{m['name']} ({per_member - len(m.get('attacks', []))})" for m in us.get('members', [])
                      if len(m.get('attacks', [])) < per_member]
            embed = self.card(GREEN if won else (GREY if tied else RED), f"We {verb} {them['name']}",
                              f"{ours[0]} – {theirs[0]} stars · {ours[1]:.1f}% – {theirs[1]:.1f}%")
            embed.set_footer(text=f'{kind} · {size}')
            embed.add_field(name='Attacks used',
                            value=f"{self.icon('sword')} {used}/{per_member * len(us.get('members', []))}")
            embed.add_field(name='Missed attacks', inline=False,
                            value=f"{self.icon('cross')} {', '.join(missed)}"[:1000] if missed
                            else f"{self.icon('tick')} None, every attack was used!")
            if badge(them):
                embed.set_thumbnail(url=badge(them))
            await channel.send(embed=embed)


bot = MechClanBot(load_env())


@bot.tree.command(name='cwl-medals', description='CWL medals for each place in a league', guild=GUILD)
@app_commands.describe(league='Defaults to our current CWL league',
                       stars='Your total stars this CWL; 8 or more pays full medals')
@app_commands.choices(league=[app_commands.Choice(name='All leagues', value=ALL_LEAGUES)] +
                     [app_commands.Choice(name=name, value=lid) for lid, (name, _, _) in CWL_LEAGUES.items()])
async def cwl_medals(interaction: discord.Interaction, league: Optional[app_commands.Choice[int]] = None,
                     stars: Optional[app_commands.Range[int, 0, 21]] = None):
    if league and league.value == ALL_LEAGUES:
        await interaction.response.send_message(embed=all_leagues_card())
        return
    league_id = league.value if league else bot.state.get('war_league_id')
    if league_id not in CWL_LEAGUES:
        await interaction.response.send_message('Pick a league: our current CWL league isn\'t known yet.', ephemeral=True)
        return
    name, medals, (bonus15, bonus30) = CWL_LEAGUES[league_id]
    share = min(stars, 8) * 10 + 20 if stars is not None else 100
    medal, star = bot.icon('cwl_medal'), bot.icon('war_star')
    if share < 100:
        description = (f'Medals for each final place with {star} **{stars} stars**, which pays {share}% '
                       f'(8+ stars pays full medals).')
    else:
        description = f'Medals for each final place, for players with {star} **8+ stars** in the week.'
    embed = bot.card(GOLD, f'CWL medals · {name}', description)
    if cwl_icon(name):
        embed.set_thumbnail(url=cwl_icon(name))
    # Eight places plus the bonus box make a 3 x 3 grid.
    for place, full in zip(PLACES, medals):
        embed.add_field(name=f'{place} place', value=f'{medal} **{round(full * share / 100)}**')
    bonus = '\n'.join(f'{n} in {size}' for n, size in ((bonus15, '15v15'), (bonus30, '30v30')) if n)
    embed.add_field(name='Bonus medals', value=bonus or 'None in this league')
    await interaction.response.send_message(embed=embed)


def league_badge(name):
    words = name.split()  # 'Crystal League I' -> the cwl_crystal1 emoji; Titan and Legend have no badge yet
    if words[0] in BADGE_TIERS and words[-1] in ROMAN:
        return bot.icon(f'cwl_{words[0].lower()}{ROMAN[words[-1]]}', bot.icon('cwl_medal'))
    return bot.icon('cwl_medal')


def all_leagues_card():
    """One box per tier (Bronze ... Legend) with 1st-8th place medals per league, so eight boxes plus a hint
    make the same 3 x 3 grid as the single-league card."""
    ours = bot.state.get('war_league_id')
    embed = bot.card(GOLD, 'CWL medals · all leagues',
                     f"Medals for 1st – 8th place with {bot.icon('war_star')} **8+ stars**. "
                     f"Bonus medals are for 15v15 / 30v30.")
    embed.set_thumbnail(url=CWL_MEDAL_IMAGE)
    tiers = {}
    for league_id, (name, medals, bonus) in CWL_LEAGUES.items():
        tiers.setdefault(name.split()[0], []).append((league_id, name, medals, bonus))
    for tier, leagues in tiers.items():
        bonus15, bonus30 = leagues[0][3]
        lines = []
        for league_id, name, medals, _ in leagues:
            label = f' {name.split()[-1]}' if len(leagues) > 1 else ''
            lines.append(f"{league_badge(name)}{label} · **{medals[0]}**–{medals[-1]}"
                         + ('  ◀ **us**' if league_id == ours else ''))
        embed.add_field(name=f"{tier} · bonus {bonus15}" + (f" / {bonus30}" if bonus30 else ''), value='\n'.join(lines))
    embed.add_field(name='One league in detail', value='Run `/cwl-medals` and pick the league.')
    return embed


@bot.tree.command(name='bases', description='Jump to the bases post for a Town Hall', guild=GUILD)
@app_commands.describe(town_hall='Town Hall level')
async def bases(interaction: discord.Interaction, town_hall: app_commands.Range[int, 11, 19]):
    forum = bot.channel('bases')
    name = f'TH{town_hall} bases'
    post = discord.utils.get(forum.threads, name=name)
    reply = interaction.response.send_message
    if post is None:
        # A post that went quiet for a week is archived and not cached. Fetching it can take longer than
        # the 3 seconds Discord allows for a reply, so show "thinking" first and answer as a follow-up.
        await interaction.response.defer()
        post = discord.utils.get([t async for t in forum.archived_threads(limit=None)], name=name)
        reply = interaction.followup.send
    if post is None:
        await reply(f'There\'s no TH{town_hall} post in {forum.mention} yet.')
        return
    embed = bot.card(BLUE, f'Town Hall {town_hall} bases', f'{bot.th(town_hall)} War, CWL, legend and farming bases. '
                                                           f'Share yours there with `/layout post`.')
    if town_hall <= 18:  # no TH19 picture in ClashKing Assets yet
        embed.set_thumbnail(url=TH_IMAGE.format(town_hall))
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=f'Open TH{town_hall} bases', url=post.jump_url,
                                    emoji=bot.icon(f'th{town_hall}') or None))
    await reply(embed=embed, view=view)


@bot.tree.command(name='rules', description='Show one part of the clan rules', guild=GUILD)
@app_commands.describe(part='Which rules to show')
@app_commands.choices(part=[app_commands.Choice(name=title, value=title) for title in rules_sections()])
async def rules(interaction: discord.Interaction, part: app_commands.Choice[str]):
    channels = {c.name: c.mention for c in interaction.guild.channels}
    text = re.sub(r'\{([a-z-]+)\}', lambda m: channels.get(m.group(1), m.group(0)), rules_sections()[part.value])
    embed = bot.card(GOLD, part.value, f"{text}\n\nAll rules: {channels.get('rules', '#rules')}")
    if bot.state.get('badge'):
        embed.set_thumbnail(url=bot.state['badge'])
    await interaction.response.send_message(embed=embed)


if __name__ == '__main__':
    handler = RotatingFileHandler(ROOT / 'bot.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # Only one copy may run, or every log would be posted twice. Holding this local port is the lock.
    lock = socket.socket()
    try:
        lock.bind(('127.0.0.1', 47831))
    except OSError:
        log.warning('another copy of the bot is already running, exiting')
        raise SystemExit(0)
    bot.run(bot.env['DISCORD_TOKEN'], log_handler=None)
