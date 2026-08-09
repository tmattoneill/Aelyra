import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import spotify_token
from app.models.requests import (
    CreatePlaylistRequest,
    GeneratePlaylistRequest,
    UpdateProfileRequest,
    UploadPlaylistRequest,
)
from app.models.responses import GeneratePlaylistResponse
from app.services.llm_service import LLMService, QueryAnalysis
from app.services.m3u_parser import M3UParser
from app.services.playlist_history_service import PlaylistHistoryService
from app.services.spotify_service import SpotifyService
from app.services.user_service import UNSET, UserService

router = APIRouter()
logger = logging.getLogger(__name__)

# One extra round of suggestions when Spotify cannot find enough of the first
# batch. Bounded so a pathological query cannot loop up the API bill.
MAX_REFILL_ROUNDS = 1


def _server_error(context: str, exc: Exception) -> HTTPException:
    """Log the real error, return one that reveals nothing about internals.

    Endpoints used to put str(exc) in the response detail, which handed
    unauthenticated callers raw OpenAI and Spotify error bodies.
    """
    logger.exception(f"{context}: {exc}")
    return HTTPException(status_code=500, detail=context)


def _spotify_http_error(context: str, exc: httpx.HTTPStatusError) -> HTTPException:
    if exc.response.status_code in (401, 403):
        return HTTPException(status_code=401, detail="Spotify token expired or invalid")
    if exc.response.status_code == 429:
        return HTTPException(status_code=429, detail="Spotify rate limit reached, please retry shortly")
    logger.error(f"{context}: Spotify returned {exc.response.status_code}")
    return HTTPException(status_code=502, detail=context)


# ==========================================================================
# SPOTIFY TRACK SEARCH HELPERS
# ==========================================================================

async def _search_single_track(spotify_service: SpotifyService, original_track: Dict) -> Dict | None:
    """Find one AI-suggested track on Spotify, trying progressively looser queries."""
    track_name = original_track.get('track_name', original_track.get('title', ''))
    artist = original_track.get('artist', '')
    album = original_track.get('album', '')

    try:
        # Track name plus artist resolves the overwhelming majority of cases.
        search_results = await spotify_service.search_track(f"{track_name} {artist}".strip(), limit=10)

        if search_results:
            if album and album != "Unknown Album":
                for result in search_results:
                    result_album = result.get('album', '')
                    if result_album and album.lower() in result_album.lower():
                        return result

                # No exact album hit: score candidates on shared album words,
                # ignoring words that carry no identifying information.
                album_words = set(album.lower().split())
                noise = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to',
                         'for', 'soundtrack', 'greatest', 'hits', 'best', 'collection'}
                best_match, best_score = None, 0
                for result in search_results:
                    result_album = result.get('album', '')
                    if not result_album:
                        continue
                    shared = (album_words & set(result_album.lower().split())) - noise
                    if len(shared) > best_score:
                        best_score, best_match = len(shared), result
                return best_match or search_results[0]
            return search_results[0]

        # Quoting the title stops Spotify splitting it into loose keywords.
        if '"' not in track_name:
            search_results = await spotify_service.search_track(f'"{track_name}" {artist}', limit=5)
            if search_results:
                return search_results[0]

        if track_name:
            search_results = await spotify_service.search_track(f'"{track_name}"', limit=5)
            if search_results:
                return search_results[0]

        logger.info(f"No Spotify match for: {track_name} by {artist}")
        return None

    except Exception as e:
        logger.warning(f"Spotify search failed for '{track_name}' by '{artist}': {e}")
        return None


