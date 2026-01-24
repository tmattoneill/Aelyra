
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, AsyncGenerator
import logging
import json
import httpx

from app.models.requests import GeneratePlaylistRequest, SearchTracksRequest, CreatePlaylistRequest, UpdateProfileRequest, UploadPlaylistRequest
from app.models.responses import GeneratePlaylistResponse, ErrorResponse
from app.services.spotify_service import SpotifyService
from app.services.openai_service import OpenAIService, QueryAnalysis
from app.database import get_db
from app.services.user_service import UserService
from app.services.playlist_history_service import PlaylistHistoryService
from app.services.m3u_parser import M3UParser
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


# ==========================================================================
# SPOTIFY TRACK SEARCH HELPERS
# ==========================================================================

async def _batch_search_spotify_tracks(
    spotify_service: SpotifyService,
    suggested_tracks: List[Dict],
    target_count: int = None
) -> List[Dict]:
    """
    Search all suggested tracks on Spotify in batches for better performance.

    Args:
        spotify_service: Spotify service instance
        suggested_tracks: List of track suggestions from OpenAI
        target_count: Optional target number of tracks (for early exit optimization)

    Returns:
        List of found Spotify tracks
    """
    found_tracks = []
    seen_track_ids = set()  # Track duplicate Spotify IDs
    batch_size = 15  # Increased batch size for better performance

    for i in range(0, len(suggested_tracks), batch_size):
        batch = suggested_tracks[i:i + batch_size]
        batch_tasks = []

        for track in batch:
            batch_tasks.append(_search_single_track(spotify_service, "", track))

        # Execute batch of searches concurrently
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Process results and filter out exceptions and duplicates
        for result in batch_results:
            if not isinstance(result, Exception) and result:
                spotify_id = result.get("spotify_id")
                if spotify_id and spotify_id not in seen_track_ids:
                    found_tracks.append(result)
                    seen_track_ids.add(spotify_id)
                elif spotify_id in seen_track_ids:
                    logger.debug(f"Skipping duplicate track: {result.get('title')} by {result.get('artist')}")

        # Early exit if we have enough tracks
        if target_count and len(found_tracks) >= target_count:
            logger.info(f"Early exit: found {len(found_tracks)} unique tracks, stopping search")
            break

        # Reduced delay for better performance
        if i + batch_size < len(suggested_tracks):
            await asyncio.sleep(0.05)

    tracks_searched = min(len(suggested_tracks), i + batch_size) if suggested_tracks else 0
    logger.info(f"Batch search: {len(found_tracks)} unique tracks found from {tracks_searched} searched")
    return found_tracks

async def _search_single_track(spotify_service: SpotifyService, search_query: str, original_track: Dict) -> Dict:
    """
    Search for a single track on Spotify with improved multi-step strategy
    """
    track_name = original_track.get('track_name', original_track.get('title', ''))
    artist = original_track.get('artist', '')
    album = original_track.get('album', '')
    
    try:
        # Strategy 1: Search with just track name + artist (more likely to succeed)
        basic_query = f"{track_name} {artist}".strip()
        search_results = await spotify_service.search_track(basic_query, limit=10)
        
        if search_results:
            # If we have album info, try to find the best match
            if album and album != "Unknown Album":
                # Look for exact album match first
                for result in search_results:
                    result_album = result.get('album', '')
                    if result_album and album.lower() in result_album.lower():
                        return result
                
                # Look for partial album matches (common words, ignoring "soundtrack", "greatest hits", etc.)
                album_words = set(album.lower().split())
                best_match = None
                best_score = 0
                
                for result in search_results:
                    result_album = result.get('album', '')
                    if result_album:
                        result_words = set(result_album.lower().split())
                        common_words = album_words.intersection(result_words)
                        # Filter out common non-descriptive words
                        meaningful_words = common_words - {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'soundtrack', 'greatest', 'hits', 'best', 'collection'}
                        
                        if len(meaningful_words) > best_score:
                            best_score = len(meaningful_words)
                            best_match = result
                
                # Return best match or first result if no good album match
                return best_match if best_match else search_results[0]
            else:
                # No album info, return first result
                return search_results[0]
        
        # Strategy 2: Try with quotes around track name
        if '"' not in track_name:
            quoted_query = f'"{track_name}" {artist}'
            search_results = await spotify_service.search_track(quoted_query, limit=5)
            if search_results:
                return search_results[0]
        
        # Strategy 3: Try just the track name (very broad)
        if track_name:
            track_only_query = f'"{track_name}"'
            search_results = await spotify_service.search_track(track_only_query, limit=5)
            if search_results:
                return search_results[0]
        
        # If all strategies fail
        logger.warning(f"No Spotify results for track: {track_name} by {artist}")
        return None
        
    except Exception as e:
        logger.warning(f"Spotify search failed for '{track_name}' by '{artist}': {str(e)}")
        return None

