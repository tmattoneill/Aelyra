
import base64
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.requests import RefreshTokenRequest, SessionExchangeRequest
from app.models.responses import AuthResponse, RefreshResponse, SessionResponse
from app.services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)

# Both stores below live in process memory, so the app must run with a single
# uvicorn worker (see utils/launch-prod.sh). Moving to more than one worker
# means moving these to Redis.

# In-memory storage for state with TTL
# Structure: {state: {"created": datetime, "valid": bool}}
oauth_states = {}
STATE_TTL = timedelta(minutes=5)
MAX_STATES = 1000  # Maximum states to store before forced cleanup

# Tokens waiting to be collected by the frontend, keyed by one-time code.
# Structure: {code: {"created": datetime, "token_info": dict, "profile": dict}}
pending_auths = {}
AUTH_CODE_TTL = timedelta(seconds=60)
MAX_PENDING_AUTHS = 1000


def _store_pending_auth(token_info: dict, profile: dict) -> str:
    """Stash tokens under a single-use code and return the code."""
    cleanup_expired_auth_codes()

    if len(pending_auths) > MAX_PENDING_AUTHS:
        oldest = sorted(pending_auths.items(), key=lambda kv: kv[1]["created"])
        for key, _ in oldest[:len(oldest) // 2]:
            pending_auths.pop(key, None)
        logger.warning("Force cleaned pending auth codes (exceeded max)")

    code_value = secrets.token_urlsafe(32)
    pending_auths[code_value] = {
        "created": datetime.now(timezone.utc),
        "token_info": token_info,
        "profile": profile,
    }
    return code_value


def cleanup_expired_auth_codes():
    """Drop auth codes nobody redeemed inside the TTL."""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in pending_auths.items() if now - v["created"] > AUTH_CODE_TTL]
    for k in expired:
        del pending_auths[k]
    if expired:
        logger.debug(f"Cleaned up {len(expired)} expired auth codes")


def _remaining_seconds(pending: dict) -> int:
    """Seconds of life left on the access token, not the original lifetime.

    The token started ageing at the callback, so returning the raw expires_in
    would tell the client it has more time than it does.
    """
    original = int(pending["token_info"].get("expires_in", 3600))
    elapsed = (datetime.now(timezone.utc) - pending["created"]).total_seconds()
    return max(0, int(original - elapsed))


