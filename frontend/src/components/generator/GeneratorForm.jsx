import React from 'react';

const PRESETS = [10, 25, 50, 100];

const EXAMPLES = [
  'Chill indie for a rainy Sunday morning',
  '90s hip hop for a road trip',
  'Upbeat songs to run to, nothing over 4 minutes',
  'Melancholy jazz like Bill Evans',
];

export default function GeneratorForm({
  query,
  onQueryChange,
  trackCount,
  onTrackCountChange,
  onSubmit,
  disabled,
}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || disabled) return;
    onSubmit();
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="playlist-query">Describe the playlist you want</label>
        <textarea
          id="playlist-query"
          className="form-input textarea"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="e.g. chill indie for a rainy Sunday morning"
          maxLength={2000}
          disabled={disabled}
        />
        <p className="form-hint">
          Mention genres, moods, eras or artists to sound like. Naming an artist
          finds music similar to them rather than their own tracks.
        </p>
      </div>

      <div className="form-group">
        <span id="track-count-label" style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>
          How many tracks? ({trackCount})
        </span>
        <div className="preset-row" role="group" aria-labelledby="track-count-label">
          {PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              className="preset-btn"
              aria-pressed={trackCount === preset}
              onClick={() => onTrackCountChange(preset)}
              disabled={disabled}
            >
              {preset}
            </button>
          ))}
        </div>
        <input
          type="range"
          className="slider"
          min="5"
          max="100"
          step="5"
          value={trackCount}
          onChange={(e) => onTrackCountChange(Number(e.target.value))}
          aria-label="Number of tracks"
          disabled={disabled}
        />
      </div>

      <div className="btn-row">
        <button type="submit" className="btn" disabled={disabled || !query.trim()}>
          Generate Playlist
        </button>
      </div>

      <div style={{ marginTop: 24 }}>
        <p className="text-faint" style={{ marginBottom: 8 }}>Try one of these:</p>
        <div className="preset-row">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="preset-btn"
              onClick={() => onQueryChange(example)}
              disabled={disabled}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}
