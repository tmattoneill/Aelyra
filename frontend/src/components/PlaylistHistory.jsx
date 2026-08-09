import React, { useCallback, useEffect, useState } from 'react';

import { api, errorMessage } from '../config';

const FALLBACK_ART = '/images/aelyra_logo_1024x1024.png';

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '';
  }
}

export default function PlaylistHistory({ onTokenExpired }) {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get('/api/user-playlists', { params: { limit: 50 } });
      setPlaylists(data.playlists ?? []);
    } catch (err) {
      if (err.response?.status === 401) {
        onTokenExpired?.();
        return;
      }
      setError(errorMessage(err, 'Could not load your playlist history.'));
    } finally {
      setLoading(false);
    }
  }, [onTokenExpired]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="card">
        <div className="loading">
          <h3>Loading your playlists…</h3>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="error" role="alert">
          {error}
        </div>
        {/* The old error state was a dead end with no way to retry. */}
        <button type="button" className="btn" onClick={load}>
          Try again
        </button>
      </div>
    );
  }

  if (playlists.length === 0) {
    return (
      <div className="card">
        <div className="empty-state">
          <h3>No playlists yet</h3>
          <p>Playlists you create with Aelyra will appear here.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 style={{ marginBottom: 4 }}>Your playlists</h2>
      <p className="text-muted" style={{ marginBottom: 20 }}>
        {playlists.length} {playlists.length === 1 ? 'playlist' : 'playlists'} created with Aelyra.
      </p>

      <div className="history-list">
        {playlists.map((playlist) => {
          const art = playlist.album_art?.length ? playlist.album_art : [FALLBACK_ART];
          return (
            /* A real anchor, so it is reachable by keyboard and openable in a
               new tab. It used to be a div with an onClick calling window.open. */
            <a
              key={playlist.id}
              className="history-card"
              href={playlist.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className={`history-art ${art.length === 1 ? 'single' : ''}`}>
                {art.slice(0, 4).map((url, i) => (
                  <img key={i} src={url} alt="" loading="lazy" />
                ))}
              </span>
              <span className="history-meta">
                <h3>{playlist.name}</h3>
                {/* The stored description already carries its own prefix; this
                    used to add a second one and render it nested. */}
                {playlist.description && (
                  <span className="text-muted" style={{ display: 'block', marginBottom: 4 }}>
                    {playlist.description}
                  </span>
                )}
                <span className="text-faint">
                  {playlist.track_count} {playlist.track_count === 1 ? 'track' : 'tracks'}
                  {playlist.created_at ? ` · ${formatDate(playlist.created_at)}` : ''}
                </span>
              </span>
            </a>
          );
        })}
      </div>
    </div>
  );
}
