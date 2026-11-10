import copy
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from recent_tracks import FeedError, make_feed, refresh


def payload():
    return {'recenttracks': {'track': [dict(
        name='Repeat' if i < 2 else f'Track {i}', artist={'#text': 'Artist'},
        album={'#text': 'Album'}, url='https://www.last.fm/music/Artist/_/Track',
        date={'uts': str(1700000000 - i)}, image=[]
    ) for i in range(7)]}}


class FeedTests(unittest.TestCase):
    def test_five_completed_newest_first_with_repeats(self):
        data = payload()
        data['recenttracks']['track'].reverse()
        data['recenttracks']['track'].insert(0, {'@attr': {'nowplaying': 'true'}})
        items = make_feed(data)['items']
        self.assertEqual(len(items), 5)
        self.assertEqual([i['title'] for i in items[:2]], ['Repeat', 'Repeat'])
        self.assertEqual(items[0]['played_at'], 1700000000)

    def test_optional_album_and_art(self):
        data = payload()
        track = data['recenttracks']['track'][0]
        del track['album']
        track['image'] = [{'#text': 'javascript:alert(1)'},
                          {'#text': 'https://lastfm.freetls.fastly.net/i/u/300x300/cover.jpg'}]
        item = make_feed(data)['items'][0]
        self.assertEqual(item['album'], '')
        self.assertTrue(item['image'].endswith('cover.jpg'))
        self.assertIsNone(make_feed(payload())['items'][0]['image'])

    def test_unsafe_links_rejected_and_art_omitted(self):
        for url in ['javascript:alert(1)', 'https://www.last.fm.evil.test/music/a',
                    'https://user@www.last.fm/music/a', 'https://www.last.fm:99/music/a']:
            data = payload()
            data['recenttracks']['track'][0]['url'] = url
            with self.assertRaises(FeedError):
                make_feed(data)
        data = payload()
        data['recenttracks']['track'][0]['image'] = [{'#text': 'https://evil.test/a.jpg'}]
        self.assertIsNone(make_feed(data)['items'][0]['image'])

    def test_failures_preserve_last_feed(self):
        bad = [None, {}, {'error': 29}, {'recenttracks': {'track': []}}, payload()]
        del bad[-1]['recenttracks']['track'][0]['date']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'feed.json'
            path.write_text('last good feed')
            for data in bad:
                with self.assertRaises(FeedError):
                    refresh(path, 'test-key', lambda _: data)
                self.assertEqual(path.read_text(), 'last good feed')
            for error in [HTTPError('redacted', 429, 'rate limited', {}, None),
                          TimeoutError(), json.JSONDecodeError('bad', '', 0)]:
                def fail(_):
                    raise error
                with self.assertRaises(Exception):
                    refresh(path, 'test-key', fail)
                self.assertEqual(path.read_text(), 'last good feed')

    def test_unchanged_content_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'feed.json'
            self.assertTrue(refresh(path, 'test-key', lambda _: payload()))
            before = path.stat().st_mtime_ns
            self.assertFalse(refresh(path, 'test-key', lambda _: payload()))
            self.assertEqual(path.stat().st_mtime_ns, before)


if __name__ == '__main__':
    unittest.main()
