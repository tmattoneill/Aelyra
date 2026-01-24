
import React, { useState, useRef, useEffect } from 'react';
import { api } from '../config';
import SkeletonLoader from './SkeletonLoader';

const PlaylistGenerator = ({ spotifyToken, userInfo, onLogout, onTokenExpired }) => {
  const [query, setQuery] = useState('');
  const [trackCount, setTrackCount] = useState(10);
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
  const [currentPass, setCurrentPass] = useState('');
  const [passProgress, setPassProgress] = useState({
    analyze: { status: 'pending', message: '' },
    generate: { status: 'pending', message: '' },
    validate: { status: 'pending', message: '' },
    search: { status: 'pending', message: '' }
  });

  // Refs for cleanup (prevent memory leaks)
  const phraseIntervalRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Cycling search phrases
  const MESSAGE_CYCLE_SPEED = 4000; // milliseconds between phrase changes (4 seconds)
  const [currentSearchPhrase, setCurrentSearchPhrase] = useState('');

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Clear any running interval
      if (phraseIntervalRef.current) {
        clearInterval(phraseIntervalRef.current);
        phraseIntervalRef.current = null;
      }
      // Abort any in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  const searchPhrases = [
    "Digging through vinyl crates",
    "Matching beats per minute",
    "Cross-referencing obscure B-sides",
    "Cracking the liner notes",
    "Finding that lost deep cut",
    "Scanning old mixtape labels",
    "Tuning the signal",
    "Tagging unknown frequencies",
    "Dusting off rare grooves",
    "Checking underground charts",
    "Flipping through back catalogs",
    "Decoding handwriting on tapes",
    "Warming up the turntables",
    "Syncing cue points",
    "Reading metadata from cassettes"
  ];

  // Track count presets
  const trackCountPresets = [10, 25, 50, 100];

  // Helper function to check if error is token expiration
  const isTokenExpiredError = (error) => {
    return error.response?.status === 401 ||
           error.response?.data?.detail?.includes('token expired') ||
           error.response?.data?.detail?.includes('token expired or invalid');
  };

  const generatePlaylist = async () => {
    if (!query.trim()) {
      setError('Please enter a description for your playlist');
      return;
    }

    // Abort any existing request before starting a new one
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Clear any existing interval
    if (phraseIntervalRef.current) {
      clearInterval(phraseIntervalRef.current);
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setProgressStatus('');
    setFoundTracks([]);
    setCurrentPass('');
    setPassProgress({
      analyze: { status: 'pending', message: '' },
      generate: { status: 'pending', message: '' },
      validate: { status: 'pending', message: '' },
      search: { status: 'pending', message: '' }
    });

    // Start cycling through search phrases
    let phraseIndex = 0;
    setCurrentSearchPhrase(searchPhrases[phraseIndex]);

    phraseIntervalRef.current = setInterval(() => {
      phraseIndex = (phraseIndex + 1) % searchPhrases.length;
      setCurrentSearchPhrase(searchPhrases[phraseIndex]);
    }, MESSAGE_CYCLE_SPEED);

    try {
      // Use streaming endpoint for real-time feedback
      const response = await fetch(`${api.defaults.baseURL}/api/generate-playlist-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query.trim(),
          spotify_access_token: spotifyToken,
          track_count: trackCount
        }),
        signal: abortControllerRef.current.signal
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

              if (data.type === 'pass_start') {
                setCurrentPass(data.pass);
                setPassProgress(prev => ({
                  ...prev,
                  [data.pass]: { status: 'in_progress', message: data.message }
                }));
                setProgressStatus(data.message);
              } else if (data.type === 'pass_progress') {
                setPassProgress(prev => ({
                  ...prev,
                  [data.pass]: { ...prev[data.pass], message: data.message }
                }));
                setProgressStatus(data.message);
              } else if (data.type === 'pass_complete') {
                setPassProgress(prev => ({
                  ...prev,
                  [data.pass]: { status: 'complete', message: data.message }
                }));
                setProgressStatus(data.message);
              } else if (data.type === 'status') {
                setProgressStatus(data.message);
              } else if (data.type === 'track_found') {
                setFoundTracks(prev => [...prev, data.track]);
                setProgressStatus(`Found ${data.count} tracks...`);
              } else if (data.type === 'complete') {
                setTracks(data.playlist.tracks);
                setPlaylistName(data.playlist.playlist_name);
                // Select all tracks by default
                setSelectedTracks(new Set(data.playlist.tracks.map(track => track.spotify_id)));
                setStep('generated');
                setLoading(false);
                // Stop cycling phrases
                if (phraseIntervalRef.current) {
                  clearInterval(phraseIntervalRef.current);
                  phraseIntervalRef.current = null;
                }
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
      // Don't show error if request was aborted (component unmounted or new request started)
      if (err.name === 'AbortError') {
        return;
      }

      console.error('Streaming error, falling back to regular endpoint:', err);

      // Fallback to original endpoint
      try {
        const response = await api.post('/api/generate-playlist', {
          query: query.trim(),
          spotify_access_token: spotifyToken,
          track_count: trackCount
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
      // Stop cycling phrases
      if (phraseIntervalRef.current) {
        clearInterval(phraseIntervalRef.current);
        phraseIntervalRef.current = null;
      }
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
    const newSelection = new Set(selectedTracks);
    if (newSelection.has(trackId)) {
      newSelection.delete(trackId);
    } else {
      newSelection.add(trackId);
    }
    setSelectedTracks(newSelection);
  };

  const selectAll = () => {
    setSelectedTracks(new Set(tracks.map(track => track.spotify_id)));
  };

  const deselectAll = () => {
    setSelectedTracks(new Set());
  };

  const startOver = () => {
    setQuery('');
    setTrackCount(10);
    setTracks([]);
    setSelectedTracks(new Set());
    setPlaylistName('');
    setError('');
    setSuccess('');
    setStep('input');
  };

  // Pass progress indicator component
  const PassProgressIndicator = () => {
    const passes = [
      { key: 'analyze', label: 'Analyze', icon: '1' },
      { key: 'generate', label: 'Generate', icon: '2' },
      { key: 'validate', label: 'Validate', icon: '3' },
      { key: 'search', label: 'Search', icon: '4' }
    ];

    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: '20px',
        marginBottom: '20px',
        flexWrap: 'wrap'
      }}>
        {passes.map((pass, index) => {
          const status = passProgress[pass.key].status;
          const isActive = status === 'in_progress';
          const isComplete = status === 'complete';

          return (
            <div key={pass.key} style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              opacity: status === 'pending' ? 0.4 : 1,
              transition: 'opacity 0.3s'
            }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: isComplete ? '#1db954' : isActive ? '#1db954' : '#333',
                color: 'white',
                fontWeight: 'bold',
                fontSize: '14px',
                marginBottom: '6px',
                animation: isActive ? 'pulse 1.5s infinite' : 'none'
              }}>
                {isComplete ? '\u2713' : pass.icon}
              </div>
              <span style={{
                fontSize: '12px',
                color: isActive || isComplete ? '#1db954' : '#888',
                fontWeight: isActive ? 'bold' : 'normal'
              }}>
                {pass.label}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="card">
        <div className="loading">
          <h3>
            {step === 'input' ? 'Generating your playlist...' : 'Creating playlist in Spotify...'}
          </h3>
          <p>{step === 'input' ? currentSearchPhrase : 'Adding tracks to your Spotify account...'}</p>

          {step === 'input' && tracks.length === 0 && (
            <div>
              {/* Pass progress indicator */}
              <PassProgressIndicator />

              {/* Current pass message */}
              {progressStatus && (
                <p style={{
                  color: '#1db954',
                  fontSize: '14px',
                  marginBottom: '15px',
                  textAlign: 'center',
                  fontWeight: '500'
                }}>
                  {progressStatus}
                </p>
              )}

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

              {/* Show skeleton loading for tracks when searching */}
              {currentPass === 'search' && foundTracks.length === 0 && (
                <div style={{ marginTop: '30px' }}>
                  <h4 style={{ marginBottom: '15px', color: '#B3B3B3' }}>Searching for tracks...</h4>
                  <SkeletonLoader type="track" count={5} />
                </div>
              )}
            </div>
          )}

          {step === 'input' && foundTracks.length > 0 && (
            <div style={{ marginTop: '20px' }}>
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
                  Found {foundTracks.length} tracks:
                </p>
                {foundTracks.slice(-8).map((track, index) => (
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
            </div>
          )}
        </div>
        <style>{`
          @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(29, 185, 84, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(29, 185, 84, 0); }
            100% { box-shadow: 0 0 0 0 rgba(29, 185, 84, 0); }
          }
        `}</style>
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

          {/* Track count selector */}
          <div className="form-group" style={{ marginTop: '20px' }}>
            <label htmlFor="trackCount">Number of Tracks: <strong>{trackCount}</strong></label>

            {/* Quick preset buttons */}
            <div style={{
              display: 'flex',
              gap: '10px',
              marginBottom: '12px',
              flexWrap: 'wrap'
            }}>
              {trackCountPresets.map(preset => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setTrackCount(preset)}
                  style={{
                    padding: '8px 16px',
                    border: trackCount === preset ? '2px solid #1db954' : '1px solid #ddd',
                    borderRadius: '20px',
                    backgroundColor: trackCount === preset ? '#1db954' : 'white',
                    color: trackCount === preset ? 'white' : '#333',
                    cursor: 'pointer',
                    fontWeight: trackCount === preset ? 'bold' : 'normal',
                    transition: 'all 0.2s'
                  }}
                >
                  {preset} tracks
                </button>
              ))}
            </div>

            {/* Slider */}
            <input
              type="range"
              id="trackCount"
              min="5"
              max="100"
              value={trackCount}
              onChange={(e) => setTrackCount(parseInt(e.target.value))}
              style={{
                width: '100%',
                height: '8px',
                borderRadius: '4px',
                background: `linear-gradient(to right, #1db954 ${(trackCount - 5) / 95 * 100}%, #ddd ${(trackCount - 5) / 95 * 100}%)`,
                outline: 'none',
                cursor: 'pointer'
              }}
            />
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '12px',
              color: '#888',
              marginTop: '4px'
            }}>
              <span>5</span>
              <span>100</span>
            </div>
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
          <p style={{ marginBottom: '10px', color: '#666' }}>
            Here are {tracks.length} tracks we found for you. Uncheck any you don't want to include.
          </p>

          {/* Selection controls */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '15px',
            padding: '10px',
            backgroundColor: '#f5f5f5',
            borderRadius: '8px'
          }}>
            <span style={{ color: '#666' }}>
              {selectedTracks.size} of {tracks.length} tracks selected
            </span>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={selectAll}
                style={{
                  padding: '6px 12px',
                  border: '1px solid #1db954',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  color: '#1db954',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Select All
              </button>
              <button
                onClick={deselectAll}
                style={{
                  padding: '6px 12px',
                  border: '1px solid #999',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  color: '#666',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Deselect All
              </button>
            </div>
          </div>

          <div className="track-list">
            {tracks.map((track, index) => (
              <div
                key={track.spotify_id}
                className={`track-item ${selectedTracks.has(track.spotify_id) ? 'selected' : ''}`}
                style={{ opacity: selectedTracks.has(track.spotify_id) ? 1 : 0.6 }}
              >
                <span style={{
                  minWidth: '24px',
                  color: '#888',
                  fontSize: '12px',
                  marginRight: '10px'
                }}>
                  {index + 1}
                </span>
                {track.album_art && (
                  <img src={track.album_art} alt={track.title} className="track-artwork" />
                )}
                <div className="track-info">
                  <div className="track-title">{track.title}</div>
                  <div className="track-artist">{track.artist}</div>
                  {track.album && track.album !== 'Unknown Album' && (
                    <div style={{ fontSize: '11px', color: '#888', marginTop: '2px' }}>
                      {track.album}
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
              {loading ? 'Creating Playlist...' : `Create Playlist in Spotify (${selectedTracks.size} tracks)`}
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