def _format_spotify_tracks(spotify_tracks: List[Dict]) -> List[Dict]:
    """
    Format Spotify tracks for the response.
    Ensures consistent format and removes duplicates.
    """
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
                "preview_url": track.get("preview_url")
            })
            seen_ids.add(spotify_id)

    return formatted_tracks

async def _ensure_minimum_tracks(
    openai_service,
    spotify_service,
    analysis: QueryAnalysis,
    current_tracks: List[Dict],
    min_required: int
) -> List[Dict]:
    """
    Ensure we have at least the minimum required tracks, generating more if needed.
    Uses the QueryAnalysis for better targeted generation.
    """
    if len(current_tracks) >= min_required:
        return current_tracks

    logger.info(f"Need {min_required - len(current_tracks)} more tracks, generating fallback...")

    try:
        # Generate additional tracks using the analysis
        needed = min_required - len(current_tracks) + 5

        # Convert current tracks to format expected by OpenAI service
        existing_ai_tracks = [
            {"track_name": t.get("title"), "artist": t.get("artist")}
            for t in current_tracks
        ]

        additional_tracks = await openai_service.generate_tracks_from_analysis(
            analysis,
            needed,
            existing_ai_tracks
        )

        if additional_tracks:
            # Search new tracks on Spotify
            new_spotify_tracks = await _batch_search_spotify_tracks(
                spotify_service,
                additional_tracks,
                target_count=needed
            )

            # Add them to our collection (avoid duplicates)
            existing_ids = {track.get("spotify_id") for track in current_tracks if track.get("spotify_id")}
            for track in new_spotify_tracks:
                spotify_id = track.get("spotify_id")
                if spotify_id and spotify_id not in existing_ids:
                    current_tracks.append(track)
                    existing_ids.add(spotify_id)

                    # Early exit when we have enough
                    if len(current_tracks) >= min_required:
                        break

    except Exception as e:
        logger.error(f"Fallback generation failed: {str(e)}")

    # If we still don't have enough, try popular tracks as last resort
    if len(current_tracks) < min_required:
        logger.warning("Using popular tracks as final fallback")
        # Build a query from analysis for fallback
        fallback_parts = analysis.genres[:2] + analysis.moods[:2]
        fallback_query = " ".join(fallback_parts) if fallback_parts else "popular music"
        needed_popular = min(min_required - len(current_tracks), 10)
        popular_tracks = await _get_popular_fallback_tracks(spotify_service, fallback_query, needed_popular)
        current_tracks.extend(popular_tracks)

    return current_tracks

async def _get_popular_fallback_tracks(spotify_service, query: str, count: int) -> List[Dict]:
    """
    Get popular tracks as a fallback when all else fails
    """
    try:
        # Search for popular tracks related to the query
        fallback_searches = [
            f"{query} popular",
            f"{query} hits",
            "popular songs",
            "top hits",
            "best songs"
        ]
        
        fallback_tracks = []
        for search_term in fallback_searches:
            try:
                results = await spotify_service.search_track(search_term, limit=5)
                fallback_tracks.extend(results)
                if len(fallback_tracks) >= count:
                    break
            except Exception as e:
                logger.warning(f"Fallback search failed for '{search_term}': {str(e)}")
                continue
        
        return fallback_tracks[:count]
    
    except Exception as e:
        logger.error(f"Popular fallback failed: {str(e)}")
        return []


