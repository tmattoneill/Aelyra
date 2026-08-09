import React from 'react';

const FALLBACK_ART = '/images/aelyra_logo_1024x1024.png';

/**
 * The reviewable track list. Selection is keyed on Spotify id, and the whole
 * row is the control rather than just the checkbox, which was a small target
 * on touch devices.
 */
export default function TrackReviewList({ tracks, selectedIds, onToggle, onSelectAll, onDeselectAll }) {
  return (
    <>
      <div className="selection-bar">
        <span className="text-muted">
          {selectedIds.size} of {tracks.length} tracks selected
        </span>
        <div className="btn-row">
          <button type="button" className="btn btn-secondary btn-small" onClick={onSelectAll}>
            Select all
          </button>
          <button type="button" className="btn btn-secondary btn-small" onClick={onDeselectAll}>
            Deselect all
          </button>
        </div>
      </div>

      <ul className="track-list" style={{ listStyle: 'none' }}>
        {tracks.map((track, index) => {
          const selected = selectedIds.has(track.spotify_id);
          return (
            <li key={track.spotify_id}>
              <button
                type="button"
                className={`track-item ${selected ? 'selected' : 'deselected'}`}
                onClick={() => onToggle(track.spotify_id)}
                aria-pressed={selected}
                aria-label={`${selected ? 'Remove' : 'Add'} ${track.title} by ${track.artist}`}
              >
                <span className="track-number">{index + 1}</span>
                <img
                  className="track-artwork"
                  src={track.album_art || FALLBACK_ART}
                  alt=""
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.src = FALLBACK_ART;
                  }}
                />
                <span className="track-info">
                  <span className="track-title" style={{ display: 'block' }}>{track.title}</span>
                  <span className="track-artist">{track.artist}</span>
                </span>
                {/* Presentational: the row carries the semantics via aria-pressed. */}
                <input
                  type="checkbox"
                  className="track-checkbox"
                  checked={selected}
                  readOnly
                  tabIndex={-1}
                  aria-hidden="true"
                />
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}
