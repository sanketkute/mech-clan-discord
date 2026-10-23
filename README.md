# Mech Clan Discord

The Discord server and bot for the Clash of Clans clan **mech clan** (`#YU9YY8UV`).

- **Mech Clan Bot** (`bot/`): instant clan and war logs, plus a few slash commands.
- **Server setup scripts** (`server-setup/`): the scripts that built and configure the Discord server.
- **Posts** (`posts/`): the #welcome and #rules messages.

Join us: [discord.gg/fjDTMZ3NYF](https://discord.gg/fjDTMZ3NYF)

## Mech Clan Bot

It checks the clan through the official Clash of Clans API every minute and posts:

- **#clan-log:** joins and leaves (as player cards with Town Hall, level, war stars and heroes), rank changes,
  Town Hall upgrades and donations
- **#war-log:** war declared, battle day, every attack (ours and theirs) and the result with missed attacks,
  for regular wars and Clan War League

Slash commands:

| Command | What it does |
|---|---|
| `/cwl-medals [league] [stars]` | CWL medals for each final place in a league, or "All leagues" at once |
| `/bases town_hall` | Links the Town Hall's post in the #bases forum |
| `/rules part` | Shows one part of the clan rules |

## Layout

```
bot/mech_bot.py          the bot
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
time (it holds local port 47831), so logs are never posted twice. On Windows we run it with
`.venv\Scripts\pythonw.exe` from a Task Scheduler task that starts at logon and restarts it on failure.

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
