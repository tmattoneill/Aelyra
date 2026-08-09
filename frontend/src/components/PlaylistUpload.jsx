import React, { useRef, useState } from 'react';

import { api, errorMessage } from '../config';

const MAX_BYTES = 100 * 1024;
// Both extensions are accepted here and by the backend parser; the file picker
// used to offer .m3u8 and then reject whatever the user chose.
const ACCEPTED = ['.m3u', '.m3u8'];

function extractPreview(content) {
  const lines = content.split('\n');
  const tracks = [];
  let pendingTitle = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;

    if (line.startsWith('#EXTINF')) {
      // Split once only: a title containing commas must survive intact.
      const commaIndex = line.indexOf(',');
      pendingTitle = commaIndex === -1 ? null : line.slice(commaIndex + 1).trim();
      continue;
    }

    if (line.includes('spotify.com/track/') || line.includes('spotify:track:')) {
      tracks.push(pendingTitle || 'Spotify track');
      pendingTitle = null;
    }
  }

  return tracks;
}

export default function PlaylistUpload({ onTokenExpired }) {
  const [fileName, setFileName] = useState('');
  const [fileContent, setFileContent] = useState('');
  const [preview, setPreview] = useState(null);
  const [customName, setCustomName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  const clear = () => {
    setFileName('');
    setFileContent('');
    setPreview(null);
    setCustomName('');
    setError(null);
    setResult(null);
    // A ref rather than document.getElementById, which reached outside React.
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setResult(null);

    const lower = file.name.toLowerCase();
    if (!ACCEPTED.some((ext) => lower.endsWith(ext))) {
      setError('Please choose a .m3u or .m3u8 file.');
      return;
    }
    if (file.size > MAX_BYTES) {
      setError('That file is too large (100KB maximum).');
      return;
    }

    const content = await file.text();
    const tracks = extractPreview(content);

    if (tracks.length === 0) {
      setError('No Spotify track links were found in that file.');
      clear();
      return;
    }

    setFileName(file.name);
    setFileContent(content);
    setPreview(tracks);
  };

  const upload = async () => {
    setUploading(true);
    setError(null);
    try {
      const { data } = await api.post('/api/upload-playlist', {
        m3u_content: fileContent,
        custom_name: customName.trim() || null,
      });
      setResult(data);
    } catch (err) {
      if (err.response?.status === 401) {
        onTokenExpired?.();
        return;
      }
      setError(errorMessage(err, 'Could not create the playlist from that file.'));
    } finally {
      setUploading(false);
    }
  };

  if (result) {
    return (
      <div className="card">
        <div className="success" role="status">
          <h2 style={{ marginBottom: 8 }}>Playlist created</h2>
          <p>
            &ldquo;{result.playlist_name}&rdquo; with {result.tracks_added}{' '}
            {result.tracks_added === 1 ? 'track' : 'tracks'}
            {result.tracks_skipped > 0 && `, ${result.tracks_skipped} skipped`}.
          </p>
        </div>

        {result.warnings?.length > 0 && (
          <div className="warning">
            <strong>Notes</strong>
            <ul style={{ margin: '8px 0 0 20px' }}>
              {result.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="btn-row">
          {result.playlist_url && (
            <a
              className="btn"
              href={result.playlist_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-block', textDecoration: 'none' }}
            >
              Open in Spotify
            </a>
          )}
          <button type="button" className="btn btn-secondary" onClick={clear}>
            Upload another
          </button>
        </div>
      </div>
    );
  }

  if (uploading) {
    return (
      <div className="card">
        <div className="loading">
          <h3>Creating your playlist…</h3>
          <p>Checking each track against Spotify.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Upload a playlist</h2>
      <p className="text-muted" style={{ margin: '12px 0 20px' }}>
        Import an M3U file containing Spotify track links. Up to 500 tracks, 100KB.
      </p>

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}

      <div className="form-group">
        <label htmlFor="m3u-file">M3U file</label>
        <input
          id="m3u-file"
          ref={inputRef}
          type="file"
          className="form-input"
          accept={ACCEPTED.join(',')}
          onChange={handleFile}
        />
      </div>

      {preview && (
        <>
          <div className="panel" style={{ marginBottom: 20 }}>
            <p style={{ marginBottom: 10 }}>
              <strong>{fileName}</strong>
              <span className="text-faint"> — {preview.length} tracks found</span>
            </p>
            <ul style={{ margin: '0 0 0 20px' }} className="text-muted">
              {preview.slice(0, 10).map((title, i) => (
                <li key={i}>{title}</li>
              ))}
            </ul>
            {preview.length > 10 && (
              <p className="text-faint" style={{ marginTop: 8 }}>
                …and {preview.length - 10} more
              </p>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="playlist-name">Playlist name (optional)</label>
            <input
              id="playlist-name"
              className="form-input"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="Leave blank to have one generated"
              maxLength={200}
            />
          </div>

          <div className="btn-row">
            <button type="button" className="btn" onClick={upload}>
              Create playlist in Spotify
            </button>
            <button type="button" className="btn btn-secondary" onClick={clear}>
              Clear
            </button>
          </div>
        </>
      )}
    </div>
  );
}
