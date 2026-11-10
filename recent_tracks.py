"""Publish a minimal public feed; never replace a good feed with an API failure."""
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class FeedError(ValueError):
    pass


def safe_url(value, hosts):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme == 'https' and url.hostname in hosts and not url.username
                and not url.password and url.port in (None, 443) and not url.query
                and not url.fragment and url.path.startswith('/')):
            return value
    except ValueError:
        pass
    return None


def text(value, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise FeedError('Invalid track metadata')
    return value.strip()


def make_feed(payload):
    if not isinstance(payload, dict) or 'error' in payload:
        raise FeedError('Last.fm API unavailable')
    recent = payload.get('recenttracks')
    if not isinstance(recent, dict) or not isinstance(recent.get('track'), list):
        raise FeedError('Malformed recent tracks')
    items = []
    for track in recent['track']:
        if not isinstance(track, dict):
            raise FeedError('Malformed track')
        attrs = track.get('@attr', {})
        if not isinstance(attrs, dict):
            raise FeedError('Malformed track attributes')
        if attrs.get('nowplaying') == 'true':
            continue
        try:
            title = text(track['name'], True)
            artist = text(track['artist']['#text'], True)
            album = text(track.get('album', {}).get('#text', ''))
            stamp = track['date']['uts']
            if not isinstance(stamp, str) or not stamp.isdecimal() or int(stamp) <= 0:
                raise FeedError('Invalid scrobble date')
            link = safe_url(track['url'], {'www.last.fm', 'last.fm'})
            if not link or not urlsplit(link).path.startswith('/music/'):
                raise FeedError('Invalid track URL')
            art = None
            images = track.get('image', [])
            if not isinstance(images, list):
                raise FeedError('Malformed artwork')
            for entry in reversed(images):
                if not isinstance(entry, dict):
                    raise FeedError('Malformed artwork')
                candidate = safe_url(entry.get('#text'), {'lastfm.freetls.fastly.net'})
                if candidate and '2a96cbd8b46e442fc41c2b86b821562f' not in candidate:
                    art = candidate
                    break
            items.append(dict(title=title, artist=artist, album=album,
                              url=link, image=art, played_at=int(stamp)))
        except (KeyError, TypeError, AttributeError) as exc:
            raise FeedError('Malformed completed scrobble') from exc
    if len(items) < 5:
        raise FeedError('Expected five completed scrobbles')
    # Stable sort preserves repeat plays, including ties; no deduplication.
    items.sort(key=lambda item: item['played_at'], reverse=True)
    return {'version': 1, 'user': 'rudrakabir', 'items': items[:5]}


def fetch_payload(key):
    query = urlencode(dict(method='user.getRecentTracks', user='rudrakabir',
                           api_key=key, format='json', limit=10))
    request = Request('https://ws.audioscrobbler.com/2.0/?' + query,
                      headers={'User-Agent': 'LastFM-Embed/1.0'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def refresh(path, key, fetcher=fetch_payload):
    if not key:
        raise FeedError('LASTFM_API_KEY is required')
    feed = make_feed(fetcher(key))
    data = json.dumps(feed, ensure_ascii=False, indent=2) + '\n'
    path = Path(path)
    if path.exists() and path.read_text(encoding='utf-8') == data:
        return False
    # Validate the entire response before writing, then atomically replace.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    try:
        changed = refresh('lastfm_data.json', os.environ.get('LASTFM_API_KEY'))
        print('Public feed updated.' if changed else 'Public feed unchanged.')
    except Exception:
        # Never log HTTP exceptions: their URLs can contain the API key.
        print('Last.fm refresh failed; last successful feed preserved.', file=sys.stderr)
        sys.exit(1)
