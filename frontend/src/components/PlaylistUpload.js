
import React, { useState } from 'react';
import { api } from '../config';

const PlaylistUpload = ({ spotifyToken, userInfo, onTokenExpired }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [customName, setCustomName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadResult, setUploadResult] = useState(null);

  // Helper function to check if error is token expiration
  const isTokenExpiredError = (error) => {
    return error.response?.status === 401 ||
           error.response?.data?.detail?.includes('token expired') ||
           error.response?.data?.detail?.includes('token expired or invalid');
  };

  // Parse M3U file to show preview
  const parseM3UFile = (content) => {
    const lines = content.split('\n');
    const tracks = [];
    let currentExtinf = null;

    for (const line of lines) {
      const trimmed = line.trim();

      // Skip empty lines and header
      if (!trimmed || trimmed === '#EXTM3U') continue;

      // Parse EXTINF metadata
      if (trimmed.startsWith('#EXTINF')) {
        const parts = trimmed.split(',', 2);
        if (parts.length === 2) {
          currentExtinf = parts[1].trim();
        }
        continue;
      }

      // Look for Spotify URLs
      if (trimmed.includes('spotify.com/track/') || trimmed.startsWith('spotify:track:')) {
        const trackInfo = {
          url: trimmed,
          extinf: currentExtinf || 'Unknown Track'
        };
        tracks.push(trackInfo);
        currentExtinf = null;
      }
    }

    return {
      totalTracks: tracks.length,
      tracks: tracks.slice(0, 10), // Preview first 10
      hasMore: tracks.length > 10
    };
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file extension
    if (!file.name.toLowerCase().endsWith('.m3u')) {
      setError('Please select a valid .m3u file');
      setSelectedFile(null);
      setPreviewData(null);
      return;
    }

    // Validate file size (max 100KB)
    if (file.size > 100 * 1024) {
      setError('File is too large. Maximum size is 100KB.');
      setSelectedFile(null);
      setPreviewData(null);
      return;
    }

    setSelectedFile(file);
    setError('');
    setSuccess('');
    setUploadResult(null);

    // Read file content
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target.result;
      setFileContent(content);

      try {
        const preview = parseM3UFile(content);

        if (preview.totalTracks === 0) {
          setError('No Spotify track URLs found in the file');
          setPreviewData(null);
          return;
        }

        setPreviewData(preview);
      } catch (err) {
        setError('Failed to parse M3U file');
        setPreviewData(null);
      }
    };

    reader.onerror = () => {
      setError('Failed to read file');
      setPreviewData(null);
    };

    reader.readAsText(file);
  };

  const handleUpload = async () => {
    if (!fileContent || !previewData) {
      setError('Please select a valid M3U file first');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await api.post('/api/upload-playlist', {
        m3u_content: fileContent,
        spotify_access_token: spotifyToken,
        custom_name: customName.trim() || null
      });

      setSuccess(response.data.message);
      setUploadResult({
        playlistUrl: response.data.playlist_url,
        playlistName: response.data.playlist_name,
        tracksAdded: response.data.tracks_added,
        tracksSkipped: response.data.tracks_skipped,
        warnings: response.data.warnings
      });

      // Reset form
      setSelectedFile(null);
      setFileContent('');
      setPreviewData(null);
      setCustomName('');

      // Reset file input
      const fileInput = document.getElementById('m3u-file-input');
      if (fileInput) fileInput.value = '';

    } catch (err) {
      console.error('Upload error:', err);

      if (isTokenExpiredError(err)) {
        setError('Your Spotify session has expired. Please reconnect your account.');
        setTimeout(() => onTokenExpired(), 2000);
        return;
      }

      const errorMessage = err.response?.data?.detail || 'Failed to upload playlist';
      setError(errorMessage);

    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setSelectedFile(null);
    setFileContent('');
    setPreviewData(null);
    setCustomName('');
    setError('');
    setSuccess('');
    setUploadResult(null);

    const fileInput = document.getElementById('m3u-file-input');
    if (fileInput) fileInput.value = '';
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ color: '#1db954', fontWeight: '500' }}>
          {userInfo?.display_name && (
            <>Hello, {userInfo.display_name}!</>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Upload Playlist from M3U File</h2>
        <p style={{ marginBottom: '20px', color: '#666' }}>
          Upload an M3U playlist file containing Spotify track URLs. We'll create a playlist in your Spotify account with an AI-generated name.
        </p>

        {/* File Upload Section */}
        {!uploadResult && (
          <>
            <div className="form-group">
              <label htmlFor="m3u-file-input">Select M3U File</label>
              <input
                id="m3u-file-input"
                type="file"
                accept=".m3u,.m3u8"
                onChange={handleFileSelect}
                style={{
                  display: 'block',
                  padding: '10px',
                  border: '2px dashed #ddd',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  width: '100%',
                  backgroundColor: '#fafafa'
                }}
              />
              <small style={{ color: '#666', marginTop: '5px', display: 'block' }}>
                Accepts .m3u files up to 100KB with Spotify track URLs
              </small>
            </div>

            {/* Preview Section */}
            {previewData && (
              <div style={{
                marginTop: '20px',
                padding: '15px',
                backgroundColor: '#f9f9f9',
                borderRadius: '8px',
                border: '1px solid #eee'
              }}>
                <h3 style={{ marginBottom: '10px', fontSize: '16px' }}>
                  Preview: {previewData.totalTracks} track{previewData.totalTracks !== 1 ? 's' : ''} found
                </h3>

                <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {previewData.tracks.map((track, index) => (
                    <div
                      key={index}
                      style={{
                        padding: '8px',
                        marginBottom: '5px',
                        backgroundColor: 'white',
                        borderRadius: '4px',
                        fontSize: '13px',
                        color: '#333'
                      }}
                    >
                      {index + 1}. {track.extinf}
                    </div>
                  ))}
                </div>

                {previewData.hasMore && (
                  <p style={{ marginTop: '10px', fontSize: '12px', color: '#888' }}>
                    + {previewData.totalTracks - 10} more tracks...
                  </p>
                )}
              </div>
            )}

            {/* Custom Name Input */}
            {previewData && (
              <div className="form-group" style={{ marginTop: '20px' }}>
                <label htmlFor="custom-name">Custom Playlist Name (Optional)</label>
                <input
                  id="custom-name"
                  type="text"
                  className="form-input"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="Leave blank to generate AI-powered name"
                  maxLength={100}
                />
                <small style={{ color: '#666', marginTop: '5px', display: 'block' }}>
                  If left blank, we'll generate a creative name based on your tracks
                </small>
              </div>
            )}

            {/* Error Display */}
            {error && (
              <div className="error" style={{ marginTop: '20px' }}>
                {error}
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
              <button
                className="btn"
                onClick={handleUpload}
                disabled={!previewData || loading}
              >
                {loading ? 'Uploading...' : 'Create Playlist in Spotify'}
              </button>

              {(previewData || selectedFile) && (
                <button
                  className="btn btn-secondary"
                  onClick={resetForm}
                  disabled={loading}
                >
                  Clear
                </button>
              )}
            </div>
          </>
        )}

        {/* Success Section */}
        {uploadResult && (
          <div>
            <div className="success" style={{ marginBottom: '20px' }}>
              {success}
            </div>

            <div style={{
              padding: '20px',
              backgroundColor: '#f0f8f4',
              borderRadius: '8px',
              border: '1px solid #1db954'
            }}>
              <h3 style={{ marginBottom: '15px', color: '#1db954' }}>
                Playlist Created Successfully!
              </h3>

              <div style={{ marginBottom: '10px' }}>
                <strong>Name:</strong> {uploadResult.playlistName}
              </div>

              <div style={{ marginBottom: '10px' }}>
                <strong>Tracks Added:</strong> {uploadResult.tracksAdded}
              </div>

              {uploadResult.tracksSkipped > 0 && (
                <div style={{ marginBottom: '10px', color: '#f89406' }}>
                  <strong>Tracks Skipped:</strong> {uploadResult.tracksSkipped} (not found on Spotify)
                </div>
              )}

              {uploadResult.warnings && uploadResult.warnings.length > 0 && (
                <div style={{ marginTop: '15px' }}>
                  <strong>Warnings:</strong>
                  <ul style={{ marginTop: '5px', fontSize: '13px', color: '#666' }}>
                    {uploadResult.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ marginTop: '20px' }}>
                <a
                  href={uploadResult.playlistUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn"
                  style={{ textDecoration: 'none', display: 'inline-block' }}
                >
                  Open in Spotify
                </a>
              </div>
            </div>

            <div style={{ marginTop: '20px' }}>
              <button className="btn btn-secondary" onClick={resetForm}>
                Upload Another Playlist
              </button>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="loading" style={{ marginTop: '20px' }}>
            <h3>Creating your playlist...</h3>
            <p>Verifying tracks and uploading to Spotify</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default PlaylistUpload;
