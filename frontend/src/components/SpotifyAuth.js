
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
      // Clear URL parameters and call success handler
      window.history.replaceState({}, document.title, window.location.pathname);
      onAuthSuccess(accessToken);
    }
  }, []);


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
    <div className="card">
      <h2>Connect Your Spotify Account</h2>
      <p style={{ marginBottom: '20px', color: '#666' }}>
        To create playlists, we need access to your Spotify account. 
        This allows us to search for songs and create playlists on your behalf.
      </p>
      
      {error && <div className="error">{error}</div>}
      
      <button 
        className="btn" 
        onClick={initiateAuth}
        disabled={loading}
      >
        {loading ? 'Connecting...' : 'Connect Spotify Account'}
      </button>
      
      <div style={{ marginTop: '20px', fontSize: '14px', color: '#666' }}>
        <strong>Permissions we'll request:</strong>
        <ul style={{ marginTop: '10px', paddingLeft: '20px' }}>
          <li>Create and modify playlists</li>
          <li>Access your profile information</li>
        </ul>
      </div>
    </div>
  );
};

export default SpotifyAuth;
