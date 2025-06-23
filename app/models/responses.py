
from pydantic import BaseModel
from typing import List, Optional

class Track(BaseModel):
    title: str
    artist: str
    spotify_id: str
    album_art: Optional[str] = None
    preview_url: Optional[str] = None
    alternatives: Optional[List['Track']] = None

class GeneratePlaylistResponse(BaseModel):
    playlist_id: Optional[str] = None
    playlist_name: str
    tracks: List[Track]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

class AuthResponse(BaseModel):
    auth_url: str

class CallbackResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
