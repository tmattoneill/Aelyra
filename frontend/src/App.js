
import React, { useState } from 'react';
import SpotifyAuth from './components/SpotifyAuth';
import PlaylistGenerator from './components/PlaylistGenerator';
import './index.css';

function App() {
  const [spotifyToken, setSpotifyToken] = useState(null);
  const [userInfo, setUserInfo] = useState(null);
  const [step, setStep] = useState(1);

  const handleAuthSuccess = (token, user) => {
    setSpotifyToken(token);
    setUserInfo(user);
    setStep(2);
  };

  const handleLogout = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
  };

  const handleTokenExpired = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
  };

  return (
    <div className="container">
      <div className="header">
          <img 
              src="/images/aelyra_logo_1024x1024.png" 
              alt="Aleyra Logo" 
              style={{
                width: '200px',
                height: '200px',
                marginRight: '20px',
                objectFit: 'contain'
              }}
          />
        <p>Create the Perect Playlilst Together</p>
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
          userInfo={userInfo}
          onLogout={handleLogout}
          onTokenExpired={handleTokenExpired}
        />
      )}
    </div>
  );
}

export default App;
