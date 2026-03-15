import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const SimpleResearchInsights = () => {
  const navigate = useNavigate();
  const [researchData, setResearchData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadResearchData = async () => {
      try {
        // First check if we have AI analysis from uploaded file
        const storedCompanyData = localStorage.getItem('companyData');
        
        if (storedCompanyData) {
          const companyData = JSON.parse(storedCompanyData);
          console.log('Research: Using AI analysis from upload');
          
          // Generate dynamic research data based on company
          const dynamicResearchData = generateDynamicResearchData(companyData);
          setResearchData(dynamicResearchData);
          console.log('Research: Dynamic research data generated');
        } else {
          // Fallback to default research data
          const defaultResearchData = {
            company: 'Unknown Company',
            research_summary: {
              news_sentiment: {
                sentiment: 'Neutral',
                score: 0.0,
                total_articles_analyzed: 0
              },
              litigation_data: {
                risk_assessment: 'Medium',
                total_cases: 0,
                active_cases: 0
              },
              industry_analysis: {
                outlook: 'Stable',
                growth_rate: 'Unknown',
                market_position: 'Unknown'
              },
              risk_signals: []
            }
          };
          setResearchData(defaultResearchData);
        }
      } catch (err) {
        console.error('Research: Error loading research data:', err);
        setError('Failed to load research data: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    loadResearchData();
  }, [navigate]);

  const generateDynamicResearchData = (companyData) => {
    if (companyData.is_multi_company && companyData.companies) {
      // Return multi-company research data
      return {
        is_multi_company: true,
        total_companies: companyData.total_companies,
        companies: companyData.companies.map(company => ({
          company: company.company,
          industry: company.industry,
          file_name: company.file_name,
          research_summary: company.ai_analysis.research_summary
        }))
      };
    } else {
      // Return single company research data
      return {
        is_multi_company: false,
        company: companyData.company,
        industry: companyData.industry,
        file_name: companyData.file_name,
        research_summary: companyData.ai_analysis.research_summary
      };
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive': return { bg: '#dcfce7', text: '#166534', border: '#22c55e' };
      case 'negative': return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
      case 'neutral': return { bg: '#f3f4f6', text: '#374151', border: '#6b7280' };
      case 'mixed': return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' };
      case 'optimistic': return { bg: '#dbeafe', text: '#1e40af', border: '#3b82f6' };
      case 'cautious': return { bg: '#f3e8ff', text: '#6b21a8', border: '#8b5cf6' };
      default: return { bg: '#f9fafb', text: '#374151', border: '#d1d5db' };
    }
  };

  const getRiskColor = (risk) => {
    switch (risk?.toLowerCase()) {
      case 'low': return { bg: '#dcfce7', text: '#166534', border: '#22c55e' };
      case 'moderate': return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' };
      case 'medium': return { bg: '#fef9c3', text: '#854d0e', border: '#eab308' };
      case 'high': return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
      default: return { bg: '#f9fafb', text: '#374151', border: '#d1d5db' };
    }
  };

  const getOutlookColor = (outlook) => {
    switch (outlook?.toLowerCase()) {
      case 'strong growth': return { bg: '#dcfce7', text: '#166534', border: '#22c55e' };
      case 'moderate growth': return { bg: '#dbeafe', text: '#1e40af', border: '#3b82f6' };
      case 'stable': return { bg: '#f3f4f6', text: '#374151', border: '#6b7280' };
      case 'declining': return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' };
      case 'transforming': return { bg: '#f3e8ff', text: '#6b21a8', border: '#8b5cf6' };
      default: return { bg: '#f9fafb', text: '#374151', border: '#d1d5db' };
    }
  };

  const SingleCompanyInsights = ({ company, index }) => {
    const sentimentColors = getSentimentColor(company.research_summary.news_sentiment.sentiment);
    const riskColors = getRiskColor(company.research_summary.litigation_data.risk_level);
    const outlookColors = getOutlookColor(company.research_summary.industry_analysis.outlook);

    return (
      <div style={{
        background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
        borderRadius: '20px',
        padding: '32px',
        marginBottom: '24px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        border: '1px solid #e2e8f0',
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
          borderRadius: '20px 20px 0 0'
        }}></div>

        {/* Company Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '32px',
          paddingBottom: '20px',
          borderBottom: '2px solid #f1f5f9'
        }}>
          <div>
            <h2 style={{
              fontSize: '28px',
              fontWeight: 'bold',
              color: '#1e293b',
              marginBottom: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <span style={{ fontSize: '32px' }}>🔍</span>
              {company.company}
            </h2>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <span style={{
                backgroundColor: '#e0e7ff',
                color: '#4338ca',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '14px',
                fontWeight: '600'
              }}>
                {company.industry}
              </span>
              <span style={{
                backgroundColor: '#f0f9ff',
                color: '#0369a1',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '14px',
                fontWeight: '600'
              }}>
                📄 {company.file_name}
              </span>
            </div>
          </div>
          <div style={{
            backgroundColor: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            color: 'white',
            padding: '8px 20px',
            borderRadius: '25px',
            fontSize: '16px',
            fontWeight: 'bold',
            boxShadow: '0 4px 6px rgba(59, 130, 246, 0.3)'
          }}>
            Company {index + 1}
          </div>
        </div>

        {/* News Sentiment Section */}
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{
            fontSize: '20px',
            fontWeight: 'bold',
            color: '#1e293b',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ fontSize: '24px' }}>📰</span>
            News Sentiment Analysis
          </h3>
          <div style={{
            backgroundColor: sentimentColors.bg,
            border: `2px solid ${sentimentColors.border}`,
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <span style={{
                  backgroundColor: sentimentColors.border,
                  color: 'white',
                  padding: '6px 16px',
                  borderRadius: '20px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  textTransform: 'uppercase'
                }}>
                  {company.research_summary.news_sentiment.sentiment}
                </span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: sentimentColors.text }}>
                  {company.research_summary.news_sentiment.score?.toFixed(2) || '0.00'}
                </p>
                <p style={{ fontSize: '12px', color: sentimentColors.text }}>Sentiment Score</p>
              </div>
            </div>
            <div style={{ marginTop: '16px' }}>
              <p style={{ fontSize: '14px', color: '#475569', fontWeight: '600', marginBottom: '8px' }}>
                Key Headlines:
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {company.research_summary.news_sentiment.key_headlines?.map((headline, idx) => (
                  <div key={idx} style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.7)',
                    padding: '12px',
                    borderRadius: '8px',
                    borderLeft: `3px solid ${sentimentColors.border}`
                  }}>
                    <p style={{ fontSize: '14px', color: '#1e293b', margin: 0 }}>
                      • {headline}
                    </p>
                  </div>
                )) || <p style={{ fontSize: '14px', color: '#64748b' }}>No headlines available</p>}
              </div>
            </div>
          </div>
        </div>

        {/* Industry Analysis Section */}
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{
            fontSize: '20px',
            fontWeight: 'bold',
            color: '#1e293b',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ fontSize: '24px' }}>📊</span>
            Industry Analysis
          </h3>
          <div style={{
            backgroundColor: outlookColors.bg,
            border: `2px solid ${outlookColors.border}`,
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              <div>
                <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Outlook</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: outlookColors.text }}>
                  {company.research_summary.industry_analysis.outlook}
                </p>
              </div>
              <div>
                <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Growth Rate</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: outlookColors.text }}>
                  {company.research_summary.industry_analysis.growth_rate}
                </p>
              </div>
              <div>
                <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Market Position</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: outlookColors.text }}>
                  {company.research_summary.industry_analysis.market_position}
                </p>
              </div>
            </div>
            <div style={{ marginTop: '16px' }}>
              <p style={{ fontSize: '14px', color: '#475569', fontWeight: '600', marginBottom: '8px' }}>
                Industry Trends:
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {company.research_summary.industry_analysis.trends?.map((trend, idx) => (
                  <div key={idx} style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.7)',
                    padding: '12px',
                    borderRadius: '8px',
                    borderLeft: `3px solid ${outlookColors.border}`
                  }}>
                    <p style={{ fontSize: '14px', color: '#1e293b', margin: 0 }}>
                      • {trend}
                    </p>
                  </div>
                )) || <p style={{ fontSize: '14px', color: '#64748b' }}>No trends available</p>}
              </div>
            </div>
          </div>
        </div>

        {/* Litigation Data Section */}
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{
            fontSize: '20px',
            fontWeight: 'bold',
            color: '#1e293b',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ fontSize: '24px' }}>⚖️</span>
            Legal & Compliance
          </h3>
          <div style={{
            backgroundColor: riskColors.bg,
            border: `2px solid ${riskColors.border}`,
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              <div>
                <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Risk Level</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: riskColors.text }}>
                  {company.research_summary.litigation_data.risk_level}
                </p>
              </div>
              <div>
                <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Pending Cases</p>
                <p style={{ fontSize: '18px', fontWeight: 'bold', color: riskColors.text }}>
                  {company.research_summary.litigation_data.pending_cases || 'N/A'}
                </p>
              </div>
            </div>
            <div style={{ marginTop: '16px' }}>
              <p style={{ fontSize: '14px', color: '#475569', fontWeight: '600', marginBottom: '8px' }}>
                Assessment:
              </p>
              <p style={{ fontSize: '14px', color: '#1e293b', margin: 0 }}>
                {company.research_summary.litigation_data.assessment || 'No assessment available'}
              </p>
            </div>
          </div>
        </div>

        {/* Market Signals Section */}
        <div>
          <h3 style={{
            fontSize: '20px',
            fontWeight: 'bold',
            color: '#1e293b',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ fontSize: '24px' }}>📈</span>
            Market Signals
          </h3>
          <div style={{
            background: 'linear-gradient(135deg, #f0f9ff, #e0f2fe)',
            border: '2px solid #0ea5e9',
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)'
          }}>
            <div style={{ marginBottom: '16px' }}>
              <p style={{ fontSize: '14px', color: '#075985', fontWeight: '600', marginBottom: '8px' }}>
                Primary Signal:
              </p>
              <p style={{ fontSize: '16px', color: '#0c4a6e', fontWeight: '600', margin: 0 }}>
                {company.research_summary.market_signals?.primary_signal || 'No signal available'}
              </p>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
              <div>
                <p style={{ fontSize: '14px', color: '#075985', fontWeight: '600', marginBottom: '8px' }}>
                  Technical Indicators:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {company.research_summary.market_signals?.technical_indicators?.map((indicator, idx) => (
                    <p key={idx} style={{ fontSize: '13px', color: '#0c4a6e', margin: 0 }}>
                      • {indicator}
                    </p>
                  )) || <p style={{ fontSize: '13px', color: '#64748b' }}>No indicators available</p>}
                </div>
              </div>
              <div>
                <p style={{ fontSize: '14px', color: '#075985', fontWeight: '600', marginBottom: '8px' }}>
                  Analyst Recommendations:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {company.research_summary.market_signals?.analyst_recommendations?.map((rec, idx) => (
                    <p key={idx} style={{ fontSize: '13px', color: '#0c4a6e', margin: 0 }}>
                      • {rec}
                    </p>
                  )) || <p style={{ fontSize: '13px', color: '#64748b' }}>No recommendations available</p>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      }}>
        <div style={{ textAlign: 'center', backgroundColor: 'white', padding: '48px', borderRadius: '24px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ 
            width: '64px', 
            height: '64px', 
            border: '6px solid #e5e7eb', 
            borderTop: '6px solid #3b82f6', 
            borderRadius: '50%', 
            animation: 'spin 1s linear infinite',
            margin: '0 auto 24px'
          }}></div>
          <p style={{ fontSize: '20px', color: '#1e293b', fontWeight: '600' }}>Loading Research Insights...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      }}>
        <div style={{ textAlign: 'center', backgroundColor: 'white', padding: '48px', borderRadius: '24px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ fontSize: '64px', marginBottom: '24px' }}>❌</div>
          <h2 style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px' }}>
            Error Loading Research
          </h2>
          <p style={{ color: '#64748b', marginBottom: '32px', fontSize: '16px' }}>{error}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              color: 'white',
              padding: '16px 32px',
              borderRadius: '12px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: '600',
              boxShadow: '0 4px 6px rgba(59, 130, 246, 0.3)'
            }}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

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
                {researchData.is_multi_company ? 'Multi-Company Research Insights' : 'Research Insights'}
              </h1>
              <p style={{ 
                fontSize: '20px', 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '400'
              }}>
                {researchData.is_multi_company 
                  ? `Individual research analysis for ${researchData.total_companies} companies`
                  : 'Comprehensive market research and sentiment analysis'
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
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.3)';
                  e.target.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                  e.target.style.transform = 'translateY(0)';
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
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '40px 24px' }}>
        {researchData.is_multi_company ? (
          <div>
            {/* Multi-company header */}
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
                📊 Multi-Company Research Analysis
              </h2>
              <p style={{ fontSize: '18px', color: '#475569', marginBottom: '24px' }}>
                Individual research insights for each uploaded company
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
                  color: '#1e40af'
                }}>
                  Total Companies: {researchData.total_companies}
                </div>
                <div style={{
                  backgroundColor: '#dcfce7',
                  padding: '12px 24px',
                  borderRadius: '25px',
                  fontSize: '16px',
                  fontWeight: '600',
                  color: '#166534'
                }}>
                  Individual Analysis: ✅
                </div>
                <div style={{
                  backgroundColor: '#fef3c7',
                  padding: '12px 24px',
                  borderRadius: '25px',
                  fontSize: '16px',
                  fontWeight: '600',
                  color: '#92400e'
                }}>
                  Unique Insights: ✅
                </div>
              </div>
            </div>

            {/* Individual company insights */}
            {researchData.companies.map((company, index) => (
              <SingleCompanyInsights key={index} company={company} index={index} />
            ))}
          </div>
        ) : (
          <SingleCompanyInsights company={researchData} index={0} />
        )}
      </div>

      </div>
  );
};

export default SimpleResearchInsights;
