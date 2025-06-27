import React, { useState, useEffect } from 'react';
import { api } from '../config';

const PlaylistHistory = ({ spotifyToken, userInfo }) => {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchPlaylists();
  }, [spotifyToken]);

  const fetchPlaylists = async () => {
    if (!spotifyToken) return;
    
    setLoading(true);
    setError('');

    try {
      const response = await api.get('/api/user-playlists', {
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

  const formatDuration = (trackCount) => {
    // Estimate duration (average 3.5 minutes per track)
    const estimatedMinutes = Math.round(trackCount * 3.5);
    if (estimatedMinutes < 60) {
      return `${estimatedMinutes} min`;
    }
    const hours = Math.floor(estimatedMinutes / 60);
    const minutes = estimatedMinutes % 60;
    return `${hours} hr ${minutes} min`;
  };

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };


  const renderAlbumArtGrid = (albumArt) => {
    // Create a 2x2 grid of album artwork
    const artArray = [...albumArt];
    
    // Fill with placeholder if we don't have 4 images
    while (artArray.length < 4) {
      artArray.push(null);
    }

    return (
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gridTemplateRows: '1fr 1fr',
        gap: '2px',
        width: '120px',
        height: '120px',
        borderRadius: '4px',
        overflow: 'hidden',
        flexShrink: 0
      }}>
        {artArray.slice(0, 4).map((art, index) => (
          <div
            key={index}
            style={{
              width: '100%',
              height: '100%',
              background: art 
                ? `url(${art}) center/cover` 
                : 'linear-gradient(45deg, #333, #555)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#888',
              fontSize: '24px'
            }}
          >
            {!art && '♪'}
          </div>
        ))}
      </div>
    );
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
        <h2 style={{ color: '#1BD760', marginBottom: '20px' }}>User Playlist History</h2>
        <div style={{ textAlign: 'center', padding: '40px', color: '#B3B3B3' }}>
          <p>No playlists created yet.</p>
          <p>Create your first playlist to see it appear here!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 style={{ 
        color: '#EFEFEF', 
        marginBottom: '30px',
        fontSize: '28px',
        fontWeight: '300'
      }}>
        Playlist History for {userInfo?.first_name || userInfo?.display_name?.split(' ')[0] || 'User'}
      </h2>
      
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column',
        gap: '20px',
        maxHeight: '70vh',
        overflowY: 'auto',
        paddingRight: '10px'
      }}>
        {playlists.map((playlist, index) => (
          <div 
            key={playlist.id}
            onClick={() => window.open(playlist.spotify_url, '_blank')}
            title="Click to open in Spotify"
            style={{
              background: '#AAAAAA',
              borderRadius: '8px',
              padding: '24px',
              display: 'flex',
              alignItems: 'center',
              gap: '20px',
              cursor: 'pointer',
              transition: 'opacity 0.2s ease',
              position: 'relative',
              minHeight: '140px',
              overflow: 'hidden'
            }}
            onMouseEnter={(e) => {
              e.target.style.opacity = '0.9';
            }}
            onMouseLeave={(e) => {
              e.target.style.opacity = '1';
            }}
          >
            {/* Album Art Grid */}
            {renderAlbumArtGrid(playlist.album_art || [])}
            
            {/* Playlist Info */}
            <div style={{ flex: 1, color: '#000', minWidth: 0, paddingRight: '8px' }}>
              <div style={{ 
                fontSize: '12px', 
                fontWeight: '500',
                marginBottom: '6px',
                opacity: 0.7,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                Public Playlist
              </div>
              
              <h3 style={{ 
                fontSize: '28px',
                fontWeight: '700',
                margin: '0 0 6px 0',
                lineHeight: '1.1',
                wordWrap: 'break-word',
                overflow: 'hidden'
              }}>
                {playlist.name}
              </h3>
              
              <div style={{ 
                fontSize: '13px',
                margin: '0 0 8px 0',
                opacity: 0.8,
                fontWeight: '500'
              }}>
                Date Created: {formatDate(playlist.created_at)}
              </div>
              
              <p style={{ 
                fontSize: '14px',
                margin: '0 0 12px 0',
                opacity: 0.9,
                lineHeight: '1.3',
                wordWrap: 'break-word',
                overflow: 'hidden'
              }}>
                Generated by Aelyra AI for: "{playlist.description}"
              </p>
              
              <div style={{ 
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '13px',
                opacity: 0.8
              }}>
                <div style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: 'rgba(0,0,0,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '10px'
                }}>
                  ♪
                </div>
                <span style={{ fontWeight: '500' }}>{userInfo?.display_name || userInfo?.id || 'User'}</span>
                <span>•</span>
                <span>{playlist.track_count} songs</span>
                <span>•</span>
                <span>{formatDuration(playlist.track_count)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PlaylistHistory;