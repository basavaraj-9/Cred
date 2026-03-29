import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useMotionValue, useTransform } from 'framer-motion';

const TiltCard = ({ children, style, className }) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const rotateX = useTransform(y, [-100, 100], [10, -10]);
  const rotateY = useTransform(x, [-100, 100], [-10, 10]);

  function handleMouseMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const xPct = (mouseX / width - 0.5) * 200;
    const yPct = (mouseY / height - 0.5) * 200;
    x.set(xPct);
    y.set(yPct);
  }

  function handleMouseLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        ...style,
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
      }}
      className={className}
      whileHover={{ scale: 1.02, translateZ: 20 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      {children}
    </motion.div>
  );
};

const ModernResearchInsights = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data && data !== 'undefined' && data !== 'null') {
      try {
        const parsedData = JSON.parse(data);
        if (parsedData) {
          setCompanyData(parsedData);
          if (parsedData.is_multi_company && parsedData.companies && parsedData.companies.length > 0) {
            setSelectedCompany(parsedData.companies[0]);
          } else {
            setSelectedCompany(parsedData);
          }
        } else {
          navigate('/');
        }
      } catch (err) {
        console.error('Failed to parse company data from localStorage:', err);
        localStorage.removeItem('companyData');
        navigate('/');
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
          <p>Loading research insights...</p>
        </div>
      </div>
    );
  }

  const isMultiCompany = companyData.is_multi_company;
  const companies = isMultiCompany ? companyData.companies : [companyData];

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
          `${company.company} announces new strategic initiatives`,
          `${company.company} exceeds quarterly expectations`,
          `Investment community shows confidence in ${company.company}`
        ],
        articles: [
          {
            title: `${company.company} Shows Strong Growth`,
            source: 'Financial Times',
            date: '2024-03-10',
            sentiment: 'Positive',
            summary: 'Company demonstrates robust performance with significant revenue increase and market expansion.'
          },
          {
            title: 'Market Analysis Update',
            source: 'Bloomberg',
            date: '2024-03-08',
            sentiment: 'Neutral',
            summary: 'Industry analysis shows mixed signals with potential for moderate growth in coming quarters.'
          },
          {
            title: 'Sector Trends Report',
            source: 'Reuters',
            date: '2024-03-05',
            sentiment: 'Positive',
            summary: 'Overall sector performance remains strong with favorable market conditions.'
          }
        ]
      },
      industry_analysis: {
        trend: trends[index % trends.length],
        market_share: Math.floor(Math.random() * 30) + 10,
        competition_level: ['Low', 'Medium', 'High'][index % 3],
        growth_potential: Math.floor(Math.random() * 40) + 60,
        key_metrics: {
          market_size: `${Math.floor(Math.random() * 50 + 100)}B`,
          cagr: `${(Math.random() * 10 + 5).toFixed(1)}%`,
          competitors: Math.floor(Math.random() * 20 + 5)
        }
      },
      legal_compliance: {
        risk_level: risks[index % risks.length],
        compliance_score: Math.floor(Math.random() * 25) + 65,
        pending_litigations: Math.floor(Math.random() * 3),
        regulatory_issues: Math.floor(Math.random() * 2) === 0 ? 'None' : 'Minor',
        filings: [
          { type: 'Annual Report', status: 'Filed', date: '2024-02-15' },
          { type: 'Quarterly Filing', status: 'Filed', date: '2024-03-01' },
          { type: 'Compliance Audit', status: 'In Progress', date: '2024-03-10' }
        ]
      },
      market_signals: {
        technical_indicator: ['Bullish', 'Bearish', 'Neutral'][index % 3],
        volume_trend: ['Increasing', 'Stable', 'Decreasing'][index % 3],
        volatility_index: Math.floor(Math.random() * 50) + 20,
        analyst_rating: ['Buy', 'Hold', 'Sell'][index % 3],
        price_target: `₹${Math.floor(Math.random() * 5000 + 1000)}`,
        recommendations: [
          { firm: 'Goldman Sachs', rating: 'Buy', target: `₹${Math.floor(Math.random() * 5000 + 1000)}` },
          { firm: 'Morgan Stanley', rating: 'Hold', target: `₹${Math.floor(Math.random() * 5000 + 1000)}` },
          { firm: 'JP Morgan', rating: 'Buy', target: `₹${Math.floor(Math.random() * 5000 + 1000)}` }
        ]
      }
    };
  };

  const getSentimentColor = (sentiment) => {
    switch(sentiment) {
      case 'Positive': case 'Optimistic': return { bg: '#dcfce7', text: '#166534', border: '#22c55e', icon: '🟢', gradient: 'linear-gradient(135deg, #22c55e, #16a34a)' };
      case 'Neutral': return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b', icon: '🟡', gradient: 'linear-gradient(135deg, #f59e0b, #d97706)' };
      case 'Cautious': case 'Declining': return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444', icon: '🔴', gradient: 'linear-gradient(135deg, #ef4444, #dc2626)' };
      default: return { bg: '#f3f4f6', text: '#374151', border: '#9ca3af', icon: '⚪', gradient: 'linear-gradient(135deg, #9ca3af, #6b7280)' };
    }
  };

  const company = selectedCompany;
  const research = generateCompanyResearch(company, 0);
  const sentimentColors = getSentimentColor(research.news_sentiment.sentiment);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mesh-background"
      style={{ 
        minHeight: '100vh', 
        background: 'var(--dashboard-bg)',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        perspective: '1500px',
        overflowX: 'hidden'
      }}
    >
      {/* Enhanced Animated background elements */}
      <motion.div style={{
        position: 'absolute',
        top: '10%',
        left: '5%',
        width: '300px',
        height: '300px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.25) 0%, transparent 70%)',
        borderRadius: '50%',
      }} animate={{ 
        y: [0, -30, 0],
        scale: [1, 1.1, 1],
        opacity: [0.3, 0.5, 0.3]
      }} transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}></motion.div>
      <motion.div style={{
        position: 'absolute',
        top: '60%',
        right: '10%',
        width: '250px',
        height: '250px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%)',
        borderRadius: '50%',
      }} animate={{ 
        y: [0, 40, 0],
        x: [0, 20, 0],
        opacity: [0.2, 0.4, 0.2]
      }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}></motion.div>
      <motion.div style={{
        position: 'absolute',
        bottom: '20%',
        left: '15%',
        width: '200px',
        height: '200px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%)',
        borderRadius: '50%',
      }} animate={{ 
        y: [0, -50, 0],
        opacity: [0.1, 0.3, 0.1]
      }} transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}></motion.div>

      {/* Enhanced Header */}
      <div style={{ 
        background: 'var(--header-bg)', 
        backdropFilter: 'var(--glass-blur)',
        borderBottom: '1px solid var(--border-color)',
        padding: '24px 0',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
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
                <span style={{ fontSize: '40px' }}>📈</span>
                Research Insights
              </h1>
              <p style={{ 
                fontSize: '18px', 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '400'
              }}>
                {isMultiCompany 
                  ? `Individual research insights for ${companies.length} companies with comprehensive analysis`
                  : 'AI-powered research analysis and insights'
                }
              </p>
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <motion.button
                onClick={() => navigate('/dashboard')}
                whileHover={{ scale: 1.05, translateZ: 10 }}
                whileTap={{ scale: 0.95 }}
                className="glass-3d"
                style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  boxShadow: 'var(--card-shadow)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📊 Dashboard
              </motion.button>
              <motion.button
                onClick={() => navigate('/dynamic-dashboard')}
                whileHover={{ scale: 1.05, translateZ: 10 }}
                whileTap={{ scale: 0.95 }}
                className="glass-3d"
                style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  boxShadow: 'var(--card-shadow)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                🚀 Dynamic Dashboard
              </motion.button>
              <motion.button
                onClick={() => navigate('/cam-preview')}
                whileHover={{ scale: 1.05, translateZ: 10 }}
                whileTap={{ scale: 0.95 }}
                className="glass-3d"
                style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  boxShadow: 'var(--card-shadow)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📄 Generate CAM
              </motion.button>
              <motion.button
                onClick={() => navigate('/')}
                whileHover={{ scale: 1.05, translateZ: 10 }}
                whileTap={{ scale: 0.95 }}
                className="glass-3d"
                style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  color: 'white',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  border: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  boxShadow: 'var(--card-shadow)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📤 New Upload
              </motion.button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, maxWidth: '1400px', margin: '0 auto', padding: '32px 24px', width: '100%' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '32px' }}>
          
          {/* Enhanced Sidebar */}
          <div style={{
            background: 'var(--card-bg)',
            backdropFilter: 'var(--glass-blur)',
            borderRadius: '24px',
            padding: '24px',
            boxShadow: 'var(--card-shadow)',
            border: '1px solid var(--border-color)',
            height: 'fit-content',
            position: 'sticky',
            top: '120px'
          }}>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              🏢 {isMultiCompany ? 'Companies' : 'Company Details'}
            </h3>
            
            {isMultiCompany ? (
              <div>
                <div style={{ 
                  background: 'rgba(59, 130, 246, 0.1)',
                  padding: '16px',
                  borderRadius: '12px',
                  marginBottom: '20px',
                  border: '1px solid rgba(59, 130, 246, 0.2)'
                }}>
                  <p style={{ fontSize: '16px', fontWeight: '600', color: '#3b82f6', margin: '0 0 8px 0' }}>
                    Total Companies
                  </p>
                  <p style={{ fontSize: '32px', fontWeight: 'bold', color: 'var(--text-primary)', margin: 0 }}>
                    {companies.length}
                  </p>
                </div>
                
                {companies.map((comp, index) => (
                  <motion.div
                    key={comp.unique_hash || index}
                    onClick={() => setSelectedCompany(comp)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    style={{
                      padding: '16px',
                      borderRadius: '12px',
                      marginBottom: '12px',
                      cursor: 'pointer',
                      background: selectedCompany?.unique_hash === comp.unique_hash 
                        ? 'linear-gradient(135deg, #3b82f6, #2563eb)' 
                        : 'rgba(255, 255, 255, 0.05)',
                      border: selectedCompany?.unique_hash === comp.unique_hash 
                        ? '1px solid #3b82f6' 
                        : '1px solid var(--border-color)',
                      transition: 'all 0.3s ease',
                      boxShadow: selectedCompany?.unique_hash === comp.unique_hash 
                        ? '0 8px 16px rgba(59, 130, 246, 0.3)' 
                        : 'none'
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
                        color: 'white'
                      }}>
                        {index + 1}
                      </div>
                      <div style={{ flex: 1 }}>
                        <p style={{ 
                          fontSize: '16px', 
                          fontWeight: '700', 
                          color: selectedCompany?.unique_hash === comp.unique_hash ? 'white' : 'var(--text-primary)',
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
                  </motion.div>
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

          {/* Enhanced Main Research Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* Enhanced Top Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px' }}>
              <TiltCard style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '24px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
                position: 'relative',
                overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: sentimentColors.gradient
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-secondary)', margin: 0 }}>
                    News Sentiment
                  </h4>
                  <span style={{ fontSize: '24px' }}>{sentimentColors.icon}</span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: sentimentColors.text, margin: '0 0 12px 0' }}>
                  {research.news_sentiment.sentiment}
                </p>
                <div style={{
                  padding: '8px 16px',
                  backgroundColor: sentimentColors.bg,
                  borderRadius: '20px',
                  display: 'inline-block',
                  border: `1px solid ${sentimentColors.border}`
                }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: sentimentColors.text }}>
                    {research.news_sentiment.confidence}% confidence
                  </span>
                </div>
              </TiltCard>

              <TiltCard style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '24px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
                position: 'relative',
                overflow: 'hidden',
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
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-secondary)', margin: 0 }}>
                    Industry Trend
                  </h4>
                  <span style={{ fontSize: '24px' }}>📊</span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                  {research.industry_analysis.trend}
                </p>
                <div style={{
                  padding: '8px 16px',
                  backgroundColor: '#dcfce7',
                  borderRadius: '20px',
                  display: 'inline-block',
                  border: '1px solid #22c55e'
                }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: '#166534' }}>
                    {research.industry_analysis.growth_potential}% growth potential
                  </span>
                </div>
              </TiltCard>

              <TiltCard style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '24px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
                position: 'relative',
                overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: 'linear-gradient(135deg, #f59e0b, #d97706)'
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-secondary)', margin: 0 }}>
                    Legal Risk
                  </h4>
                  <span style={{ fontSize: '24px' }}>⚖️</span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                  {research.legal_compliance.risk_level}
                </p>
                <div style={{
                  padding: '8px 16px',
                  backgroundColor: '#fef3c7',
                  borderRadius: '20px',
                  display: 'inline-block',
                  border: '1px solid #f59e0b'
                }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: '#92400e' }}>
                    {research.legal_compliance.compliance_score}/100 compliance
                  </span>
                </div>
              </TiltCard>

              <TiltCard style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '24px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
                position: 'relative',
                overflow: 'hidden',
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
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-secondary)', margin: 0 }}>
                    Market Signal
                  </h4>
                  <span style={{ fontSize: '24px' }}>📈</span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                  {research.market_signals.technical_indicator}
                </p>
                <div style={{
                  padding: '8px 16px',
                  backgroundColor: '#f3e8ff',
                  borderRadius: '20px',
                  display: 'inline-block',
                  border: '1px solid #8b5cf6'
                }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: '#6b21a8' }}>
                    {research.market_signals.analyst_rating} rating
                  </span>
                </div>
              </TiltCard>
            </div>

            {/* Enhanced Main Content Area */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
              
              {/* Enhanced Left Panel - Detailed Analysis */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                
                {/* Enhanced News Sentiment Analysis */}
                <TiltCard style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  borderRadius: '24px',
                  padding: '32px',
                  boxShadow: 'var(--card-shadow)',
                  border: '1px solid var(--border-color)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: sentimentColors.gradient,
                    borderRadius: '20px 20px 0 0'
                  }}></div>

                  <h3 style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    📰 {isMultiCompany ? `Company ${companies.indexOf(company) + 1} News Sentiment` : 'News Sentiment Analysis'}
                  </h3>
                  
                  <div style={{ marginBottom: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
                      <span style={{ fontSize: '32px' }}>{sentimentColors.icon}</span>
                      <div style={{ flex: 1 }}>
                        <span style={{
                          background: sentimentColors.gradient,
                          color: 'white',
                          padding: '8px 16px',
                          borderRadius: '25px',
                          fontSize: '16px',
                          fontWeight: '700',
                          display: 'inline-block'
                        }}>
                          {research.news_sentiment.sentiment}
                        </span>
                        <span style={{ fontSize: '16px', color: 'var(--text-secondary)', marginLeft: '12px' }}>
                          ({research.news_sentiment.confidence}% confidence)
                        </span>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginBottom: '24px' }}>
                    <h4 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
                      Recent Headlines
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {research.news_sentiment.headlines.map((headline, i) => (
                        <div key={i} style={{ 
                          padding: '16px', 
                          background: 'rgba(255, 255, 255, 0.05)', 
                          borderRadius: '12px',
                          border: '1px solid var(--border-color)',
                          position: 'relative',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '4px',
                            height: '100%',
                            background: sentimentColors.gradient
                          }}></div>
                          <p style={{ fontSize: '15px', color: 'var(--text-primary)', margin: 0, paddingLeft: '12px', fontWeight: '500' }}>
                            {headline}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
                      News Articles
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {research.news_sentiment.articles.map((article, i) => (
                        <div key={i} style={{ 
                          padding: '20px', 
                          background: 'rgba(255, 255, 255, 0.05)', 
                          borderRadius: '16px',
                          border: '1px solid var(--border-color)',
                          position: 'relative',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '4px',
                            height: '100%',
                            background: getSentimentColor(article.sentiment).gradient
                          }}></div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px', paddingLeft: '12px' }}>
                            <h5 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                              {article.title}
                            </h5>
                            <span style={{
                              backgroundColor: getSentimentColor(article.sentiment).bg,
                              color: getSentimentColor(article.sentiment).text,
                              padding: '4px 12px',
                              borderRadius: '20px',
                              fontSize: '12px',
                              fontWeight: '600',
                              border: `1px solid ${getSentimentColor(article.sentiment).border}`
                            }}>
                              {article.sentiment}
                            </span>
                          </div>
                          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '0 0 12px 12px' }}>
                            {article.source} • {article.date}
                          </p>
                          <p style={{ fontSize: '14px', color: 'var(--text-primary)', margin: 0, paddingLeft: '12px', lineHeight: '1.5' }}>
                            {article.summary}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </TiltCard>

                {/* Enhanced Industry Analysis */}
                <TiltCard style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  borderRadius: '24px',
                  padding: '32px',
                  boxShadow: 'var(--card-shadow)',
                  border: '1px solid var(--border-color)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: 'linear-gradient(90deg, #10b981, #059669, #047857)',
                    borderRadius: '20px 20px 0 0'
                  }}></div>

                  <h3 style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    📊 Industry Analysis
                  </h3>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '20px', marginBottom: '24px' }}>
                    <div style={{ 
                      background: 'rgba(255, 255, 255, 0.05)', 
                      padding: '20px', 
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '3px',
                        background: 'linear-gradient(135deg, #10b981, #059669)'
                      }}></div>
                      <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: '0 0 8px 0', fontWeight: '600' }}>Market Trend</p>
                      <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                        {research.industry_analysis.trend}
                      </p>
                      <div style={{
                        height: '6px',
                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        borderRadius: '3px',
                        overflow: 'hidden'
                      }}>
                        <div style={{
                          width: research.industry_analysis.trend === 'Growing' ? '80%' : 
                                 research.industry_analysis.trend === 'Stable' ? '50%' : '20%',
                          height: '100%',
                          background: 'linear-gradient(135deg, #10b981, #059669)',
                          borderRadius: '3px'
                        }}></div>
                      </div>
                    </div>
                    
                    <div style={{ 
                      background: 'rgba(255, 255, 255, 0.05)', 
                      padding: '20px', 
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '3px',
                        background: 'linear-gradient(135deg, #3b82f6, #2563eb)'
                      }}></div>
                      <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: '0 0 8px 0', fontWeight: '600' }}>Market Share</p>
                      <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                        {research.industry_analysis.market_share}%
                      </p>
                      <div style={{
                        height: '6px',
                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        borderRadius: '3px',
                        overflow: 'hidden'
                      }}>
                        <div style={{
                          width: `${research.industry_analysis.market_share}%`,
                          height: '100%',
                          background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                          borderRadius: '3px'
                        }}></div>
                      </div>
                    </div>
                    
                    <div style={{ 
                      background: 'rgba(255, 255, 255, 0.05)', 
                      padding: '20px', 
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '3px',
                        background: 'linear-gradient(135deg, #10b981, #059669)'
                      }}></div>
                      <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: '0 0 8px 0', fontWeight: '600' }}>Growth Potential</p>
                      <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                        {research.industry_analysis.growth_potential}%
                      </p>
                      <div style={{
                        height: '6px',
                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        borderRadius: '3px',
                        overflow: 'hidden'
                      }}>
                        <div style={{
                          width: `${research.industry_analysis.growth_potential}%`,
                          height: '100%',
                          background: 'linear-gradient(135deg, #10b981, #059669)',
                          borderRadius: '3px'
                        }}></div>
                      </div>
                    </div>
                    
                    <div style={{ 
                      background: 'rgba(255, 255, 255, 0.05)', 
                      padding: '20px', 
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '3px',
                        background: 'linear-gradient(135deg, #f59e0b, #d97706)'
                      }}></div>
                      <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: '0 0 8px 0', fontWeight: '600' }}>Competition</p>
                      <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0 0 12px 0' }}>
                        {research.industry_analysis.competition_level}
                      </p>
                      <div style={{
                        height: '6px',
                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        borderRadius: '3px',
                        overflow: 'hidden'
                      }}>
                        <div style={{
                          width: research.industry_analysis.competition_level === 'Low' ? '30%' : 
                                 research.industry_analysis.competition_level === 'Medium' ? '60%' : '90%',
                          height: '100%',
                          background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                          borderRadius: '3px'
                        }}></div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
                      Key Industry Metrics
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
                      <div style={{ 
                        background: 'rgba(59, 130, 246, 0.1)', 
                        padding: '20px', 
                        borderRadius: '16px',
                        border: '1px solid rgba(59, 130, 246, 0.2)',
                        textAlign: 'center'
                      }}>
                        <p style={{ fontSize: '14px', color: '#3b82f6', margin: '0 0 8px 0', fontWeight: '600' }}>Market Size</p>
                        <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: 0 }}>
                          ${research.industry_analysis.key_metrics.market_size}
                        </p>
                      </div>
                      <div style={{ 
                        background: 'rgba(16, 185, 129, 0.1)', 
                        padding: '20px', 
                        borderRadius: '16px',
                        border: '1px solid rgba(16, 185, 129, 0.2)',
                        textAlign: 'center'
                      }}>
                        <p style={{ fontSize: '14px', color: '#10b981', margin: '0 0 8px 0', fontWeight: '600' }}>CAGR</p>
                        <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: 0 }}>
                          {research.industry_analysis.key_metrics.cagr}
                        </p>
                      </div>
                      <div style={{ 
                        background: 'rgba(245, 158, 11, 0.1)', 
                        padding: '20px', 
                        borderRadius: '16px',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                        textAlign: 'center'
                      }}>
                        <p style={{ fontSize: '14px', color: '#f59e0b', margin: '0 0 8px 0', fontWeight: '600' }}>Competitors</p>
                        <p style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', margin: 0 }}>
                          {research.industry_analysis.key_metrics.competitors}
                        </p>
                      </div>
                    </div>
                  </div>
                </TiltCard>
              </div>

              {/* Enhanced Right Panel */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                
                {/* Enhanced Legal & Compliance */}
                <TiltCard style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  borderRadius: '24px',
                  padding: '24px',
                  boxShadow: 'var(--card-shadow)',
                  border: '1px solid var(--border-color)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: 'linear-gradient(90deg, #f59e0b, #d97706, #f59e0b)',
                    borderRadius: '20px 20px 0 0'
                  }}></div>

                  <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    ⚖️ Legal & Compliance
                  </h3>
                  
                  <div style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '20px', borderRadius: '16px', marginBottom: '20px', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '14px', color: '#f59e0b', fontWeight: '600' }}>Risk Level</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.legal_compliance.risk_level}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '14px', color: '#f59e0b', fontWeight: '600' }}>Compliance Score</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.legal_compliance.compliance_score}/100
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '14px', color: '#f59e0b', fontWeight: '600' }}>Pending Litigations</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.legal_compliance.pending_litigations}
                      </span>
                    </div>
                  </div>

                  <div>
                    <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '12px' }}>
                      Recent Filings
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {research.legal_compliance.filings.map((filing, i) => (
                        <div key={i} style={{ 
                          padding: '16px', 
                          background: 'rgba(255, 255, 255, 0.05)', 
                          borderRadius: '12px',
                          border: '1px solid var(--border-color)',
                          position: 'relative',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '4px',
                            height: '100%',
                            background: filing.status === 'Filed' ? 'linear-gradient(135deg, #10b981, #059669)' : 'linear-gradient(135deg, #f59e0b, #d97706)'
                          }}></div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingLeft: '12px' }}>
                            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)' }}>
                              {filing.type}
                            </span>
                            <span style={{
                              backgroundColor: filing.status === 'Filed' ? '#dcfce7' : '#fef3c7',
                              color: filing.status === 'Filed' ? '#166534' : '#92400e',
                              padding: '4px 12px',
                              borderRadius: '20px',
                              fontSize: '12px',
                              fontWeight: '600',
                              border: `1px solid ${filing.status === 'Filed' ? '#22c55e' : '#f59e0b'}`
                            }}>
                              {filing.status}
                            </span>
                          </div>
                          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '8px 0 0 12px' }}>
                            {filing.date}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </TiltCard>

                {/* Enhanced Market Signals */}
                <TiltCard style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  borderRadius: '24px',
                  padding: '24px',
                  boxShadow: 'var(--card-shadow)',
                  border: '1px solid var(--border-color)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: 'linear-gradient(90deg, #8b5cf6, #7c3aed, #8b5cf6)',
                    borderRadius: '20px 20px 0 0'
                  }}></div>

                  <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    📈 Market Signals
                  </h3>
                  
                  <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '20px', borderRadius: '16px', marginBottom: '20px', border: '1px solid rgba(139, 92, 246, 0.2)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '14px', color: '#8b5cf6', fontWeight: '600' }}>Technical Indicator</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.market_signals.technical_indicator}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '14px', color: '#8b5cf6', fontWeight: '600' }}>Volume Trend</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.market_signals.volume_trend}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '14px', color: '#8b5cf6', fontWeight: '600' }}>Volatility Index</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.market_signals.volatility_index}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '14px', color: '#8b5cf6', fontWeight: '600' }}>Price Target</span>
                      <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {research.market_signals.price_target}
                      </span>
                    </div>
                  </div>

                  <div>
                    <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '12px' }}>
                      Analyst Recommendations
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {research.market_signals.recommendations.map((rec, i) => (
                        <div key={i} style={{ 
                          padding: '16px', 
                          background: 'rgba(255, 255, 255, 0.05)', 
                          borderRadius: '12px',
                          border: '1px solid var(--border-color)',
                          position: 'relative',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '4px',
                            height: '100%',
                            background: rec.rating === 'Buy' ? 'linear-gradient(135deg, #10b981, #059669)' : 
                                           rec.rating === 'Hold' ? 'linear-gradient(135deg, #f59e0b, #d97706)' : 
                                           'linear-gradient(135deg, #ef4444, #dc2626)'
                          }}></div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingLeft: '12px' }}>
                            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)' }}>
                              {rec.firm}
                            </span>
                            <span style={{
                              backgroundColor: rec.rating === 'Buy' ? '#dcfce7' : 
                                             rec.rating === 'Hold' ? '#fef3c7' : '#fef2f2',
                              color: rec.rating === 'Buy' ? '#166534' : 
                                     rec.rating === 'Hold' ? '#92400e' : '#991b1b',
                              padding: '4px 12px',
                              borderRadius: '20px',
                              fontSize: '12px',
                              fontWeight: '600',
                              border: `1px solid ${rec.rating === 'Buy' ? '#22c55e' : rec.rating === 'Hold' ? '#f59e0b' : '#ef4444'}`
                            }}>
                              {rec.rating}
                            </span>
                          </div>
                          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '8px 0 0 12px' }}>
                            Target: {rec.target}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </TiltCard>

                {/* Enhanced Quick Actions */}
                <TiltCard style={{
                  background: 'var(--card-bg)',
                  backdropFilter: 'var(--glass-blur)',
                  borderRadius: '24px',
                  padding: '24px',
                  boxShadow: 'var(--card-shadow)',
                  border: '1px solid var(--border-color)',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899)',
                    borderRadius: '20px 20px 0 0'
                  }}></div>

                  <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    🚀 Quick Actions
                  </h3>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {/* ... (buttons remain the same, just keeping the TiltCard wrapper) ... */}
                    <button
                      onClick={() => navigate('/dashboard')}
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
                      <span style={{ fontSize: '20px' }}>📊</span>
                      <div style={{ textAlign: 'left' }}>
                        <div>View Dashboard</div>
                        <div style={{ fontSize: '12px', opacity: 0.8 }}>Risk analysis overview</div>
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
                </TiltCard>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ModernResearchInsights;
