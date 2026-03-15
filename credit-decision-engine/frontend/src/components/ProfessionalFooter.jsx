import React from 'react';

const ProfessionalFooter = () => {
  const currentYear = new Date().getFullYear();
  
  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.1)',
      backdropFilter: 'blur(20px)',
      borderTop: '1px solid rgba(255, 255, 255, 0.2)',
      padding: '24px 0',
      marginTop: 'auto'
    }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '24px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              background: 'linear-gradient(135deg, #667eea, #764ba2)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '16px',
              fontWeight: 'bold',
              color: 'white'
            }}>
              AI
            </div>
            <div>
              <p style={{ 
                fontSize: '14px', 
                fontWeight: '600', 
                color: 'white', 
                margin: '0' 
              }}>
                AI Credit Decisioning Engine
              </p>
              <p style={{ 
                fontSize: '12px', 
                color: 'rgba(255, 255, 255, 0.8)', 
                margin: '0' 
              }}>
                Professional Credit Analysis System
              </p>
            </div>
          </div>
          
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '24px',
            fontSize: '12px',
            color: 'rgba(255, 255, 255, 0.8)'
          }}>
            <span>© {currentYear} All rights reserved</span>
            <span>•</span>
            <span style={{ cursor: 'pointer', transition: 'color 0.3s ease' }}>
              Privacy Policy
            </span>
            <span>•</span>
            <span style={{ cursor: 'pointer', transition: 'color 0.3s ease' }}>
              Terms of Service
            </span>
          </div>
        </div>
        
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          textAlign: 'center'
        }}>
          <p style={{ 
            fontSize: '11px', 
            color: 'rgba(255, 255, 255, 0.6)', 
            margin: 0 
          }}>
            Powered by Advanced AI Technology | Version 2.0.1 | Last Updated: {new Date().toLocaleDateString()}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProfessionalFooter;
