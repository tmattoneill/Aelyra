import React, { useState, useEffect } from 'react';
import axios from 'axios';

const PlaylistHistory = ({ spotifyToken }) => {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedPlaylist, setExpandedPlaylist] = useState(null);

  useEffect(() => {
    fetchPlaylists();
  }, [spotifyToken]);

  const fetchPlaylists = async () => {
    if (!spotifyToken) return;
    
    setLoading(true);
    setError('');

    try {
      const response = await axios.get('http://127.0.0.1:5988/api/user-playlists', {
        params: {
          spotify_access_token: spotifyToken,
          limit: 50
        }
      });
      
      setPlaylists(response.data.playlists || []);
    } catch (error) {
      console.error('Error fetching playlists:', error);
      setError('Failed to load playlist history');
    } finally {
      setLoading(false);
    }
  };

  const togglePlaylistExpansion = (playlistId) => {
    setExpandedPlaylist(expandedPlaylist === playlistId ? null : playlistId);
  };

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="card">
        <div className="loading">Loading your playlist history...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="error">{error}</div>
      </div>
    );
  }

  if (playlists.length === 0) {
    return (
      <div className="card">
        <h2 style={{ color: '#1BD760', marginBottom: '20px' }}>Playlist History</h2>
        <div style={{ textAlign: 'center', padding: '40px', color: '#B3B3B3' }}>
          <p>No playlists created yet.</p>
          <p>Create your first playlist to see it appear here!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 style={{ color: '#1BD760', marginBottom: '20px' }}>
        Playlist History ({playlists.length})
      </h2>
      
      <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
        {playlists.map((playlist, index) => (
          <div 
            key={playlist.id}
            style={{
              background: '#181818',
              border: '1px solid #404040',
              borderRadius: '8px',
              marginBottom: '15px',
              overflow: 'hidden'
            }}
          >
            <div 
              style={{
                padding: '20px',
                cursor: 'pointer',
                borderBottom: expandedPlaylist === playlist.id ? '1px solid #404040' : 'none'
              }}
              onClick={() => togglePlaylistExpansion(playlist.id)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ 
                    color: '#EFEFEF', 
                    margin: '0 0 8px 0',
                    fontSize: '18px',
                    fontWeight: '600'
                  }}>
                    {playlist.name}
                  </h3>
                  
                  <p style={{ 
                    color: '#B3B3B3', 
                    margin: '0 0 10px 0',
                    fontSize: '14px',
                    lineHeight: '1.4'
                  }}>
                    {playlist.description}
                  </p>
                  
                  <div style={{ 
                    display: 'flex', 
                    gap: '20px', 
                    fontSize: '12px', 
                    color: '#B3B3B3' 
                  }}>
                    <span>{playlist.track_count} tracks</span>
                    <span>Created: {formatDate(playlist.created_at)}</span>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <a
                    href={playlist.spotify_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary"
                    style={{ 
                      padding: '8px 15px', 
                      fontSize: '12px',
                      textDecoration: 'none',
                      display: 'inline-block'
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    Open in Spotify
                  </a>
                  
                  <span style={{ 
                    color: '#B3B3B3', 
                    fontSize: '18px',
                    transform: expandedPlaylist === playlist.id ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s ease'
                  }}>
                    ▼
                  </span>
                </div>
              </div>
            </div>
            
            {expandedPlaylist === playlist.id && (
              <div style={{ padding: '0 20px 20px 20px' }}>
                <h4 style={{ 
                  color: '#EFEFEF', 
                  marginBottom: '15px',
                  fontSize: '14px',
                  fontWeight: '600'
                }}>
                  Track List:
                </h4>
                
                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  {playlist.tracks.map((track) => (
                    <div 
                      key={`${playlist.id}-${track.position}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '8px 0',
                        borderBottom: '1px solid #2A2A2A'
                      }}
                    >
                      <span style={{ 
                        color: '#B3B3B3', 
                        minWidth: '30px',
                        fontSize: '12px'
                      }}>
                        {track.position}.
                      </span>
                      
                      <div style={{ flex: 1 }}>
                        <div style={{ 
                          color: '#EFEFEF', 
                          fontSize: '14px',
                          marginBottom: '2px'
                        }}>
                          {track.name}
                        </div>
                        <div style={{ 
                          color: '#B3B3B3', 
                          fontSize: '12px'
                        }}>
                          {track.artist} • {track.album}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default PlaylistHistory;