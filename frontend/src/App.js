
import React, { useState } from 'react';
import SpotifyAuth from './components/SpotifyAuth';
import PlaylistGenerator from './components/PlaylistGenerator';
import './index.css';

function App() {
  const [spotifyToken, setSpotifyToken] = useState(null);
  const [step, setStep] = useState(1);

  const handleAuthSuccess = (token) => {
    setSpotifyToken(token);
    setStep(2);
  };

  const handleLogout = () => {
    setSpotifyToken(null);
    setStep(1);
  };

  return (
    <div className="container">
      <div className="header">
        <h1>🎵 PlayMaker</h1>
        <p>AI-Powered Spotify Playlist Generator</p>
      </div>

      <div className="steps">
        <div className={`step ${step >= 1 ? 'active' : ''}`}>
          <div className="step-number">1</div>
          <span>Connect Spotify</span>
        </div>
        <div className={`step ${step >= 2 ? 'active' : ''}`}>
          <div className="step-number">2</div>
          <span>Generate Playlist</span>
        </div>
      </div>

      {!spotifyToken ? (
        <SpotifyAuth onAuthSuccess={handleAuthSuccess} />
      ) : (
        <PlaylistGenerator 
          spotifyToken={spotifyToken} 
          onLogout={handleLogout}
        />
      )}
    </div>
  );
}

export default App;
