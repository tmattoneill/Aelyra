import React from 'react';

import { clearSession } from '../auth/authStore';

/**
 * Catches render-time crashes so the app shows something useful rather than a
 * blank page. Styling comes from index.css instead of inline objects with
 * e.target hover mutation, which fired on whichever child was hovered.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled error in component tree:', error, errorInfo);
  }

  handleReset = () => {
    clearSession();
    window.location.href = '/';
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="container">
        <div className="card">
          <div className="empty-state">
            <h3>Something went wrong</h3>
            <p>The page hit an unexpected error. Reloading usually clears it.</p>

            {import.meta.env.DEV && this.state.error && (
              <pre
                className="panel"
                style={{
                  textAlign: 'left',
                  marginTop: 20,
                  overflowX: 'auto',
                  fontSize: 13,
                }}
              >
                {String(this.state.error?.stack || this.state.error)}
              </pre>
            )}

            <div className="btn-row" style={{ justifyContent: 'center', marginTop: 20 }}>
              <button type="button" className="btn" onClick={() => window.location.reload()}>
                Reload page
              </button>
              <button type="button" className="btn btn-secondary" onClick={this.handleReset}>
                Reset session
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
