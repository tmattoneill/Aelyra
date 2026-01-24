import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error to console for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    // Clear session storage and reload
    sessionStorage.removeItem('spotify_token');
    sessionStorage.removeItem('user_info');
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#121212',
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: '#282828',
            borderRadius: '8px',
            padding: '40px',
            maxWidth: '500px',
            textAlign: 'center',
            color: '#fff'
          }}>
            <h2 style={{
              fontSize: '24px',
              marginBottom: '16px',
              color: '#1DB954'
            }}>
              Something went wrong
            </h2>
            <p style={{
              color: '#B3B3B3',
              marginBottom: '24px',
              lineHeight: '1.5'
            }}>
              An unexpected error occurred. Please try reloading the page.
              If the problem persists, try resetting your session.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details style={{
                textAlign: 'left',
                marginBottom: '24px',
                padding: '16px',
                backgroundColor: '#1a1a1a',
                borderRadius: '4px',
                fontSize: '12px',
                color: '#ff6b6b'
              }}>
                <summary style={{ cursor: 'pointer', marginBottom: '8px' }}>
                  Error Details
                </summary>
                <pre style={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  margin: 0
                }}>
                  {this.state.error.toString()}
                  {this.state.errorInfo && this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button
                onClick={this.handleReload}
                style={{
                  backgroundColor: '#1DB954',
                  color: '#000',
                  border: 'none',
                  padding: '12px 24px',
                  borderRadius: '20px',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#1ed760'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#1DB954'}
              >
                Reload Page
              </button>
              <button
                onClick={this.handleReset}
                style={{
                  backgroundColor: 'transparent',
                  color: '#B3B3B3',
                  border: '1px solid #B3B3B3',
                  padding: '12px 24px',
                  borderRadius: '20px',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => {
                  e.target.style.color = '#fff';
                  e.target.style.borderColor = '#fff';
                }}
                onMouseOut={(e) => {
                  e.target.style.color = '#B3B3B3';
                  e.target.style.borderColor = '#B3B3B3';
                }}
              >
                Reset Session
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
