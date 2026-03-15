import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const SimpleDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        console.log('Dashboard: Loading data from localStorage...');
        const storedCompanyData = localStorage.getItem('companyData');
        console.log('Dashboard: Raw stored data:', storedCompanyData);
        
        if (!storedCompanyData) {
          console.log('Dashboard: No company data found, redirecting...');
          navigate('/');
          return;
        }

        const data = JSON.parse(storedCompanyData);
        console.log('Dashboard: Parsed data:', data);
        
        setCompanyData(data);
        setLoading(false);
        
      } catch (err) {
        console.error('Dashboard: Error loading data:', err);
        setError('Failed to load dashboard data: ' + err.message);
        setLoading(false);
      }
    };

    loadData();
  }, [navigate]);

  const formatCurrency = (amount) => {
    if (amount >= 10000000) {
      return `₹${(amount / 10000000).toFixed(1)}Cr`;
    } else if (amount >= 100000) {
      return `₹${(amount / 100000).toFixed(1)}Lakhs`;
    } else {
      return `₹${amount.toLocaleString()}`;
    }
  };

  const getRiskColor = (score) => {
    if (score < 35) return { bg: '#dcfce7', text: '#166534', border: '#22c55e' };
    if (score < 65) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' };
    return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
  };

  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'Approve': return { bg: '#dcfce7', text: '#166534' };
      case 'Reject': return { bg: '#fef2f2', text: '#991b1b' };
      default: return { bg: '#fef3c7', text: '#92400e' };
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
      case 'high': return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' };
      case 'medium': return { bg: '#fef9c3', text: '#854d0e', border: '#eab308' };
      case 'low': return { bg: '#f0f9ff', text: '#1e40af', border: '#3b82f6' };
      default: return { bg: '#f9fafb', text: '#374151', border: '#6b7280' };
    }
  };

  const SingleCompanyCard = ({ company, index }) => {
    const riskColors = getRiskColor(company.ai_analysis.risk_analysis.risk_score);
    const decisionColors = getDecisionColor(company.ai_analysis.decision_result.decision);

    return (
      <div style={{ 
        backgroundColor: 'white', 
        borderRadius: '16px', 
        marginBottom: '32px',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
        border: '1px solid #e5e7eb',
        overflow: 'hidden'
      }}>
        {/* Company Header */}
        <div style={{
          background: `linear-gradient(to right, #2563eb, #4f46e5)`,
          color: 'white',
          padding: '24px 32px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h2 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px' }}>
              {company.company}
            </h2>
            <p style={{ fontSize: '16px', color: '#dbeafe', opacity: 0.9 }}>
              {company.industry} • File: {company.file_name}
            </p>
          </div>
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
            padding: '8px 16px',
            borderRadius: '9999px',
            fontSize: '14px',
            fontWeight: '600'
          }}>
            Company {index + 1}
          </div>
        </div>

        <div style={{ padding: '32px' }}>
          {/* Risk Score and Decision */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
            gap: '24px', 
            marginBottom: '32px' 
          }}>
            <div style={{ 
              backgroundColor: riskColors.bg, 
              padding: '24px', 
              borderRadius: '12px', 
              border: `2px solid ${riskColors.border}`,
              textAlign: 'center'
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                Risk Score
              </h3>
              <p style={{ fontSize: '36px', fontWeight: 'bold', color: riskColors.text }}>
                {company.ai_analysis.risk_analysis.risk_score}
              </p>
              <p style={{ fontSize: '14px', color: riskColors.text, marginTop: '4px' }}>
                {company.ai_analysis.risk_analysis.risk_category}
              </p>
            </div>
            
            <div style={{ 
              backgroundColor: decisionColors.bg, 
              padding: '24px', 
              borderRadius: '12px', 
              textAlign: 'center'
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                Credit Decision
              </h3>
              <p style={{ fontSize: '24px', fontWeight: 'bold', color: decisionColors.text }}>
                {company.ai_analysis.decision_result.decision}
              </p>
              <p style={{ fontSize: '14px', color: decisionColors.text, marginTop: '4px' }}>
                Confidence: {(company.ai_analysis.decision_result.confidence_score * 100).toFixed(1)}%
              </p>
            </div>
          </div>

          {/* Financial Overview */}
          <div style={{ marginBottom: '32px' }}>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#111827', marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
              <span style={{ marginRight: '8px' }}>📊</span>
              Financial Summary
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div style={{ 
                backgroundColor: '#f9fafb', 
                padding: '16px', 
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Revenue</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#111827' }}>
                  {formatCurrency(company.revenue)}
                </p>
              </div>
              <div style={{ 
                backgroundColor: '#f9fafb', 
                padding: '16px', 
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Profit</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#111827' }}>
                  {formatCurrency(company.profit)}
                </p>
              </div>
              <div style={{ 
                backgroundColor: '#f9fafb', 
                padding: '16px', 
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Assets</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#111827' }}>
                  {formatCurrency(company.assets)}
                </p>
              </div>
              <div style={{ 
                backgroundColor: '#f9fafb', 
                padding: '16px', 
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Liabilities</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#111827' }}>
                  {formatCurrency(company.liabilities)}
                </p>
              </div>
            </div>
          </div>

          {/* Loan Details */}
          <div style={{ marginBottom: '32px' }}>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#111827', marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
              <span style={{ marginRight: '8px' }}>💰</span>
              Loan Analysis
            </h3>
            <div style={{ 
              backgroundColor: 'linear-gradient(to right, #dbeafe, #eff6ff)', 
              padding: '20px', 
              borderRadius: '12px', 
              border: '1px solid #3b82f6'
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <div>
                  <p style={{ fontSize: '12px', color: '#1e40af', marginBottom: '4px' }}>Approved Loan Amount</p>
                  <p style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e40af' }}>
                    {formatCurrency(company.ai_analysis.loan_analysis.approved_loan_amount)}
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: '12px', color: '#1e40af', marginBottom: '4px' }}>Interest Rate</p>
                  <p style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e40af' }}>
                    {company.ai_analysis.loan_analysis.interest_rate}%
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: '12px', color: '#1e40af', marginBottom: '4px' }}>Tenure</p>
                  <p style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e40af' }}>
                    {company.ai_analysis.loan_analysis.recommended_tenure} months
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Factors */}
          <div>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#111827', marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
              <span style={{ marginRight: '8px' }}>⚠️</span>
              Key Risk Factors
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {company.ai_analysis.risk_factors.slice(0, 4).map((factor, idx) => {
                const colors = getSeverityColor(factor.severity);
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '12px',
                      padding: '16px',
                      borderRadius: '8px',
                      borderLeft: `4px solid ${colors.border}`,
                      backgroundColor: colors.bg
                    }}
                  >
                    <div style={{ fontSize: '20px' }}>
                      {factor.severity === 'High' ? '🚨' : factor.severity === 'Medium' ? '⚡' : 'ℹ️'}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ fontSize: '12px', fontWeight: '600', textTransform: 'uppercase', color: colors.text }}>
                          {factor.category}
                        </span>
                        <span style={{ 
                          fontSize: '12px', 
                          padding: '2px 8px', 
                          borderRadius: '9999px', 
                          backgroundColor: colors.border,
                          color: 'white',
                          fontWeight: '600'
                        }}>
                          {factor.severity}
                        </span>
                      </div>
                      <p style={{ fontSize: '14px', color: '#374151', marginBottom: '4px' }}>
                        {factor.description}
                      </p>
                      {factor.recommendation && (
                        <p style={{ fontSize: '12px', color: '#6b7280', fontStyle: 'italic' }}>
                          💡 {factor.recommendation}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f0f9ff' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            width: '48px', 
            height: '48px', 
            border: '4px solid #e5e7eb', 
            borderTop: '4px solid #2563eb', 
            borderRadius: '50%', 
            animation: 'spin 1s linear infinite',
            margin: '0 auto 16px'
          }}></div>
          <p style={{ fontSize: '18px', color: '#4b5563' }}>Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f0f9ff' }}>
        <div style={{ textAlign: 'center', padding: '32px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>❌</div>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#111827', marginBottom: '16px' }}>
            Error Loading Dashboard
          </h2>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>{error}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              backgroundColor: '#2563eb',
              color: 'white',
              padding: '12px 24px',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: '600'
            }}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const isMultiCompany = companyData?.is_multi_company;
  const companies = isMultiCompany ? companyData.companies : [companyData];

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
              {companyData?.upload_timestamp && (
                <p style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.8)', marginTop: '8px' }}>
                  Last updated: {new Date(companyData.upload_timestamp).toLocaleString()}
                </p>
              )}
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
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.3)';
                  e.target.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                  e.target.style.transform = 'translateY(0)';
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
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.3)';
                  e.target.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                  e.target.style.transform = 'translateY(0)';
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
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.3)';
                  e.target.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                  e.target.style.transform = 'translateY(0)';
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
          /* Multi-company header */
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

        {companies.map((company, index) => (
          <SingleCompanyCard key={company.unique_hash || index} company={company} index={index} />
        ))}
      </div>
    </div>
  );
};

export default SimpleDashboard;
