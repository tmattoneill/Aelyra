
import httpx
from typing import List, Dict, Optional
import logging
import hashlib
import time
from functools import wraps

logger = logging.getLogger(__name__)

# Simple in-memory cache for Spotify API responses
_spotify_cache = {}
CACHE_TTL = 300  # 5 minutes

def cache_response(ttl=CACHE_TTL):
    """Decorator to cache Spotify API responses"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = hashlib.md5(
                f"{func.__name__}:{str(args[1:])}:{str(kwargs)}".encode()
            ).hexdigest()
            
            # Check if cached response exists and is still valid
            if cache_key in _spotify_cache:
                cached_data, timestamp = _spotify_cache[cache_key]
                if time.time() - timestamp < ttl:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_data
            
            # Call the actual function
            result = await func(*args, **kwargs)
            
            # Cache the result
            _spotify_cache[cache_key] = (result, time.time())
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
        return wrapper
    return decorator

class SpotifyService:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.spotify.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    @cache_response(ttl=600)  # Cache search results for 10 minutes
    async def search_track(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for tracks on Spotify using async HTTP
        """
        try:
            params = {
                "q": query,
                "type": "track",
                "limit": limit
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    headers=self.headers,
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
            
            tracks = []
            
            for track in data["tracks"]["items"]:
                track_data = {
                    "title": track["name"],
                    "artist": ", ".join([artist["name"] for artist in track["artists"]]),
                    "album": track["album"]["name"],
                    "spotify_id": track["id"],
                    "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                    "preview_url": track.get("preview_url")
                }
                tracks.append(track_data)
            
            return tracks
            
        except httpx.HTTPError as e:
            logger.error(f"Spotify search error: {str(e)}")
            raise Exception(f"Failed to search Spotify: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in search_track: {str(e)}")
            raise Exception(f"Failed to search Spotify: {str(e)}")
    
    async def get_user_profile(self) -> Dict:
        """
        Get current user's profile
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            raise Exception(f"Failed to get user profile: {str(e)}")
    
    async def create_playlist(self, name: str, description: str = "") -> Dict:
        """
        Create a new playlist for the user
        """
        try:
            data = {
                "name": name,
                "description": description,
                "public": False
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/me/playlists",
                    headers=self.headers,
                    json=data,
                    timeout=15.0
                )
                response.raise_for_status()
                return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to create playlist: {str(e)}")
            raise Exception(f"Failed to create playlist: {str(e)}")
    
    async def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict:
        """
        Add tracks to a playlist
        """
        try:
            # Convert track IDs to Spotify URIs
            uris = [f"spotify:track:{track_id}" for track_id in track_ids]
            
            data = {"uris": uris}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/playlists/{playlist_id}/tracks",
                    headers=self.headers,
                    json=data,
                    timeout=15.0
                )
                response.raise_for_status()
                return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to add tracks to playlist: {str(e)}")
            raise Exception(f"Failed to add tracks to playlist: {str(e)}")
    
    @cache_response(ttl=3600)  # Cache track details for 1 hour
    async def get_tracks_details(self, track_ids: List[str]) -> List[Dict]:
        """
        Get detailed information for multiple tracks by their IDs
        """
        try:
            # Spotify API allows up to 50 tracks per request
            track_data = []
            
            async with httpx.AsyncClient() as client:
                for i in range(0, len(track_ids), 50):
                    batch_ids = track_ids[i:i+50]
                    params = {"ids": ",".join(batch_ids)}
                    
                    response = await client.get(
                        f"{self.base_url}/tracks",
                        headers=self.headers,
                        params=params,
                        timeout=10.0
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    for track in data["tracks"]:
                        if track:  # Track might be None if not found
                            track_info = {
                                "spotify_id": track["id"],
                                "name": track["name"],
                                "artist": ", ".join([artist["name"] for artist in track["artists"]]),
                                "album": track["album"]["name"],
                                "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None
                            }
                            track_data.append(track_info)
            
            return track_data
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get track details: {str(e)}")
            raise Exception(f"Failed to get track details: {str(e)}")
