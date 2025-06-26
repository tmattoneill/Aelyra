# 🎵 PlayMaker

An AI-powered Spotify playlist generator with multi-user support, persistent storage, and advanced user management. Users can create custom playlists from natural language descriptions, manage their account information, and access their complete playlist history.

## Features

### Core Functionality
- **Natural Language Playlist Generation**: Describe your ideal playlist in plain English
- **AI-Powered Track Suggestions**: Uses OpenAI GPT-3.5-turbo for intelligent music recommendations
- **Spotify Integration**: Full OAuth authentication and playlist creation in user accounts
- **Track Alternatives**: Multiple options for each suggested track with one-click swapping
- **Real-time Preview**: Album artwork and track previews before playlist creation

### User Management & Authentication
- **Multi-User Support**: Complete user account system with persistent profiles
- **Spotify OAuth Integration**: Secure authentication with Spotify accounts
- **User Profile Management**: Customizable first name, last name, location, and personal settings
- **Personal OpenAI API Keys**: Users can store their own OpenAI API keys for enhanced results
- **Persistent Sessions**: User data and preferences saved across sessions

### Playlist History & Management
- **Complete Playlist History**: Track all playlists created by each user
- **Detailed Track Storage**: Full metadata for every track in every playlist
- **Playlist Metadata**: Creation dates, descriptions, and unique identifiers
- **Spotify Links**: Direct links to created playlists on Spotify
- **User Association**: All playlists linked to authenticated users

### Database & Storage
- **SQLite Database**: Persistent storage for users, playlists, and tracks
- **Alembic Migrations**: Database schema versioning and upgrades
- **Automatic Profile Creation**: User profiles created seamlessly during first login
- **Data Integrity**: Relational database structure for reliable data management

## Architecture

**Backend**: FastAPI (Python) with SQLAlchemy ORM and Alembic migrations  
**Frontend**: React with Vite build system (migrated from Create React App)  
**Database**: SQLite with automatic migrations  
**Authentication**: Spotify OAuth 2.0 with persistent user sessions  
**Development**: HTTP on 127.0.0.1 for Spotify OAuth compatibility

## Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm (Node.js 20+ recommended for optimal Vite performance)
- **Spotify Developer Account** ([Create one here](https://developer.spotify.com/dashboard))
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys)) - Optional, users can provide their own

## Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd PlayMaker
```

### 2. Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env
```

### 3. Database Setup
```bash
# Initialize database with Alembic migrations
alembic upgrade head
```

### 4. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 5. Spotify App Configuration

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click "Create App"
3. Fill in app details:
   - **App name**: PlayMaker
   - **App description**: AI-powered playlist generator
   - **Website**: `http://127.0.0.1:3000`
   - **Redirect URIs**: `http://127.0.0.1:5988/api/spotify/callback`
4. Save your **Client ID** and **Client Secret**

### 6. Environment Configuration

Edit `.env` file with your credentials:

