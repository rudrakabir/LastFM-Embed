# LastFM Embed

Five most recent completed public scrobbles for rudrakabir, newest first.
Repeat plays remain separate. The official Last.fm user.getRecentTracks API
requires an app key but no user authentication, signature, or session token.

Set the repository Actions secret `LASTFM_API_KEY`. Run **Update Last.fm feed**
manually from Actions; after merging it also runs at 00:17, 06:17, 12:17 and
18:17 UTC (GitHub schedules can be delayed). GitHub may disable schedules in
public repositories after 60 days without activity; re-enable the workflow if needed.

The workflow publishes `lastfm_data.json` only when its contents change.
HTTP errors, rate limits, invalid JSON, or malformed completed scrobbles fail
the run while preserving the last good feed. No API response or exception URL
is logged. Missing artwork is allowed; only Last.fm's HTTPS image CDN is used.
The feed contains public track metadata and scrobble timestamps, never the key.

The Jekyll website fetches the raw feed at runtime. Updating this repository
does not trigger a website deploy. During review the site preview can use the
feature branch feed; switch it to `main` before the website production merge.

Local checks: `python3 -m unittest discover -s tests -v`.
Local refresh: provide `LASTFM_API_KEY` through the environment and run
`python3 recent_tracks.py`. Do not put credentials in source or command arguments.
