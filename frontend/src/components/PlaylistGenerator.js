
import React, { useState } from 'react';
import { api } from '../config';
import SkeletonLoader from './SkeletonLoader';

const PlaylistGenerator = ({ spotifyToken, userInfo, onLogout, onTokenExpired }) => {
  const [query, setQuery] = useState('');
  const [tracks, setTracks] = useState([]);
  const [selectedTracks, setSelectedTracks] = useState(new Set());
  const [playlistName, setPlaylistName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rawAiResponse, setRawAiResponse] = useState('');
  const [showRawResponse, setShowRawResponse] = useState(false);
  const [success, setSuccess] = useState('');
  const [step, setStep] = useState('input'); // 'input', 'generated', 'created'
  
  // New state for streaming progress
  const [progressStatus, setProgressStatus] = useState('');
  const [foundTracks, setFoundTracks] = useState([]);
  const [trackCount, setTrackCount] = useState(0);

  // Helper function to check if error is token expiration
  const isTokenExpiredError = (error) => {
    return error.response?.status === 401 || 
           error.response?.data?.detail?.includes('token expired') ||
           error.response?.data?.detail?.includes('token expired or invalid');
  };

  const generatePlaylist = async () => {
    console.log('Starting playlist generation with token:', !!spotifyToken);
    if (!query.trim()) {
      setError('Please enter a description for your playlist');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setProgressStatus('');
    setFoundTracks([]);
    setTrackCount(0);

    try {
      // Use streaming endpoint for real-time feedback
      const response = await fetch(`${api.defaults.baseURL}/api/generate-playlist-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query.trim(),
          spotify_access_token: spotifyToken
        })
      });

      if (!response.ok) {
        throw new Error('Failed to start playlist generation');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'status') {
                setProgressStatus(data.message);
              } else if (data.type === 'track_found') {
                setFoundTracks(prev => [...prev, data.track]);
                setTrackCount(data.count);
                setProgressStatus(`Found ${data.count} tracks...`);
              } else if (data.type === 'complete') {
                setTracks(data.playlist.tracks);
                setPlaylistName(data.playlist.playlist_name);
                setSelectedTracks(new Set(data.playlist.tracks.map(track => track.spotify_id)));
                setStep('generated');
                setLoading(false);
                return;
              } else if (data.type === 'error') {
                throw new Error(data.message);
              }
            } catch (parseError) {
              console.warn('Failed to parse streaming data:', parseError);
            }
          }
        }
      }
    } catch (err) {
      console.error('Streaming error, falling back to regular endpoint:', err);
      
      // Fallback to original endpoint
      try {
        const response = await api.post('/api/generate-playlist', {
          query: query.trim(),
          spotify_access_token: spotifyToken
        });

        setTracks(response.data.tracks);
        setPlaylistName(response.data.playlist_name);
        setSelectedTracks(new Set(response.data.tracks.map(track => track.spotify_id)));
        setStep('generated');
      } catch (fallbackErr) {
        const errorDetail = fallbackErr.response?.data?.detail || 'Failed to generate playlist';
        
        // Check if this is an AI parsing error with raw response
        if (errorDetail.includes('Failed to parse AI response|RAW_RESPONSE:')) {
          const [errorMsg, rawResponse] = errorDetail.split('|RAW_RESPONSE:');
          setError(errorMsg);
          setRawAiResponse(rawResponse);
        } else {
          // Provide more helpful error messages
          let userFriendlyError = errorDetail;
          if (errorDetail.includes('token expired')) {
            userFriendlyError = 'Your Spotify session has expired. Please reconnect your account.';
            setTimeout(() => onTokenExpired(), 2000);
          } else if (errorDetail.includes('Failed to generate')) {
            userFriendlyError = 'Unable to generate playlist suggestions. Please try a different description or try again later.';
          } else if (errorDetail.includes('Failed to search Spotify')) {
            userFriendlyError = 'Unable to search Spotify for tracks. Please check your connection and try again.';
          }
          
          setError(userFriendlyError);
          setRawAiResponse('');
        }
        setShowRawResponse(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const createPlaylist = async () => {
    console.log('Creating playlist with token:', !!spotifyToken, 'tracks:', selectedTracks.size);
    if (selectedTracks.size === 0) {
      setError('Please select at least one track');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/api/create-playlist', {
        name: playlistName,
        track_ids: Array.from(selectedTracks),
        spotify_access_token: spotifyToken,
        description: `Generated by Aelyra AI for: "${query}"`
      });

      setSuccess(`Playlist "${playlistName}" created successfully! You can find it in your Spotify account.`);
      setStep('created');
    } catch (err) {
      console.error('Create playlist error:', err);
      if (isTokenExpiredError(err)) {
        console.log('Token expired during playlist creation - redirecting to auth');
        setError('Your Spotify session has expired. Please reconnect your account.');
        setTimeout(() => onTokenExpired(), 2000); // Show error for 2 seconds before redirect
        return;
      }
      setError(err.response?.data?.detail || 'Failed to create playlist');
    } finally {
      setLoading(false);
    }
  };

  const toggleTrackSelection = (trackId) => {
    console.log('toggleTrackSelection called with:', trackId);
    console.log('Current selectedTracks:', selectedTracks);
    const newSelection = new Set(selectedTracks);
    if (newSelection.has(trackId)) {
      newSelection.delete(trackId);
      console.log('Removing track from selection');
    } else {
      newSelection.add(trackId);
      console.log('Adding track to selection');
    }
    setSelectedTracks(newSelection);
    console.log('New selection:', newSelection);
  };

  const selectAlternative = (originalTrackId, alternativeTrack) => {
    console.log('selectAlternative called:', { originalTrackId, alternativeTrack });
    const newSelection = new Set(selectedTracks);
    newSelection.delete(originalTrackId);
    newSelection.add(alternativeTrack.spotify_id);
    setSelectedTracks(newSelection);
    
    // Update the tracks array to show the selected alternative
    setTracks(tracks.map(track => {
      if (track.spotify_id === originalTrackId) {
        // Find the original track data
        const originalTrack = {
          title: track.title,
          artist: track.artist,
          spotify_id: track.spotify_id,
          album_art: track.album_art,
          preview_url: track.preview_url
        };
        
        // Remove the selected alternative from alternatives list and add original track
        const newAlternatives = track.alternatives
          .filter(alt => alt.spotify_id !== alternativeTrack.spotify_id)
          .concat([originalTrack]);
        
        // Return the alternative as the main track with updated alternatives
        return {
          ...alternativeTrack,
          alternatives: newAlternatives
        };
      }
      return track;
    }));
  };

  const startOver = () => {
    setQuery('');
    setTracks([]);
    setSelectedTracks(new Set());
    setPlaylistName('');
    setError('');
    setSuccess('');
    setStep('input');
  };

  if (loading) {
    return (
      <div className="card">
        <div className="loading">
          <h3>
            {step === 'input' ? 'Generating your playlist...' : 'Creating playlist in Spotify...'}
          </h3>
          <p>This may take a few moments.</p>
          
          {step === 'input' && tracks.length === 0 && (
            <div>
              <div style={{ textAlign: 'center', margin: '20px 0' }}>
                <video 
                  width="700"
                  autoPlay 
                  loop 
                  muted 
                  style={{ 
                    borderRadius: '8px',
                    maxWidth: '100%',
                    height: 'auto',
                    border: '1px solid #efefef'
                  }}
                >
                  <source src="/images/aelyra_thinking.mov" type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
              </div>
              
              {/* Show skeleton loading for tracks when we have some progress */}
              {foundTracks.length === 0 && progressStatus.includes('searching') && (
                <div style={{ marginTop: '30px' }}>
                  <h4 style={{ marginBottom: '15px', color: '#B3B3B3' }}>Searching for tracks...</h4>
                  <SkeletonLoader type="track" count={5} />
                </div>
              )}
            </div>
          )}
          
          {step === 'input' && (
            <div style={{ marginTop: '20px' }}>
              {progressStatus && (
                <p style={{ color: '#666', fontSize: '14px', marginBottom: '15px' }}>
                  {progressStatus}
                </p>
              )}
              
              {foundTracks.length > 0 && (
                <div style={{ 
                  maxHeight: '300px', 
                  overflowY: 'auto',
                  border: '1px solid #eee',
                  borderRadius: '8px',
                  padding: '10px',
                  backgroundColor: '#fafafa'
                }}>
                  <p style={{ 
                    fontSize: '12px', 
                    color: '#888', 
                    margin: '0 0 10px 0',
                    textAlign: 'center' 
                  }}>
                    Latest tracks found:
                  </p>
                  {foundTracks.slice(-5).map((track, index) => (
                    <div key={index} style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      marginBottom: '8px',
                      padding: '5px',
                      backgroundColor: 'white',
                      borderRadius: '4px',
                      fontSize: '12px'
                    }}>
                      {track.album_art && (
                        <img 
                          src={track.album_art} 
                          alt={track.title}
                          style={{ 
                            width: '30px', 
                            height: '30px', 
                            borderRadius: '4px',
                            marginRight: '8px',
                            objectFit: 'cover'
                          }}
                        />
                      )}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ 
                          fontWeight: '500', 
                          color: '#333',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}>
                          {track.title}
                        </div>
                        <div style={{ 
                          color: '#666',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}>
                          {track.artist}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ color: '#1db954', fontWeight: '500' }}>
          {userInfo?.display_name && (
            <>Hello, {userInfo.display_name}!</>
          )}
        </div>
        <button className="btn btn-secondary" onClick={onLogout}>
          Disconnect Spotify
        </button>
      </div>

      {step === 'input' && (
        <div className="card">
          <h2>Describe Your Perfect Playlist</h2>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            Tell us what kind of music you're looking for. Be as specific or general as you'd like!
          </p>

          <div className="form-group">
            <label htmlFor="query">Playlist Description</label>
            <textarea
              id="query"
              className="form-input textarea"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., 'Upbeat songs for a morning workout' or 'Chill indie songs for studying' or 'Classic rock anthems from the 80s'"
              rows="4"
            />
          </div>


          {error && (
            <div className="error">
              {error}
              {rawAiResponse && (
                <div style={{ marginTop: '10px' }}>
                  <button 
                    onClick={() => setShowRawResponse(!showRawResponse)}
                    style={{ 
                      background: 'none', 
                      border: '1px solid #ccc', 
                      padding: '5px 10px', 
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    {showRawResponse ? 'Hide' : 'Show'} AI Response
                  </button>
                  {showRawResponse && (
                    <div style={{ 
                      marginTop: '10px', 
                      padding: '10px', 
                      backgroundColor: '#f5f5f5', 
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      maxHeight: '200px',
                      overflow: 'auto'
                    }}>
                      {rawAiResponse}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <button className="btn" onClick={generatePlaylist}>
            Generate Playlist
          </button>
        </div>
      )}

      {step === 'generated' && tracks.length > 0 && (
        <div className="card">
          <h2>"{playlistName}"</h2>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            Here are the tracks we found for you. Select the ones you want to include, 
            or click on alternatives to swap them out.
          </p>

          <div className="track-list">
            {tracks.map((track) => (
              <div key={track.spotify_id} className={`track-item ${selectedTracks.has(track.spotify_id) ? 'selected' : ''}`}>
                {track.album_art && (
                  <img src={track.album_art} alt={track.title} className="track-artwork" />
                )}
                <div className="track-info">
                  <div className="track-title">{track.title}</div>
                  <div className="track-artist">{track.artist}</div>
                  
                  {track.alternatives && track.alternatives.length > 0 && (
                    <div className="alternatives">
                      <h4>Alternative versions:</h4>
                      {track.alternatives.map((alt, index) => (
                        <div 
                          key={alt.spotify_id} 
                          className="alternative-item"
                          onClick={() => selectAlternative(track.spotify_id, alt)}
                        >
                          {alt.album_art && (
                            <img src={alt.album_art} alt={alt.title} className="alternative-artwork" />
                          )}
                          <div>
                            <div style={{ fontSize: '14px', fontWeight: '500' }}>{alt.title}</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>{alt.artist}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <input
                  type="checkbox"
                  className="track-checkbox"
                  checked={selectedTracks.has(track.spotify_id)}
                  onChange={() => toggleTrackSelection(track.spotify_id)}
                />
              </div>
            ))}
          </div>

          <div style={{ marginTop: '30px', textAlign: 'center' }}>
            
            {error && (
              <div className="error">
                {error}
                {rawAiResponse && (
                  <div style={{ marginTop: '10px' }}>
                    <button 
                      onClick={() => setShowRawResponse(!showRawResponse)}
                      style={{ 
                        background: 'none', 
                        border: '1px solid #ccc', 
                        padding: '5px 10px', 
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      {showRawResponse ? 'Hide' : 'Show'} AI Response
                    </button>
                    {showRawResponse && (
                      <div style={{ 
                        marginTop: '10px', 
                        padding: '10px', 
                        backgroundColor: '#f5f5f5', 
                        border: '1px solid #ddd',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap',
                        maxHeight: '200px',
                        overflow: 'auto'
                      }}>
                        {rawAiResponse}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            
            <button className="btn" onClick={createPlaylist} disabled={selectedTracks.size === 0 || loading}>
              {loading ? 'Creating Playlist...' : 'Create Playlist in Spotify'}
            </button>
            <button className="btn btn-secondary" onClick={startOver}>
              Start Over
            </button>
          </div>
        </div>
      )}

      {step === 'created' && (
        <div className="card">
          <h2>Playlist Created!</h2>
          {success && <div className="success">{success}</div>}
          
          <div style={{ textAlign: 'center', marginTop: '30px' }}>
            <button className="btn" onClick={startOver}>
              Create Another Playlist
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlaylistGenerator;
