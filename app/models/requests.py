
from pydantic import BaseModel
from typing import Optional

class GeneratePlaylistRequest(BaseModel):
    query: str
    openai_api_key: Optional[str] = None
    spotify_access_token: str

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
    openai_api_key: Optional[str] = None
    spotify_access_token: str
