import React from 'react';

const SkeletonLoader = ({ type = 'track', count = 1 }) => {
  const renderTrackSkeleton = () => (
    <div className="skeleton-track" style={{
      display: 'flex',
      alignItems: 'center',
      padding: '15px',
      backgroundColor: '#3E3E3E',
      borderRadius: '8px',
      marginBottom: '10px',
      animation: 'skeleton-loading 1.5s infinite ease-in-out'
    }}>
      {/* Album art skeleton */}
      <div style={{
        width: '60px',
        height: '60px',
        backgroundColor: '#535353',
        borderRadius: '4px',
        marginRight: '15px'
      }} />
      
      {/* Track info skeleton */}
      <div style={{ flex: 1 }}>
        {/* Track title */}
        <div style={{
          height: '16px',
          backgroundColor: '#535353',
          borderRadius: '4px',
          marginBottom: '8px',
          width: '70%'
        }} />
        
        {/* Artist name */}
        <div style={{
          height: '14px',
          backgroundColor: '#535353',
          borderRadius: '4px',
          width: '50%'
        }} />
      </div>
      
      {/* Checkbox skeleton */}
      <div style={{
        width: '20px',
        height: '20px',
        backgroundColor: '#535353',
        borderRadius: '3px'
      }} />
    </div>
  );

  const renderCardSkeleton = () => (
    <div className="skeleton-card" style={{
      backgroundColor: '#282828',
      borderRadius: '8px',
      padding: '30px',
      marginBottom: '30px',
      border: '1px solid #404040'
    }}>
      {/* Title skeleton */}
      <div style={{
        height: '32px',
        backgroundColor: '#404040',
        borderRadius: '4px',
        marginBottom: '20px',
        width: '60%'
      }} />
      
      {/* Content skeleton */}
      <div style={{
        height: '16px',
        backgroundColor: '#404040',
        borderRadius: '4px',
        marginBottom: '10px',
        width: '90%'
      }} />
      <div style={{
        height: '16px',
        backgroundColor: '#404040',
        borderRadius: '4px',
        marginBottom: '20px',
        width: '75%'
      }} />
    </div>
  );

  const skeletons = [];
  for (let i = 0; i < count; i++) {
    skeletons.push(
      <div key={i}>
        {type === 'track' ? renderTrackSkeleton() : renderCardSkeleton()}
      </div>
    );
  }

  return (
    <div className="skeleton-loader">
      <style>{`
        @keyframes skeleton-loading {
          0% {
            opacity: 1;
          }
          50% {
            opacity: 0.7;
          }
          100% {
            opacity: 1;
          }
        }
      `}</style>
      {skeletons}
    </div>
  );
};

export default SkeletonLoader;