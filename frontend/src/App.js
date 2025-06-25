
import React, { useState } from 'react';
import SpotifyAuth from './components/SpotifyAuth';
import PlaylistGenerator from './components/PlaylistGenerator';
import UserProfile from './components/UserProfile';
import PlaylistHistory from './components/PlaylistHistory';
import './index.css';

function App() {
  const [spotifyToken, setSpotifyToken] = useState(null);
  const [userInfo, setUserInfo] = useState(null);
  const [step, setStep] = useState(1);
  const [activeTab, setActiveTab] = useState('generate');

  const handleAuthSuccess = (token, user) => {
    setSpotifyToken(token);
    setUserInfo(user);
    setStep(2);
  };

  const handleLogout = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
    setActiveTab('generate');
  };

  const handleTokenExpired = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
    setActiveTab('generate');
  };

  const handleProfileUpdate = (updatedProfile) => {
    setUserInfo(prev => ({
      ...prev,
      ...updatedProfile
    }));
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'generate':
        return (
          <PlaylistGenerator 
            spotifyToken={spotifyToken}
            userInfo={userInfo}
            onLogout={handleLogout}
            onTokenExpired={handleTokenExpired}
          />
        );
      case 'profile':
        return (
          <UserProfile 
            spotifyToken={spotifyToken}
            userInfo={userInfo}
            onProfileUpdate={handleProfileUpdate}
          />
        );
      case 'history':
        return (
          <PlaylistHistory 
            spotifyToken={spotifyToken}
          />
        );
      default:
        return null;
    }
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
        <p>Create the Perfect Playlilst Together</p>
      </div>

      {!spotifyToken ? (
        <>
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
          <SpotifyAuth onAuthSuccess={handleAuthSuccess} />
        </>
      ) : (
        <>
          {/* Navigation Tabs */}
          <div className="nav-tabs">
            <button 
              className={`nav-tab ${activeTab === 'generate' ? 'active' : ''}`}
              onClick={() => setActiveTab('generate')}
            >
              Generate Playlist
            </button>
            <button 
              className={`nav-tab ${activeTab === 'profile' ? 'active' : ''}`}
              onClick={() => setActiveTab('profile')}
            >
              Account Information
            </button>
            <button 
              className={`nav-tab ${activeTab === 'history' ? 'active' : ''}`}
              onClick={() => setActiveTab('history')}
            >
              Playlist History
            </button>
            <button 
              className="nav-tab logout-tab"
              onClick={handleLogout}
            >
              Logout
            </button>
          </div>

          {/* Tab Content */}
          {renderTabContent()}
        </>
      )}
    </div>
  );
}

export default App;
