
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging

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

@router.post("/generate-playlist", response_model=GeneratePlaylistResponse)
async def generate_playlist(request: GeneratePlaylistRequest, db: Session = Depends(get_db)):
    """
    Main endpoint: Generate a playlist based on natural language query
    """
    try:
        # Get user's stored OpenAI API key if available
        openai_api_key = request.openai_api_key
        if not openai_api_key:
            # Try to get user's stored API key
            spotify_service = SpotifyService(request.spotify_access_token)
            user_profile = await spotify_service.get_user_profile()
            user_service = UserService(db)
            user = user_service.get_user_by_spotify_username(user_profile["id"])
            if user and user.openai_api_key:
                openai_api_key = user.openai_api_key
        
        # Initialize services
        openai_service = OpenAIService(openai_api_key)
        spotify_service = SpotifyService(request.spotify_access_token)
        
        # Generate track suggestions using OpenAI
        suggested_tracks = await openai_service.generate_track_suggestions(request.query)
        
        # Search for tracks on Spotify and get alternatives
        tracks_with_alternatives = []
        for track in suggested_tracks:
            search_results = await spotify_service.search_track(f"{track['title']} {track['artist']}")
            if search_results:
                # Take the first result as main track, rest as alternatives
                main_track = search_results[0]
                alternatives = search_results[1:5]  # Up to 4 alternatives
                
                tracks_with_alternatives.append({
                    "title": main_track["title"],
                    "artist": main_track["artist"],
                    "spotify_id": main_track["spotify_id"],
                    "album_art": main_track.get("album_art"),
                    "preview_url": main_track.get("preview_url"),
                    "alternatives": alternatives
                })
        
        # Generate playlist title
        playlist_name = await openai_service.generate_playlist_title(request.query)
        
        return GeneratePlaylistResponse(
            playlist_name=playlist_name,
            tracks=tracks_with_alternatives
        )
        
    except Exception as e:
        logger.error(f"Error generating playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
                "location": user.location,
                "has_openai_key": bool(user.openai_api_key)
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
            request.description or f"Generated by PlayMaker"
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
            "location": request.location,
            "openai_api_key": request.openai_api_key
        }.items() if v is not None}
        
        updated_user = user_service.update_user(user, **update_data)
        
        return {
            "message": "Profile updated successfully",
            "first_name": updated_user.first_name,
            "last_name": updated_user.last_name,
            "location": updated_user.location,
            "has_openai_key": bool(updated_user.openai_api_key)
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
