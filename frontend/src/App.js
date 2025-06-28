
import React, { useState, useEffect } from 'react';
import SpotifyAuth from './components/SpotifyAuth';
import PlaylistGenerator from './components/PlaylistGenerator';
import UserProfile from './components/UserProfile';
import PlaylistHistory from './components/PlaylistHistory';
import { api } from './config';
import './index.css';

function App() {
  const [spotifyToken, setSpotifyToken] = useState(null);
  const [userInfo, setUserInfo] = useState(null);
  const [step, setStep] = useState(1);
  const [activeTab, setActiveTab] = useState('generate');
  const [tokenLoading, setTokenLoading] = useState(true);

  // Load token from sessionStorage on app start
  useEffect(() => {
    const loadSavedToken = async () => {
      try {
        const savedToken = sessionStorage.getItem('spotify_token');
        const savedUser = sessionStorage.getItem('user_info');
        
        if (savedToken && savedUser) {
          console.log('Found saved token, validating...');
          
          // Validate token by testing it with user-info endpoint
          try {
            const response = await api.get('/api/user-info', {
              params: { spotify_access_token: savedToken }
            });
            
            // Token is valid, restore session
            setSpotifyToken(savedToken);
            setUserInfo(JSON.parse(savedUser));
            setStep(2);
            console.log('Token validated successfully, session restored');
          } catch (error) {
            console.log('Saved token is invalid or expired, clearing...');
            sessionStorage.removeItem('spotify_token');
            sessionStorage.removeItem('user_info');
          }
        }
      } catch (error) {
        console.error('Error loading saved token:', error);
      } finally {
        setTokenLoading(false);
      }
    };

    loadSavedToken();
  }, []);

  const handleAuthSuccess = (token, user) => {
    setSpotifyToken(token);
    setUserInfo(user);
    setStep(2);
    
    // Save to sessionStorage for persistence
    sessionStorage.setItem('spotify_token', token);
    sessionStorage.setItem('user_info', JSON.stringify(user));
    console.log('Token saved to session storage');
  };

  const handleLogout = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
    setActiveTab('generate');
    
    // Clear sessionStorage
    sessionStorage.removeItem('spotify_token');
    sessionStorage.removeItem('user_info');
    console.log('Token cleared from session storage');
  };

  const handleTokenExpired = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
    setActiveTab('generate');
    
    // Clear sessionStorage when token expires
    sessionStorage.removeItem('spotify_token');
    sessionStorage.removeItem('user_info');
    console.log('Expired token cleared from session storage');
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
            userInfo={userInfo}
          />
        );
      default:
        return null;
    }
  };

  // Show loading while checking for saved token
  if (tokenLoading) {
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
        <div className="card">
          <div className="loading">
            <h3>Checking your session...</h3>
            <p>Validating your Spotify connection</p>
          </div>
        </div>
      </div>
    );
  }

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