def cleanup_expired_states():
    """Remove expired OAuth states to prevent memory leaks"""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in oauth_states.items()
               if now - v.get("created", now) > STATE_TTL]
    for k in expired:
        del oauth_states[k]
    if expired:
        logger.debug(f"Cleaned up {len(expired)} expired OAuth states")

    # Force cleanup if too many states (potential attack or leak)
    if len(oauth_states) > MAX_STATES:
        # Remove oldest half of states
        sorted_states = sorted(oauth_states.items(),
                               key=lambda x: x[1].get("created", datetime.min.replace(tzinfo=timezone.utc)))
        to_remove = sorted_states[:len(sorted_states) // 2]
        for k, _ in to_remove:
            del oauth_states[k]
        logger.warning(f"Force cleaned {len(to_remove)} OAuth states (exceeded max)")

def _split_display_name(display_name: str | None) -> dict:
    """Split a Spotify display name into first and last name.

    Spotify gives a single free-text field, so this is a best guess: everything
    after the first space becomes the last name. Users can correct it in their
    profile, and those edits are preserved on later logins.
    """
    if not display_name or not display_name.strip():
        return {"first_name": None, "last_name": None}
    parts = display_name.strip().split(None, 1)
    return {
        "first_name": parts[0],
        "last_name": parts[1] if len(parts) > 1 else None,
    }


async def get_spotify_user_profile(access_token: str) -> dict:
    """Fetch user profile from Spotify API"""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.spotify.com/v1/me", headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.json()

@router.get("", response_model=AuthResponse)
async def spotify_auth_no_slash():
    """
    Initiate Spotify OAuth flow (no trailing slash)
    """
    return await spotify_auth()

@router.get("/", response_model=AuthResponse)
async def spotify_auth():
    """
    Initiate Spotify OAuth flow
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

    if not client_id:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")

    if not redirect_uri:
        raise HTTPException(status_code=500, detail="Spotify redirect URI not configured")

    # Generate random state for security
    state = secrets.token_urlsafe(32)

    # Clean up expired states before adding new one
    cleanup_expired_states()

    # Store state with creation time for TTL tracking
    oauth_states[state] = {"created": datetime.now(timezone.utc), "valid": True}

    # Spotify OAuth scopes needed for playlist creation
    scopes = [
        "playlist-modify-public",
        "playlist-modify-private",
        "user-read-private",
        "user-read-email"
    ]

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "scope": " ".join(scopes),
        "redirect_uri": redirect_uri,
        "state": state
    })

    return AuthResponse(auth_url=auth_url)

@router.get("/callback")
async def spotify_callback(code: str = None, state: str = None, error: str = None, db: Session = Depends(get_db)):
    """
    Handle Spotify OAuth callback
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state")

    # Clean up expired states before verification
    cleanup_expired_states()

    # Verify state exists and is valid
    state_data = oauth_states.get(state)
    if not state_data or not state_data.get("valid"):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Check if state has expired
    if datetime.now(timezone.utc) - state_data.get("created", datetime.min.replace(tzinfo=timezone.utc)) > STATE_TTL:
        del oauth_states[state]
        raise HTTPException(status_code=400, detail="State parameter has expired")

    del oauth_states[state]  # Clean up used state

    # Exchange code for access token
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Spotify credentials not configured")

    if not redirect_uri:
        raise HTTPException(status_code=500, detail="Spotify redirect URI not configured")

    # Prepare authorization header
    auth_string = f"{client_id}:{client_secret}"
    auth_bytes = auth_string.encode("ascii")
    auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }

    token_headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.spotify.com/api/token",
                data=token_data,
                headers=token_headers,
                timeout=15.0
            )
            response.raise_for_status()
            token_info = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Spotify token exchange failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to exchange authorization code with Spotify")

    if "access_token" not in token_info:
        logger.error("Spotify token response missing access_token")
        raise HTTPException(status_code=502, detail="Spotify returned an unexpected token response")

    # Fetch the user profile so the account exists before the session starts.
    profile = {}
    try:
        profile = await get_spotify_user_profile(token_info["access_token"])

        user_service = UserService(db)
        user_service.get_or_create_user(
            spotify_username=profile.get("id") or "",
            email=profile.get("email"),
            **_split_display_name(profile.get("display_name")),
            location=profile.get("country"),
        )
    except Exception:
        # A profile-storage failure must not block the login itself, but the
        # session has to be rolled back or every later query on it fails.
        db.rollback()
        logger.exception("Failed to create or update user profile during OAuth callback")

    # Hand the frontend a single-use code instead of the tokens themselves.
    # Tokens in a redirect URL end up in browser history, the Referer header of
    # the next outbound request, and every proxy and server log along the way.
    code_value = _store_pending_auth(token_info, profile)

    frontend_base_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return RedirectResponse(url=f"{frontend_base_url}/?auth_code={urllib.parse.quote(code_value)}")


@router.post("/session", response_model=SessionResponse)
async def exchange_session(request: SessionExchangeRequest):
    """Redeem the one-time code from the OAuth redirect for the actual tokens."""
    cleanup_expired_auth_codes()

    pending = pending_auths.pop(request.code, None)
    if pending is None:
        # Covers unknown, already-used and expired codes alike; distinguishing
        # them would only help someone guessing.
        raise HTTPException(status_code=400, detail="Invalid or expired authorization code")

    if datetime.now(timezone.utc) - pending["created"] > AUTH_CODE_TTL:
        raise HTTPException(status_code=400, detail="Invalid or expired authorization code")

    token_info = pending["token_info"]
    expires_in = _remaining_seconds(pending)

    return SessionResponse(
        access_token=token_info["access_token"],
        refresh_token=token_info.get("refresh_token"),
        expires_in=expires_in,
        user=pending.get("profile") or None,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_access_token(request: RefreshTokenRequest):
    """Exchange a refresh token for a new access token."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Spotify credentials not configured")

    auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode("ascii")).decode("ascii")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "refresh_token", "refresh_token": request.refresh_token},
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=15.0,
            )
    except httpx.HTTPError as e:
        logger.error(f"Spotify refresh request failed: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Spotify to refresh the session")

    if response.status_code in (400, 401):
        # The refresh token has been revoked or rotated away; the client must
        # start a fresh OAuth flow.
        raise HTTPException(status_code=401, detail="Refresh token is no longer valid")
    if response.status_code >= 400:
        logger.error(f"Spotify refresh returned {response.status_code}")
        raise HTTPException(status_code=502, detail="Spotify rejected the refresh request")

    token_info = response.json()
    if "access_token" not in token_info:
        raise HTTPException(status_code=502, detail="Spotify returned an unexpected refresh response")

    return RefreshResponse(
        access_token=token_info["access_token"],
        # Spotify may or may not rotate the refresh token; pass it on if it did.
        refresh_token=token_info.get("refresh_token"),
        expires_in=int(token_info.get("expires_in", 3600)),
    )
