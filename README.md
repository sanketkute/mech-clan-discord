# Mech Clan Discord

The Discord server and bot for the Clash of Clans clan **mech clan** (`#YU9YY8UV`).

- **Mech Clan Bot** (`bot/`): instant clan and war logs, plus a few slash commands.
- **Server setup scripts** (`server-setup/`): the scripts that built and configure the Discord server.
- **Posts** (`posts/`): the #welcome and #rules messages.

Join us: [discord.gg/fjDTMZ3NYF](https://discord.gg/fjDTMZ3NYF)

## Mech Clan Bot

It checks the clan through the official Clash of Clans API every minute and posts:

- **#clan-log:** joins and leaves (as player cards with Town Hall, level, war stars and heroes), rank changes,
  Town Hall upgrades, and one live donation board a day, edited as members donate (`DONATION_LOG` in
  `bot/mech_bot.py` switches it off)
- **#war-log:** war declared, battle day, every attack (ours and theirs) and the result with missed attacks,
  for regular wars and Clan War League
- **#cwl:** during Clan War League, one pinned card with the 8 clans of our group, ranked by stars, with each clan's
  attacks this round and the Town Halls of its lineup. Buttons 1-7 show a round's results to whoever taps them.

War reminders (6 h, 2 h and 30 min before a war ends, pinging members linked with `/link`) are built in but off
(`WAR_REMINDERS_ON` in `bot/mech_bot.py`); the clan uses ClashPerk's reminders and links.

Its Discord status shows whether it can read the game: green "Watching mech clan" while the checks work, yellow
"No game data since 17:21" after 5 minutes of failed checks. After 10 minutes it also posts an alert in #leaders,
and an all-clear once the checks work again. From a terminal, `mechbot` shows whether the bot is running, when it
last checked the game, its Discord connection and recent errors; `mechbot restart` restarts it and `mechbot log`
shows the end of its log. That needs the repo folder on the PATH; without it, run `mechbot.cmd` from the repo.

Slash commands:

| Command | What it does |
|---|---|
| `/cwl-medals [league] [stars]` | CWL medals for each final place in a league, or "All leagues" at once |
| `/bases town_hall` | Links the Town Hall's post in the #bases forum |
| `/rules part` | Shows one part of the clan rules |

## Layout

```
bot/mech_bot.py          the bot
bot/war_board.py         the live war board: one message per war, edited every minute, with an attack thread
bot/donation_board.py    the daily donation board: top donors of the day, posted silently in #clan-log
bot/cwl_group.py         the live CWL group card in #cwl and the round results behind its buttons
bot/status.py            is the bot running and reading the game? (run as `mechbot`, also from the laptop over SSH)
deploy/                  the systemd service that runs the bot on the server
mechbot.cmd              the short `mechbot` command: status, `mechbot restart`, `mechbot log`
bot/phone_check.py       checks that every line of both boards fits on a phone without wrapping
server-setup/            one-off Discord REST scripts, run by hand
  discord_api.py           small REST client used by the scripts
  build_layout.py          channels, categories, rank roles, permissions, Community settings
  th_roles.py              Town Hall roles TH1-TH19
  onboarding.py            onboarding with a "What's your Town Hall level?" question
  bases_posts.py           one #bases forum post per Town Hall
  post_info.py             posts (or updates) #welcome and #rules from posts/
  audit.py, backup.py      dump the server's structure and messages to JSON
  cleanup_2026_10_23*.py   the one-off cleanup of the old server
posts/                   welcome.md and rules.md
```

Local files that are never committed: `.env`, `bot_state.json` (what the bot has already seen), `bot.log`
and server backups.

## Setup

1. Python 3.10 or newer.
2. Install the packages:
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill it in:
   - `DISCORD_TOKEN`: a Discord application with a bot, added to the server.
   - `COC_EMAIL` / `COC_PASSWORD`: a free account at [developer.clashofclans.com](https://developer.clashofclans.com).
     The bot creates its own API key for the machine's IP through [coc.py](https://github.com/mathsman5133/coc.py).
4. The server id and clan tag are constants at the top of `bot/mech_bot.py` and in the scripts. Change them to
   use this for another clan.

## Running

```
.venv\Scripts\python bot\mech_bot.py
```

On first start it only records the current clan and war, so nothing old gets posted. Only one copy can run at a
time (it holds local port 47831), so logs are never posted twice on one machine; never run it on two machines.

It runs on a free Oracle Cloud server (Ubuntu) as the systemd service in `deploy/mech-clan-bot.service`, which starts
it at boot and restarts it if it stops. A server keeps one IP address, so its Clash API key never has to change; on a
laptop that moves between networks, the key kept getting refused for hours. With `BOT_SERVER` and `BOT_SSH_KEY` in the
laptop's `.env`, `mechbot` on the laptop checks and restarts the bot on the server over SSH.

The server setup scripts are run from the repo root, for example `python server-setup/post_info.py`. They're safe
to re-run unless the file says otherwise.

## Credits

- Game icons: [ClashKing Assets](https://github.com/ClashKingInc/ClashKingAssets) (served from assets.clashk.ing).
  They're uploaded to Discord as the bot's emojis, not stored here.
- CWL medal and bonus tables: [ClashPerk](https://github.com/clashperk/clashperk) (MIT).
- Clan logs, reminders, account linking and auto roles in our server also use [ClashPerk](https://clashperk.com).

This content is not affiliated with, endorsed, sponsored, or specifically approved by Supercell and Supercell is not
responsible for it. For more information see Supercell's [Fan Content Policy](https://www.supercell.com/fan-content-policy).
Clash of Clans and its art are trademarks and copyright of Supercell.

## License

The code is under the [MIT License](LICENSE). Clash of Clans art belongs to Supercell.