@router.post("/generate-playlist", response_model=GeneratePlaylistResponse)
async def generate_playlist(request: GeneratePlaylistRequest, db: Session = Depends(get_db)):
    """
    Main endpoint: Generate a playlist based on natural language query using multi-pass agentic approach.

    The generation follows three passes:
    1. ANALYZE: Parse the query to extract genres, moods, eras, themes, etc.
    2. GENERATE: Create track suggestions based on the analysis
    3. VALIDATE: Ensure diversity (max 2 tracks per artist, no duplicates)
    """
    try:
        # Initialize services
        openai_service = OpenAIService()
        spotify_service = SpotifyService(request.spotify_access_token)

        # Use the new agentic multi-pass generation
        suggested_tracks, analysis = await openai_service.generate_playlist_agentic(
            query=request.query,
            track_count=request.track_count
        )
        logger.info(f"Generated {len(suggested_tracks)} tracks from agentic generation")

        # Search all tracks on Spotify
        spotify_tracks = await _batch_search_spotify_tracks(
            spotify_service,
            suggested_tracks,
            target_count=request.track_count
        )
        logger.info(f"Found {len(spotify_tracks)} tracks on Spotify")

        # Ensure we have enough tracks
        if len(spotify_tracks) < request.track_count:
            spotify_tracks = await _ensure_minimum_tracks(
                openai_service,
                spotify_service,
                analysis,
                spotify_tracks,
                min_required=request.track_count
            )
            logger.info(f"Final track count after fallbacks: {len(spotify_tracks)}")

        # Format tracks for response (no alternatives, just flat list)
        formatted_tracks = _format_spotify_tracks(spotify_tracks[:request.track_count])
        logger.info(f"Returning {len(formatted_tracks)} formatted tracks")

        # Generate playlist title
        playlist_name = await openai_service.generate_playlist_title(request.query)

        return GeneratePlaylistResponse(
            playlist_name=playlist_name,
            tracks=formatted_tracks
        )

    except Exception as e:
        logger.error(f"Error generating playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-playlist-stream")
