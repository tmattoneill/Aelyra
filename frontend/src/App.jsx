import React, { useCallback, useEffect, useState } from 'react';

import {
  clearSession,
  getSession,
  onSessionExpired,
  updateUser,
} from './auth/authStore';
import PlaylistGenerator from './components/PlaylistGenerator';
import PlaylistHistory from './components/PlaylistHistory';
import PlaylistUpload from './components/PlaylistUpload';
import SpotifyAuth from './components/SpotifyAuth';
import UserProfile from './components/UserProfile';
import { api } from './config';
import './index.css';

const TABS = [
  { id: 'generate', label: 'Generate Playlist' },
  { id: 'upload', label: 'Upload Playlist' },
  { id: 'profile', label: 'Account' },
  { id: 'history', label: 'History' },
];

function Header() {
  return (
    <header className="header">
      <img src="/images/aelyra_logo_1024x1024.png" alt="" />
      <h1>Aelyra</h1>
      <p>Create the perfect playlist together</p>
    </header>
  );
}

export default function App() {
  const [userInfo, setUserInfo] = useState(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [activeTab, setActiveTab] = useState('generate');
  const [checkingSession, setCheckingSession] = useState(true);

  const handleLogout = useCallback(() => {
    clearSession();
    setAuthenticated(false);
    setUserInfo(null);
    setActiveTab('generate');
  }, []);

  // The axios interceptors call this when a session cannot be recovered.
  useEffect(() => onSessionExpired(handleLogout), [handleLogout]);

  // Restore a session on load, confirming the token still works.
  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    const restore = async () => {
      const session = getSession();
      if (!session?.access_token) {
        if (mounted) setCheckingSession(false);
        return;
      }

      try {
        const { data } = await api.get('/api/user-info', { signal: controller.signal });
        if (!mounted) return;
        setUserInfo(data);
        updateUser(data);
        setAuthenticated(true);
      } catch (err) {
        // A network blip should not force a full re-login; only clear the
        // session when the server actually rejects the token.
        if (!mounted || err.name === 'CanceledError' || err.name === 'AbortError') return;
        if (err.response?.status === 401) {
          clearSession();
        } else {
          setUserInfo(session.user);
          setAuthenticated(true);
        }
      } finally {
        if (mounted) setCheckingSession(false);
      }
    };

    restore();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  const handleAuthSuccess = useCallback((session) => {
    setUserInfo(session.user);
    setAuthenticated(true);
  }, []);

  const handleProfileUpdate = useCallback((patch) => {
    setUserInfo((prev) => ({ ...prev, ...patch }));
    // Persist through to storage, otherwise edits vanished on reload.
    updateUser(patch);
  }, []);

  if (checkingSession) {
    return (
      <div className="container">
        <Header />
        <div className="card">
          <div className="loading">
            <h3>Checking your session…</h3>
            <p>Validating your Spotify connection.</p>
          </div>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="container">
        <Header />
        <SpotifyAuth onAuthSuccess={handleAuthSuccess} />
      </div>
    );
  }

  return (
    <div className="container">
      <Header />

      <nav className="nav-tabs" role="tablist" aria-label="Sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls="tab-panel"
            className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div id="tab-panel" role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
        {activeTab === 'generate' && <PlaylistGenerator onTokenExpired={handleLogout} />}
        {activeTab === 'upload' && <PlaylistUpload onTokenExpired={handleLogout} />}
        {activeTab === 'profile' && (
          <UserProfile
            userInfo={userInfo}
            onProfileUpdate={handleProfileUpdate}
            onLogout={handleLogout}
          />
        )}
        {activeTab === 'history' && <PlaylistHistory onTokenExpired={handleLogout} />}
      </div>
    </div>
  );
}
