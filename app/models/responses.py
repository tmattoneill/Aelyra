from typing import List, Optional

from pydantic import BaseModel


class Track(BaseModel):
    title: str
    artist: str
    spotify_id: str
    album: Optional[str] = None
    album_art: Optional[str] = None
    preview_url: Optional[str] = None


class GeneratePlaylistResponse(BaseModel):
    playlist_id: Optional[str] = None
    playlist_name: str
    tracks: List[Track]
    # Let the client tell the difference between a full playlist and a short
    # one, instead of silently receiving fewer tracks than it asked for.
    requested_count: Optional[int] = None
    found_count: Optional[int] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class AuthResponse(BaseModel):
    auth_url: str


class SessionResponse(BaseModel):
    """Tokens handed back when the frontend redeems its one-time auth code."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int
    user: Optional[dict] = None


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int
