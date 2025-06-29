
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, AsyncGenerator
import logging
import json

from app.models.requests import GeneratePlaylistRequest, SearchTracksRequest, CreatePlaylistRequest, UpdateProfileRequest
from app.models.responses import GeneratePlaylistResponse, ErrorResponse
from app.services.spotify_service import SpotifyService
from app.services.openai_service import OpenAIService
from app.database import get_db
from app.services.user_service import UserService
from app.services.playlist_history_service import PlaylistHistoryService
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

async def _batch_search_spotify_tracks(spotify_service: SpotifyService, suggested_tracks: List[Dict]) -> List[Dict]:
    """
    Search all suggested tracks on Spotify in batches for better performance
    """
    found_tracks = []
    seen_track_ids = set()  # Track duplicate Spotify IDs
    batch_size = 15  # Increased batch size for better performance
    
    # Early exit if we have enough tracks for 10 main + alternatives
    target_tracks = 50  # 10 main tracks * 5 (1 main + 4 alternatives)
    
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
        if len(found_tracks) >= target_tracks:
            logger.info(f"Early exit: found {len(found_tracks)} unique tracks, stopping search")
            break
        
        # Reduced delay for better performance
        if i + batch_size < len(suggested_tracks):
            await asyncio.sleep(0.05)
    
    logger.info(f"Batch search: {len(found_tracks)} unique tracks found from {min(len(suggested_tracks), i + batch_size)} searched")
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

def _group_tracks_with_alternatives(spotify_tracks: List[Dict]) -> List[Dict]:
    """
    Group Spotify tracks into 10 main tracks with 4 alternatives each
    Ensures no duplicate Spotify IDs across main tracks and alternatives
    """
    tracks_with_alternatives = []
    used_spotify_ids = set()  # Track used Spotify IDs globally
    
    # Create a deduplicated list first
    unique_tracks = []
    for track in spotify_tracks:
        spotify_id = track.get("spotify_id")
        if spotify_id and spotify_id not in used_spotify_ids:
            unique_tracks.append(track)
            used_spotify_ids.add(spotify_id)
    
    logger.info(f"Deduplicated {len(spotify_tracks)} tracks to {len(unique_tracks)} unique tracks")
    
    # Now group the unique tracks
    tracks_per_group = 5  # 1 main + 4 alternatives
    
    for i in range(0, min(50, len(unique_tracks)), tracks_per_group):
        group = unique_tracks[i:i + tracks_per_group]
        
        if not group:
            break
            
        # First track is the main track
        main_track = group[0]
        alternatives = group[1:5]  # Up to 4 alternatives
        
        tracks_with_alternatives.append({
            "title": main_track["title"],
            "artist": main_track["artist"], 
            "spotify_id": main_track["spotify_id"],
            "album_art": main_track.get("album_art"),
            "preview_url": main_track.get("preview_url"),
            "alternatives": alternatives
        })
        
        # Stop once we have 10 groups
        if len(tracks_with_alternatives) >= 10:
            break
    
    return tracks_with_alternatives

async def _ensure_minimum_tracks(openai_service, spotify_service, query: str, current_tracks: List[Dict], min_required: int) -> List[Dict]:
    """
    Ensure we have at least the minimum required tracks, generating more if needed
    Optimized to be more efficient and have better fallback strategies
    """
    if len(current_tracks) >= min_required:
        return current_tracks
    
    logger.info(f"Need {min_required - len(current_tracks)} more tracks, generating fallback...")
    
    try:
        # Generate fewer additional tracks initially for faster response
        needed = min_required - len(current_tracks) + 5  # Reduced extra generation
        
        # Try a more focused approach 
        additional_tracks = await openai_service._generate_additional_tracks(query, current_tracks, needed)
        
        if additional_tracks:
            # Search new tracks on Spotify with smaller batches for faster response
            new_spotify_tracks = await _batch_search_spotify_tracks(spotify_service, additional_tracks)
            
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
        needed_popular = min(min_required - len(current_tracks), 10)  # Limit popular fallback
        popular_tracks = await _get_popular_fallback_tracks(spotify_service, query, needed_popular)
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

