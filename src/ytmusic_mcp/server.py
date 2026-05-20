"""FastMCP server exposing YouTube Music tools.

Tool categories
---------------
Base CRUD       : search, playlist_list, playlist_create, playlist_get_tracks,
                  playlist_add_tracks, playlist_remove_tracks, playlist_update,
                  playlist_delete
Killer features : add_by_search, bulk_create_from_spec, playlist_clone_with_filter,
                  dedupe_playlist
Smart features  : find_similar_to_song, seed_playlist_from_tracks,
                  get_artist_top_songs
Meta            : config

Returns are plain dicts/lists so the LLM can reason over them directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from mcp.server.fastmcp import FastMCP

from ytmusic_mcp.auth import (
    BROWSER_JSON,
    CONFIG_DIR,
    auth_status,
    get_client,
    is_authenticated,
)

mcp = FastMCP("YouTube Music")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slim_track(item: dict) -> dict:
    """Project a search/playlist item to a compact LLM-friendly dict."""
    entry: dict[str, Any] = {
        "title": item.get("title"),
        "videoId": item.get("videoId"),
    }
    artists = item.get("artists")
    if artists:
        entry["artists"] = [a.get("name") for a in artists if a.get("name")]
    album = item.get("album")
    if album:
        entry["album"] = album.get("name") if isinstance(album, dict) else str(album)
    if item.get("duration"):
        entry["duration"] = item["duration"]
    if item.get("year"):
        entry["year"] = item["year"]
    return entry


def _first_song_videoid(yt, query: str) -> dict | None:
    """Return the best matching song for `query`, or None if nothing found.

    Strategy: prefer ``filter='songs'`` (official catalog) first, then fall back
    to ``filter='videos'`` (covers many remixes/edits that don't have an
    official song record).
    """
    for filt in ("songs", "videos"):
        try:
            results = yt.search(query, filter=filt, limit=5)
        except Exception:
            results = []
        for item in results:
            if item.get("videoId"):
                return {
                    "videoId": item["videoId"],
                    "title": item.get("title"),
                    "artists": [a.get("name") for a in (item.get("artists") or []) if a.get("name")],
                    "duration": item.get("duration"),
                    "matchedAs": filt,
                }
    return None


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


# ---------------------------------------------------------------------------
# Base: search
# ---------------------------------------------------------------------------

@mcp.tool()
def search(query: str, filter: str = "songs", limit: int = 10) -> list[dict]:
    """Search the YouTube Music catalog.

    Args:
        query: Free-text search query (e.g. "Espresso Sabrina Carpenter").
        filter: One of: songs, videos, albums, artists, playlists, community_playlists.
        limit: Max results to return (default 10).

    Returns:
        Compact list of result dicts with title, videoId/browseId/playlistId,
        artists, album, duration.
    """
    yt = get_client()
    results = yt.search(query, filter=filter, limit=limit) or []
    out: list[dict] = []
    for item in results[:limit]:
        entry: dict[str, Any] = {
            "resultType": item.get("resultType"),
            "title": item.get("title"),
        }
        if item.get("videoId"):
            entry["videoId"] = item["videoId"]
        if item.get("browseId"):
            entry["browseId"] = item["browseId"]
        if item.get("playlistId"):
            entry["playlistId"] = item["playlistId"]
        artists = item.get("artists")
        if artists:
            entry["artists"] = [a.get("name") for a in artists if a.get("name")]
        album = item.get("album")
        if album and isinstance(album, dict):
            entry["album"] = album.get("name")
        if item.get("duration"):
            entry["duration"] = item["duration"]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Base: playlist CRUD
# ---------------------------------------------------------------------------

@mcp.tool()
def playlist_list(limit: int = 50) -> dict:
    """List the user's playlists.

    Args:
        limit: Max playlists to return (default 50).

    Returns:
        ``{"count": int, "playlists": [{"playlistId", "title", "count"}, ...]}``
    """
    yt = get_client()
    playlists = yt.get_library_playlists(limit=limit) or []
    return {
        "count": len(playlists),
        "playlists": [
            {
                "playlistId": p.get("playlistId"),
                "title": p.get("title"),
                "count": p.get("count"),
            }
            for p in playlists
        ],
    }


@mcp.tool()
def playlist_create(
    title: str,
    description: str = "",
    privacy: str = "PRIVATE",
) -> dict:
    """Create a new (empty) playlist.

    Args:
        title: Playlist title.
        description: Optional description.
        privacy: PRIVATE | UNLISTED | PUBLIC. Default PRIVATE.

    Returns:
        ``{"playlistId": str, "title": str}``
    """
    yt = get_client()
    playlist_id = yt.create_playlist(
        title=title,
        description=description,
        privacy_status=privacy.upper(),
    )
    return {"playlistId": playlist_id, "title": title, "privacy": privacy.upper()}


@mcp.tool()
def playlist_get_tracks(playlist_id: str, limit: int = 200) -> dict:
    """Get tracks in a playlist.

    Args:
        playlist_id: The playlist ID.
        limit: Max tracks to return (default 200).
    """
    yt = get_client()
    pl = yt.get_playlist(playlistId=playlist_id, limit=limit)
    tracks = pl.get("tracks", []) or []
    return {
        "playlistId": playlist_id,
        "title": pl.get("title"),
        "description": pl.get("description"),
        "trackCount": len(tracks),
        "tracks": [
            {
                "videoId": t.get("videoId"),
                "setVideoId": t.get("setVideoId"),  # needed for remove
                "title": t.get("title"),
                "artists": [a.get("name") for a in (t.get("artists") or [])],
                "duration": t.get("duration"),
            }
            for t in tracks[:limit]
        ],
    }


@mcp.tool()
def playlist_add_tracks(playlist_id: str, video_ids: list[str]) -> dict:
    """Add tracks to a playlist by videoId (batch).

    Args:
        playlist_id: The playlist ID.
        video_ids: List of YouTube videoIds to add.
    """
    if not video_ids:
        return {"error": "video_ids cannot be empty"}
    yt = get_client()
    result = yt.add_playlist_items(
        playlistId=playlist_id,
        videoIds=video_ids,
        duplicates=False,
    )
    return {
        "playlistId": playlist_id,
        "requested": len(video_ids),
        "status": result.get("status", "unknown") if isinstance(result, dict) else "ok",
        "raw": result if isinstance(result, dict) else None,
    }


@mcp.tool()
def playlist_remove_tracks(
    playlist_id: str,
    tracks: list[dict],
) -> dict:
    """Remove tracks from a playlist.

    Args:
        playlist_id: The playlist ID.
        tracks: List of dicts each containing ``videoId`` and ``setVideoId``.
            Get these from ``playlist_get_tracks``.
    """
    yt = get_client()
    result = yt.remove_playlist_items(playlistId=playlist_id, videos=tracks)
    return {
        "playlistId": playlist_id,
        "requested": len(tracks),
        "status": result.get("status", "unknown") if isinstance(result, dict) else "ok",
    }


@mcp.tool()
def playlist_update(
    playlist_id: str,
    title: str | None = None,
    description: str | None = None,
    privacy: str | None = None,
) -> dict:
    """Update playlist metadata (title / description / privacy)."""
    yt = get_client()
    kwargs: dict[str, Any] = {"playlistId": playlist_id}
    if title is not None:
        kwargs["title"] = title
    if description is not None:
        kwargs["description"] = description
    if privacy is not None:
        kwargs["privacyStatus"] = privacy.upper()
    result = yt.edit_playlist(**kwargs)
    return {
        "playlistId": playlist_id,
        "status": result.get("status", "unknown") if isinstance(result, dict) else "ok",
        "updated": {k: v for k, v in kwargs.items() if k != "playlistId"},
    }


@mcp.tool()
def playlist_delete(playlist_id: str) -> dict:
    """Delete a playlist."""
    yt = get_client()
    result = yt.delete_playlist(playlistId=playlist_id)
    return {
        "playlistId": playlist_id,
        "status": result.get("status", "unknown") if isinstance(result, dict) else "ok",
    }


# ---------------------------------------------------------------------------
# Killer features
# ---------------------------------------------------------------------------

@mcp.tool()
def add_by_search(
    playlist_id: str,
    queries: list[str],
    skip_missing: bool = True,
) -> dict:
    """Search YouTube Music for each query and add the best match to the playlist.

    One-step "give me a list of song names, get them into a playlist" workflow.
    Falls back from songs filter to videos filter when no song record exists
    (catches remixes/edits).

    Args:
        playlist_id: Target playlist ID.
        queries: List of free-text queries, e.g. ["Espresso Sabrina Carpenter", ...].
        skip_missing: If True, skip queries with no match. If False, abort on first miss.

    Returns:
        ``{"added": [...], "missing": [...], "status": ...}``
    """
    yt = get_client()
    found: list[dict] = []
    missing: list[str] = []

    for q in queries:
        match = _first_song_videoid(yt, q)
        if match:
            match["query"] = q
            found.append(match)
        else:
            missing.append(q)
            if not skip_missing:
                return {
                    "error": f"No match for query: {q!r}",
                    "added": [],
                    "missing": [q],
                }

    if not found:
        return {"added": [], "missing": missing, "status": "no matches"}

    video_ids = [m["videoId"] for m in found]
    result = yt.add_playlist_items(
        playlistId=playlist_id,
        videoIds=video_ids,
        duplicates=False,
    )
    return {
        "playlistId": playlist_id,
        "added": found,
        "missing": missing,
        "addedCount": len(found),
        "missingCount": len(missing),
        "status": result.get("status", "unknown") if isinstance(result, dict) else "ok",
    }


@mcp.tool()
def bulk_create_from_spec(spec_path: str, dry_run: bool = False) -> dict:
    """Create multiple playlists from a YAML spec file.

    Spec format::

        playlists:
          - name: "🕺 EN Dance Hard"
            description: "Англомовна хардова туса"
            privacy: PRIVATE
            tracks:
              - "Take On Me a-ha remix"
              - "Tokyo Drift Teriyaki Boyz"
          - name: "💃 EN Dance Lite"
            tracks: [...]

    Args:
        spec_path: Absolute path to the YAML file.
        dry_run: If True, only report what would be done — don't touch YT Music.
    """
    path = Path(spec_path).expanduser().resolve()
    if not path.exists():
        return {"error": f"Spec file not found: {path}"}

    with open(path, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh) or {}

    playlists = spec.get("playlists") or []
    if not playlists:
        return {"error": "Spec contains no 'playlists' key or it is empty"}

    yt = None if dry_run else get_client()
    report: list[dict] = []

    for pl in playlists:
        name = pl.get("name")
        if not name:
            report.append({"skipped": pl, "reason": "missing 'name'"})
            continue
        tracks: Iterable[str] = pl.get("tracks") or []
        entry: dict[str, Any] = {
            "name": name,
            "trackQueries": len(list(tracks)) if isinstance(tracks, list) else 0,
        }

        if dry_run:
            entry["wouldCreate"] = True
            report.append(entry)
            continue

        # Create the playlist
        pid = yt.create_playlist(
            title=name,
            description=pl.get("description", ""),
            privacy_status=str(pl.get("privacy", "PRIVATE")).upper(),
        )
        entry["playlistId"] = pid

        # Add tracks via add_by_search-style search
        found: list[dict] = []
        missing: list[str] = []
        for q in pl.get("tracks") or []:
            match = _first_song_videoid(yt, q)
            if match:
                match["query"] = q
                found.append(match)
            else:
                missing.append(q)

        if found:
            video_ids = [m["videoId"] for m in found]
            yt.add_playlist_items(
                playlistId=pid,
                videoIds=video_ids,
                duplicates=False,
            )

        entry["added"] = len(found)
        entry["missing"] = missing
        report.append(entry)

    return {
        "dryRun": dry_run,
        "specPath": str(path),
        "playlistCount": len(report),
        "results": report,
    }


@mcp.tool()
def playlist_clone_with_filter(
    source_playlist_id: str,
    new_title: str,
    new_description: str = "",
    exclude_artists: list[str] | None = None,
    exclude_title_keywords: list[str] | None = None,
    privacy: str = "PRIVATE",
) -> dict:
    """Clone an existing playlist into a new one, filtering out unwanted tracks.

    Use case: derive ``UA Dance Hard`` from ``UA Dance Lite`` by excluding
    Russian-language artists; or strip "live" / "karaoke" versions.

    Args:
        source_playlist_id: Source playlist ID to clone from.
        new_title: Title for the new playlist.
        new_description: Description for the new playlist.
        exclude_artists: List of artist name substrings to filter out (case-insensitive).
        exclude_title_keywords: List of substrings to look for in track titles.
        privacy: Privacy for the new playlist (default PRIVATE).
    """
    yt = get_client()
    src = yt.get_playlist(playlistId=source_playlist_id, limit=500)
    src_tracks = src.get("tracks", []) or []

    excl_artists = [_normalize(a) for a in (exclude_artists or [])]
    excl_kw = [_normalize(k) for k in (exclude_title_keywords or [])]

    kept: list[dict] = []
    dropped: list[dict] = []

    for t in src_tracks:
        title = _normalize(t.get("title"))
        artists_norm = [_normalize(a.get("name")) for a in (t.get("artists") or [])]

        # Artist exclusion: drop if ANY artist matches ANY excluded substring
        if any(any(ex in a for a in artists_norm) for ex in excl_artists if ex):
            dropped.append(_slim_track(t))
            continue
        # Title keyword exclusion
        if any(kw in title for kw in excl_kw if kw):
            dropped.append(_slim_track(t))
            continue
        kept.append(t)

    if not kept:
        return {
            "error": "Nothing left after filtering — refusing to create empty playlist",
            "sourcePlaylistId": source_playlist_id,
            "droppedCount": len(dropped),
        }

    new_pid = yt.create_playlist(
        title=new_title,
        description=new_description,
        privacy_status=privacy.upper(),
    )
    video_ids = [t.get("videoId") for t in kept if t.get("videoId")]
    yt.add_playlist_items(
        playlistId=new_pid,
        videoIds=video_ids,
        duplicates=False,
    )
    return {
        "newPlaylistId": new_pid,
        "newTitle": new_title,
        "sourcePlaylistId": source_playlist_id,
        "keptCount": len(kept),
        "droppedCount": len(dropped),
        "droppedSample": dropped[:10],
    }


@mcp.tool()
def dedupe_playlist(playlist_id: str, dry_run: bool = False) -> dict:
    """Find and (optionally) remove duplicate tracks in a playlist.

    Considers a track a duplicate if its videoId appears more than once.

    Args:
        playlist_id: The playlist ID.
        dry_run: If True, only report duplicates; don't remove anything.
    """
    yt = get_client()
    pl = yt.get_playlist(playlistId=playlist_id, limit=500)
    tracks = pl.get("tracks", []) or []

    seen: dict[str, dict] = {}
    duplicates: list[dict] = []
    for t in tracks:
        vid = t.get("videoId")
        if not vid:
            continue
        if vid in seen:
            duplicates.append(
                {"videoId": vid, "setVideoId": t.get("setVideoId"), "title": t.get("title")}
            )
        else:
            seen[vid] = t

    if not duplicates:
        return {"playlistId": playlist_id, "duplicates": 0, "removed": 0}

    if dry_run:
        return {
            "playlistId": playlist_id,
            "duplicates": len(duplicates),
            "removed": 0,
            "wouldRemove": duplicates,
        }

    # Build the {"videoId", "setVideoId"} list ytmusicapi wants
    to_remove = [
        {"videoId": d["videoId"], "setVideoId": d["setVideoId"]}
        for d in duplicates
        if d.get("setVideoId")
    ]
    if not to_remove:
        return {
            "playlistId": playlist_id,
            "duplicates": len(duplicates),
            "removed": 0,
            "note": "No setVideoId on duplicates — cannot remove",
        }
    result = yt.remove_playlist_items(playlistId=playlist_id, videos=to_remove)
    return {
        "playlistId": playlist_id,
        "duplicates": len(duplicates),
        "removed": len(to_remove),
        "status": result.get("status", "unknown") if isinstance(result, dict) else "ok",
    }


# ---------------------------------------------------------------------------
# Smart features (YouTube's own recommender)
# ---------------------------------------------------------------------------

@mcp.tool()
def find_similar_to_song(video_id: str, limit: int = 20) -> dict:
    """Find songs similar to the given track using YouTube Music's recommender.

    Uses the "Up Next" / watch playlist YouTube generates for any song —
    the same engine that powers YT Music's auto-play queue.

    Args:
        video_id: Seed track's videoId.
        limit: Max similar tracks to return (default 20).
    """
    yt = get_client()
    watch = yt.get_watch_playlist(videoId=video_id, limit=limit + 1)
    tracks = watch.get("tracks", []) or []
    # First track is usually the seed itself — drop it.
    similar = [t for t in tracks if t.get("videoId") != video_id][:limit]
    return {
        "seedVideoId": video_id,
        "count": len(similar),
        "similar": [_slim_track(t) for t in similar],
    }


@mcp.tool()
def seed_playlist_from_tracks(
    title: str,
    seed_queries: list[str],
    per_seed: int = 10,
    description: str = "",
    privacy: str = "PRIVATE",
    include_seeds: bool = True,
) -> dict:
    """Create a new playlist seeded from a list of "anchor" tracks.

    Workflow:
        1. Resolve each seed query → videoId (via search)
        2. For each seed, fetch ``per_seed`` similar tracks from YouTube
        3. Optionally include the seed tracks themselves
        4. De-duplicate and create the playlist

    Use case: give 5 "anchor" artists/tracks from your taste
    (e.g. Корж, Скриптонит, Miyagi) → get a 50-track playlist matching that vibe.

    Args:
        title: Title for the new playlist.
        seed_queries: List of search queries for anchor tracks.
        per_seed: How many similar tracks to fetch per seed (default 10).
        description: Optional description.
        privacy: PRIVATE | UNLISTED | PUBLIC.
        include_seeds: If True, also include the seed tracks themselves.
    """
    yt = get_client()
    seen: set[str] = set()
    chosen: list[dict] = []
    seed_resolved: list[dict] = []
    seed_missing: list[str] = []

    for q in seed_queries:
        match = _first_song_videoid(yt, q)
        if not match:
            seed_missing.append(q)
            continue
        seed_resolved.append(match)
        if include_seeds and match["videoId"] not in seen:
            seen.add(match["videoId"])
            chosen.append({
                "videoId": match["videoId"],
                "title": match.get("title"),
                "artists": match.get("artists"),
                "source": f"seed: {q}",
            })

        try:
            watch = yt.get_watch_playlist(videoId=match["videoId"], limit=per_seed + 1)
        except Exception:
            continue
        for t in (watch.get("tracks") or [])[: per_seed + 1]:
            vid = t.get("videoId")
            if not vid or vid in seen or vid == match["videoId"]:
                continue
            seen.add(vid)
            chosen.append({
                "videoId": vid,
                "title": t.get("title"),
                "artists": [a.get("name") for a in (t.get("artists") or [])],
                "source": f"similar to: {q}",
            })

    if not chosen:
        return {
            "error": "No tracks found",
            "seedMissing": seed_missing,
        }

    pid = yt.create_playlist(
        title=title,
        description=description,
        privacy_status=privacy.upper(),
    )
    yt.add_playlist_items(
        playlistId=pid,
        videoIds=[c["videoId"] for c in chosen],
        duplicates=False,
    )
    return {
        "playlistId": pid,
        "title": title,
        "added": len(chosen),
        "seedsResolved": [s["title"] for s in seed_resolved],
        "seedsMissing": seed_missing,
        "trackSample": chosen[:10],
    }


@mcp.tool()
def get_artist_top_songs(artist_query: str, limit: int = 20) -> dict:
    """Get top songs for an artist by name (uses YT Music's own ranking).

    Args:
        artist_query: Artist name (free-text search).
        limit: Max songs to return.
    """
    yt = get_client()
    # Step 1: resolve artist to browseId via search
    artist_hits = yt.search(artist_query, filter="artists", limit=1) or []
    if not artist_hits:
        return {"error": f"No artist found for query: {artist_query!r}"}
    artist_hit = artist_hits[0]
    browse_id = artist_hit.get("browseId")
    if not browse_id:
        return {"error": "Artist match has no browseId"}

    # Step 2: fetch artist page
    artist = yt.get_artist(channelId=browse_id)
    songs = ((artist.get("songs") or {}).get("results")) or []

    return {
        "artist": artist.get("name"),
        "browseId": browse_id,
        "count": len(songs[:limit]),
        "songs": [_slim_track(s) for s in songs[:limit]],
    }


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

@mcp.tool()
def config(action: str = "info") -> dict:
    """Report MCP configuration and auth status.

    Args:
        action: ``info`` (paths + flag) or ``auth_status`` (full check, pings YT).
    """
    if action == "auth_status":
        return auth_status()
    if action == "info":
        return {
            "config_dir": str(CONFIG_DIR),
            "auth_file": str(BROWSER_JSON),
            "authenticated": is_authenticated(),
        }
    return {"error": f"Unknown action: {action}. Use: info, auth_status"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
