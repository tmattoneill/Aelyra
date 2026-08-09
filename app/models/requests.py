from typing import Optional

from pydantic import BaseModel, Field

# The Spotify access token is no longer part of any request body. It travels in
# the Authorization header and is read by the spotify_token dependency, so it
# stays out of server logs, browser history and proxy caches.


class GeneratePlaylistRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    track_count: int = Field(default=10, ge=5, le=100, description="Number of tracks to generate (5-100)")


class CreatePlaylistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    track_ids: list[str] = Field(max_length=500)
    # Omit to have one written from the playlist's contents.
    description: Optional[str] = Field(default=None, max_length=300)
    # The app used to decide visibility silently; now the user chooses.
    public: bool = False
    # Echoed back into the description generator so it can describe the brief.
    query: Optional[str] = Field(default=None, max_length=2000)


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=100)
    # Distinguishes "leave the stored key alone" (None) from "delete it" (True).
    remove_openai_api_key: bool = False
    openai_api_key: Optional[str] = Field(default=None, max_length=200)


class UploadPlaylistRequest(BaseModel):
    public: bool = False
    # Bounded here so an oversized body is rejected before it is deserialised;
    # M3UParser applies the same limit for non-HTTP callers.
    m3u_content: str = Field(max_length=100_000)
    custom_name: Optional[str] = Field(default=None, max_length=200)


class SessionExchangeRequest(BaseModel):
    """Exchange a one-time auth code from the OAuth redirect for tokens."""
    code: str = Field(min_length=1, max_length=200)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=500)
