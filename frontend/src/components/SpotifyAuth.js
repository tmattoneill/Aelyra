
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SpotifyAuth = ({ onAuthSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Check for auth callback
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access_token');
    const error = urlParams.get('error');

    if (error) {
      setError(`Spotify authentication failed: ${error}`);
      return;
    }

    if (accessToken) {
      // Clear URL parameters and fetch user info
      window.history.replaceState({}, document.title, window.location.pathname);
      fetchUserInfo(accessToken);
    }
  }, []);

  const fetchUserInfo = async (token) => {
    try {
      const response = await axios.get(`/api/user-info?spotify_access_token=${token}`);
      onAuthSuccess(token, response.data);
    } catch (err) {
      setError('Failed to fetch user information');
      console.error('User info fetch error:', err);
    }
  };


  const initiateAuth = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.get('/api/spotify');
      window.location.href = response.data.auth_url;
    } catch (err) {
      setError('Failed to initiate Spotify authentication');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card">
        <div className="loading">
          <h3>Connecting to Spotify...</h3>
          <p>Please wait while we set up your connection.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: '20px' }}>
        <h2>How It Works</h2>
        <div style={{ color: '#B3B3B3', fontSize: '16px', lineHeight: '1.6' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginTop: '20px' }}>
            <div>
              <div style={{ color: '#1BD760', fontWeight: '600', marginBottom: '8px' }}>1. Connect Spotify</div>
              <p>Securely connect your Spotify account to allow playlist creation</p>
            </div>
            <div>
              <div style={{ color: '#1BD760', fontWeight: '600', marginBottom: '8px' }}>2. Describe Your Playlist</div>
              <p>Tell us what kind of music you want in natural language</p>
            </div>
            <div>
              <div style={{ color: '#1BD760', fontWeight: '600', marginBottom: '8px' }}>3. Review & Customize</div>
              <p>Choose from AI-generated tracks and alternative suggestions</p>
            </div>
            <div>
              <div style={{ color: '#1BD760', fontWeight: '600', marginBottom: '8px' }}>4. Create Playlist</div>
              <p>Your custom playlist is automatically created in Spotify</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Connect Your Spotify Account</h2>
        <p style={{ marginBottom: '20px', color: '#B3B3B3' }}>
          To get started, connect your Spotify account. We'll use AI to generate personalized playlists based on your preferences.
        </p>
        
        {error && <div className="error">{error}</div>}
        
        <button 
          className="btn" 
          onClick={initiateAuth}
          disabled={loading}
        >
          {loading ? 'Connecting...' : 'Connect Spotify Account'}
        </button>
        
        <div style={{ marginTop: '25px', padding: '20px', background: '#181818', borderRadius: '6px', border: '1px solid #404040' }}>
          <div style={{ color: '#EFEFEF', fontWeight: '600', marginBottom: '12px' }}>What You Can Create:</div>
          <ul style={{ color: '#B3B3B3', paddingLeft: '20px', lineHeight: '1.8' }}>
            <li>"Upbeat songs for a morning workout"</li>
            <li>"Chill indie songs for studying"</li>
            <li>"Classic rock anthems from the 80s"</li>
            <li>"Sad songs for rainy days"</li>
            <li>"Party music with heavy bass"</li>
          </ul>
        </div>

        <div style={{ marginTop: '20px', fontSize: '14px', color: '#B3B3B3' }}>
          <strong style={{ color: '#EFEFEF' }}>Permissions Required:</strong>
          <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
            <li>Create and modify playlists</li>
            <li>Access your profile information</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default SpotifyAuth;
