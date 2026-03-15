import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const ProfessionalNavigation = ({ title, subtitle, showBackButton = false }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Upload', icon: '📤' },
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/research', label: 'Research', icon: '📈' },
    { path: '/cam-preview', label: 'CAM', icon: '📄' }
  ];

  const isActive = (path) => location.pathname === path;

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.1)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
      padding: '16px 0',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      position: 'sticky',
      top: 0,
      zIndex: 1000
    }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {showBackButton && (
              <button
                onClick={() => navigate(-1)}
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  borderRadius: '8px',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                ← Back
              </button>
            )}
            <div>
              <h1 style={{ 
                fontSize: '28px', 
                fontWeight: 'bold', 
                marginBottom: '4px', 
                color: 'white',
                textShadow: '0 2px 4px rgba(0,0,0,0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                {title}
              </h1>
              {subtitle && (
                <p style={{ 
                  fontSize: '14px', 
                  color: 'rgba(255, 255, 255, 0.9)',
                  fontWeight: '400',
                  margin: 0
                }}>
                  {subtitle}
                </p>
              )}
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {navItems.map((item) => (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                style={{
                  backgroundColor: isActive(item.path) 
                    ? 'rgba(255, 255, 255, 0.3)' 
                    : 'rgba(255, 255, 255, 0.1)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  border: isActive(item.path) 
                    ? '2px solid rgba(255, 255, 255, 0.5)' 
                    : '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '8px',
                  padding: '10px 16px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: isActive(item.path) ? '700' : '600',
                  transition: 'all 0.3s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: isActive(item.path) 
                    ? '0 4px 6px rgba(0, 0, 0, 0.2)' 
                    : '0 2px 4px rgba(0, 0, 0, 0.1)'
                }}
              >
                <span style={{ fontSize: '16px' }}>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfessionalNavigation;
