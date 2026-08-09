# TODO: M3U export

Not built. This is the counterpart to the M3U *import* that already exists in
`app/services/m3u_parser.py`.

## Why it matters

Spotify's API is closed to us in practice. Extended quota needs a scale Aelyra
will not reach, so the app is capped at development mode's 25 manually
allowlisted users. Spotify also removed `/recommendations`, `/audio-features`
and related endpoints for new apps in late 2024, and in August 2026 shipped
their own prompt-to-playlist feature — a free-text box, a Generate button and a
public/private toggle.

Writing M3U removes the dependency. The playlist stops being something Spotify
must agree to store and becomes a file: importable by Apple Music, Tidal, Plex,
VLC, Lidarr, or anything else that reads the format. The 25-seat cap stops
mattering when the deliverable is a download.

The generation half of the app needs Spotify for exactly one thing — proving a
suggested track is real. That is replaceable (MusicBrainz has no quota gate),
but it is a separate piece of work and not required for export.

## What already exists

- `M3UParser.parse()` reads both `#EXTM3U` and plain M3U, and extracts ids from
  `open.spotify.com/track/...` URLs and `spotify:track:...` URIs.
- The review screen holds the selected tracks in memory.
- `playlist_tracks` persists `spotify_track_id`, `track_name`, `artist_name`,
  `album_name` and `position` for every playlist ever created, so history is
  exportable too, not just the current session.

## The format

```
#EXTM3U
#EXTINF:-1,Fela Kuti - Water No Get Enemy
https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT
```

`#EXTINF` takes duration in **seconds** followed by a comma and the display
title. We do not currently store duration — neither `get_tracks_details()` nor
the `playlist_tracks` table captures it — so `-1` (the conventional "unknown")
is correct for now. Spotify returns `duration_ms` on the track object, so
capturing it is a small change to `get_tracks_details()` plus a column and a
migration, worth doing only if a target importer turns out to care.

Watch the comma: a title containing one must not be escaped or truncated, since
`#EXTINF` splits on the *first* comma only. The import side already had a bug
here (JS `split(',', 2)` truncates rather than keeping the remainder) — the
export side should round-trip cleanly through our own parser, which is the
obvious test.

## Sketch

Backend — one endpoint, no new dependency:

- `POST /api/export-m3u` taking the same `track_ids` shape as
  `/api/create-playlist`, returning `text/plain` with
  `Content-Disposition: attachment; filename="<playlist>.m3u"`.
- Or `GET /api/user-playlists/{playlist_hash}/export.m3u` to export any past
  playlist straight from `playlist_tracks` without touching Spotify at all.

The second is the more interesting one: it works even if the Spotify
integration is unavailable, since every field needed is already in the database.

Frontend:

- A "Download .m3u" button beside "Save to Spotify" on the review screen, and on
  each card in Playlist History.
- Worth considering as an alternative to saving rather than an extra step —
  export is the path that survives whatever Spotify does next.

## Tests

`tests/test_m3u_parser.py` already covers the import direction. Add a
round-trip: build a playlist, export it, parse the result with `M3UParser`, and
assert the ids and order come back identical — including a title with a comma
and one with non-ASCII characters.
