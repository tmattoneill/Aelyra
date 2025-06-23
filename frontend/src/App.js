
import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [playlist, setPlaylist] = useState(null);
  const [error, setError] = useState('');
  const [accessToken, setAccessToken] = useState('');

  const handleAuth = async () => {
    try {
      const response = await axios.get('/api/spotify/spotify');
      window.open(response.data.auth_url, '_blank');
      alert('Please complete the authorization in the new tab, then copy the access token from the callback response and paste it in the token field.');
    } catch (error) {
      setError('Failed to initiate Spotify authorization');
    }
  };

  const generatePlaylist = async () => {
    if (!query.trim()) {
      setError('Please enter a playlist description');
      return;
    }
    
    if (!accessToken.trim()) {
      setError('Please authorize with Spotify first and enter your access token');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post('/api/generate-playlist', {
        query: query,
        spotify_access_token: accessToken
      });
      
      setPlaylist(response.data);
    } catch (error) {
      setError(error.response?.data?.detail || 'Failed to generate playlist');
    } finally {
      setLoading(false);
    }
  };

  const createPlaylist = async () => {
    if (!playlist || !accessToken) return;

    setLoading(true);
    try {
      const trackIds = playlist.tracks
        .filter(track => track.spotify_id)
        .map(track => track.spotify_id);

      const response = await axios.post('/api/create-playlist', {
        name: playlist.playlist_name,
        track_ids: trackIds,
        spotify_access_token: accessToken,
        description: `Generated from: ${query}`
      });

      alert(`Playlist "${playlist.playlist_name}" created successfully! Open Spotify to see it.`);
    } catch (error) {
      setError(error.response?.data?.detail || 'Failed to create playlist');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🎵 Playlist Generator</h1>
        <p>AI-Powered Spotify Playlist Creation</p>
      </header>

      <main className="App-main">
        {!accessToken && (
          <div className="auth-section">
            <h3>Step 1: Authorize with Spotify</h3>
            <button onClick={handleAuth} className="auth-button">
              Authorize Spotify
            </button>
            <input
              type="text"
              placeholder="Paste your access token here"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              className="token-input"
            />
          </div>
        )}

        {accessToken && (
          <div className="generator-section">
            <div className="input-section">
              <h3>Describe your perfect playlist</h3>
              <textarea
                placeholder="e.g., upbeat songs for morning workout, chill music for studying, romantic dinner songs..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="query-input"
                rows="3"
              />
              <button 
                onClick={generatePlaylist} 
                disabled={loading}
                className="generate-button"
              >
                {loading ? 'Generating...' : 'Generate Playlist'}
              </button>
            </div>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            {playlist && (
              <div className="playlist-results">
                <h2>🎶 {playlist.playlist_name}</h2>
                <div className="tracks-grid">
                  {playlist.tracks.map((track, index) => (
                    <div key={index} className="track-card">
                      {track.album_art && (
                        <img 
                          src={track.album_art} 
                          alt={`${track.title} album art`}
                          className="album-art"
                        />
                      )}
                      <div className="track-info">
                        <h4>{track.title}</h4>
                        <p>{track.artist}</p>
                        {track.preview_url && (
                          <audio controls className="preview-audio">
                            <source src={track.preview_url} type="audio/mpeg" />
                          </audio>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                <button 
                  onClick={createPlaylist}
                  disabled={loading}
                  className="create-playlist-button"
                >
                  {loading ? 'Creating...' : 'Create Playlist in Spotify'}
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