async def _batch_search_spotify_tracks(
    spotify_service: SpotifyService,
    suggested_tracks: List[Dict],
    target_count: int = None,
    seen_track_ids: set = None,
) -> tuple[List[Dict], List[Dict]]:
    """Search suggestions on Spotify concurrently, in batches.

    Returns (found tracks, suggestions with no Spotify match). The misses feed
    back into the model so it can suggest different tracks.
    """
    found_tracks: List[Dict] = []
    unmatched: List[Dict] = []
    seen_track_ids = seen_track_ids if seen_track_ids is not None else set()
    batch_size = 15

    for i in range(0, len(suggested_tracks), batch_size):
        batch = suggested_tracks[i:i + batch_size]
        results = await asyncio.gather(
            *(_search_single_track(spotify_service, track) for track in batch),
            return_exceptions=True,
        )

        for suggestion, result in zip(batch, results):
            if isinstance(result, Exception) or not result:
                unmatched.append(suggestion)
                continue
            spotify_id = result.get("spotify_id")
            if spotify_id and spotify_id not in seen_track_ids:
                found_tracks.append(result)
                seen_track_ids.add(spotify_id)
            else:
                logger.debug(f"Duplicate Spotify result: {result.get('title')}")

        if target_count and len(found_tracks) >= target_count:
            logger.info(f"Found {len(found_tracks)} tracks, ending search early")
            break

        if i + batch_size < len(suggested_tracks):
            await asyncio.sleep(0.05)

    logger.info(f"Spotify search: {len(found_tracks)} found, {len(unmatched)} unmatched")
    return found_tracks, unmatched


def _format_spotify_tracks(spotify_tracks: List[Dict]) -> List[Dict]:
    """Shape tracks for the API response, dropping any repeated Spotify id."""
    formatted_tracks = []
    seen_ids = set()

    for track in spotify_tracks:
        spotify_id = track.get("spotify_id")
        if spotify_id and spotify_id not in seen_ids:
            formatted_tracks.append({
                "title": track.get("title", "Unknown"),
                "artist": track.get("artist", "Unknown"),
                "album": track.get("album", "Unknown Album"),
                "spotify_id": spotify_id,
                "album_art": track.get("album_art"),
                "preview_url": track.get("preview_url"),
            })
            seen_ids.add(spotify_id)

    return formatted_tracks


async def _refill_tracks(
    llm_service: LLMService,
    spotify_service: SpotifyService,
    analysis: QueryAnalysis,
    found_tracks: List[Dict],
    unmatched: List[Dict],
    target_count: int,
) -> List[Dict]:
    """Ask the model for replacements for suggestions Spotify could not find.

    The previous behaviour padded short playlists with results for "popular
    songs" and "top hits", which silently handed back tracks unrelated to what
    was asked for. Coming up short and saying so is more honest, so this makes
    one focused retry and then reports whatever it has.
    """
    tracks = list(found_tracks)
    seen_ids = {t.get("spotify_id") for t in tracks if t.get("spotify_id")}

    for round_number in range(MAX_REFILL_ROUNDS):
        if len(tracks) >= target_count:
            break

        needed = target_count - len(tracks)
        logger.info(f"Refill round {round_number + 1}: need {needed} more tracks")

        try:
            existing_as_suggestions = [
                {"track_name": t.get("title"), "artist": t.get("artist")} for t in tracks
            ]
            replacements = await llm_service.generate_tracks_from_analysis(
                analysis,
                needed,
                existing_tracks=existing_as_suggestions,
                unavailable_tracks=unmatched,
            )
            if not replacements:
                break

            new_tracks, new_unmatched = await _batch_search_spotify_tracks(
                spotify_service, replacements, target_count=needed, seen_track_ids=seen_ids
            )
            if not new_tracks:
                break

            tracks.extend(new_tracks)
            unmatched = new_unmatched

        except Exception as e:
            logger.warning(f"Refill round {round_number + 1} failed: {e}")
            break

    return tracks


# ==========================================================================
# GENERATION ENDPOINTS
# ==========================================================================

@router.post("/generate-playlist", response_model=GeneratePlaylistResponse)
async def generate_playlist(
    request: GeneratePlaylistRequest,
    token: str = Depends(spotify_token),
):
    """Generate a playlist from a natural language query.

    Runs three passes (analyse, generate, validate) then resolves each
    suggestion against Spotify.
    """
    try:
        llm_service = LLMService()
        spotify_service = SpotifyService(token)

        suggested_tracks, analysis = await llm_service.generate_playlist_agentic(
            query=request.query,
            track_count=request.track_count,
        )
        logger.info(f"Generated {len(suggested_tracks)} suggestions")

        spotify_tracks, unmatched = await _batch_search_spotify_tracks(
            spotify_service, suggested_tracks, target_count=request.track_count
        )

        if len(spotify_tracks) < request.track_count:
            spotify_tracks = await _refill_tracks(
                llm_service, spotify_service, analysis,
                spotify_tracks, unmatched, request.track_count,
            )

        formatted_tracks = _format_spotify_tracks(spotify_tracks[:request.track_count])
        playlist_name = await llm_service.generate_playlist_title(request.query)

        if len(formatted_tracks) < request.track_count:
            logger.info(
                f"Returning {len(formatted_tracks)} of {request.track_count} requested tracks"
            )

        return GeneratePlaylistResponse(
            playlist_name=playlist_name,
            tracks=formatted_tracks,
            requested_count=request.track_count,
            found_count=len(formatted_tracks),
        )

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to generate playlist", e)
    except Exception as e:
        raise _server_error("Failed to generate playlist", e)


