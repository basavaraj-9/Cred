import React from 'react';

const ProfessionalLoading = ({ message = 'Loading...', size = 'medium', fullScreen = false }) => {
  const getSize = () => {
    switch (size) {
      case 'small': return { container: '40px', spinner: '24px', text: '14px' };
      case 'large': return { container: '120px', spinner: '48px', text: '18px' };
      default: return { container: '80px', spinner: '32px', text: '16px' };
    }
  };

  const dimensions = getSize();

  const containerStyle = fullScreen ? {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999
  } : {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: dimensions.container
  };

  return (
    <div style={containerStyle}>
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '16px',
        padding: '32px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)',
        animation: 'fadeIn 0.3s ease-out'
      }}>
        <div style={{
          width: dimensions.spinner,
          height: dimensions.spinner,
          border: '3px solid #f1f5f9',
          borderTop: '3px solid #3b82f6',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
          marginBottom: '16px'
        }}></div>
        
        <div style={{
          fontSize: dimensions.text,
          fontWeight: '600',
          color: '#374151',
          textAlign: 'center'
        }}>
          {message}
        </div>
        
        <div style={{
          display: 'flex',
          gap: '4px',
          marginTop: '12px'
        }}>
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: '#3b82f6',
            animation: 'pulse 1.5s infinite',
            animationDelay: '0s'
          }}></div>
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: '#3b82f6',
            animation: 'pulse 1.5s infinite',
            animationDelay: '0.2s'
          }}></div>
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: '#3b82f6',
            animation: 'pulse 1.5s infinite',
            animationDelay: '0.4s'
          }}></div>
        </div>
      </div>
    </div>
  );
};

export default ProfessionalLoading;
