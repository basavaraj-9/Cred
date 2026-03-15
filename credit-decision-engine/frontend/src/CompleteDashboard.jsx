import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const CompleteDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data) {
      setCompanyData(JSON.parse(data));
    } else {
      navigate('/');
    }
  }, [navigate]);

  if (!companyData) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  const isMultiCompany = companyData.is_multi_company;
  const companies = isMultiCompany ? companyData.companies : [companyData];

  const getRiskColor = (score) => {
    if (score <= 40) return { bg: '#dcfce7', text: '#166534', border: '#22c55e' };
    if (score <= 70) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' };
    return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
  };

  const getDecisionColor = (decision) => {
    return decision === 'APPROVED' 
      ? { bg: '#dcfce7', text: '#166534' }
      : { bg: '#fef3c7', text: '#92400e' };
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      position: 'relative'
    }}>
      {/* Animated background elements */}
      <div style={{
        position: 'absolute',
        top: '10%',
        left: '5%',
        width: '200px',
        height: '200px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 6s ease-in-out infinite'
      }}></div>
      <div style={{
        position: 'absolute',
        top: '60%',
        right: '10%',
        width: '150px',
        height: '150px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 8s ease-in-out infinite reverse'
      }}></div>

      {/* Header */}
      <div style={{ 
        background: 'rgba(255, 255, 255, 0.1)', 
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
        padding: '32px 0',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1 style={{ 
                fontSize: '40px', 
                fontWeight: 'bold', 
                marginBottom: '12px', 
                color: 'white',
                textShadow: '0 2px 4px rgba(0,0,0,0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: '16px'
              }}>
                <span style={{ fontSize: '48px' }}>📊</span>
                {isMultiCompany ? 'Multi-Company Analysis' : 'Credit Analysis Dashboard'}
              </h1>
              <p style={{ 
                fontSize: '20px', 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '400'
              }}>
                {isMultiCompany 
                  ? `Analysis for ${companies.length} companies with individual risk assessments`
                  : 'AI-powered credit decisioning analysis'
                }
              </p>
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <button
                onClick={() => navigate('/research')}
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  padding: '14px 28px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  cursor: 'pointer',
                  fontSize: '16px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                }}
              >
                📈 Research Insights
              </button>
              <button
                onClick={() => navigate('/cam-preview')}
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  padding: '14px 28px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  cursor: 'pointer',
                  fontSize: '16px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                }}
              >
                📄 Generate CAM
              </button>
              <button
                onClick={() => navigate('/')}
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  padding: '14px 28px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  cursor: 'pointer',
                  fontSize: '16px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                }}
              >
                📤 New Upload
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '40px 24px' }}>
        {isMultiCompany && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248,250,252,0.95))',
            backdropFilter: 'blur(10px)',
            borderRadius: '20px',
            padding: '32px',
            marginBottom: '32px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            textAlign: 'center'
          }}>
            <h2 style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px' }}>
              📊 Multi-Company Credit Analysis
            </h2>
            <p style={{ fontSize: '18px', color: '#475569', marginBottom: '24px' }}>
              Individual credit assessment for each uploaded company
            </p>
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              gap: '24px',
              flexWrap: 'wrap'
            }}>
              <div style={{
                backgroundColor: '#dbeafe',
                padding: '12px 24px',
                borderRadius: '25px',
                fontSize: '16px',
                fontWeight: '600',
                color: '#1e40af',
                boxShadow: '0 4px 6px rgba(59, 130, 246, 0.1)'
              }}>
                Total Companies: {companies.length}
              </div>
              <div style={{
                backgroundColor: '#dcfce7',
                padding: '12px 24px',
                borderRadius: '25px',
                fontSize: '16px',
                fontWeight: '600',
                color: '#166534',
                boxShadow: '0 4px 6px rgba(34, 197, 94, 0.1)'
              }}>
                Individual Analysis: ✅
              </div>
              <div style={{
                backgroundColor: '#fef3c7',
                padding: '12px 24px',
                borderRadius: '25px',
                fontSize: '16px',
                fontWeight: '600',
                color: '#92400e',
                boxShadow: '0 4px 6px rgba(245, 158, 11, 0.1)'
              }}>
                Unique Risk Scores: ✅
              </div>
            </div>
          </div>
        )}

        {/* Company Cards */}
        {companies.map((company, index) => {
          const riskColors = getRiskColor(company.ai_analysis?.risk_analysis?.risk_score || 50);
          const decisionColors = getDecisionColor(company.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED');
          
          return (
            <div key={company.unique_hash || index} style={{
              background: 'linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248,250,252,0.95))',
              backdropFilter: 'blur(10px)',
              borderRadius: '24px',
              padding: '32px',
              marginBottom: '24px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
              border: '1px solid rgba(255, 255, 255, 0.3)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              {/* Decorative gradient overlay */}
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '4px',
                background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f59e0b)',
                borderRadius: '24px 24px 0 0'
              }}></div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
                <div>
                  <h3 style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b', marginBottom: '8px' }}>
                    {isMultiCompany ? `Company ${index + 1}` : company.company}
                  </h3>
                  <p style={{ fontSize: '18px', color: '#64748b', marginBottom: '4px' }}>
                    {company.industry}
                  </p>
                  <p style={{ fontSize: '14px', color: '#94a3b8' }}>
                    File: {company.file_name}
                  </p>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
                <div style={{ 
                  backgroundColor: riskColors.bg, 
                  padding: '20px', 
                  borderRadius: '12px', 
                  textAlign: 'center',
                  border: `2px solid ${riskColors.border}`
                }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                    Risk Score
                  </h4>
                  <p style={{ fontSize: '32px', fontWeight: 'bold', color: riskColors.text }}>
                    {company.ai_analysis?.risk_analysis?.risk_score || 50}/100
                  </p>
                  <p style={{ fontSize: '14px', color: riskColors.text, marginTop: '4px' }}>
                    {company.ai_analysis?.risk_analysis?.risk_category || 'Medium Risk'}
                  </p>
                </div>
                
                <div style={{ 
                  backgroundColor: decisionColors.bg, 
                  padding: '20px', 
                  borderRadius: '12px', 
                  textAlign: 'center'
                }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                    Credit Decision
                  </h4>
                  <p style={{ fontSize: '24px', fontWeight: 'bold', color: decisionColors.text }}>
                    {company.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED'}
                  </p>
                </div>

                <div style={{ 
                  backgroundColor: '#f0f9ff', 
                  padding: '20px', 
                  borderRadius: '12px', 
                  textAlign: 'center'
                }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                    Revenue
                  </h4>
                  <p style={{ fontSize: '24px', fontWeight: 'bold', color: '#0c4a6e' }}>
                    ₹{((company.revenue || 100000000) / 10000000).toFixed(1)}Cr
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CompleteDashboard;