@router.post("/generate-playlist-stream")
async def generate_playlist_stream(
    request: GeneratePlaylistRequest,
    token: str = Depends(spotify_token),
):
    """Same generation flow, streamed as server-sent events for live progress."""

    async def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    async def generate_with_progress() -> AsyncGenerator[str, None]:
        try:
            llm_service = LLMService()
            spotify_service = SpotifyService(token)

            # PASS 1: analyse the query
            yield await sse({'type': 'pass_start', 'pass': 'analyze',
                             'message': 'Analyzing your music preferences...'})
            analysis = await llm_service.analyze_query(request.query)
            genres_str = ', '.join(analysis.genres[:3]) if analysis.genres else 'various genres'
            moods_str = ', '.join(analysis.moods[:2]) if analysis.moods else 'mixed moods'
            yield await sse({'type': 'pass_complete', 'pass': 'analyze',
                             'message': f"Found: {genres_str} / {moods_str}"})

            # PASS 2: generate suggestions
            yield await sse({'type': 'pass_start', 'pass': 'generate',
                             'message': f'Generating {request.track_count} track recommendations...'})
            suggested_tracks = await llm_service.generate_tracks_from_analysis(
                analysis, request.track_count
            )
            yield await sse({'type': 'pass_complete', 'pass': 'generate',
                             'message': f'Generated {len(suggested_tracks)} potential tracks'})

            # PASS 3: diversity
            yield await sse({'type': 'pass_start', 'pass': 'validate',
                             'message': 'Validating playlist diversity...'})
            diversity_report = llm_service.validate_diversity(suggested_tracks, analysis)
            if diversity_report.is_valid:
                yield await sse({'type': 'pass_complete', 'pass': 'validate',
                                 'message': 'Diversity check passed'})
            else:
                issue_msg = diversity_report.issues[0] if diversity_report.issues else "diversity issues"
                yield await sse({'type': 'pass_progress', 'pass': 'validate',
                                 'message': f'Fixing: {issue_msg}'})
                suggested_tracks = llm_service.apply_diversity_fixes(suggested_tracks)
                if len(suggested_tracks) < request.track_count:
                    needed = request.track_count - len(suggested_tracks)
                    replacements = await llm_service.generate_replacement_tracks(
                        analysis, needed, suggested_tracks, diversity_report.artist_violations
                    )
                    suggested_tracks.extend(replacements[:needed])
                yield await sse({'type': 'pass_complete', 'pass': 'validate',
                                 'message': 'Diversity issues resolved'})

            # PASS 4: resolve against Spotify, streaming each hit as it lands
            yield await sse({'type': 'pass_start', 'pass': 'search',
                             'message': 'Searching Spotify for tracks...'})

            spotify_tracks: List[Dict] = []
            unmatched: List[Dict] = []
            seen_ids = set()
            batch_size = 10

            for i in range(0, len(suggested_tracks), batch_size):
                batch = suggested_tracks[i:i + batch_size]
                results = await asyncio.gather(
                    *(_search_single_track(spotify_service, track) for track in batch),
                    return_exceptions=True,
                )

                for suggestion, result in zip(batch, results):
                    if isinstance(result, Exception) or not result:
                        unmatched.append(suggestion)
                        continue
                    spotify_id = result.get("spotify_id")
                    if spotify_id and spotify_id not in seen_ids:
                        spotify_tracks.append(result)
                        seen_ids.add(spotify_id)
                        yield await sse({
                            'type': 'track_found',
                            'track': {
                                'title': result['title'],
                                'artist': result['artist'],
                                'spotify_id': spotify_id,
                                'album_art': result.get('album_art'),
                            },
                            'count': len(spotify_tracks),
                        })

                if len(spotify_tracks) >= request.track_count:
                    break

            yield await sse({'type': 'pass_complete', 'pass': 'search',
                             'message': f'Found {len(spotify_tracks)} tracks on Spotify'})

            if len(spotify_tracks) < request.track_count:
                yield await sse({'type': 'status', 'message': 'Looking for a few more tracks...'})
                spotify_tracks = await _refill_tracks(
                    llm_service, spotify_service, analysis,
                    spotify_tracks, unmatched, request.track_count,
                )

            formatted_tracks = _format_spotify_tracks(spotify_tracks[:request.track_count])

            yield await sse({'type': 'status', 'message': 'Creating playlist title...'})
            playlist_name = await llm_service.generate_playlist_title(request.query)

            # Say so when the playlist is short rather than quietly padding it.
            if len(formatted_tracks) < request.track_count:
                yield await sse({
                    'type': 'partial',
                    'requested': request.track_count,
                    'found': len(formatted_tracks),
                    'message': (
                        f'Found {len(formatted_tracks)} of {request.track_count} tracks. '
                        'Some suggestions were not available on Spotify.'
                    ),
                })

            yield await sse({
                'type': 'complete',
                'playlist': {
                    'playlist_name': playlist_name,
                    'tracks': formatted_tracks,
                    'track_count': len(formatted_tracks),
                    'requested_count': request.track_count,
                },
            })

        except asyncio.CancelledError:
            # Client navigated away or hit cancel; nothing to report.
            logger.info("Playlist stream cancelled by client")
            raise
        except Exception as e:
            logger.exception(f"Error in streaming playlist generation: {e}")
            yield await sse({
                'type': 'error',
                'message': 'Playlist generation failed. Please try again.',
            })

    return StreamingResponse(
        generate_with_progress(),
        # Must be text/event-stream for the frames below to be valid SSE.
        # CORS headers come from CORSMiddleware; setting them here too produced
        # a duplicate Access-Control-Allow-Origin, which browsers reject.
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # stop nginx buffering the stream
        },
    )


