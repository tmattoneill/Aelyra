import React, { useEffect, useRef, useState } from 'react';

import { api, errorMessage, exchangeAuthCode } from '../config';

const STEPS = [
  { title: '1. Connect Spotify', body: 'Link your account so playlists can be saved to it.' },
  { title: '2. Describe your playlist', body: 'Say what you want in plain language: mood, genre, era, artists to sound like.' },
  { title: '3. Review the tracks', body: 'Keep the ones you want and drop the rest before saving.' },
  { title: '4. Save to Spotify', body: 'The playlist appears in your account, ready to play.' },
];

export default function SpotifyAuth({ onAuthSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const exchangedRef = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authCode = params.get('auth_code');
    const oauthError = params.get('error');

    if (oauthError) {
      setError('Spotify declined the connection. Please try again.');
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    if (!authCode) return;

    // The code is single-use, so React 18 StrictMode's double-invoked effect
    // must not redeem it twice.
    if (exchangedRef.current) return;
    exchangedRef.current = true;

    // Strip the code from the URL before the network call so it never lingers
    // in the address bar or a shared link.
    window.history.replaceState({}, document.title, window.location.pathname);

    setLoading(true);
    exchangeAuthCode(authCode)
      .then((session) => onAuthSuccess(session))
      .catch((err) => {
        setError(errorMessage(err, 'Could not complete the Spotify connection. Please try again.'));
      })
      .finally(() => setLoading(false));
  }, [onAuthSuccess]);

  const initiateAuth = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get('/api/spotify');
      window.location.href = data.auth_url;
    } catch (err) {
      setError(errorMessage(err, 'Could not start the Spotify connection.'));
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card">
        <div className="loading">
          <h3>Connecting to Spotify…</h3>
          <p>One moment while your session is set up.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="card">
        <h2>How it works</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
            gap: 20,
            marginTop: 20,
          }}
        >
          {STEPS.map((step) => (
            <div key={step.title}>
              <div style={{ color: 'var(--brand)', fontWeight: 600, marginBottom: 8 }}>
                {step.title}
              </div>
              <p className="text-muted">{step.body}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Connect your Spotify account</h2>
        <p className="text-muted" style={{ margin: '12px 0 20px' }}>
          Aelyra needs permission to create playlists in your account and to read
          your profile. It never plays, deletes or changes anything else.
        </p>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        <button type="button" className="btn" onClick={initiateAuth}>
          Connect Spotify Account
        </button>
      </div>
    </div>
  );
}