def _pad_track_groups(current_groups: List[Dict], all_tracks: List[Dict]) -> List[Dict]:
    """
    Pad track groups to ensure we have exactly 10 groups
    """
    padded_groups = current_groups.copy()
    used_track_ids = set()
    
    # Collect all already used track IDs
    for group in current_groups:
        used_track_ids.add(group["spotify_id"])
        for alt in group.get("alternatives", []):
            used_track_ids.add(alt.get("spotify_id"))
    
    # Find unused tracks
    unused_tracks = [track for track in all_tracks if track.get("spotify_id") not in used_track_ids]
    
    # Create additional groups from unused tracks
    while len(padded_groups) < 10 and unused_tracks:
        main_track = unused_tracks.pop(0)
        alternatives = unused_tracks[:4]
        unused_tracks = unused_tracks[4:]
        
        padded_groups.append({
            "title": main_track["title"],
            "artist": main_track["artist"],
            "spotify_id": main_track["spotify_id"],
            "album_art": main_track.get("album_art"),
            "preview_url": main_track.get("preview_url"),
            "alternatives": alternatives
        })
    
    # If we still don't have 10 groups, we'll just return what we have
    # Rather than create duplicates which break React key uniqueness
    logger.warning(f"Could only create {len(padded_groups)} unique groups instead of 10")
    
    # Don't create duplicates - this was causing React key conflicts
    
    return padded_groups  # Return unique groups only

@router.post("/generate-playlist", response_model=GeneratePlaylistResponse)
async def generate_playlist(request: GeneratePlaylistRequest, db: Session = Depends(get_db)):
    """
    Main endpoint: Generate a playlist based on natural language query using bulk generation
    """
    try:
        # Initialize services
        openai_service = OpenAIService()
        spotify_service = SpotifyService(request.spotify_access_token)
        
        # Generate 35 track suggestions in one bulk call for faster response
        suggested_tracks = await openai_service.generate_track_suggestions(request.query, count=35)
        logger.info(f"Generated {len(suggested_tracks)} tracks from OpenAI")
        
        # Search all tracks on Spotify in batches for better performance
        spotify_tracks = await _batch_search_spotify_tracks(spotify_service, suggested_tracks)
        logger.info(f"Found {len(spotify_tracks)} tracks on Spotify")
        
        # Ensure we have enough tracks, with fallback generation if needed
        spotify_tracks = await _ensure_minimum_tracks(openai_service, spotify_service, request.query, spotify_tracks, min_required=10)
        logger.info(f"Final track count after fallbacks: {len(spotify_tracks)}")
        
        # Group tracks into main tracks + alternatives (10 groups of 5 tracks each)
        tracks_with_alternatives = _group_tracks_with_alternatives(spotify_tracks)
        logger.info(f"Created {len(tracks_with_alternatives)} track groups")
        
        # Final safety check - ensure we have exactly 10 groups
        if len(tracks_with_alternatives) < 10:
            logger.warning(f"Only created {len(tracks_with_alternatives)} groups, padding to 10")
            tracks_with_alternatives = _pad_track_groups(tracks_with_alternatives, spotify_tracks)
        
        # Generate playlist title
        playlist_name = await openai_service.generate_playlist_title(request.query)
        
        return GeneratePlaylistResponse(
            playlist_name=playlist_name,
            tracks=tracks_with_alternatives
        )
        
    except Exception as e:
        logger.error(f"Error generating playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-playlist-stream")
