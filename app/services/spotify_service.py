
import hashlib
import logging
import threading
from functools import wraps
from typing import Dict, List

import httpx
from cachetools import TTLCache

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

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        """Raise on an error response, logging what Spotify actually said.

        raise_for_status alone reports only the status code, and the previous
        code then wrapped it in a plain Exception. That threw away both the
        response body, which carries Spotify's reason for a 400, and the status
        code itself, so callers could not tell an expired token from a bad
        request and every failure surfaced as a 500.
        """
        if response.is_success:
            return

        detail = ""
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message") or str(payload)
        except Exception:
            detail = response.text[:500]

        logger.error(f"Spotify refused to {action}: {response.status_code} {detail}")
        response.raise_for_status()

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
                self._raise_for_status(response, "search tracks")
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

        except httpx.HTTPStatusError:
            # Let the status code reach the router so 401 and 429 can be
            # translated into the right response instead of a blanket 500.
            raise
        except httpx.HTTPError as e:
            logger.error(f"Spotify search transport error: {e}")
            raise

    async def get_user_profile(self) -> Dict:
        """
        Get current user's profile
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me",
                headers=self.headers,
                timeout=10.0
            )
            self._raise_for_status(response, "read the user profile")
            return response.json()

    # Spotify rejects the whole request with a bare 400 if either field is over
    # length, so they are clamped here rather than relied on upstream.
    MAX_PLAYLIST_NAME = 100
    MAX_PLAYLIST_DESCRIPTION = 300

    @staticmethod
    def _clamp(value: str, limit: int) -> str:
        value = (value or "").strip()
        if len(value) <= limit:
            return value
        return value[: limit - 1].rstrip() + "…"

    async def create_playlist(self, name: str, description: str = "", public: bool = False) -> Dict:
        """
        Create a new playlist for the user.

        Spotify's `public` flag controls whether the playlist is listed on the
        user's profile. A playlist created with public=False is still reachable
        by anyone holding its link, which is why the UI says "on your profile"
        rather than promising secrecy.
        """
        data = {
            "name": self._clamp(name, self.MAX_PLAYLIST_NAME) or "Aelyra Playlist",
            "description": self._clamp(description, self.MAX_PLAYLIST_DESCRIPTION),
            "public": public,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/me/playlists",
                headers=self.headers,
                json=data,
                timeout=15.0
            )
            self._raise_for_status(response, "create playlist")
            return response.json()

    async def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict:
        """
        Add tracks to a playlist, 100 at a time (Spotify's per-request limit)
        """
        result = {}
        async with httpx.AsyncClient() as client:
            for start in range(0, len(track_ids), 100):
                uris = [f"spotify:track:{tid}" for tid in track_ids[start:start + 100]]
                response = await client.post(
                    f"{self.base_url}/playlists/{playlist_id}/tracks",
                    headers=self.headers,
                    json={"uris": uris},
                    timeout=15.0
                )
                self._raise_for_status(response, "add tracks to the playlist")
                result = response.json()
        return result

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
                    self._raise_for_status(response, "read track details")

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

        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            logger.error(f"Transport error reading track details: {e}")
            raise
