"""Set up #bases as agreed with the owner on 2026-10-23: TH11-TH18 tags, new guidelines, and one post per
Town Hall where members share bases with ClashPerk's /layout post.
Safe to re-run: existing tags keep their ids and existing posts are left alone. For TH19, add 19 to LEVELS."""
from discord_api import call, get

GUILD = '1316103480644993116'
REASON = 'Town Hall posts in #bases'
LEVELS = range(11, 19)
GUIDELINES = 'One post per Town Hall. Open yours and use /layout post to share a base.'
WEEK = 10080  # minutes; the longest auto-archive Discord allows


def first_message(n):
    return (f'**Town Hall {n} bases**: war, CWL, legend and farming bases.\n\n'
            '**Share a base:** type `/layout post` in this post. Add a screenshot of the base and its share link '
            'from the Layout Editor. Use **notes** to say what it\'s for, e.g. "CWL anti-3-star".\n'
            '**Copy a base:** tap the link on a base card and it opens in Clash of Clans.')


def main():
    forum = next(c for c in get(f'/guilds/{GUILD}/channels') if c['name'] == 'bases' and c['type'] == 15)
    tags = {t['name']: t for t in forum['available_tags']}
    wanted = [tags.get(f'TH{n}', {'name': f'TH{n}'}) for n in LEVELS]
    others = [t for name, t in tags.items() if name not in {f'TH{n}' for n in LEVELS}]
    forum = call('PATCH', f'/channels/{forum["id"]}', {'available_tags': wanted + others, 'topic': GUIDELINES}, REASON)
    tag_ids = {t['name']: t['id'] for t in forum['available_tags']}
    print('tags:', ', '.join(tag_ids))

    active = [t for t in get(f'/guilds/{GUILD}/threads/active')['threads'] if t.get('parent_id') == forum['id']]
    archived = get(f'/channels/{forum["id"]}/threads/archived/public')['threads']
    existing = {t['name'] for t in active + archived}
    # Lowest level first, so TH18 is the newest post and starts at the top.
    for n in LEVELS:
        name = f'TH{n} bases'
        if name in existing:
            continue
        call('POST', f'/channels/{forum["id"]}/threads', {
            'name': name, 'applied_tags': [tag_ids[f'TH{n}']], 'auto_archive_duration': WEEK,
            'message': {'content': first_message(n), 'allowed_mentions': {'parse': []}}}, REASON)
        print(f'created post {name}')


if __name__ == '__main__':
    main()