async def generate_playlist_stream(request: GeneratePlaylistRequest, db: Session = Depends(get_db)):
    """
    Streaming endpoint for real-time playlist generation feedback.
    Uses multi-pass agentic approach with progress updates for each pass:
    1. ANALYZE: Parse the query
    2. GENERATE: Create track suggestions
    3. VALIDATE: Ensure diversity
    4. SEARCH: Find tracks on Spotify
    """
    async def generate_with_progress() -> AsyncGenerator[str, None]:
        analysis = None

        try:
            # Initialize services
            openai_service = OpenAIService()
            spotify_service = SpotifyService(request.spotify_access_token)

            # Track progress events to send to client
            progress_events = []

            async def progress_callback(pass_name: str, message: str):
                event = {
                    'type': 'pass_progress',
                    'pass': pass_name,
                    'message': message
                }
                progress_events.append(event)

            # PASS 1: Analyze the query
            yield f"data: {json.dumps({'type': 'pass_start', 'pass': 'analyze', 'message': 'Analyzing your music preferences...'})}\n\n"

            analysis = await openai_service.analyze_query(request.query)
            genres_str = ', '.join(analysis.genres[:3]) if analysis.genres else 'various genres'
            moods_str = ', '.join(analysis.moods[:2]) if analysis.moods else 'mixed moods'
            analysis_summary = f"Found: {genres_str} / {moods_str}"
            yield f"data: {json.dumps({'type': 'pass_complete', 'pass': 'analyze', 'message': analysis_summary})}\n\n"

            # PASS 2: Generate tracks
            yield f"data: {json.dumps({'type': 'pass_start', 'pass': 'generate', 'message': f'Generating {request.track_count} track recommendations...'})}\n\n"

            suggested_tracks = await openai_service.generate_tracks_from_analysis(
                analysis,
                request.track_count
            )
            yield f"data: {json.dumps({'type': 'pass_complete', 'pass': 'generate', 'message': f'Generated {len(suggested_tracks)} potential tracks'})}\n\n"

            # PASS 3: Validate diversity
            yield f"data: {json.dumps({'type': 'pass_start', 'pass': 'validate', 'message': 'Validating playlist diversity...'})}\n\n"

            diversity_report = await openai_service.validate_diversity(suggested_tracks, analysis)
            if diversity_report.is_valid:
                yield f"data: {json.dumps({'type': 'pass_complete', 'pass': 'validate', 'message': 'Diversity check passed'})}\n\n"
            else:
                issue_msg = diversity_report.issues[0] if diversity_report.issues else "diversity issues"
                yield f"data: {json.dumps({'type': 'pass_progress', 'pass': 'validate', 'message': 'Fixing: ' + issue_msg})}\n\n"
                # Apply diversity fixes
                suggested_tracks = await _apply_diversity_fixes(
                    openai_service, analysis, suggested_tracks, diversity_report, request.track_count
                )
                yield f"data: {json.dumps({'type': 'pass_complete', 'pass': 'validate', 'message': 'Diversity issues resolved'})}\n\n"

            # PASS 4: Search Spotify
            yield f"data: {json.dumps({'type': 'pass_start', 'pass': 'search', 'message': 'Searching Spotify for tracks...'})}\n\n"

            spotify_tracks = []
            seen_ids = set()
            batch_size = 10

            for i in range(0, len(suggested_tracks), batch_size):
                batch = suggested_tracks[i:i + batch_size]
                batch_tasks = [_search_single_track(spotify_service, "", track) for track in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for result in batch_results:
                    if not isinstance(result, Exception) and result:
                        spotify_id = result.get("spotify_id")
                        if spotify_id and spotify_id not in seen_ids:
                            spotify_tracks.append(result)
                            seen_ids.add(spotify_id)
                            # Send track found event
                            yield f"data: {json.dumps({'type': 'track_found', 'track': {'title': result['title'], 'artist': result['artist'], 'album_art': result.get('album_art')}, 'count': len(spotify_tracks)})}\n\n"

                # Early exit if we have enough
                if len(spotify_tracks) >= request.track_count:
                    break

            yield f"data: {json.dumps({'type': 'pass_complete', 'pass': 'search', 'message': f'Found {len(spotify_tracks)} tracks on Spotify'})}\n\n"

            # Ensure minimum tracks if needed
            if len(spotify_tracks) < request.track_count:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Finding additional tracks...'})}\n\n"
                spotify_tracks = await _ensure_minimum_tracks(
                    openai_service, spotify_service, analysis, spotify_tracks, request.track_count
                )

            # Format tracks for response (flat list, no alternatives)
            formatted_tracks = _format_spotify_tracks(spotify_tracks[:request.track_count])

            # Generate title
            yield f"data: {json.dumps({'type': 'status', 'message': 'Creating playlist title...'})}\n\n"
            playlist_name = await openai_service.generate_playlist_title(request.query)

            # Send final result
            result = {
                'type': 'complete',
                'playlist': {
                    'playlist_name': playlist_name,
                    'tracks': formatted_tracks,
                    'track_count': len(formatted_tracks)
                }
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming playlist generation: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_with_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


async def _apply_diversity_fixes(
    openai_service,
    analysis: QueryAnalysis,
    tracks: List[Dict],
    report,
    target_count: int
) -> List[Dict]:
    """
    Apply diversity fixes by removing problematic tracks and generating replacements.
    """
    # Remove tracks from over-represented artists
    artist_count = {}
    cleaned_tracks = []

    for track in tracks:
        artist = track.get('artist', '').lower()
        if artist_count.get(artist, 0) < 2:
            cleaned_tracks.append(track)
            artist_count[artist] = artist_count.get(artist, 0) + 1

    # Remove duplicate track names
    seen_names = set()
    final_tracks = []
    for track in cleaned_tracks:
        name = track.get('track_name', track.get('title', '')).lower()
        if name not in seen_names:
            final_tracks.append(track)
            seen_names.add(name)

    # Generate replacements if needed
    if len(final_tracks) < target_count:
        needed = target_count - len(final_tracks) + 5
        replacements = await openai_service.generate_replacement_tracks(
            analysis,
            needed,
            final_tracks,
            report.artist_violations
        )
        final_tracks.extend(replacements)

    return final_tracks[:target_count + 5]  # Return with small buffer

@router.get("/search-tracks")
async def search_tracks(q: str, spotify_access_token: str):
    """
    Search for specific tracks on Spotify
    """
    try:
        spotify_service = SpotifyService(spotify_access_token)
        results = await spotify_service.search_track(q)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error searching tracks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user-info")
async def get_user_info(spotify_access_token: str, db: Session = Depends(get_db)):
    """
    Get user profile information and validate token
    """
    try:
        spotify_service = SpotifyService(spotify_access_token)
        user_profile = await spotify_service.get_user_profile()
        
        # Get or create user record
        user_service = UserService(db)
        user = user_service.get_user_by_spotify_username(user_profile["id"])
        
        response_data = {
            "id": user_profile["id"],
            "display_name": user_profile.get("display_name", user_profile["id"]),
            "email": user_profile.get("email"),
            "images": user_profile.get("images", [])
        }
        
        # Add stored profile data if user exists
        if user:
            response_data.update({
                "first_name": user.first_name,
                "last_name": user.last_name,
                "location": user.location
            })
        
        return response_data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error getting user info: {e.response.status_code}")
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-playlist")
async def create_playlist(request: CreatePlaylistRequest, db: Session = Depends(get_db)):
    """
    Create a playlist in user's Spotify account
    """
    try:
        spotify_service = SpotifyService(request.spotify_access_token)
        
        # Verify token is valid by getting user profile
        user_profile = await spotify_service.get_user_profile()
        
        # Create playlist
        playlist = await spotify_service.create_playlist(
            request.name, 
            request.description or f"Generated by Aelyra"
        )
        
        # Add tracks to playlist
        if request.track_ids:
            await spotify_service.add_tracks_to_playlist(playlist["id"], request.track_ids)
        
        # Save playlist history
        try:
            user_service = UserService(db)
            user = user_service.get_user_by_spotify_username(user_profile["id"])
            
            if user:
                # Get detailed track information
                track_details = await spotify_service.get_tracks_details(request.track_ids)
                
                # Save playlist history
                playlist_history_service = PlaylistHistoryService(db)
                playlist_history_service.create_playlist_history(
                    user_id=user.id,
                    playlist_name=request.name,
                    user_description=request.description or "",
                    spotify_playlist_id=playlist["id"],
                    spotify_playlist_url=playlist["external_urls"]["spotify"],
                    track_data=track_details
                )
        except Exception as history_error:
            # Log the error but don't fail the playlist creation
            logger.error(f"Error saving playlist history: {str(history_error)}")
        
        return {
            "playlist_id": playlist["id"],
            "playlist_url": playlist["external_urls"]["spotify"],
            "message": "Playlist created successfully"
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating playlist: {e.response.status_code}")
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/user-profile")
async def update_user_profile(request: UpdateProfileRequest, db: Session = Depends(get_db)):
    """
    Update user profile information
    """
    try:
        spotify_service = SpotifyService(request.spotify_access_token)
        user_profile = await spotify_service.get_user_profile()
        
        user_service = UserService(db)
        user = user_service.get_user_by_spotify_username(user_profile["id"])
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user with provided data
        update_data = {k: v for k, v in {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "location": request.location
        }.items() if v is not None}
        
        updated_user = user_service.update_user(user, **update_data)
        
        return {
            "message": "Profile updated successfully",
            "first_name": updated_user.first_name,
            "last_name": updated_user.last_name,
            "location": updated_user.location
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error updating user profile: {e.response.status_code}")
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user-playlists")
async def get_user_playlists(spotify_access_token: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """
    Get user's playlist history
    """
    try:
        spotify_service = SpotifyService(spotify_access_token)
        user_profile = await spotify_service.get_user_profile()
        
        user_service = UserService(db)
        user = user_service.get_user_by_spotify_username(user_profile["id"])
        
        if not user:
            return {"playlists": []}
        
        playlist_history_service = PlaylistHistoryService(db)
        # Use eager loading to prevent N+1 queries
        playlists = playlist_history_service.get_user_playlists(user.id, limit, offset, include_tracks=True)

        # Collect all track IDs for batch fetching album art
        all_track_ids = []
        playlist_track_map = {}  # Map playlist_hash -> list of track_ids for album art

        for playlist in playlists:
            # Access eagerly loaded tracks
            tracks = playlist.tracks[:4] if playlist.tracks else []
            track_ids = [track.spotify_track_id for track in tracks]
            all_track_ids.extend(track_ids)
            playlist_track_map[playlist.playlist_hash] = track_ids

        # Batch fetch album art for all playlists in one call (up to 50 tracks)
        album_art_cache = {}
        if all_track_ids:
            try:
                # Fetch up to 50 tracks at once
                unique_track_ids = list(set(all_track_ids))[:50]
                track_details = await spotify_service.get_tracks_details(unique_track_ids)
                for track in track_details:
                    if track and track.get('spotify_id') and track.get('album_art'):
                        album_art_cache[track['spotify_id']] = track['album_art']
            except Exception as e:
                logger.warning(f"Failed to batch fetch album art: {e}")

        playlist_data = []
        for playlist in playlists:
            # Get album art from cache
            track_ids = playlist_track_map.get(playlist.playlist_hash, [])
            album_art_urls = [album_art_cache.get(tid) for tid in track_ids if album_art_cache.get(tid)]

            playlist_data.append({
                "id": playlist.playlist_hash,
                "name": playlist.playlist_name,
                "description": playlist.user_description,
                "spotify_url": playlist.spotify_playlist_url,
                "created_at": playlist.created_at.isoformat(),
                "track_count": playlist.track_count,
                "album_art": album_art_urls[:4],  # Limit to 4 for 2x2 grid
                "tracks": [
                    {
                        "position": track.position,
                        "name": track.track_name,
                        "artist": track.artist_name,
                        "album": track.album_name,
                        "spotify_id": track.spotify_track_id
                    }
                    for track in sorted(playlist.tracks, key=lambda t: t.position)
                ]
            })
        
        return {"playlists": playlist_data}
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error getting user playlists: {e.response.status_code}")
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user playlists: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-playlist")
async def upload_playlist(request: UploadPlaylistRequest, db: Session = Depends(get_db)):
    """
    Upload a playlist from an M3U file containing Spotify track URLs
    """
    try:
        # Validate M3U content
        is_valid, error_msg = M3UParser.validate_file_content(request.m3u_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid M3U file: {error_msg}")

        # Parse M3U file
        try:
            parsed_data = M3UParser.parse(request.m3u_content)
            track_ids = parsed_data['track_ids']
            warnings = parsed_data['warnings']

            logger.info(f"Parsed M3U file: {len(track_ids)} tracks, {len(warnings)} warnings")

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Initialize Spotify service
        spotify_service = SpotifyService(request.spotify_access_token)

        # Verify token is valid by getting user profile
        user_profile = await spotify_service.get_user_profile()

        # Get track details from Spotify to verify they exist
        try:
            track_details = await spotify_service.get_tracks_details(track_ids)

            # Filter out tracks that don't exist (None values)
            valid_tracks = [track for track in track_details if track is not None]
            valid_track_ids = [track['spotify_id'] for track in valid_tracks]

            if not valid_track_ids:
                raise HTTPException(
                    status_code=400,
                    detail="None of the tracks in the M3U file are available on Spotify"
                )

            # Warn if some tracks were skipped
            skipped_count = len(track_ids) - len(valid_track_ids)
            if skipped_count > 0:
                warnings.append(f"{skipped_count} tracks were not found on Spotify and were skipped")
                logger.warning(f"Skipped {skipped_count} unavailable tracks")

        except Exception as e:
            logger.error(f"Error fetching track details: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to verify tracks on Spotify"
            )

        # Generate playlist name using OpenAI (or use custom name if provided)
        if request.custom_name and request.custom_name.strip():
            playlist_name = request.custom_name.strip()
        else:
            # Generate AI name based on track metadata
            try:
                openai_service = OpenAIService()

                # Create a descriptive query from track artists and names
                sample_artists = list(set([track['artist'] for track in valid_tracks[:10]]))
                sample_tracks = [track['name'] for track in valid_tracks[:5]]

                # Create a query for the AI to generate a name
                query = f"A playlist with {len(valid_track_ids)} tracks featuring artists like {', '.join(sample_artists[:5])}"

                playlist_name = await openai_service.generate_playlist_title(query)
                logger.info(f"Generated playlist name: {playlist_name}")

            except Exception as e:
                logger.warning(f"Failed to generate AI playlist name: {str(e)}, using fallback")
                playlist_name = "Uploaded Playlist"

        # Create playlist in Spotify
        try:
            playlist = await spotify_service.create_playlist(
                playlist_name,
                f"Uploaded via Aelyra from M3U file ({len(valid_track_ids)} tracks)"
            )

            # Add tracks to playlist
            await spotify_service.add_tracks_to_playlist(playlist["id"], valid_track_ids)

        except Exception as e:
            logger.error(f"Error creating playlist: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create playlist on Spotify: {str(e)}"
            )

        # Save playlist history
        try:
            user_service = UserService(db)
            user = user_service.get_user_by_spotify_username(user_profile["id"])

            if user:
                playlist_history_service = PlaylistHistoryService(db)
                playlist_history_service.create_playlist_history(
                    user_id=user.id,
                    playlist_name=playlist_name,
                    user_description=f"Uploaded from M3U file",
                    spotify_playlist_id=playlist["id"],
                    spotify_playlist_url=playlist["external_urls"]["spotify"],
                    track_data=valid_tracks
                )
        except Exception as history_error:
            # Log the error but don't fail the playlist creation
            logger.error(f"Error saving playlist history: {str(history_error)}")

        # Return success response
        return {
            "success": True,
            "playlist_id": playlist["id"],
            "playlist_name": playlist_name,
            "playlist_url": playlist["external_urls"]["spotify"],
            "tracks_added": len(valid_track_ids),
            "tracks_skipped": skipped_count,
            "warnings": warnings,
            "message": f"Playlist '{playlist_name}' created successfully with {len(valid_track_ids)} tracks"
        }

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error uploading playlist: {e.response.status_code}")
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
