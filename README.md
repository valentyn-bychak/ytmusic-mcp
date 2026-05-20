# ytmusic-mcp

YouTube Music MCP server. Lets Claude (and any MCP-compatible client) search the YT Music catalog and manage your playlists through natural language.

Wraps the [`ytmusicapi`](https://github.com/sigma67/ytmusicapi) library and exposes it as MCP tools.

## Status

Personal project. Not affiliated with Google / YouTube. Uses the unofficial YT Music API — works because YT Music's web app uses these same endpoints internally.

## Quick start

```bash
# from the project root
./setup.sh
```

The `setup.sh` script handles everything: installs Python + GitHub CLI via Homebrew if missing, creates a venv, installs deps, registers the MCP in Claude Desktop, and walks you through the one-time auth step.

After setup, restart Claude Desktop and the MCP is ready.

## Tools

### Base CRUD
- `search` — search the catalog (songs, albums, artists, playlists)
- `playlist_list` — list your playlists
- `playlist_create` — create a new (empty) playlist
- `playlist_get_tracks` — read a playlist
- `playlist_add_tracks` — add tracks by `videoId` (batch)
- `playlist_remove_tracks` — remove tracks (needs `setVideoId`)
- `playlist_update` — change title / description / privacy
- `playlist_delete` — delete a playlist

### Killer features
- `add_by_search` — give a list of search queries, get them all into a playlist in one call
- `bulk_create_from_spec` — create multiple playlists from a YAML file in one go
- `playlist_clone_with_filter` — clone a playlist, excluding tracks by artist or title keyword
- `dedupe_playlist` — find and remove duplicate tracks

### Smart features
- `find_similar_to_song` — get tracks YouTube considers similar to a seed track
- `seed_playlist_from_tracks` — give anchor tracks, get a vibe-matched playlist auto-generated
- `get_artist_top_songs` — top N songs for an artist

### Meta
- `config` — config info and auth status

## Auth

The MCP uses browser-cookie authentication via `ytmusicapi`. One-time setup:

1. Open Chrome → https://music.youtube.com (make sure you're logged in)
2. Open DevTools (Cmd+Opt+I) → Network tab
3. Click on any request to `music.youtube.com`
4. Right-click → Copy → **Copy request headers**
5. Run `ytmusic-mcp auth` and paste when prompted (finish with Ctrl+D)

Credentials are saved to `~/.config/ytmusic-mcp/browser.json` and stay valid for ~2 years.

## CLI

```bash
ytmusic-mcp init           # ensure config directory exists
ytmusic-mcp auth           # one-time auth setup
ytmusic-mcp status         # check auth state, ping YT Music
ytmusic-mcp serve          # run MCP server over stdio
```

## License

MIT
