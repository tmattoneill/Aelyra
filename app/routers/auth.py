
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import os
import urllib.parse
import httpx
import secrets
import base64

from app.models.responses import AuthResponse, CallbackResponse
from app.database import get_db
from app.services.user_service import UserService

router = APIRouter()

# In-memory storage for state (use Redis in production)
oauth_states = {}

async def get_spotify_user_profile(access_token: str) -> dict:
    """Fetch user profile from Spotify API"""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.spotify.com/v1/me", headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.json()

@router.get("", response_model=AuthResponse)
async def spotofy_auth_no_slash():
    """
    Initiate Spotify OAuth flow No Slash
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
    oauth_states[state] = True
    
    # Spotify OAuth scopes needed for playlist creation
    scopes = [
        "playlist-modify-public",
        "playlist-modify-private", 
        "user-read-private"
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
    
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    del oauth_states[state]  # Clean up
    
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
        
        # Fetch user profile from Spotify
        try:
            profile = await get_spotify_user_profile(token_info['access_token'])
            
            # Create or update user record
            user_service = UserService(db)
            user = user_service.get_or_create_user(
                email=profile.get('email', ''),
                spotify_username=profile.get('id', ''),
                first_name=profile.get('display_name', '').split(' ')[0] if profile.get('display_name') else None,
                location=profile.get('country')
            )
            
        except Exception as e:
            # Log the error but don't fail the auth flow
            print(f"Error creating/updating user profile: {str(e)}")
        
        # Redirect back to frontend with token
        frontend_base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        frontend_url = f"{frontend_base_url}/?access_token={token_info['access_token']}&expires_in={token_info['expires_in']}"
        if token_info.get("refresh_token"):
            frontend_url += f"&refresh_token={token_info['refresh_token']}"
        
        return RedirectResponse(url=frontend_url)
        
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange code for token: {str(e)}")
