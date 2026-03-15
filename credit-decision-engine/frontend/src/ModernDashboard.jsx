import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const ModernDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data) {
      const parsedData = JSON.parse(data);
      setCompanyData(parsedData);
      if (parsedData.is_multi_company && parsedData.companies.length > 0) {
        setSelectedCompany(parsedData.companies[0]);
      } else {
        setSelectedCompany(parsedData);
      }
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
    if (score <= 40) return { bg: '#dcfce7', text: '#166534', border: '#22c55e', icon: '🟢', gradient: 'linear-gradient(135deg, #22c55e, #16a34a)' };
    if (score <= 70) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b', icon: '🟡', gradient: 'linear-gradient(135deg, #f59e0b, #d97706)' };
    return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444', icon: '🔴', gradient: 'linear-gradient(135deg, #ef4444, #dc2626)' };
  };

  const getDecisionColor = (decision) => {
    return decision === 'APPROVED' 
      ? { bg: '#dcfce7', text: '#166534', icon: '✅', gradient: 'linear-gradient(135deg, #22c55e, #16a34a)' }
      : { bg: '#fef3c7', text: '#92400e', icon: '⚠️', gradient: 'linear-gradient(135deg, #f59e0b, #d97706)' };
  };

  const company = selectedCompany;
  const riskColors = getRiskColor(company?.ai_analysis?.risk_analysis?.risk_score || 50);
  const decisionColors = getDecisionColor(company?.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED');

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #1e40af 0%, #0f766e 50%, #0891b2 100%)',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Enhanced Animated background elements */}
      <div style={{
        position: 'absolute',
        top: '10%',
        left: '5%',
        width: '300px',
        height: '300px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.25) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 6s ease-in-out infinite'
      }}></div>
      <div style={{
        position: 'absolute',
        top: '60%',
        right: '10%',
        width: '250px',
        height: '250px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 8s ease-in-out infinite reverse'
      }}></div>
      <div style={{
        position: 'absolute',
        bottom: '20%',
        left: '15%',
        width: '200px',
        height: '200px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 10s ease-in-out infinite'
      }}></div>

      {/* Enhanced Header */}
      <div style={{ 
        background: 'rgba(255, 255, 255, 0.1)', 
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
        padding: '24px 0',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
        position: 'sticky',
        top: 0,
        zIndex: 1000
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1 style={{ 
                fontSize: '36px', 
                fontWeight: 'bold', 
                marginBottom: '8px', 
                color: 'white',
                textShadow: '0 2px 4px rgba(0,0,0,0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: '16px'
              }}>
                <span style={{ fontSize: '40px' }}>📊</span>
                Credit Analysis Dashboard
              </h1>
              <p style={{ 
                fontSize: '18px', 
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
                  background: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📈 Research Insights
              </button>
              <button
                onClick={() => navigate('/cam-preview')}
                style={{
                  background: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📄 Generate CAM
              </button>
              <button
                onClick={() => navigate('/')}
                style={{
                  background: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📤 New Upload
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '32px' }}>
          
          {/* Enhanced Sidebar */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(20px)',
            borderRadius: '20px',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            height: 'fit-content',
            position: 'sticky',
            top: '120px'
          }}>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              🏢 {isMultiCompany ? 'Companies' : 'Company Details'}
            </h3>
            
            {isMultiCompany ? (
              <div>
                <div style={{ 
                  background: 'linear-gradient(135deg, #dbeafe, #eff6ff)',
                  padding: '16px',
                  borderRadius: '12px',
                  marginBottom: '20px',
                  border: '1px solid #3b82f6'
                }}>
                  <p style={{ fontSize: '16px', fontWeight: '600', color: '#1e40af', margin: '0 0 8px 0' }}>
                    Total Companies
                  </p>
                  <p style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e40af', margin: 0 }}>
                    {companies.length}
                  </p>
                </div>
                
                {companies.map((comp, index) => (
                  <div
                    key={comp.unique_hash || index}
                    onClick={() => setSelectedCompany(comp)}
                    style={{
                      padding: '16px',
                      borderRadius: '12px',
                      marginBottom: '12px',
                      cursor: 'pointer',
                      background: selectedCompany?.unique_hash === comp.unique_hash 
                        ? 'linear-gradient(135deg, #3b82f6, #2563eb)' 
                        : 'linear-gradient(135deg, #f8fafc, #f1f5f9)',
                      border: selectedCompany?.unique_hash === comp.unique_hash 
                        ? '2px solid #3b82f6' 
                        : '1px solid #e2e8f0',
                      transition: 'all 0.3s ease',
                      transform: selectedCompany?.unique_hash === comp.unique_hash ? 'scale(1.02)' : 'scale(1)',
                      boxShadow: selectedCompany?.unique_hash === comp.unique_hash 
                        ? '0 8px 16px rgba(59, 130, 246, 0.3)' 
                        : '0 2px 4px rgba(0, 0, 0, 0.05)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '10px',
                        background: selectedCompany?.unique_hash === comp.unique_hash 
                          ? 'rgba(255, 255, 255, 0.2)' 
                          : 'linear-gradient(135deg, #3b82f6, #2563eb)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '18px',
                        fontWeight: 'bold',
                        color: selectedCompany?.unique_hash === comp.unique_hash ? 'white' : 'white'
                      }}>
                        {index + 1}
                      </div>
                      <div style={{ flex: 1 }}>
                        <p style={{ 
                          fontSize: '16px', 
                          fontWeight: '700', 
                          color: selectedCompany?.unique_hash === comp.unique_hash ? 'white' : '#1e293b',
                          margin: '0 0 4px 0' 
                        }}>
                          Company {index + 1}
                        </p>
                        <p style={{ 
                          fontSize: '14px', 
                          color: selectedCompany?.unique_hash === comp.unique_hash ? 'rgba(255,255,255,0.8)' : '#64748b',
                          margin: 0 
                        }}>
                          {comp.industry}
                        </p>
                      </div>
                    </div>
                    {selectedCompany?.unique_hash === comp.unique_hash && (
                      <div style={{
                        marginTop: '12px',
                        padding: '8px 12px',
                        backgroundColor: 'rgba(255, 255, 255, 0.15)',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: 'rgba(255, 255, 255, 0.9)',
                        fontWeight: '600'
                      }}>
                        Currently Selected
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div>
                <div style={{ 
                  background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                  padding: '20px',
                  borderRadius: '16px',
                  color: 'white',
                  textAlign: 'center'
                }}>
                  <div style={{
                    width: '60px',
                    height: '60px',
                    borderRadius: '15px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '24px',
                    fontWeight: 'bold',
                    margin: '0 auto 16px auto'
                  }}>
                    🏢
                  </div>
                  <p style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 8px 0' }}>
                    {companyData.company}
                  </p>
                  <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.8)', margin: 0 }}>
                    {companyData.industry}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Enhanced Main Dashboard Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* Enhanced Top Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px' }}>
              <div style={{
                background: 'rgba(255, 255, 255, 0.95)',
                backdropFilter: 'blur(20px)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.3s ease'
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: riskColors.gradient
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                    Risk Score
                  </h4>
                  <span style={{ fontSize: '24px' }}>{riskColors.icon}</span>
                </div>
                <p style={{ fontSize: '32px', fontWeight: 'bold', color: riskColors.text, margin: '0 0 12px 0' }}>
                  {company?.ai_analysis?.risk_analysis?.risk_score || 50}/100
                </p>
                <div style={{
                  height: '8px',
                  backgroundColor: '#e2e8f0',
                  borderRadius: '4px',
                  overflow: 'hidden',
                  marginBottom: '8px'
                }}>
                  <div style={{
                    width: `${company?.ai_analysis?.risk_analysis?.risk_score || 50}%`,
                    height: '100%',
                    background: riskColors.gradient,
                    borderRadius: '4px',
                    transition: 'width 0.3s ease'
                  }}></div>
                </div>
                <p style={{ fontSize: '14px', color: '#64748b', margin: 0 }}>
                  {company?.ai_analysis?.risk_analysis?.risk_category || 'Medium Risk'}
                </p>
              </div>

              <div style={{
                background: 'rgba(255, 255, 255, 0.95)',
                backdropFilter: 'blur(20px)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.3s ease'
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: decisionColors.gradient
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                    Credit Decision
                  </h4>
                  <span style={{ fontSize: '24px' }}>{decisionColors.icon}</span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: decisionColors.text, margin: '0 0 12px 0' }}>
                  {company?.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED'}
                </p>
                <div style={{
                  padding: '8px 16px',
                  backgroundColor: decisionColors.bg,
                  borderRadius: '20px',
                  display: 'inline-block'
                }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: decisionColors.text }}>
                    Final Recommendation
                  </span>
                </div>
              </div>

              <div style={{
                background: 'rgba(255, 255, 255, 0.95)',
                backdropFilter: 'blur(20px)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.3s ease'
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: 'linear-gradient(135deg, #10b981, #059669)'
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                    Revenue
                  </h4>
                  <span style={{ fontSize: '24px' }}>💰</span>
                </div>
                <p style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b', margin: '0 0 12px 0' }}>
                  ₹{((company?.revenue || 100000000) / 10000000).toFixed(1)}Cr
                </p>
                <p style={{ fontSize: '14px', color: '#64748b', margin: 0 }}>
                  Annual Revenue
                </p>
              </div>

              <div style={{
                background: 'rgba(255, 255, 255, 0.95)',
                backdropFilter: 'blur(20px)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.3s ease'
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: 'linear-gradient(135deg, #8b5cf6, #7c3aed)'
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                    Industry
                  </h4>
                  <span style={{ fontSize: '24px' }}>🏭</span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b', margin: '0 0 12px 0' }}>
                  {company?.industry || 'N/A'}
                </p>
                <p style={{ fontSize: '14px', color: '#64748b', margin: 0 }}>
                  Sector Classification
                </p>
              </div>
            </div>

            {/* Enhanced Main Content Area */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
              
              {/* Enhanced Left Panel - Company Details */}
              <div style={{
                background: 'rgba(255, 255, 255, 0.95)',
                backdropFilter: 'blur(20px)',
                borderRadius: '20px',
                padding: '32px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f59e0b)',
                  borderRadius: '20px 20px 0 0'
                }}></div>

                <h3 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                  📊 {isMultiCompany ? `Company ${companies.indexOf(company) + 1} Analysis` : 'Company Analysis'}
                </h3>
                
                <div style={{ marginBottom: '32px' }}>
                  <h4 style={{ fontSize: '18px', fontWeight: '600', color: '#374151', marginBottom: '16px' }}>
                    Risk Assessment
                  </h4>
                  <div style={{
                    background: riskColors.bg,
                    padding: '24px',
                    borderRadius: '16px',
                    border: `2px solid ${riskColors.border}`,
                    position: 'relative',
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      position: 'absolute',
                      top: '0',
                      left: '0',
                      right: '0',
                      height: '3px',
                      background: riskColors.gradient
                    }}></div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                      <span style={{ fontSize: '16px', color: '#64748b', fontWeight: '600' }}>Overall Risk Score</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '32px', fontWeight: 'bold', color: riskColors.text }}>
                          {company?.ai_analysis?.risk_analysis?.risk_score || 50}
                        </span>
                        <span style={{ fontSize: '20px', color: riskColors.text }}>/100</span>
                      </div>
                    </div>
                    <div style={{
                      height: '12px',
                      backgroundColor: 'rgba(255, 255, 255, 0.3)',
                      borderRadius: '6px',
                      overflow: 'hidden',
                      marginBottom: '16px'
                    }}>
                      <div style={{
                        width: `${company?.ai_analysis?.risk_analysis?.risk_score || 50}%`,
                        height: '100%',
                        background: riskColors.gradient,
                        borderRadius: '6px',
                        transition: 'width 0.5s ease',
                        boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
                      }}></div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '18px' }}>{riskColors.icon}</span>
                      <span style={{ fontSize: '16px', color: riskColors.text, fontWeight: '600' }}>
                        {company?.ai_analysis?.risk_analysis?.risk_category || 'Medium Risk'}
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{ marginBottom: '32px' }}>
                  <h4 style={{ fontSize: '18px', fontWeight: '600', color: '#374151', marginBottom: '16px' }}>
                    Credit Decision
                  </h4>
                  <div style={{
                    background: decisionColors.bg,
                    padding: '32px',
                    borderRadius: '16px',
                    textAlign: 'center',
                    border: `2px solid ${decisionColors.border}`,
                    position: 'relative',
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      position: 'absolute',
                      top: '0',
                      left: '0',
                      right: '0',
                      height: '3px',
                      background: decisionColors.gradient
                    }}></div>
                    <div style={{ fontSize: '48px', marginBottom: '16px' }}>{decisionColors.icon}</div>
                    <p style={{ fontSize: '28px', fontWeight: 'bold', color: decisionColors.text, margin: '0 0 12px 0' }}>
                      {company?.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED'}
                    </p>
                    <p style={{ fontSize: '16px', color: '#64748b', margin: 0 }}>
                      Based on comprehensive AI analysis
                    </p>
                  </div>
                </div>

                <div>
                  <h4 style={{ fontSize: '18px', fontWeight: '600', color: '#374151', marginBottom: '16px' }}>
                    Financial Metrics
                  </h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                    <div style={{ 
                      background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)', 
                      padding: '20px', 
                      borderRadius: '12px',
                      border: '1px solid #e2e8f0',
                      transition: 'all 0.3s ease'
                    }}>
                      <p style={{ fontSize: '14px', color: '#64748b', margin: '0 0 8px 0', fontWeight: '600' }}>Revenue</p>
                      <p style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', margin: 0 }}>
                        ₹{((company?.revenue || 100000000) / 10000000).toFixed(1)}Cr
                      </p>
                    </div>
                    <div style={{ 
                      background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)', 
                      padding: '20px', 
                      borderRadius: '12px',
                      border: '1px solid #e2e8f0',
                      transition: 'all 0.3s ease'
                    }}>
                      <p style={{ fontSize: '14px', color: '#64748b', margin: '0 0 8px 0', fontWeight: '600' }}>Industry</p>
                      <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', margin: 0 }}>
                        {company?.industry || 'N/A'}
                      </p>
                    </div>
                    <div style={{ 
                      background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)', 
                      padding: '20px', 
                      borderRadius: '12px',
                      border: '1px solid #e2e8f0',
                      transition: 'all 0.3s ease'
                    }}>
                      <p style={{ fontSize: '14px', color: '#64748b', margin: '0 0 8px 0', fontWeight: '600' }}>File</p>
                      <p style={{ fontSize: '12px', fontWeight: 'bold', color: '#1e293b', margin: 0, wordBreak: 'break-word' }}>
                        {company?.file_name || 'N/A'}
                      </p>
                    </div>
                    <div style={{ 
                      background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)', 
                      padding: '20px', 
                      borderRadius: '12px',
                      border: '1px solid #e2e8f0',
                      transition: 'all 0.3s ease'
                    }}>
                      <p style={{ fontSize: '14px', color: '#64748b', margin: '0 0 8px 0', fontWeight: '600' }}>Status</p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: '#10b981',
                          animation: 'pulse 2s infinite'
                        }}></div>
                        <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#1e293b', margin: 0 }}>
                          Active
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Enhanced Right Panel - Quick Actions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                
                <div style={{
                  background: 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(20px)',
                  borderRadius: '20px',
                  padding: '24px',
                  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899)'
                  }}></div>

                  <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    🚀 Quick Actions
                  </h3>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <button
                      onClick={() => navigate('/research')}
                      style={{
                        background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        padding: '16px 20px',
                        cursor: 'pointer',
                        fontSize: '15px',
                        fontWeight: '600',
                        transition: 'all 0.3s ease',
                        boxShadow: '0 4px 6px rgba(59, 130, 246, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px'
                      }}
                    >
                      <span style={{ fontSize: '20px' }}>📈</span>
                      <div style={{ textAlign: 'left' }}>
                        <div>View Research Insights</div>
                        <div style={{ fontSize: '12px', opacity: 0.8 }}>Detailed analysis & reports</div>
                      </div>
                    </button>
                    
                    <button
                      onClick={() => navigate('/cam-preview')}
                      style={{
                        background: 'linear-gradient(135deg, #10b981, #059669)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        padding: '16px 20px',
                        cursor: 'pointer',
                        fontSize: '15px',
                        fontWeight: '600',
                        transition: 'all 0.3s ease',
                        boxShadow: '0 4px 6px rgba(16, 185, 129, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px'
                      }}
                    >
                      <span style={{ fontSize: '20px' }}>📄</span>
                      <div style={{ textAlign: 'left' }}>
                        <div>Generate CAM Report</div>
                        <div style={{ fontSize: '12px', opacity: 0.8 }}>Downloadable reports</div>
                      </div>
                    </button>
                    
                    <button
                      onClick={() => navigate('/')}
                      style={{
                        background: 'linear-gradient(135deg, #8b5cf6, #7c3aed)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        padding: '16px 20px',
                        cursor: 'pointer',
                        fontSize: '15px',
                        fontWeight: '600',
                        transition: 'all 0.3s ease',
                        boxShadow: '0 4px 6px rgba(139, 92, 246, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px'
                      }}
                    >
                      <span style={{ fontSize: '20px' }}>📤</span>
                      <div style={{ textAlign: 'left' }}>
                        <div>Upload New Document</div>
                        <div style={{ fontSize: '12px', opacity: 0.8 }}>Add more companies</div>
                      </div>
                    </button>
                  </div>
                </div>

                <div style={{
                  background: 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(20px)',
                  borderRadius: '20px',
                  padding: '24px',
                  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: 'linear-gradient(90deg, #10b981, #059669, #047857)'
                  }}></div>

                  <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    📋 Summary
                  </h3>
                  
                  <div style={{ background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)', padding: '20px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '14px', color: '#64748b', lineHeight: '1.6' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                        <span style={{ fontWeight: '600' }}>Company:</span>
                        <span style={{ fontWeight: 'bold', color: '#1e293b' }}>{company?.company || 'N/A'}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                        <span style={{ fontWeight: '600' }}>Risk Level:</span>
                        <span style={{ 
                          fontWeight: 'bold', 
                          color: riskColors.text,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          backgroundColor: riskColors.bg,
                          border: `1px solid ${riskColors.border}`
                        }}>
                          {company?.ai_analysis?.risk_analysis?.risk_category || 'Medium Risk'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                        <span style={{ fontWeight: '600' }}>Decision:</span>
                        <span style={{ 
                          fontWeight: 'bold', 
                          color: decisionColors.text,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          backgroundColor: decisionColors.bg,
                          border: `1px solid ${decisionColors.border}`
                        }}>
                          {company?.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: '600' }}>Revenue:</span>
                        <span style={{ fontWeight: 'bold', color: '#1e293b' }}>
                          ₹{((company?.revenue || 100000000) / 10000000).toFixed(1)}Cr
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ModernDashboard;
