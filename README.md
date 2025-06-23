# 🎵 PlayMaker

An AI-powered Spotify playlist generator that creates curated playlists from natural language descriptions. Simply describe the mood, genre, or vibe you want, and PlayMaker will generate a custom playlist using OpenAI's GPT and Spotify's music catalog.

## Features

- **Natural Language Input**: Describe your playlist in plain English (e.g., "upbeat songs for morning workout", "chill indie rock for studying")
- **AI-Powered Suggestions**: Uses OpenAI GPT-3.5-turbo to generate relevant track suggestions
- **Spotify Integration**: Full OAuth authentication and playlist creation in your Spotify account
- **Track Alternatives**: Provides multiple options for each suggested track with one-click swapping
- **Real-time Preview**: See album artwork and preview tracks before creating the playlist
- **Flexible API Keys**: Use your own OpenAI API key or rely on system defaults

## Architecture

**Backend**: FastAPI (Python) with OpenAI and Spotify Web API integration  
**Frontend**: React with Create React App  
**Authentication**: Spotify OAuth 2.0 flow  
**Development**: HTTP on loopback addresses for Spotify OAuth compatibility

## Prerequisites

- **Python 3.11+** with pip
- **Node.js 16+** with npm
- **Spotify Developer Account** ([Create one here](https://developer.spotify.com/dashboard))
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys)) - Optional, can be user-provided

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd PlayMaker
```

### 2. Backend Setup
```bash
# Install Python dependencies
pip install fastapi "uvicorn[standard]" pydantic requests python-dotenv openai

# Create environment configuration
cp .env.example .env
```

### 3. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 4. Spotify App Configuration

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click "Create App"
3. Fill in app details:
   - **App name**: PlayMaker
   - **App description**: AI-powered playlist generator
   - **Website**: `http://localhost:3000`
   - **Redirect URIs**: `http://127.0.0.1:5988/api/spotify/callback`
4. Save your **Client ID** and **Client Secret**

### 5. Environment Configuration

Edit `.env` file with your credentials:

```bash
# Spotify API Configuration
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5988/api/spotify/callback

# OpenAI API Configuration (Optional - users can provide their own)
OPENAI_API_KEY=your_openai_api_key

# Development
DEBUG=True
```

## Running the Application

### Start Backend Server
```bash
python main.py
```
The backend will be available at `http://127.0.0.1:5988`

### Start Frontend Server
```bash
cd frontend
npm start
```
The frontend will be available at `http://localhost:3000`

### Access the Application
Open your browser and navigate to `http://localhost:3000`

## Usage

1. **Connect Spotify**: Click "Connect Spotify Account" and authorize the application
2. **Describe Your Playlist**: Enter a natural language description of the playlist you want
3. **Optional OpenAI Key**: Provide your own OpenAI API key for potentially better results
4. **Generate Playlist**: Click "Generate Playlist" to get AI-powered track suggestions
5. **Customize Selection**: Review suggestions, swap alternatives, and select your favorite tracks
6. **Create in Spotify**: Click "Create Playlist in Spotify" to save it to your account

## API Endpoints

### Authentication
- `GET /api/spotify` - Initiate Spotify OAuth flow
- `GET /api/spotify/callback` - Handle OAuth callback

### Playlist Operations
- `POST /api/generate-playlist` - Generate playlist from natural language query
- `POST /api/create-playlist` - Create playlist in user's Spotify account
- `GET /api/search-tracks` - Search Spotify tracks

### Utility
- `GET /health` - Health check endpoint

## Project Structure

```
PlayMaker/
├── app/
│   ├── models/          # Pydantic request/response models
│   ├── routers/         # FastAPI route handlers
│   │   ├── auth.py      # Spotify OAuth endpoints
│   │   └── playlist.py  # Playlist generation endpoints
│   └── services/        # Business logic
│       ├── openai_service.py    # OpenAI API integration
│       └── spotify_service.py   # Spotify API integration
├── frontend/
│   ├── src/
│   │   ├── components/  # React components
│   │   │   ├── SpotifyAuth.js      # OAuth handling
│   │   │   └── PlaylistGenerator.js # Main playlist interface
│   │   ├── App.js       # Main React app
│   │   └── index.css    # Styling
│   └── package.json     # Frontend dependencies
├── main.py              # FastAPI application entry point
├── .env                 # Environment configuration
└── README.md           # This file
```

## Known Limitations

### Technical Limitations
- **Session-based Authentication**: Spotify tokens are stored in browser memory only and are lost on page refresh
- **No Persistent Storage**: No database; all data is ephemeral
- **HTTP Development Only**: Uses HTTP with loopback addresses for Spotify OAuth compatibility
- **In-memory OAuth State**: OAuth state stored in memory (should use Redis for production)
- **No Rate Limiting**: API endpoints have no rate limiting implemented

### Spotify API Limitations
- **OAuth Redirect Constraints**: Must use `http://127.0.0.1` (not `localhost`) for local development
- **Playlist Permissions**: Requires explicit user authorization for playlist modification
- **Track Availability**: Song availability varies by region and Spotify catalog changes

### OpenAI Integration Limitations
- **JSON Parsing Sensitivity**: AI responses must be valid JSON; parsing failures show expandable raw response
- **Model Limitations**: Relies on GPT-3.5-turbo knowledge cutoff and music familiarity
- **Token Costs**: Each playlist generation consumes OpenAI API tokens

### User Experience Limitations
- **No Playlist Editing**: Cannot modify playlists after creation (must recreate)
- **Limited Track Metadata**: Shows basic track info (title, artist, album art) without detailed metadata
- **No Offline Mode**: Requires active internet connection for all operations

## Production Considerations

For production deployment, consider:

- **HTTPS Configuration**: Implement proper SSL certificates for production domains
- **Database Integration**: Add persistent storage for user sessions and playlist history
- **Redis for OAuth State**: Replace in-memory OAuth state storage
- **Rate Limiting**: Implement API rate limiting and quota management
- **Error Handling**: Enhanced error reporting and monitoring
- **Security Hardening**: Proper CORS configuration, input validation, and secret management
- **Caching**: Cache Spotify search results and AI responses for better performance

## Troubleshooting

### Common Issues

**"INVALID_CLIENT: Insecure redirect URI"**
- Ensure Spotify redirect URI is exactly: `http://127.0.0.1:5988/api/spotify/callback`
- Use `127.0.0.1` not `localhost` for the redirect URI

**"Failed to initiate Spotify authentication"**
- Check that backend is running on port 5988
- Verify SPOTIFY_CLIENT_ID is set correctly in `.env`

**"Failed to parse AI response"**
- Click "Show AI Response" to see the raw OpenAI output
- Try rephrasing your playlist description
- Check OPENAI_API_KEY is valid

**Frontend won't connect to backend**
- Verify backend is running on `http://127.0.0.1:5988`
- Check frontend proxy configuration in `package.json`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on the GitHub repository.