async def generate_playlist_stream(request: GeneratePlaylistRequest, db: Session = Depends(get_db)):
    """
    Streaming endpoint for real-time playlist generation feedback
    """
    async def generate_with_progress() -> AsyncGenerator[str, None]:
        try:
            # Initialize services
            openai_service = OpenAIService()
            spotify_service = SpotifyService(request.spotify_access_token)
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Generating track suggestions...'})}\n\n"
            
            # Generate 50 track suggestions in one bulk call
            suggested_tracks = await openai_service.generate_track_suggestions(request.query)
            yield f"data: {json.dumps({'type': 'status', 'message': f'Generated {len(suggested_tracks)} track suggestions, searching Spotify...'})}\n\n"
            
            # Search tracks with progress updates
            spotify_tracks = []
            batch_size = 10
            
            for i in range(0, len(suggested_tracks), batch_size):
                batch = suggested_tracks[i:i + batch_size]
                batch_tracks = await _batch_search_spotify_tracks_with_progress(spotify_service, batch, i, len(suggested_tracks))
                
                # Send progress for each found track
                for track in batch_tracks:
                    if track:
                        spotify_tracks.append(track)
                        yield f"data: {json.dumps({'type': 'track_found', 'track': {'title': track['title'], 'artist': track['artist'], 'album_art': track.get('album_art')}, 'count': len(spotify_tracks)})}\n\n"
            
            yield f"data: {json.dumps({'type': 'status', 'message': f'Found {len(spotify_tracks)} tracks, organizing playlist...'})}\n\n"
            
            # Ensure minimum tracks with fallbacks
            spotify_tracks = await _ensure_minimum_tracks_with_progress(openai_service, spotify_service, request.query, spotify_tracks, 10)
            
            # Group tracks into final playlist
            tracks_with_alternatives = _group_tracks_with_alternatives(spotify_tracks)
            
            if len(tracks_with_alternatives) < 10:
                tracks_with_alternatives = _pad_track_groups(tracks_with_alternatives, spotify_tracks)
            
            # Generate title
            yield f"data: {json.dumps({'type': 'status', 'message': 'Creating playlist title...'})}\n\n"
            playlist_name = await openai_service.generate_playlist_title(request.query)
            
            # Send final result
            result = {
                'type': 'complete',
                'playlist': {
                    'playlist_name': playlist_name,
                    'tracks': tracks_with_alternatives
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

async def _batch_search_spotify_tracks_with_progress(spotify_service: SpotifyService, suggested_tracks: List[Dict], batch_start: int, total_tracks: int) -> List[Dict]:
    """
    Search tracks with progress feedback - faster than original batch function
    """
    found_tracks = []
    batch_tasks = []
    
    for track in suggested_tracks:
        # _search_single_track now handles the search strategy internally  
        batch_tasks.append(_search_single_track(spotify_service, "", track))
    
    # Execute batch concurrently  
    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
    
    for result in batch_results:
        if not isinstance(result, Exception) and result:
            found_tracks.append(result)
    
    return found_tracks

async def _ensure_minimum_tracks_with_progress(openai_service, spotify_service, query: str, current_tracks: List[Dict], min_required: int) -> List[Dict]:
    """
    Ensure minimum tracks with progress updates - simplified for speed
    """
    if len(current_tracks) >= min_required:
        return current_tracks
    
    try:
        needed = min_required - len(current_tracks) + 5  # Generate fewer extra for speed
        additional_tracks = await openai_service._generate_additional_tracks(query, current_tracks, needed)
        
        if additional_tracks:
            new_spotify_tracks = await _batch_search_spotify_tracks_with_progress(spotify_service, additional_tracks, 0, len(additional_tracks))
            
            existing_ids = {track.get("spotify_id") for track in current_tracks}
            for track in new_spotify_tracks:
                if track.get("spotify_id") not in existing_ids:
                    current_tracks.append(track)
                    existing_ids.add(track.get("spotify_id"))
                    if len(current_tracks) >= min_required:
                        break
    except Exception as e:
        logger.error(f"Fallback generation failed: {str(e)}")
    
    return current_tracks

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
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        # Check if it's a token-related error
        if "401" in str(e) or "403" in str(e) or "Bad Request" in str(e):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
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
        
    except Exception as e:
        logger.error(f"Error creating playlist: {str(e)}")
        # Check if it's a token-related error
        if "401" in str(e) or "403" in str(e) or "Bad Request" in str(e):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
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
        
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        if "401" in str(e) or "403" in str(e):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
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
        playlists = playlist_history_service.get_user_playlists(user.id, limit, offset)
        
        playlist_data = []
        for playlist in playlists:
            tracks = playlist_history_service.get_playlist_tracks(playlist.id)
            
            # Get album art for the first 4 tracks for UI display
            album_art_urls = []
            if tracks:
                first_four_track_ids = [track.spotify_track_id for track in tracks[:4]]
                try:
                    # Add small delay to avoid overwhelming Spotify API
                    await asyncio.sleep(0.03)  # 30ms delay
                    track_details = await spotify_service.get_tracks_details(first_four_track_ids)
                    album_art_urls = [track.get('album_art') for track in track_details if track.get('album_art')]
                except Exception as e:
                    logger.warning(f"Failed to get album art for playlist {playlist.playlist_hash}: {e}")
            
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
                    for track in tracks
                ]
            })
        
        return {"playlists": playlist_data}
        
    except Exception as e:
        logger.error(f"Error getting user playlists: {str(e)}")
        if "401" in str(e) or "403" in str(e):
            raise HTTPException(status_code=401, detail="Spotify token expired or invalid")
        raise HTTPException(status_code=500, detail=str(e))
