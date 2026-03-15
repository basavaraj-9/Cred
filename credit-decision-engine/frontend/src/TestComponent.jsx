import React from 'react';

const TestComponent = () => {
  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#f0f9ff', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      flexDirection: 'column',
      padding: '20px'
    }}>
      <h1 style={{ fontSize: '48px', color: '#2563eb', marginBottom: '20px' }}>
        🎉 Test Component Working!
      </h1>
      <p style={{ fontSize: '24px', color: '#4b5563', textAlign: 'center' }}>
        If you can see this, React is working properly.
      </p>
      <div style={{ 
        backgroundColor: 'white', 
        padding: '20px', 
        borderRadius: '12px', 
        marginTop: '20px',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
      }}>
        <p style={{ fontSize: '16px', color: '#374151' }}>
          The issue might be with the dashboard component or routing.
        </p>
      </div>
    </div>
  );
};

export default TestComponent;
