"""Shared FastAPI dependencies."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# auto_error=False so a missing header produces our own 401 with a useful
# message rather than FastAPI's bare 403.
_bearer = HTTPBearer(auto_error=False, description="Spotify access token")


def spotify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Extract the Spotify access token from the Authorization header.

    Endpoints previously accepted this token in a query string or JSON body,
    which wrote live credentials into access logs. The header keeps it out of
    anything that records URLs.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Spotify access token. Send it as 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
