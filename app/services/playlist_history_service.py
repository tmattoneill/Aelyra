from sqlalchemy.orm import Session
from app.models.playlist_history import PlaylistHistory, PlaylistTrack
from app.models.user import User
from typing import List, Optional
import hashlib
from datetime import datetime

class PlaylistHistoryService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_playlist_history(self, user_id: int, playlist_name: str, user_description: str,
                              spotify_playlist_id: str, spotify_playlist_url: str,
                              track_data: List[dict]) -> PlaylistHistory:
        """
        Create a playlist history record with associated tracks
        
        Args:
            user_id: ID of the user who created the playlist
            playlist_name: System-generated playlist name
            user_description: Original user query/description
            spotify_playlist_id: Spotify's playlist ID
            spotify_playlist_url: URL to the playlist on Spotify
            track_data: List of track dictionaries with track info
        """
        # Generate MD5 hash from playlist name + current datetime
        hash_input = f"{playlist_name}{datetime.utcnow().isoformat()}"
        playlist_hash = hashlib.md5(hash_input.encode()).hexdigest()
        
        # Create playlist history record
        playlist_history = PlaylistHistory(
            playlist_hash=playlist_hash,
            user_id=user_id,
            playlist_name=playlist_name,
            user_description=user_description,
            spotify_playlist_id=spotify_playlist_id,
            spotify_playlist_url=spotify_playlist_url,
            track_count=len(track_data)
        )
        
        self.db.add(playlist_history)
        self.db.flush()  # Get the ID without committing
        
        # Create track records
        for position, track in enumerate(track_data, 1):
            playlist_track = PlaylistTrack(
                playlist_history_id=playlist_history.id,
                spotify_track_id=track.get('spotify_id', ''),
                track_name=track.get('name', ''),
                artist_name=track.get('artist', ''),
                album_name=track.get('album', ''),
                position=position
            )
            self.db.add(playlist_track)
        
        self.db.commit()
        self.db.refresh(playlist_history)
        return playlist_history
    
    def get_user_playlists(self, user_id: int, limit: int = 50, offset: int = 0) -> List[PlaylistHistory]:
        """Get playlist history for a specific user"""
        return (self.db.query(PlaylistHistory)
                .filter(PlaylistHistory.user_id == user_id)
                .order_by(PlaylistHistory.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all())
    
    def get_playlist_details(self, playlist_hash: str) -> Optional[PlaylistHistory]:
        """Get detailed playlist information including tracks"""
        return (self.db.query(PlaylistHistory)
                .filter(PlaylistHistory.playlist_hash == playlist_hash)
                .first())
    
    def get_playlist_tracks(self, playlist_history_id: int) -> List[PlaylistTrack]:
        """Get all tracks for a specific playlist"""
        return (self.db.query(PlaylistTrack)
                .filter(PlaylistTrack.playlist_history_id == playlist_history_id)
                .order_by(PlaylistTrack.position)
                .all())