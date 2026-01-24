
import React, { useState, useEffect } from 'react';
import SpotifyAuth from './components/SpotifyAuth';
import PlaylistGenerator from './components/PlaylistGenerator';
import UserProfile from './components/UserProfile';
import PlaylistHistory from './components/PlaylistHistory';
import PlaylistUpload from './components/PlaylistUpload';
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
    let mounted = true;
    const controller = new AbortController();

    const loadSavedToken = async () => {
      try {
        const savedToken = sessionStorage.getItem('spotify_token');
        const savedUser = sessionStorage.getItem('user_info');

        if (savedToken && savedUser) {
          // Validate token by testing it with user-info endpoint
          try {
            await api.get('/api/user-info', {
              params: { spotify_access_token: savedToken },
              signal: controller.signal
            });

            // Only update state if component is still mounted
            if (mounted) {
              setSpotifyToken(savedToken);
              setUserInfo(JSON.parse(savedUser));
              setStep(2);
            }
          } catch (error) {
            // Don't clear storage if request was aborted
            if (error.name !== 'AbortError' && mounted) {
              sessionStorage.removeItem('spotify_token');
              sessionStorage.removeItem('user_info');
            }
          }
        }
      } catch (error) {
        // Only log if not an abort error
        if (error.name !== 'AbortError') {
          console.error('Error loading saved token:', error);
        }
      } finally {
        if (mounted) {
          setTokenLoading(false);
        }
      }
    };

    loadSavedToken();

    // Cleanup function
    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  const handleAuthSuccess = (token, user) => {
    setSpotifyToken(token);
    setUserInfo(user);
    setStep(2);

    // Save to sessionStorage for persistence
    sessionStorage.setItem('spotify_token', token);
    sessionStorage.setItem('user_info', JSON.stringify(user));
  };

  const handleLogout = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
    setActiveTab('generate');

    // Clear sessionStorage
    sessionStorage.removeItem('spotify_token');
    sessionStorage.removeItem('user_info');
  };

  const handleTokenExpired = () => {
    setSpotifyToken(null);
    setUserInfo(null);
    setStep(1);
    setActiveTab('generate');

    // Clear sessionStorage when token expires
    sessionStorage.removeItem('spotify_token');
    sessionStorage.removeItem('user_info');
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
      case 'upload':
        return (
          <PlaylistUpload
            spotifyToken={spotifyToken}
            userInfo={userInfo}
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
              className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              Upload Playlist
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
