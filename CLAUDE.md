# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PlayMaker is an AI-powered Spotify playlist generator with a FastAPI Python backend and React frontend. Users provide natural language queries, and the system generates playlists using OpenAI suggestions and Spotify's API.

## Development Commands

### SSL Certificate Setup (First Time Only)
```bash
# Generate SSL certificates for local HTTPS development
mkdir -p certs
cd certs
mkcert localhost 127.0.0.1 ::1

# Install CA in system trust store (REQUIRED for browser trust)
# Option 1: Automatic (requires sudo password)
mkcert -install

# Option 2: Manual installation if automatic fails
# Run the helper script and follow instructions:
./install-ca.sh

# Option 3: Manual via Keychain Access
# 1. Open Keychain Access app
# 2. Drag the rootCA.pem file (found via `mkcert -CAROOT`) into System keychain
# 3. Double-click the certificate and set to "Always Trust"
```

**Important**: The CA certificate MUST be installed and trusted for HTTPS to work without browser warnings. This is required for Spotify OAuth authentication.

### Backend (Python)
```bash
# Run development server with HTTPS
python main.py

# Alternative using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 5988 --reload --ssl-keyfile=./certs/localhost+2-key.pem --ssl-certfile=./certs/localhost+2.pem
```

### Frontend (React)
```bash
cd frontend
npm start      # Development server with HTTPS (port 3000)
npm run build  # Production build
npm test       # Run tests
```

## Architecture

### Backend Structure
- **Entry Point**: `main.py` - FastAPI app with CORS middleware
- **Routers**: 
  - `app/routers/playlist.py` - Core playlist generation endpoints
  - `app/routers/auth.py` - Spotify OAuth flow
- **Services**:
  - `app/services/openai_service.py` - AI track suggestion generation using GPT-3.5-turbo
  - `app/services/spotify_service.py` - Spotify Web API integration
- **Models**: `app/models/` - Pydantic request/response models

### Frontend Structure
- **Main Flow**: Two-step wizard (Spotify Auth → Playlist Generation)
- **Components**:
  - `SpotifyAuth.js` - OAuth handling with callback detection
  - `PlaylistGenerator.js` - Multi-step playlist creation with track alternatives

### Key API Endpoints
- `POST /api/generate-playlist` - Generate playlist from natural language
- `GET /api/spotify` - Initiate Spotify OAuth
- `GET /api/spotify/callback` - Handle OAuth callback
- `POST /api/create-playlist` - Create playlist in user's Spotify account

## Important Implementation Details

### Authentication Flow
1. Frontend initiates OAuth via `/api/spotify`
2. Backend generates secure state parameter (stored in-memory)
3. User authorizes on Spotify
4. Callback validates state and exchanges code for access token
5. Access token used for subsequent Spotify API calls

### Track Alternative System
The app provides 4 alternative tracks for each AI suggestion. Users can swap tracks using a sophisticated selection system implemented with JavaScript Sets for performance.

### Environment Variables Required
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret  
SPOTIFY_REDIRECT_URI=https://localhost:5988/api/spotify/callback
OPENAI_API_KEY=your_openai_api_key
```

### Development Setup
- **HTTPS Required**: Both servers run with HTTPS for Spotify OAuth authentication
- Backend runs on port 5988 with hot reload and SSL (`https://localhost:5988`)
- Frontend runs on port 3000 with HTTPS and proxy to backend (`"proxy": "https://localhost:5988"`)
- SSL certificates generated with mkcert and stored in `./certs/` directory
- Uses uv for Python package management (see `uv.lock`)

## Key Dependencies

### Backend
- FastAPI 0.104.1+ with Uvicorn
- OpenAI 1.3.0+ for AI suggestions
- Pydantic 2.5.0+ for data validation
- Requests for HTTP calls

### Frontend  
- React 18.2.0 with Create React App
- Axios for API communication

## Production Considerations

- CORS is currently set to allow all origins (`allow_origins=["*"]`) - needs hardening
- OAuth state is stored in-memory - should use Redis or database for production
- No rate limiting implemented on API endpoints