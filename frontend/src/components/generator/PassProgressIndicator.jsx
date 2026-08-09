import React from 'react';

const PASSES = [
  { key: 'analyze', label: 'Analyse' },
  { key: 'generate', label: 'Generate' },
  { key: 'validate', label: 'Validate' },
  { key: 'search', label: 'Search' },
];

/**
 * The four-stage progress rail shown while a playlist is generating.
 *
 * Lives in its own module because it was previously declared inside
 * PlaylistGenerator's render. React saw a brand-new component type on every
 * render and remounted the whole subtree, restarting the pulse animation
 * constantly.
 */
export default function PassProgressIndicator({ passProgress }) {
  return (
    <div className="pass-track">
      {PASSES.map(({ key, label }) => {
        const state = passProgress[key] ?? 'pending';
        return (
          <div key={key} className={`pass-node ${state}`}>
            {state === 'complete' ? '✓ ' : ''}
            {label}
          </div>
        );
      })}
    </div>
  );
}