# ==========================================================================
# SPOTIFY / PROFILE ENDPOINTS
# ==========================================================================

@router.get("/search-tracks")
async def search_tracks(q: str, token: str = Depends(spotify_token)):
    """Search Spotify for tracks matching a free-text query."""
    try:
        spotify_service = SpotifyService(token)
        return {"results": await spotify_service.search_track(q)}
    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to search tracks", e)
    except Exception as e:
        raise _server_error("Failed to search tracks", e)


@router.get("/user-info")
async def get_user_info(token: str = Depends(spotify_token), db: Session = Depends(get_db)):
    """Return the caller's Spotify profile, merged with stored profile fields."""
    try:
        spotify_service = SpotifyService(token)
        user_profile = await spotify_service.get_user_profile()

        user_service = UserService(db)
        user = user_service.get_user_by_spotify_username(user_profile["id"])

        response_data = {
            "id": user_profile["id"],
            "display_name": user_profile.get("display_name", user_profile["id"]),
            "email": user_profile.get("email"),
            "images": user_profile.get("images", []),
        }

        if user:
            response_data.update({
                "first_name": user.first_name,
                "last_name": user.last_name,
                "location": user.location,
                # Never return the key itself, only whether one is stored.
                "has_openai_key": bool(user.openai_api_key),
            })
        else:
            response_data["has_openai_key"] = False

        return response_data
    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to get user info", e)
    except Exception as e:
        raise _server_error("Failed to get user info", e)


