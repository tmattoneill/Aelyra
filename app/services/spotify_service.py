
import httpx
from typing import List, Dict, Optional
import logging
import hashlib
from functools import wraps
from cachetools import TTLCache
import threading

logger = logging.getLogger(__name__)

# Thread-safe TTL cache for Spotify API responses
# Max 1000 entries, 5 minute TTL (300 seconds)
_spotify_cache = TTLCache(maxsize=1000, ttl=300)
_cache_lock = threading.Lock()

# Separate cache for longer-lived data (track details) - 1 hour TTL
_track_details_cache = TTLCache(maxsize=500, ttl=3600)
_track_cache_lock = threading.Lock()


def cache_response(ttl=300, use_track_cache=False):
    """Decorator to cache Spotify API responses with automatic eviction"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = hashlib.md5(
                f"{func.__name__}:{str(args[1:])}:{str(kwargs)}".encode()
            ).hexdigest()

            # Select appropriate cache
            cache = _track_details_cache if use_track_cache else _spotify_cache
            lock = _track_cache_lock if use_track_cache else _cache_lock

            # Check if cached response exists (TTLCache handles expiration)
            with lock:
                if cache_key in cache:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cache[cache_key]

            # Call the actual function
            result = await func(*args, **kwargs)

            # Cache the result
            with lock:
                cache[cache_key] = result
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
    
    @cache_response(ttl=300)  # Cache search results for 5 minutes
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
    
    @cache_response(ttl=3600, use_track_cache=True)  # Cache track details for 1 hour
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
