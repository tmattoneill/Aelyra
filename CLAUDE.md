# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Aelyra is an AI-powered Spotify playlist generator with a FastAPI Python backend and React frontend. Users provide natural language queries, and the system generates playlists using OpenAI suggestions and Spotify's API.

## Development Commands

### Quick Start (Recommended)
```bash
# Use the automated launcher script
./utils/launch-dev.sh

# This starts both backend and frontend automatically
# Backend: http://127.0.0.1:5988
# Frontend: http://localhost:3000
```

### Backend (Python)
```bash
# Create virtual environment (first time only)
python3.12 -m venv venv  # Use Python 3.12, NOT 3.13 (pydantic compatibility)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Alternative using uv (faster, recommended)
uv pip install -r requirements.txt

# Run development server (HTTP on 127.0.0.1 for Spotify OAuth compatibility)
python main.py

# Alternative using uvicorn directly
uvicorn main:app --host 127.0.0.1 --port 5988 --reload
```

### Frontend (React + Vite)
```bash
cd frontend
npm install    # Install dependencies
npm run dev    # Development server (port 3000) - uses Vite
npm start      # Also runs development server
npm run build  # Production build
npm test       # Run tests (Jest)
```

### Environment Setup
```bash
# Copy environment template and configure
cp .env.example .env
# Edit .env with your Spotify and OpenAI API credentials
```

## Architecture

### Backend Structure
- **Entry Point**: `main.py` - FastAPI app with CORS middleware
- **Routers**: 
  - `app/routers/playlist.py` - Core playlist generation endpoints
  - `app/routers/auth.py` - Spotify OAuth flow
- **Services**:
  - `app/services/openai_service.py` - AI track suggestions via structured outputs
  - `app/services/spotify_service.py` - Spotify Web API integration
  - `app/services/user_service.py` - User profile management and database operations
  - `app/services/playlist_history_service.py` - Playlist history tracking and retrieval
  - `app/services/m3u_parser.py` - M3U playlist file parser for upload feature
- **Models**: `app/models/` - Pydantic request/response models and SQLAlchemy database models

### Frontend Structure
- **Build System**: Vite (migrated from Create React App)
- **Entry Point**: `main.jsx` - React app entry point
- **Main Flow**: Connect Spotify, then a tabbed app (Generate / Upload / Account / History)
- **Components** (all `.jsx`; the Vite esbuild loader override is gone):
  - `auth/authStore.js` - the single session record in sessionStorage
  - `config.js` - axios instance with Bearer auth and single-flight token refresh
  - `lib/sse.js` - server-sent event parsing with cross-chunk buffering
  - `hooks/useStreamingGeneration.js` - owns the generation stream lifecycle
  - `components/generator/*` - form, progress rail, review list
  - `SpotifyAuth.jsx` - redeems the one-time auth code
  - `PlaylistUpload.jsx`, `PlaylistHistory.jsx`, `UserProfile.jsx`

### Key API Endpoints
- `POST /api/generate-playlist` - Generate playlist from natural language
- `POST /api/generate-playlist-stream` - Streaming endpoint with real-time progress
- `POST /api/upload-playlist` - Upload playlist from M3U file
- `POST /api/create-playlist` - Create playlist in user's Spotify account
- `GET /api/spotify` - Initiate Spotify OAuth
- `GET /api/spotify/callback` - Handle OAuth callback, redirect with a one-time code
- `POST /api/spotify/session` - Redeem that code for tokens
- `POST /api/spotify/refresh` - Renew an expired access token
- `GET /api/user-info` - Get user profile and validate token
- `PUT /api/user-profile` - Update user profile information
- `GET /api/user-playlists` - Get user's playlist history

## Important Implementation Details

### Spotify OAuth Requirements
- **HTTP Loopback Only**: Spotify requires `http://127.0.0.1` (not `localhost`) for local development
- **Redirect URI**: Must be exactly `http://127.0.0.1:5988/api/spotify/callback` in Spotify app settings
- Backend exchanges the authorization code for tokens, then redirects with a one-time code

### Authentication Flow
1. Frontend calls `/api/spotify` and gets the Spotify authorization URL
2. User authorizes on Spotify and is redirected to the backend callback
3. Backend exchanges the code for tokens and stashes them under a single-use,
   60-second code, then redirects to `FRONTEND_URL/?auth_code=...`
4. Frontend POSTs that code to `/api/spotify/session` and stores the tokens

Tokens are never placed in a URL, and every authenticated request sends them as
`Authorization: Bearer <token>`, never as a query parameter or body field.

Both the OAuth state store and the pending auth codes live in process memory,
so the app must run with a single uvicorn worker.

