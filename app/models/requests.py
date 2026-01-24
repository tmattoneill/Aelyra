
from pydantic import BaseModel, Field
from typing import Optional

class GeneratePlaylistRequest(BaseModel):
    query: str
    spotify_access_token: str
    track_count: int = Field(default=10, ge=5, le=100, description="Number of tracks to generate (5-100)")

class SearchTracksRequest(BaseModel):
    tracks: list[str]
    spotify_access_token: str

class CreatePlaylistRequest(BaseModel):
    name: str
    track_ids: list[str]
    spotify_access_token: str
    description: Optional[str] = None

class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    location: Optional[str] = None
    spotify_access_token: str

class UploadPlaylistRequest(BaseModel):
    m3u_content: str
    spotify_access_token: str
    custom_name: Optional[str] = None