@router.post("/create-playlist")
async def create_playlist(
    request: CreatePlaylistRequest,
    token: str = Depends(spotify_token),
    db: Session = Depends(get_db),
):
    """Create the playlist in the caller's Spotify account."""
    try:
        spotify_service = SpotifyService(token)
        user_profile = await spotify_service.get_user_profile()

        description = request.description
        if not description:
            # Summarise what is actually in the playlist rather than echoing the
            # prompt, which read badly and used to overflow Spotify's limit.
            try:
                tracks = await spotify_service.get_tracks_details(request.track_ids[:30])
                description = await LLMService().generate_playlist_description(
                    request.query or request.name, tracks
                )
            except Exception as e:
                logger.warning(f"Falling back to a default description: {e}")
                description = "Generated by Aelyra"

        playlist = await spotify_service.create_playlist(
            request.name, description, public=request.public
        )

        if request.track_ids:
            await spotify_service.add_tracks_to_playlist(playlist["id"], request.track_ids)

        try:
            user_service = UserService(db)
            user = user_service.get_user_by_spotify_username(user_profile["id"])
            if user:
                track_details = await spotify_service.get_tracks_details(request.track_ids)
                PlaylistHistoryService(db).create_playlist_history(
                    user_id=user.id,
                    playlist_name=request.name,
                    user_description=request.description or "",
                    spotify_playlist_id=playlist["id"],
                    spotify_playlist_url=playlist["external_urls"]["spotify"],
                    track_data=track_details,
                )
        except Exception as history_error:
            # History is a nicety; a failure here must not lose the playlist.
            db.rollback()
            logger.exception(f"Error saving playlist history: {history_error}")

        return {
            "playlist_id": playlist["id"],
            "playlist_url": playlist["external_urls"]["spotify"],
            "message": "Playlist created successfully",
        }

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to create playlist", e)
    except Exception as e:
        raise _server_error("Failed to create playlist", e)