### AI Response Processing
- OpenAI service automatically strips markdown formatting from AI responses
- Handles both raw JSON and markdown-wrapped JSON (```json blocks)
- Enhanced error handling shows expandable raw AI response when parsing fails

### Generation Quality
All OpenAI calls use strict `json_schema` structured outputs, so responses cannot
come back as prose or markdown-fenced JSON and need no string repair.

Model parameters come from `MODEL_CAPABILITIES` in `openai_service.py`, built by
testing the live API. Two rules are not guessable: gpt-5-mini rejects any explicit
temperature, and gpt-5.2 accepts temperature only when reasoning is off. Track
generation takes reasoning over temperature, since suggesting tracks that exist
matters more than sampling variety. Models are overridable with `AELYRA_MODEL_FAST`
and `AELYRA_MODEL_KNOWLEDGE`.

When Spotify cannot find enough of the suggestions, the router makes one focused
retry telling the model which ones were unavailable, then reports the shortfall
(`found_count` against `requested_count`, and a `partial` stream event). It does
not pad the playlist with unrelated popular tracks.

### M3U Playlist Upload
Users can upload existing playlists from M3U files containing Spotify track URLs:
- Supports both standard M3U and extended M3U (EXTM3U) formats
- Extracts Spotify track IDs from URLs (`open.spotify.com/track/...`) and URIs (`spotify:track:...`)
- Validates tracks exist on Spotify and skips unavailable ones
- Generates AI-powered playlist names based on track metadata (or accepts custom names)
- Maximum 500 tracks per file, 100KB file size limit
- Provides detailed warnings for duplicates, non-Spotify URLs, and missing tracks

### Testing
```bash
pytest -q                      # backend
cd frontend && npm test        # frontend
ruff check .                   # lint
```

### Environment Variables Required
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret  
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5988/api/spotify/callback
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=sqlite:///./aelyra.db  # Optional, defaults to SQLite
DEBUG=True                     # defaults to False when unset
# Optional model overrides
# AELYRA_MODEL_FAST=gpt-5-mini
# AELYRA_MODEL_KNOWLEDGE=gpt-5.2
```

Deployment target details (server host, ssh port, restart command) live in
`.deploy.env`, which is gitignored. Copy `.deploy.env.example` to create it.

### Development Setup
- **HTTP Development**: Uses HTTP with loopback IP (127.0.0.1) for Spotify OAuth compatibility
- Backend runs on `http://127.0.0.1:5988` with hot reload
- Frontend runs on `http://localhost:3000` with Vite dev server and proxy to backend
- **Package Management**: uv recommended for faster Python dependency installation
- **Development Launcher**: Use `./utils/launch-dev.sh` script to start both backend and frontend
- SSL certificates available in `certs/` directory for production setup

## Multi-User Support

### Database Architecture
- **SQLite Database**: `aelyra.db` for user profile and playlist history storage
- **User Model**: Stores email, Spotify username, name, location, account creation date, and personal OpenAI API key
- **Playlist History Model**: Tracks all playlists created by users with metadata
- **Playlist Tracks Model**: Stores individual track details for each playlist
- **Automatic Profile Creation**: User profiles are automatically created/updated during Spotify OAuth flow

### User Features
- **Personal OpenAI Keys**: Users can store their own OpenAI API keys for playlist generation
- **Profile Persistence**: User data persists across sessions and includes Spotify profile information
- **Playlist History**: Complete history of all playlists created by each user
- **Track Storage**: Detailed track information including Spotify IDs, names, artists, and albums
- **Privacy**: Secure storage of personal API keys (encryption recommended for production)

### Playlist History Features
- **Automatic Tracking**: Playlists are automatically saved when "Create Playlist" is clicked
- **Unique Identification**: Each playlist gets an MD5 hash based on name + creation timestamp
- **Complete Track Lists**: All selected tracks are stored with full metadata
- **Spotify Integration**: Direct links to created playlists on Spotify
- **User Association**: Each playlist is linked to the authenticated user

### Database Management
```bash
# Run database migrations
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "Description of changes"
```

## Key Dependencies

### Backend
- FastAPI 0.104.1+ with Uvicorn
- OpenAI 1.90.0+ for AI suggestions  
- Pydantic 2.5.0+ for data validation
- SQLAlchemy 2.0.41+ for database ORM
- Alembic for database migrations
- Requests for HTTP calls

### Frontend  
- React 18.2.0 with Vite 6.0.3+ (build system)
- Jest 30.0.3+ for testing
- Testing Library suite for React testing
- Axios for API communication

## Key Implementation Notes

### Error Handling
- AI parsing errors include expandable "Show AI Response" button to view raw OpenAI output
- Frontend handles both standard errors and special AI parsing error format
- Backend includes raw AI response in error message when JSON parsing fails

### Session Management
- One `aelyra_auth` record in sessionStorage holds the token, its absolute expiry
  and the user profile, so they cannot drift apart
- Axios interceptors attach the Bearer token and refresh it ahead of expiry,
  sharing a single in-flight refresh across concurrent requests
- OAuth state and pending auth codes are in-memory on the backend, which is why
  it runs a single worker; Redis would be needed to scale out
- User profiles and playlist history are persisted in SQLite

### Common Development Issues
- **"INVALID_CLIENT: Insecure redirect URI"**: Ensure Spotify redirect URI uses `http://127.0.0.1:5988/api/spotify/callback` (not localhost)
- **"Failed to parse AI response"**: Click "Show AI Response" to see raw OpenAI output; usually caused by non-JSON AI responses
- **Frontend connection errors**: Verify backend is running on `127.0.0.1:5988` and frontend proxy is configured correctly

## Production Deployment

### Production Scripts
Production scripts are in the `utils/` directory:

```bash
# Build and prepare for production
./utils/deploy-prod.sh

# Launch production server with HTTPS
./utils/launch-prod.sh
```

**Requirements:**
- `.env.prod` file with production configuration
- SSL certificates in `certs/` directory (`localhost+2.pem`, `localhost+2-key.pem`)
- Database migrations applied (`alembic upgrade head`)

### Production Considerations
- CORS is restricted to `CORS_ORIGINS`; `DEBUG` defaults to false and a `*`
  origin is dropped rather than combined with credentials
- No rate limiting on API endpoints yet: generation costs OpenAI spend per call
- nginx terminates TLS in front; `certs/` holds an mkcert certificate valid only
  for localhost, so it cannot serve the public hostname
- In-memory OAuth state and auth codes require a single worker
- SQLite is single-writer; concurrent writes will contend