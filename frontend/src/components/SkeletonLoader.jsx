import React from 'react';

/**
 * Placeholder rows shown while tracks are being resolved.
 * Animation lives in index.css rather than an injected <style> tag, which was
 * previously re-added to the document on every render.
 */
export default function SkeletonLoader({ count = 3 }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div className="track-item" key={i}>
          <div className="skeleton track-artwork" />
          <div className="track-info">
            <div className="skeleton" style={{ height: 14, width: '55%', marginBottom: 8 }} />
            <div className="skeleton" style={{ height: 12, width: '35%' }} />
          </div>
        </div>
      ))}
    </div>
  );
}