```bash
# Spotify API Configuration
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5988/api/spotify/callback

# OpenAI API Configuration (Optional - users can provide their own)
OPENAI_API_KEY=your_openai_api_key

# Database Configuration
DATABASE_URL=sqlite:///./playmaker.db

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

## User Guide

### Getting Started
1. **Connect Spotify Account**: Click "Connect Spotify Account" and authorize the application
2. **Automatic Profile Creation**: Your user profile is automatically created from your Spotify account
3. **Customize Profile**: Update your first name, last name, and other preferences in Account Information

### Creating Playlists
1. **Describe Your Playlist**: Enter a natural language description (e.g., "upbeat pop songs for working out")
2. **Optional Personal OpenAI Key**: Use your own OpenAI API key for potentially better results
3. **Generate Playlist**: Click "Generate Playlist" to get AI-powered track suggestions
4. **Customize Selection**: Review suggestions, swap alternatives, and select your favorite tracks
5. **Create in Spotify**: Click "Create Playlist in Spotify" to save it to your account

### Account Management
- **Profile Information**: Update first name, last name, and location
- **OpenAI API Key**: Store your personal OpenAI API key for playlist generation
- **Account Details**: View Spotify username, email, and account creation date

### Playlist History
- **View All Playlists**: Access complete history of all your created playlists
- **Playlist Details**: See creation dates, descriptions, and track lists
- **Spotify Links**: Click through to view/play playlists on Spotify
- **Track Information**: Complete metadata for every track in every playlist

## API Endpoints

### Authentication
- `GET /api/spotify` - Initiate Spotify OAuth flow
- `GET /api/spotify/callback` - Handle OAuth callback and create/update user profiles

### User Management
- `GET /api/user/{user_id}` - Get user profile information
- `PUT /api/user/{user_id}` - Update user profile information
- `GET /api/user/{user_id}/playlists` - Get user's playlist history

### Playlist Operations
- `POST /api/generate-playlist` - Generate playlist from natural language query
- `POST /api/create-playlist` - Create playlist in user's Spotify account
- `GET /api/search-tracks` - Search Spotify tracks

### Utility
- `GET /health` - Health check endpoint

## Database Schema

### Users Table
- **id**: Primary key
- **email**: Spotify email address
- **spotify_username**: Spotify user ID
- **first_name**: User's first name (customizable)
- **last_name**: User's last name (customizable)
- **location**: User's country/location
- **openai_api_key**: Personal OpenAI API key (optional)
- **created_at**: Account creation timestamp

### Playlists Table
- **id**: Primary key
- **user_id**: Foreign key to users
- **playlist_id**: MD5 hash identifier
- **name**: Playlist name
- **description**: User's original description
- **spotify_playlist_id**: Spotify playlist ID
- **spotify_url**: Direct Spotify playlist URL
- **created_at**: Creation timestamp

### Playlist Tracks Table
- **id**: Primary key
- **playlist_id**: Foreign key to playlists
- **spotify_track_id**: Spotify track ID
- **track_name**: Track title
- **artist_name**: Artist name
- **album_name**: Album name
- **track_order**: Position in playlist

## Project Structure

```
PlayMaker/
├── app/
│   ├── models/              # Database models and Pydantic schemas
│   │   ├── user.py         # User database model
│   │   ├── playlist.py     # Playlist and track models
│   │   └── requests.py     # API request/response models
│   ├── routers/            # FastAPI route handlers
│   │   ├── auth.py         # Spotify OAuth and user management
│   │   ├── playlist.py     # Playlist generation and management
│   │   └── user.py         # User profile endpoints
│   └── services/           # Business logic
│       ├── openai_service.py      # OpenAI API integration
│       ├── spotify_service.py     # Spotify API integration
│       ├── user_service.py        # User management logic
│       └── playlist_service.py    # Playlist management logic
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── SpotifyAuth.js         # OAuth handling
│   │   │   ├── PlaylistGenerator.js   # Main playlist interface
│   │   │   ├── UserProfile.js         # Account management
│   │   │   └── PlaylistHistory.js     # Playlist history view
│   │   ├── App.js          # Main React app with routing
│   │   ├── main.jsx        # Vite entry point
│   │   └── config.js       # API configuration
│   ├── vite.config.js      # Vite build configuration
│   └── package.json        # Frontend dependencies
├── alembic/                # Database migrations
│   ├── versions/           # Migration files
│   └── alembic.ini         # Alembic configuration
├── main.py                 # FastAPI application entry point
├── database.py             # Database connection and setup
├── .env                    # Environment configuration
├── requirements.txt        # Python dependencies
├── deploy-prod.sh          # Production deployment script
└── README.md              # This file
```

## Development Notes

### Frontend Build System (Vite Migration)

The frontend has been migrated from Create React App to Vite for improved performance:

**Performance Improvements:**
- Dev server startup: ~200ms (vs 15+ seconds with CRA)
- Production builds: ~800ms (vs minutes with CRA)
- Hot module replacement: Nearly instantaneous
- Zero deprecation warnings from outdated dependencies

**Build Commands:**
- `npm start` or `npm run dev` - Development server
- `npm run build` - Production build (outputs to `dist/`)
- `npm run preview` - Preview production build
- `npm test` - Run tests with Jest

**Rebuild Instructions:**
```bash
# Standard rebuild (recommended)
cd frontend
npm install
npm start

