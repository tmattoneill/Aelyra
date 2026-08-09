import React, { useEffect, useState } from 'react';

import SkeletonLoader from '../SkeletonLoader';
import PassProgressIndicator from './PassProgressIndicator';

const PHRASES = [
  'Digging through the crates…',
  'Cross-referencing b-sides…',
  'Checking what actually exists on Spotify…',
  'Balancing the artist spread…',
  'Sequencing the running order…',
];

export default function GenerationProgress({
  passProgress,
  currentPass,
  statusMessage,
  foundTracks,
  onCancel,
}) {
  const [phraseIndex, setPhraseIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setPhraseIndex((i) => (i + 1) % PHRASES.length), 4000);
    return () => clearInterval(id);
  }, []);

  // Only the last few, newest first, so the feed does not grow without bound.
  const recentTracks = foundTracks.slice(-8).reverse();

  return (
    <div className="card">
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ marginBottom: 8 }}>Building your playlist</h2>
        <p className="text-muted">{PHRASES[phraseIndex]}</p>
      </div>

      <PassProgressIndicator passProgress={passProgress} />

      {/* Announced to screen readers as it changes, which the old status text was not. */}
      <p className="text-muted" style={{ textAlign: 'center' }} aria-live="polite">
        {statusMessage}
      </p>

      <div className="btn-row" style={{ justifyContent: 'center', marginTop: 20 }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {currentPass === 'search' && (
        <div className="found-feed">
          {recentTracks.length > 0 ? (
            <>
              <p className="text-faint" style={{ marginBottom: 10 }}>
                Found {foundTracks.length} so far
              </p>
              {recentTracks.map((track) => (
                <div className="track-item" key={track.spotify_id ?? `${track.title}-${track.artist}`}>
                  <img className="track-artwork" src={track.album_art} alt="" loading="lazy" />
                  <span className="track-info">
                    <span className="track-title" style={{ display: 'block' }}>{track.title}</span>
                    <span className="track-artist">{track.artist}</span>
                  </span>
                </div>
              ))}
            </>
          ) : (
            <SkeletonLoader count={4} />
          )}
        </div>
      )}
    </div>
  );
}
