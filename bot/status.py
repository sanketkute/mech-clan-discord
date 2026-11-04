"""Is Mech Clan Bot working? A check for the laptop (owner's request, 2026-11-02), no Discord needed. Through
mechbot.cmd in the repo root, which is on the user's PATH:
    mechbot            is it working?
    mechbot restart    restart it, wait for its first check, then show the status
    mechbot log        the last 20 lines of bot.log
It reads what the running bot leaves behind: its lock port (held while it runs), bot_state.json (saved after every
check, with the health of the last checks) and bot.log (Discord connection and errors). Exits with 1 on a problem.

Since 2026-11-04 the bot runs on an Oracle Cloud server. With BOT_SERVER (user@host) and BOT_SSH_KEY in the laptop's
.env, mechbot on the laptop runs this same script on the server over SSH. On the server, restart uses systemd."""
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
TASK = 'Mech Clan Bot'  # the Windows scheduled task that runs the bot on the laptop
SERVICE = 'mech-clan-bot'  # the systemd service that runs it on the server (deploy/mech-clan-bot.service)
LOCK_PORT = 47831  # mech_bot.py holds this local port while it runs
CHECK_EVERY = timedelta(minutes=1)
LOG_LINE = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ (\w+) ([\w.]+): (.*)')


def running():
    probe = socket.socket()
    try:
        probe.bind(('127.0.0.1', LOCK_PORT))
        return False
    except OSError:
        return True
    finally:
        probe.close()


def clock(moment, now):
    """"17:21", with the weekday ("Mon 17:21") when it isn't today."""
    return f'{moment:%H:%M}' if moment.date() == now.date() else f'{moment:%a %H:%M}'


def ago(moment, now):
    seconds = int((now - moment).total_seconds())
    if seconds < 120:
        return f'{seconds} s ago'
    return f'{seconds // 60} min ago' if seconds < 7200 else f'{seconds // 3600} h ago'


def log_lines():
    """(time, level, logger, message) for every line of bot.log that starts an entry."""
    try:
        text = (ROOT / 'bot.log').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    return [(datetime.strptime(m[1], '%Y-%m-%d %H:%M:%S'), m[2], m[3], m[4])
            for m in map(LOG_LINE.match, text.splitlines()) if m]


def restart():
    """Stop the task, wait until the old copy has let go of its lock (starting earlier makes the new copy exit, as
    the first version of this did on 2026-11-02), start it again and wait for its first check."""
    def task(action):
        subprocess.run(['powershell', '-NoProfile', '-Command', f"{action}-ScheduledTask '{TASK}'"], check=True)

    print('Restarting the bot...', flush=True)
    started = time.time()
    if os.name == 'nt':
        task('Stop')
        for _ in range(30):
            if not running():
                break
            time.sleep(1)
        started = time.time()
        task('Start')
    else:  # systemd waits for the old copy to exit before it starts the new one
        subprocess.run(['sudo', 'systemctl', 'restart', SERVICE], check=True)
    state_file = ROOT / 'bot_state.json'
    for _ in range(120):  # the first check usually lands within 20 seconds
        time.sleep(1)
        if state_file.exists() and state_file.stat().st_mtime > started:
            break


def show_log(count=20):
    try:
        lines = (ROOT / 'bot.log').read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        lines = ['(no bot.log yet)']
    print('\n'.join(lines[-count:]))


def server():
    """(user@host, key path) from the laptop's .env when the bot runs on the server, else None."""
    if os.name != 'nt':
        return None
    try:
        env = dict(line.split('=', 1) for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines()
                   if '=' in line and not line.lstrip().startswith('#'))
    except OSError:
        return None
    host = env.get('BOT_SERVER', '').strip()
    return (host, env.get('BOT_SSH_KEY', '').strip()) if host else None


def main(args):
    remote = server()
    if remote:
        host, key = remote
        command = 'cd ~/mech-clan && .venv/bin/python bot/status.py ' + ' '.join(args[:1])
        # BatchMode: fail with a message instead of waiting for input; accept-new: trust the server's host key on the
        # first connection (Windows' ssh keeps its own list), but refuse if it ever changes.
        options = ['-o', 'ConnectTimeout=15', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new']
        return subprocess.run(['ssh', *options] + (['-i', key] if key else []) + [host, command]).returncode
    if args == ['log']:
        show_log()
        return 0
    if args == ['restart']:
        restart()
    elif args:
        print('Usage: mechbot [restart | log]')
        return 2
    return status()


def status():
    now = datetime.now()
    problems, rows = [], []

    is_running = running()
    rows.append(('Running', 'yes' if is_running else 'NO'))
    if not is_running:
        problems.append("The bot isn't running. Start it: mechbot restart")

    state_file = ROOT / 'bot_state.json'
    if state_file.exists():
        last = datetime.fromtimestamp(state_file.stat().st_mtime)
        rows.append(('Last check', f'{last:%H:%M:%S} ({ago(last, now)})'))
        if is_running and now - last > 3 * CHECK_EVERY:
            problems.append('No check for a while, so the bot may be stuck. Restart it: mechbot restart')
        health = json.loads(state_file.read_text(encoding='utf-8')).get('health') or {}
    else:
        rows.append(('Last check', 'never'))
        health = {}
    if health.get('since'):
        since = datetime.fromisoformat(health['since']).astimezone().replace(tzinfo=None)
        reason = health.get('reason', 'unknown reason')
        rows.append(('Game data', f'failing since {clock(since, now)} ({reason})'))
        problems.append(f'The clan and war checks are failing: {reason}.')
    else:
        rows.append(('Game data', 'reading fine'))

    lines = log_lines()
    connects = [(t, msg) for t, level, name, msg in lines if name.startswith('discord')
                and ('connected to Gateway' in msg or 'RESUMED' in msg or 'Attempting a reconnect' in msg)]
    if connects:
        when, msg = connects[-1]
        connected = 'Attempting a reconnect' not in msg
        rows.append(('Discord', f"{'connected' if connected else 'reconnecting'} since {clock(when, now)}"))
        if is_running and not connected:
            problems.append("The bot is trying to reconnect to Discord (is the laptop's internet working?).")
    errors = [(t, f'{name}: {msg}') for t, level, name, msg in lines if level == 'ERROR' and now - t < timedelta(hours=1)]
    rows.append(('Errors (1 h)', f'{len(errors)}, last at {errors[-1][0]:%H:%M}: {errors[-1][1][:70]}' if errors
                 else 'none'))

    print('Mech Clan Bot is working.' if not problems else 'Mech Clan Bot has a problem:')
    for problem in problems:
        print(f'  ! {problem}')
    for label, value in rows:
        print(f'  {label + ":":<14}{value}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
