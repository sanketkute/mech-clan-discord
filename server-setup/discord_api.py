"""Minimal Discord REST client for the Mech Clan bot. Reads the bot token from .env in the repo root."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = 'https://discord.com/api/v10'


def _token():
    for line in (Path(__file__).parent.parent / '.env').read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('DISCORD_TOKEN='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('DISCORD_TOKEN missing from .env')


TOKEN = _token()


def call(method, path, body=None, reason=None):
    headers = {
        'Authorization': f'Bot {TOKEN}',
        'User-Agent': 'DiscordBot (https://github.com/mech-clan, 1.0)',
        'Content-Type': 'application/json',
    }
    if reason:
        headers['X-Audit-Log-Reason'] = reason
    data = json.dumps(body).encode() if body is not None else None
    while True:
        req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read()).get('retry_after', 1)) + 0.2)
                continue
            raise RuntimeError(f'{method} {path} -> {e.code}: {e.read().decode()[:300]}') from None


def get(path):
    return call('GET', path)
