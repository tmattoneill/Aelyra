
import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SpotifyService:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.spotify.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    async def search_track(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for tracks on Spotify
        """
        try:
            params = {
                "q": query,
                "type": "track",
                "limit": limit
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            tracks = []
            
            for track in data["tracks"]["items"]:
                track_data = {
                    "title": track["name"],
                    "artist": ", ".join([artist["name"] for artist in track["artists"]]),
                    "spotify_id": track["id"],
                    "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                    "preview_url": track.get("preview_url")
                }
                tracks.append(track_data)
            
            return tracks
            
        except requests.RequestException as e:
            logger.error(f"Spotify search error: {str(e)}")
            raise Exception(f"Failed to search Spotify: {str(e)}")
    
    async def get_user_profile(self) -> Dict:
        """
        Get current user's profile
        """
        try:
            response = requests.get(
                f"{self.base_url}/me",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
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
            
            response = requests.post(
                f"{self.base_url}/me/playlists",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
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
            
            response = requests.post(
                f"{self.base_url}/playlists/{playlist_id}/tracks",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to add tracks to playlist: {str(e)}")
            raise Exception(f"Failed to add tracks to playlist: {str(e)}")
    
    async def get_tracks_details(self, track_ids: List[str]) -> List[Dict]:
        """
        Get detailed information for multiple tracks by their IDs
        """
        try:
            # Spotify API allows up to 50 tracks per request
            track_data = []
            
            for i in range(0, len(track_ids), 50):
                batch_ids = track_ids[i:i+50]
                params = {"ids": ",".join(batch_ids)}
                
                response = requests.get(
                    f"{self.base_url}/tracks",
                    headers=self.headers,
                    params=params
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
            
        except requests.RequestException as e:
            logger.error(f"Failed to get track details: {str(e)}")
            raise Exception(f"Failed to get track details: {str(e)}")
