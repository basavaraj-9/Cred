import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, 
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, PieChart, Pie, Cell 
} from 'recharts';
import BankAnalysisTab from './components/BankAnalysisTab';

const ModernDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [simulation, setSimulation] = useState({
    amount: 10,
    rate: 12,
    tenure: 36,
    riskScore: 50
  });

  useEffect(() => {
    if (selectedCompany) {
      const loanData = selectedCompany.loan_affordability;
      const amount = parseFloat(loanData?.max_loan_amount?.replace(/[^0-9.]/g, '') || 10);
      const rate = parseFloat(loanData?.interest_rate?.replace(/[^0-9.]/g, '') || 12);
      const tenure = loanData?.loan_term_months || 36;
      
      setSimulation({
        amount,
        rate,
        tenure,
        riskScore: selectedCompany.ai_analysis?.risk_analysis?.risk_score || 50
      });
    }
  }, [selectedCompany]);

  const handleSimulationChange = (field, value) => {
    const val = parseFloat(value);
    const newSim = { ...simulation, [field]: val };
    
    // Simulate risk score impact
    const baseRisk = selectedCompany?.ai_analysis?.risk_analysis?.risk_score || 50;
    const origAmount = parseFloat(selectedCompany?.loan_affordability?.max_loan_amount?.replace(/[^0-9.]/g, '') || 10);
    
    const amountImpact = (newSim.amount - origAmount) / origAmount * 20;
    const rateImpact = (newSim.rate - 12) * 2;
    const tenureImpact = (newSim.tenure - 36) / 12 * 5;
    
    newSim.riskScore = Math.max(1, Math.min(100, Math.round(baseRisk - (amountImpact + rateImpact + tenureImpact))));
    setSimulation(newSim);
  };

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data && data !== 'undefined' && data !== 'null') {
      try {
        const parsedData = JSON.parse(data);
        console.log('Raw data from localStorage:', parsedData);
        if (parsedData) {
          setCompanyData(parsedData);
          if (parsedData.is_multi_company && parsedData.companies && parsedData.companies.length > 0) {
            console.log('Setting selected company (multi):', parsedData.companies[0]);
            setSelectedCompany(parsedData.companies[0]);
          } else {
            console.log('Setting selected company (single):', parsedData);
            setSelectedCompany(parsedData);
          }
        } else {
          console.error('Parsed data is empty');
          navigate('/');
        }
      } catch (err) {
        console.error('Failed to parse company data from localStorage:', err);
        localStorage.removeItem('companyData');
        navigate('/');
      }
    } else {
      console.log('No valid company data in localStorage, redirecting to upload');
      navigate('/');
    }
  }, [navigate]);

  if (!companyData) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        background: 'var(--bg-primary)',
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
  console.log('Current company data:', company);
  console.log('Loan affordability:', company?.loan_affordability);
  console.log('Financial metrics:', company?.financial_metrics);
  console.log('Liabilities breakdown:', company?.liabilities_breakdown);
  console.log('Risk score:', company?.ai_analysis?.risk_analysis?.risk_score);
  const riskColors = getRiskColor(company?.ai_analysis?.risk_analysis?.risk_score || 50);
  const decisionColors = getDecisionColor(company?.ai_analysis?.decision_result?.decision || 'REVIEW REQUIRED');

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'var(--dashboard-bg)',
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
                onClick={() => navigate('/dynamic-dashboard')}
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
                🚀 Dynamic Dashboard
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
            background: 'var(--card-bg)',
            backdropFilter: 'var(--glass-blur)',
            borderRadius: '20px',
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
            
            {/* Tab Navigation */}
            <div style={{ 
              display: 'flex', 
              gap: '12px', 
              background: 'var(--card-bg)', 
              padding: '6px', 
              borderRadius: '16px', 
              width: 'fit-content',
              border: '1px solid var(--border-color)',
              backdropFilter: 'var(--glass-blur)'
            }}>
              <button
                onClick={() => setActiveTab('overview')}
                style={{
                  padding: '10px 24px',
                  borderRadius: '12px',
                  border: 'none',
                  background: activeTab === 'overview' ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : 'transparent',
                  color: activeTab === 'overview' ? 'white' : 'var(--text-secondary)',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease'
                }}
              >
                📊 Overview
              </button>
              <button
                onClick={() => setActiveTab('bank')}
                style={{
                  padding: '10px 24px',
                  borderRadius: '12px',
                  border: 'none',
                  background: activeTab === 'bank' ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : 'transparent',
                  color: activeTab === 'bank' ? 'white' : 'var(--text-secondary)',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease'
                }}
              >
                🏦 Bank Analysis
              </button>
            </div>

            {activeTab === 'overview' ? (
              <>
                {/* Enhanced Top Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px' }}>
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
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
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-secondary)', margin: 0 }}>
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
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
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

              {/* New Loan Affordability Card */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
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
                    Max Loan Amount
                  </h4>
                  <span style={{ fontSize: '24px' }}>💰</span>
                </div>
                <p style={{ fontSize: '28px', fontWeight: 'bold', color: '#059669', margin: '0 0 12px 0' }}>
                  {company?.loan_affordability?.max_loan_amount || '0M'}
                </p>
                <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Interest Rate:</span>
                    <span style={{ fontWeight: '600' }}>{company?.loan_affordability?.interest_rate || '8%'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Term:</span>
                    <span style={{ fontWeight: '600' }}>{company?.loan_affordability?.loan_term_months || 60} months</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Affordability Score:</span>
                    <span style={{ fontWeight: '600', color: '#059669' }}>{company?.loan_affordability?.affordability_score || 75}/100</span>
                  </div>
                </div>
              </div>

              {/* New Financial Health Card */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
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
                  background: 'linear-gradient(135deg, #3b82f6, #2563eb)'
                }}></div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                    Financial Health
                  </h4>
                  <span style={{ fontSize: '24px' }}>📊</span>
                </div>
                <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Debt-to-Equity:</span>
                    <span style={{ fontWeight: '600' }}>{company?.financial_metrics?.debt_to_equity_ratio || '1.5'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Current Ratio:</span>
                    <span style={{ fontWeight: '600' }}>{company?.financial_metrics?.current_ratio || '1.8'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Profit Margin:</span>
                    <span style={{ fontWeight: '600' }}>{company?.financial_metrics?.profit_margin || '12%'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Interactive Charts Section */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              {/* Financial Performance Chart */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
                height: '400px',
                transition: 'all 0.3s ease'
              }}>
                <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px' }}>
                  📈 Financial Overview (Major Metrics)
                </h3>
                <ResponsiveContainer width="100%" height="80%">
                  <BarChart data={[
                    { name: 'Assets', value: parseFloat(company?.financial_metrics?.total_assets?.replace(/[^0-9.]/g, '') || 500) },
                    { name: 'Liabilities', value: parseFloat(company?.financial_metrics?.total_liabilities?.replace(/[^0-9.]/g, '') || 200) },
                    { name: 'Revenue', value: parseFloat(company?.financial_metrics?.monthly_revenue?.replace(/[^0-9.]/g, '') || 100) * 12 },
                    { name: 'Equity', value: parseFloat(company?.financial_metrics?.equity?.replace(/[^0-9.]/g, '') || 300) }
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                    <XAxis dataKey="name" stroke="var(--text-secondary)" />
                    <YAxis stroke="var(--text-secondary)" />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-color)', color: 'var(--text-primary)' }} />
                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Risk Factor Distribution (Explainable AI) */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
                height: '400px',
                transition: 'all 0.3s ease'
              }}>
                <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px' }}>
                  🎯 AI Decision Rationale (Factor Weighting)
                </h3>
                <ResponsiveContainer width="100%" height="80%">
                  <RadarChart cx="50%" cy="50%" outerRadius="80%" data={
                    company?.ai_analysis?.factor_weights ? 
                    Object.keys(company?.ai_analysis?.factor_weights).map(key => ({
                      subject: key.replace('_', ' ').toUpperCase(),
                      A: company.ai_analysis.factor_weights[key],
                      fullMark: 100
                    })) : [
                      { subject: 'FINANCIAL', A: 80, fullMark: 100 },
                      { subject: 'MARKET', A: 65, fullMark: 100 },
                      { subject: 'INDUSTRY', A: 70, fullMark: 100 },
                      { subject: 'HISTORY', A: 50, fullMark: 100 }
                    ]
                  }>
                    <PolarGrid stroke="var(--border-color)" />
                    <PolarAngleAxis dataKey="subject" stroke="var(--text-secondary)" fontSize={10} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="var(--text-secondary)" />
                    <Radar name="Weight" dataKey="A" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.6} />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-color)', color: 'var(--text-primary)' }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* New Detailed Financial Metrics Section */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              
              {/* Financial Metrics Card */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '28px',
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
                  background: 'linear-gradient(135deg, #3b82f6, #2563eb)'
                }}></div>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  💼 Financial Metrics
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Total Assets</p>
                    <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', margin: 0 }}>
                      {company?.financial_metrics?.total_assets || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Total Liabilities</p>
                    <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.financial_metrics?.total_liabilities || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Equity</p>
                    <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#059669', margin: 0 }}>
                      {company?.financial_metrics?.equity || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Monthly Revenue</p>
                    <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', margin: 0 }}>
                      {company?.financial_metrics?.monthly_revenue || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Monthly Profit</p>
                    <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#059669', margin: 0 }}>
                      {company?.financial_metrics?.monthly_profit || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Cash Flow</p>
                    <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#3b82f6', margin: 0 }}>
                      {company?.financial_metrics?.cash_flow || '0M'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Liabilities Breakdown Card */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '28px',
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
                  background: 'linear-gradient(135deg, #ef4444, #dc2626)'
                }}></div>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  ⚠️ Liabilities Breakdown
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Accounts Payable</p>
                    <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.liabilities_breakdown?.accounts_payable || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Short-term Debt</p>
                    <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.liabilities_breakdown?.short_term_debt || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Accrued Expenses</p>
                    <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.liabilities_breakdown?.accrued_expenses || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Long-term Bank Loans</p>
                    <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.liabilities_breakdown?.long_term_bank_loans || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Bonds Payable</p>
                    <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.liabilities_breakdown?.bonds_payable || '0M'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 4px 0' }}>Other Liabilities</p>
                    <p style={{ fontSize: '16px', fontWeight: 'bold', color: '#dc2626', margin: 0 }}>
                      {company?.liabilities_breakdown?.other_current_liabilities || '0M'}
                    </p>
                  </div>
                </div>
              </div>
            </div>

              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
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
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '24px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
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

            {/* Risk Analysis Factors */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(20px)',
              borderRadius: '20px',
              padding: '28px',
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
                background: 'linear-gradient(135deg, #8b5cf6, #7c3aed)'
              }}></div>
              <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                🎯 Risk Analysis Factors
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
                {Object.entries(company?.ai_analysis?.risk_analysis?.factors || {}).map(([key, value]) => (
                  <div key={key} style={{
                    background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)',
                    padding: '20px',
                    borderRadius: '16px',
                    border: '1px solid #e2e8f0',
                    transition: 'all 0.3s ease'
                  }}>
                    <p style={{ fontSize: '14px', color: '#64748b', margin: '0 0 8px 0', fontWeight: '600' }}>
                      {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: value > 70 ? '#10b981' : value > 40 ? '#f59e0b' : '#ef4444'
                      }}></div>
                      <p style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b', margin: 0 }}>
                        {value}/100
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Reasoning */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(20px)',
              borderRadius: '20px',
              padding: '28px',
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
                background: 'linear-gradient(135deg, #06b6d4, #0891b2)'
              }}></div>
              <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                🤖 AI Reasoning
              </h3>
              <div style={{
                background: 'linear-gradient(135deg, #f0f9ff, #e0f2fe)',
                padding: '20px',
                borderRadius: '16px',
                border: '1px solid #0ea5e9'
              }}>
                <p style={{ fontSize: '16px', color: '#0c4a6e', lineHeight: '1.6', margin: 0 }}>
                  {company?.ai_analysis?.decision_result?.reasoning || 'AI analysis based on comprehensive financial metrics and risk assessment.'}
                </p>
              </div>
            </div>
            {/* AI Decision Rationale & What-If Panel */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              {/* Decision Rationale */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '32px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
              }}>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                  📜 Decision Rationale
                </h3>
                <div style={{
                  background: 'rgba(59, 130, 246, 0.1)',
                  padding: '20px',
                  borderRadius: '16px',
                  border: '1px solid rgba(59, 130, 246, 0.2)',
                  marginBottom: '24px'
                }}>
                  <p style={{ fontSize: '16px', fontWeight: '600', color: '#3b82f6', marginBottom: '8px' }}>
                    AI Summary
                  </p>
                  <p style={{ fontSize: '15px', color: 'var(--text-primary)', margin: 0, lineHeight: '1.6' }}>
                    {company?.ai_analysis?.decision_rationale?.summary || "Analysis indicates stable financial metrics with moderate exposure to market volatility. The primary decision driver is the current health of the manufacturing sector."}
                  </p>
                </div>
                <div>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '12px' }}>
                    Key Observations
                  </h4>
                  <ul style={{ paddingLeft: '20px', margin: 0 }}>
                    {(company?.ai_analysis?.decision_rationale?.key_observations || [
                      "Consistent revenue growth over the last 12 months.",
                      "Low debt-to-equity ratio compared to industry peers.",
                      "Diversified client base reduces single-source risk."
                    ]).map((obs, i) => (
                      <li key={i} style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '8px' }}>
                        {obs}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* What-If Panel */}
              <div style={{
                background: 'var(--card-bg)',
                backdropFilter: 'var(--glass-blur)',
                borderRadius: '20px',
                padding: '32px',
                boxShadow: 'var(--card-shadow)',
                border: '1px solid var(--border-color)',
              }}>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                  🧪 What-If Analysis
                </h3>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
                  Simulate different loan scenarios to see real-time impact on risk assessment.
                </p>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Loan Amount</span>
                      <span style={{ fontSize: '14px', color: '#3b82f6', fontWeight: 'bold' }}>{simulation.amount.toFixed(1)}M</span>
                    </div>
                    <input 
                      type="range" 
                      min={simulation.amount * 0.5} 
                      max={simulation.amount * 2} 
                      step="0.1"
                      value={simulation.amount}
                      onChange={(e) => handleSimulationChange('amount', e.target.value)}
                      style={{ width: '100%', cursor: 'pointer' }} 
                    />
                  </div>
                  
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Interest Rate</span>
                      <span style={{ fontSize: '14px', color: '#3b82f6', fontWeight: 'bold' }}>{simulation.rate.toFixed(1)}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="5" 
                      max="25" 
                      step="0.5"
                      value={simulation.rate}
                      onChange={(e) => handleSimulationChange('rate', e.target.value)}
                      style={{ width: '100%', cursor: 'pointer' }} 
                    />
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Tenure (Months)</span>
                      <span style={{ fontSize: '14px', color: '#3b82f6', fontWeight: 'bold' }}>{simulation.tenure} months</span>
                    </div>
                    <input 
                      type="range" 
                      min="6" 
                      max="84" 
                      step="6"
                      value={simulation.tenure}
                      onChange={(e) => handleSimulationChange('tenure', e.target.value)}
                      style={{ width: '100%', cursor: 'pointer' }} 
                    />
                  </div>
                </div>

                <div style={{ 
                  marginTop: '32px', 
                  padding: '16px', 
                  background: simulation.riskScore >= 70 ? 'linear-gradient(135deg, #22c55e, #16a34a)' : simulation.riskScore >= 50 ? 'linear-gradient(135deg, #f59e0b, #d97706)' : 'linear-gradient(135deg, #ef4444, #dc2626)', 
                  borderRadius: '12px',
                  color: 'white',
                  textAlign: 'center',
                  transition: 'all 0.5s ease'
                }}>
                  <p style={{ fontSize: '12px', opacity: 0.9, margin: '0 0 4px 0' }}>Simulated Risk Score</p>
                  <p style={{ fontSize: '24px', fontWeight: 'bold', margin: 0 }}>{simulation.riskScore} / 100</p>
                </div>
              </div>
            </div>
          </>
        ) : (
          <BankAnalysisTab bankData={company?.bank_analysis} />
        )}
      </div>
    </div>
  </div>
</div>
  );
};

export default ModernDashboard;