# Full clean rebuild (only if needed)
cd frontend
rm package-lock.json
rm -rf node_modules
npm install
npm start
```

**Environment Variables:**
- Uses `VITE_` prefix instead of `REACT_APP_`
- Access via `import.meta.env` instead of `process.env`
- Vite 6.x for Node.js 18+ compatibility

### Database Management

**Migrations:**
```bash
# Create new migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# View migration history
alembic history
```

**Database Reset (Development):**
```bash
# WARNING: This deletes all data
rm playmaker.db
alembic upgrade head
```

## Production Deployment

Use the included deployment script for production deployments:

```bash
# Dry run to test deployment process
./deploy-prod.sh --dry-run

# Full deployment
./deploy-prod.sh
```

The script handles:
- Code updates from Git
- Database migrations
- Frontend build process
- Dependency installation
- Backup creation
- Error handling with automatic rollback

## Known Issues & Fixes

### Recently Fixed Issues
- ✅ **User Profile Overwrite Bug**: Fixed issue where custom first names were overwritten with Spotify username on each login
- ✅ **Vite Migration**: Successfully migrated from deprecated Create React App to Vite
- ✅ **Node.js Compatibility**: Vite downgraded to 6.x for Node.js 18+ compatibility
- ✅ **ES Module Support**: Updated configuration for proper ES module handling

### Current Limitations

**Technical Limitations:**
- **HTTP Development Only**: Uses HTTP with loopback addresses for Spotify OAuth compatibility
- **No Rate Limiting**: API endpoints have no rate limiting implemented
- **Single Database File**: SQLite database not suitable for high-concurrency production use

**Spotify API Limitations:**
- **OAuth Redirect Constraints**: Must use `http://127.0.0.1` (not `localhost`) for backend redirect URI
- **Track Availability**: Song availability varies by region and Spotify catalog changes
- **Playlist Permissions**: Requires explicit user authorization for playlist modification

**User Experience Limitations:**
- **No Playlist Editing**: Cannot modify playlists after creation (must recreate)
- **Session Tokens**: Spotify tokens require re-authentication on browser refresh
- **Limited Track Metadata**: Basic track info only (no audio features, popularity, etc.)

## Production Considerations

For production deployment, consider:

- **HTTPS Configuration**: Implement proper SSL certificates for production domains
- **Database Scaling**: Consider PostgreSQL for high-concurrency production use
- **Redis Integration**: Add caching for Spotify search results and session management
- **Rate Limiting**: Implement API rate limiting and quota management
- **Error Monitoring**: Enhanced error reporting and application monitoring
- **Security Hardening**: Proper CORS configuration, input validation, and secret management
- **Backup Strategy**: Automated database backups and disaster recovery procedures

## Troubleshooting

### Common Issues

**"INVALID_CLIENT: Insecure redirect URI"**
- Ensure Spotify redirect URI is exactly: `http://127.0.0.1:5988/api/spotify/callback`
- Use `127.0.0.1` not `localhost` for the redirect URI in Spotify app settings

**"Failed to initiate Spotify authentication"**
- Check that backend is running on port 5988
- Verify SPOTIFY_CLIENT_ID is set correctly in `.env`
- Ensure database is initialized with `alembic upgrade head`

**"Failed to parse AI response"**
- Click "Show AI Response" to see the raw OpenAI output
- Try rephrasing your playlist description
- Check OPENAI_API_KEY is valid or provide a personal key

**Frontend won't connect to backend**
- Verify backend is running on `http://127.0.0.1:5988`
- Check that proxy configuration is correct in `vite.config.js`
- Ensure both frontend and backend are using correct ports

**Database migration errors**
- Delete `playmaker.db` and run `alembic upgrade head` to recreate
- Check that all migration files are present in `alembic/versions/`
- Verify DATABASE_URL in `.env` points to correct location

**Build errors on production**
- Ensure Node.js version is 18+ (20+ recommended)
- Check that all dependencies install without errors
- Verify Vite configuration supports target Node.js version

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and ensure build passes
5. Update documentation as needed
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on the GitHub repository.

---

**Latest Updates:**
- ✅ **v2.0**: Multi-user support with persistent storage
- ✅ **v1.5**: User profile management and playlist history
- ✅ **v1.2**: Vite migration for improved performance
- ✅ **v1.1**: Bug fixes for user profile persistence