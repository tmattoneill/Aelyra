# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PlayMaker is an AI-powered Spotify playlist generator with a FastAPI Python backend and React frontend. Users provide natural language queries, and the system generates playlists using OpenAI suggestions and Spotify's API.

## Development Commands

### Backend (Python)
```bash
# Install dependencies
pip install -r requirements.txt

# Alternative using uv (faster)
uv pip install -r requirements.txt

# Run development server (HTTP on 127.0.0.1 for Spotify OAuth compatibility)
python main.py

# Alternative using uvicorn directly
uvicorn main:app --host 127.0.0.1 --port 5988 --reload
```

### Frontend (React)
```bash
cd frontend
npm install    # Install dependencies
npm start      # Development server (port 3000)
npm run build  # Production build
npm test       # Run tests
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

### Spotify OAuth Requirements
- **HTTP Loopback Only**: Spotify requires `http://127.0.0.1` (not `localhost`) for local development
- **Redirect URI**: Must be exactly `http://127.0.0.1:5988/api/spotify/callback` in Spotify app settings
- Backend exchanges authorization code for access token, then redirects to frontend with token

### Authentication Flow
1. Frontend calls `/api/spotify` → Gets Spotify authorization URL
2. User authorizes on Spotify → Redirected to backend callback
3. Backend exchanges code for access token → Redirects to frontend with token in URL params
4. Frontend extracts token from URL and stores in React state (session-based)

### AI Response Processing
- OpenAI service automatically strips markdown formatting from AI responses
- Handles both raw JSON and markdown-wrapped JSON (```json blocks)
- Enhanced error handling shows expandable raw AI response when parsing fails

### Track Alternative System
Each AI suggestion includes up to 4 alternative tracks from Spotify search results. Frontend uses JavaScript Sets for efficient track selection management.

### Environment Variables Required
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret  
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5988/api/spotify/callback
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=sqlite:///./playmaker.db  # Optional, defaults to SQLite
DEBUG=True
```

### Development Setup
- **HTTP Development**: Uses HTTP with loopback IP (127.0.0.1) for Spotify OAuth compatibility
- Backend runs on `http://127.0.0.1:5988` with hot reload
- Frontend runs on `http://localhost:3000` with proxy to backend
- No SSL certificates required for development
- Standard pip for Python package management

## Multi-User Support

### Database Architecture
- **SQLite Database**: `playmaker.db` for user profile and playlist history storage
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
- OpenAI 1.3.0+ for AI suggestions
- Pydantic 2.5.0+ for data validation
- SQLAlchemy 2.0+ for database ORM
- Alembic for database migrations
- Requests for HTTP calls

### Frontend  
- React 18.2.0 with Create React App
- Axios for API communication

## Key Implementation Notes

### Error Handling
- AI parsing errors include expandable "Show AI Response" button to view raw OpenAI output
- Frontend handles both standard errors and special AI parsing error format
- Backend includes raw AI response in error message when JSON parsing fails

### Session Management
- Spotify tokens stored in browser memory only (lost on page refresh)
- OAuth state stored in-memory on backend (use Redis for production)
- No persistent user sessions or data storage

### Common Development Issues
- **"INVALID_CLIENT: Insecure redirect URI"**: Ensure Spotify redirect URI uses `http://127.0.0.1:5988/api/spotify/callback` (not localhost)
- **"Failed to parse AI response"**: Click "Show AI Response" to see raw OpenAI output; usually caused by non-JSON AI responses
- **Frontend connection errors**: Verify backend is running on `127.0.0.1:5988` and frontend proxy is configured correctly

## Production Considerations

- CORS currently allows all origins - needs hardening for production
- No rate limiting on API endpoints
- HTTP-only development setup requires HTTPS implementation for production
- In-memory OAuth state storage needs Redis/database replacement
- No persistent storage for playlists or user data