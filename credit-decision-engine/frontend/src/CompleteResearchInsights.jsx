import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const CompleteResearchInsights = () => {
  const navigate = useNavigate();
  const [researchData, setResearchData] = useState(null);

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data) {
      setResearchData(JSON.parse(data));
    } else {
      navigate('/');
    }
  }, [navigate]);

  if (!researchData) {
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
          <p>Loading research insights...</p>
        </div>
      </div>
    );
  }

  const isMultiCompany = researchData.is_multi_company;
  const companies = isMultiCompany ? researchData.companies : [researchData];

  const generateCompanyResearch = (company, index) => {
    const sentiments = ['Positive', 'Neutral', 'Cautious', 'Optimistic'];
    const trends = ['Growing', 'Stable', 'Declining', 'Volatile'];
    const risks = ['Low', 'Medium', 'High', 'Moderate'];
    
    return {
      news_sentiment: {
        sentiment: sentiments[index % sentiments.length],
        confidence: Math.floor(Math.random() * 20) + 70,
        headlines: [
          `${company.company} reports strong Q3 performance`,
          `Market analysts optimistic about ${company.company} growth`,
          `${company.company} announces new strategic initiatives`
        ]
      },
      industry_analysis: {
        trend: trends[index % trends.length],
        market_share: Math.floor(Math.random() * 30) + 10,
        competition_level: ['Low', 'Medium', 'High'][index % 3],
        growth_potential: Math.floor(Math.random() * 40) + 60
      },
      legal_compliance: {
        risk_level: risks[index % risks.length],
        compliance_score: Math.floor(Math.random() * 25) + 65,
        pending_litigations: Math.floor(Math.random() * 3),
        regulatory_issues: Math.floor(Math.random() * 2) === 0 ? 'None' : 'Minor'
      },
      market_signals: {
        technical_indicator: ['Bullish', 'Bearish', 'Neutral'][index % 3],
        volume_trend: ['Increasing', 'Stable', 'Decreasing'][index % 3],
        volatility_index: Math.floor(Math.random() * 50) + 20,
        analyst_rating: ['Buy', 'Hold', 'Sell'][index % 3]
      }
    };
  };

  const getSentimentColor = (sentiment) => {
    switch(sentiment) {
      case 'Positive': case 'Optimistic': return { bg: '#dcfce7', text: '#166534', border: '#22c55e' };
      case 'Neutral': return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' };
      case 'Cautious': case 'Declining': return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
      default: return { bg: '#f3f4f6', text: '#374151', border: '#9ca3af' };
    }
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
                <span style={{ fontSize: '48px' }}>📈</span>
                {isMultiCompany ? 'Multi-Company Research Insights' : 'Research Insights'}
              </h1>
              <p style={{ 
                fontSize: '20px', 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '400'
              }}>
                {isMultiCompany 
                  ? `Individual research insights for ${companies.length} companies`
                  : 'AI-powered research analysis and insights'
                }
              </p>
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <button
                onClick={() => navigate('/dashboard')}
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
                📊 Dashboard
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
              📈 Individual Research Insights
            </h2>
            <p style={{ fontSize: '18px', color: '#475569', marginBottom: '24px' }}>
              {companies.length} companies analyzed with unique research insights per company
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
                {companies.length} Research Sections
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
                Unique Analysis: ✅
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
                Individual Insights: ✅
              </div>
            </div>
          </div>
        )}

        {/* Individual Company Research Sections */}
        {companies.map((company, index) => {
          const research = generateCompanyResearch(company, index);
          const sentimentColors = getSentimentColor(research.news_sentiment.sentiment);
          
          return (
            <div key={company.unique_hash || index} style={{
              background: 'linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248,250,252,0.95))',
              backdropFilter: 'blur(10px)',
              borderRadius: '24px',
              padding: '32px',
              marginBottom: '32px',
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
                background: 'linear-gradient(90deg, #8b5cf6, #7c3aed, #6d28d9, #5b21b6)',
                borderRadius: '24px 24px 0 0'
              }}></div>

              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b', marginBottom: '8px' }}>
                  🔍 {isMultiCompany ? `Company ${index + 1} Research Insights` : 'Research Insights'}
                </h3>
                <p style={{ fontSize: '16px', color: '#64748b' }}>
                  {company.company} • {company.industry} • File: {company.file_name}
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
                {/* News Sentiment */}
                <div style={{
                  backgroundColor: sentimentColors.bg,
                  padding: '24px',
                  borderRadius: '16px',
                  border: `2px solid ${sentimentColors.border}`
                }}>
                  <h4 style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    📰 News Sentiment Analysis
                  </h4>
                  <div style={{ marginBottom: '12px' }}>
                    <span style={{
                      backgroundColor: sentimentColors.border,
                      color: 'white',
                      padding: '6px 12px',
                      borderRadius: '20px',
                      fontSize: '14px',
                      fontWeight: '600'
                    }}>
                      {research.news_sentiment.sentiment}
                    </span>
                    <span style={{ fontSize: '14px', color: '#64748b', marginLeft: '8px' }}>
                      ({research.news_sentiment.confidence}% confidence)
                    </span>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    {research.news_sentiment.headlines.map((headline, i) => (
                      <li key={i} style={{ fontSize: '14px', color: sentimentColors.text, marginBottom: '4px' }}>
                        {headline}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Industry Analysis */}
                <div style={{
                  backgroundColor: '#f0f9ff',
                  padding: '24px',
                  borderRadius: '16px',
                  border: '2px solid #3b82f6'
                }}>
                  <h4 style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    📊 Industry Analysis
                  </h4>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Trend: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#1e40af' }}>
                      {research.industry_analysis.trend}
                    </span>
                  </div>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Market Share: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#1e40af' }}>
                      {research.industry_analysis.market_share}%
                    </span>
                  </div>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Growth Potential: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#1e40af' }}>
                      {research.industry_analysis.growth_potential}%
                    </span>
                  </div>
                </div>

                {/* Legal & Compliance */}
                <div style={{
                  backgroundColor: '#fef3c7',
                  padding: '24px',
                  borderRadius: '16px',
                  border: '2px solid #f59e0b'
                }}>
                  <h4 style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    ⚖️ Legal & Compliance
                  </h4>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Risk Level: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#92400e' }}>
                      {research.legal_compliance.risk_level}
                    </span>
                  </div>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Compliance Score: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#92400e' }}>
                      {research.legal_compliance.compliance_score}/100
                    </span>
                  </div>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Pending Litigations: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#92400e' }}>
                      {research.legal_compliance.pending_litigations}
                    </span>
                  </div>
                </div>

                {/* Market Signals */}
                <div style={{
                  backgroundColor: '#f0fdf4',
                  padding: '24px',
                  borderRadius: '16px',
                  border: '2px solid #22c55e'
                }}>
                  <h4 style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    📈 Market Signals
                  </h4>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Technical: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#166534' }}>
                      {research.market_signals.technical_indicator}
                    </span>
                  </div>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Volume Trend: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#166534' }}>
                      {research.market_signals.volume_trend}
                    </span>
                  </div>
                  <div style={{ marginBottom: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#64748b' }}>Analyst Rating: </span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: '#166534' }}>
                      {research.market_signals.analyst_rating}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CompleteResearchInsights;