@router.put("/user-profile")
async def update_user_profile(
    request: UpdateProfileRequest,
    token: str = Depends(spotify_token),
    db: Session = Depends(get_db),
):
    """Update the caller's stored profile fields."""
    try:
        spotify_service = SpotifyService(token)
        user_profile = await spotify_service.get_user_profile()

        user_service = UserService(db)
        user = user_service.get_user_by_spotify_username(user_profile["id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_data = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "location": request.location,
        }

        # An empty key field means "unchanged"; clearing needs an explicit flag.
        if request.remove_openai_api_key:
            update_data["openai_api_key"] = UNSET
        elif request.openai_api_key:
            update_data["openai_api_key"] = request.openai_api_key

        updated_user = user_service.update_user(user, **update_data)

        return {
            "message": "Profile updated successfully",
            "first_name": updated_user.first_name,
            "last_name": updated_user.last_name,
            "location": updated_user.location,
            "has_openai_key": bool(updated_user.openai_api_key),
        }

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to update user profile", e)
    except Exception as e:
        raise _server_error("Failed to update user profile", e)


@router.get("/user-playlists")
async def get_user_playlists(
    limit: int = 20,
    offset: int = 0,
    token: str = Depends(spotify_token),
    db: Session = Depends(get_db),
):
    """Return the caller's playlist history, newest first."""
    try:
        limit = max(1, min(limit, 50))
        offset = max(0, offset)

        spotify_service = SpotifyService(token)
        user_profile = await spotify_service.get_user_profile()

        user_service = UserService(db)
        user = user_service.get_user_by_spotify_username(user_profile["id"])
        if not user:
            return {"playlists": []}

        playlists = PlaylistHistoryService(db).get_user_playlists(
            user.id, limit, offset, include_tracks=True
        )

        # Collect the cover tracks for every playlist, then resolve their album
        # art in as few Spotify calls as possible (50 ids per request).
        playlist_track_map = {}
        all_track_ids = []
        for playlist in playlists:
            track_ids = [t.spotify_track_id for t in (playlist.tracks or [])[:4]]
            playlist_track_map[playlist.playlist_hash] = track_ids
            all_track_ids.extend(track_ids)

        album_art_cache = {}
        unique_track_ids = list(dict.fromkeys(all_track_ids))
        for chunk_start in range(0, len(unique_track_ids), 50):
            chunk = unique_track_ids[chunk_start:chunk_start + 50]
            try:
                for track in await spotify_service.get_tracks_details(chunk):
                    if track and track.get('spotify_id') and track.get('album_art'):
                        album_art_cache[track['spotify_id']] = track['album_art']
            except Exception as e:
                logger.warning(f"Failed to fetch album art batch: {e}")

        playlist_data = []
        for playlist in playlists:
            track_ids = playlist_track_map.get(playlist.playlist_hash, [])
            album_art_urls = [album_art_cache[tid] for tid in track_ids if tid in album_art_cache]

            playlist_data.append({
                "id": playlist.playlist_hash,
                "name": playlist.playlist_name,
                "description": playlist.user_description,
                "spotify_url": playlist.spotify_playlist_url,
                "created_at": playlist.created_at.isoformat(),
                "track_count": playlist.track_count,
                "album_art": album_art_urls[:4],
                "tracks": [
                    {
                        "position": track.position,
                        "name": track.track_name,
                        "artist": track.artist_name,
                        "album": track.album_name,
                        "spotify_id": track.spotify_track_id,
                    }
                    for track in sorted(playlist.tracks, key=lambda t: t.position)
                ],
            })

        return {"playlists": playlist_data}

    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to get playlist history", e)
    except Exception as e:
        raise _server_error("Failed to get playlist history", e)


@router.post("/upload-playlist")
async def upload_playlist(
    request: UploadPlaylistRequest,
    token: str = Depends(spotify_token),
    db: Session = Depends(get_db),
):
    """Create a Spotify playlist from an uploaded M3U file."""
    try:
        is_valid, error_msg = M3UParser.validate_file_content(request.m3u_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid M3U file: {error_msg}")

        try:
            parsed_data = M3UParser.parse(request.m3u_content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        track_ids = parsed_data['track_ids']
        warnings = parsed_data['warnings']
        logger.info(f"Parsed M3U: {len(track_ids)} tracks, {len(warnings)} warnings")

        spotify_service = SpotifyService(token)
        user_profile = await spotify_service.get_user_profile()

        try:
            track_details = await spotify_service.get_tracks_details(track_ids)
        except Exception as e:
            raise _server_error("Failed to verify tracks on Spotify", e)

        valid_tracks = [track for track in track_details if track is not None]
        valid_track_ids = [track['spotify_id'] for track in valid_tracks]

        # Raised outside the try above: it used to sit inside it, where the
        # broad handler turned this 400 into a misleading 500.
        if not valid_track_ids:
            raise HTTPException(
                status_code=400,
                detail="None of the tracks in the M3U file are available on Spotify",
            )

        skipped_count = len(track_ids) - len(valid_track_ids)
        if skipped_count > 0:
            warnings.append(f"{skipped_count} tracks were not found on Spotify and were skipped")

        if request.custom_name and request.custom_name.strip():
            playlist_name = request.custom_name.strip()
        else:
            try:
                llm_service = LLMService()
                sample_artists = list(dict.fromkeys(t['artist'] for t in valid_tracks[:10]))
                query = (
                    f"A playlist of {len(valid_track_ids)} tracks featuring artists like "
                    f"{', '.join(sample_artists[:5])}"
                )
                playlist_name = await llm_service.generate_playlist_title(query)
            except Exception as e:
                logger.warning(f"Failed to generate playlist name, using fallback: {e}")
                playlist_name = "Uploaded Playlist"

        try:
            playlist = await spotify_service.create_playlist(
                playlist_name,
                f"Uploaded via Aelyra from M3U file ({len(valid_track_ids)} tracks)",
                public=request.public,
            )
            await spotify_service.add_tracks_to_playlist(playlist["id"], valid_track_ids)
        except httpx.HTTPStatusError as e:
            raise _spotify_http_error("Failed to create playlist on Spotify", e)
        except Exception as e:
            raise _server_error("Failed to create playlist on Spotify", e)

        try:
            user_service = UserService(db)
            user = user_service.get_user_by_spotify_username(user_profile["id"])
            if user:
                PlaylistHistoryService(db).create_playlist_history(
                    user_id=user.id,
                    playlist_name=playlist_name,
                    user_description="Uploaded from M3U file",
                    spotify_playlist_id=playlist["id"],
                    spotify_playlist_url=playlist["external_urls"]["spotify"],
                    track_data=valid_tracks,
                )
        except Exception as history_error:
            db.rollback()
            logger.exception(f"Error saving playlist history: {history_error}")

        return {
            "success": True,
            "playlist_id": playlist["id"],
            "playlist_name": playlist_name,
            "playlist_url": playlist["external_urls"]["spotify"],
            "tracks_added": len(valid_track_ids),
            "tracks_skipped": skipped_count,
            "warnings": warnings,
            "message": f"Playlist '{playlist_name}' created with {len(valid_track_ids)} tracks",
        }

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise _spotify_http_error("Failed to upload playlist", e)
    except Exception as e:
        raise _server_error("Failed to upload playlist", e)
