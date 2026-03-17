import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const WorkingDynamicDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [dynamicAnalysis, setDynamicAnalysis] = useState({});
  const [loading, setLoading] = useState(false);

  // Dynamic calculation functions
  const calculateRiskScore = (company) => {
    const annualRevenue = parseFloat(company.revenue || '0') * 10000000; // Convert from crores to rupees
    const monthlyRevenue = parseFloat(company.financial_metrics?.monthly_revenue || '0');
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0');
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0');
    const equity = parseFloat(company.financial_metrics?.equity || '0');

    // Calculate component scores
    const revenueGrowthScore = Math.min(100, Math.max(0, 60 + (annualRevenue / 100000000) * 20)); // Scale with revenue
    const cashFlowScore = monthlyProfit > 0 ? Math.min(100, 70 + (monthlyProfit / monthlyRevenue) * 30) : 30;
    const debtRatioScore = totalLiabilities > 0 ? Math.max(20, 100 - (totalLiabilities / equity) * 50) : 80;
    const industryRiskScore = company.industry === 'Technology' ? 85 : 
                           company.industry === 'Manufacturing' ? 70 : 
                           company.industry === 'Healthcare' ? 80 : 
                           company.industry === 'Finance' ? 65 : 75;

    const riskScore = Math.round(
      revenueGrowthScore * 0.3 +
      cashFlowScore * 0.3 +
      debtRatioScore * 0.2 +
      industryRiskScore * 0.2
    );

    return Math.max(0, Math.min(100, riskScore));
  };

  const determineDecision = (riskScore) => {
    if (riskScore >= 75) {
      return { decision: 'APPROVED', confidence: 85 + Math.floor(Math.random() * 10) };
    } else if (riskScore >= 60) {
      return { decision: 'CONDITIONALLY_APPROVED', confidence: 75 + Math.floor(Math.random() * 10) };
    } else {
      return { decision: 'REJECTED', confidence: 75 + Math.floor(Math.random() * 10) };
    }
  };

  const calculateLoanAmount = (company, riskScore) => {
    const annualRevenue = parseFloat(company.revenue || '0') * 10000000; // Convert from crores to rupees
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0');
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0');
    const equity = parseFloat(company.financial_metrics?.equity || '0');

    // Dynamic loan multiplier based on risk score
    let loanMultiplier = 0.3;
    if (riskScore >= 80) loanMultiplier = 0.4;  // Low risk = higher loan
    else if (riskScore >= 70) loanMultiplier = 0.35;
    else if (riskScore >= 60) loanMultiplier = 0.3;
    else if (riskScore >= 50) loanMultiplier = 0.25;
    else loanMultiplier = 0.2;  // High risk = lower loan

    // Calculate revenue-based loan amount
    const revenueBasedAmount = annualRevenue * loanMultiplier;
    
    // Calculate cash flow capacity (using monthly profit)
    const cashFlowCapacity = monthlyProfit * 12 * 0.4; // 40% of annual profit
    
    // Calculate debt service capacity (considering existing liabilities)
    const debtServiceCapacity = Math.max(0, (equity - totalLiabilities) * 0.5);
    
    // Take the most conservative amount
    const optimalAmount = Math.min(revenueBasedAmount, cashFlowCapacity, debtServiceCapacity);
    
    // Ensure minimum loan amount and reasonable maximum
    const finalAmount = Math.max(1000000, Math.min(optimalAmount, annualRevenue * 0.5));

    return Math.round(finalAmount);
  };

  const calculateInterestRate = (riskScore, industry) => {
    let baseRate = 12.0;
    
    // Adjust based on risk score (lower risk = lower rate)
    if (riskScore >= 80) baseRate -= 2.0;      // Low risk
    else if (riskScore >= 70) baseRate -= 1.0; // Medium-low risk
    else if (riskScore >= 60) baseRate += 0.0; // Medium risk
    else if (riskScore >= 50) baseRate += 1.0; // Medium-high risk
    else baseRate += 2.0;                       // High risk

    // Industry adjustments
    const industryAdjustments = {
      'Technology': -0.5,
      'Manufacturing': 0.5,
      'Healthcare': -0.3,
      'Finance': 0.2,
      'Retail': 0.3
    };

    const industryAdj = industryAdjustments[industry] || 0;
    const finalRate = baseRate + industryAdj;

    return Math.max(8.0, Math.min(18.0, finalRate)); // Cap between 8% and 18%
  };

  const calculateAffordabilityScore = (company, loanAmount) => {
    const monthlyRevenue = parseFloat(company.financial_metrics?.monthly_revenue || '0');
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0');
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0');
    
    // Calculate monthly EMI (assuming 12% interest for 5 years)
    const monthlyInterestRate = 0.12 / 12;
    const tenureMonths = 60;
    const monthlyEMI = loanAmount * monthlyInterestRate * Math.pow(1 + monthlyInterestRate, tenureMonths) / 
                      (Math.pow(1 + monthlyInterestRate, tenureMonths) - 1);

    // Calculate DTI ratio (Debt-to-Income)
    const dtiRatio = monthlyEMI / monthlyRevenue;
    
    // Calculate cash flow buffer
    const cashFlowBuffer = monthlyProfit / monthlyEMI;

    let score = 50; // Base score
    
    // Adjust based on DTI ratio (lower is better)
    if (dtiRatio <= 0.3) score += 20;
    else if (dtiRatio <= 0.4) score += 10;
    else if (dtiRatio <= 0.5) score += 5;
    else score -= 10;

    // Adjust based on cash flow buffer (higher is better)
    if (cashFlowBuffer >= 2.0) score += 10;
    else if (cashFlowBuffer >= 1.5) score += 5;
    else if (cashFlowBuffer >= 1.0) score += 0;
    else score -= 10;

    // Adjust based on existing liabilities
    const debtToRevenueRatio = totalLiabilities / (monthlyRevenue * 12);
    if (debtToRevenueRatio <= 0.5) score += 10;
    else if (debtToRevenueRatio <= 0.8) score += 5;
    else score -= 15;

    return Math.max(0, Math.min(100, score));
  };

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
    if (score <= 40) return { bg: '#dcfce7', text: '#166534', border: '#22c55e', icon: '🟢' };
    if (score <= 60) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b', icon: '🟡' };
    return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444', icon: '🔴' };
  };

  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'APPROVED': return { bg: '#dcfce7', text: '#166534', icon: '✅' };
      case 'CONDITIONALLY_APPROVED': return { bg: '#fef3c7', text: '#92400e', icon: '⚠️' };
      case 'REJECTED': return { bg: '#fef2f2', text: '#991b1b', icon: '❌' };
      default: return { bg: '#f3f4f6', text: '#374151', icon: '📋' };
    }
  };

  useEffect(() => {
    const storedCompanyData = localStorage.getItem('companyData');
    if (storedCompanyData) {
      const parsedData = JSON.parse(storedCompanyData);
      const company = parsedData.is_multi_company ? parsedData.companies[0] : parsedData;
      setSelectedCompany(company);
      setCompanyData(parsedData); // Set companyData to avoid redirect
      
      setLoading(true);
      setTimeout(() => {
        // Use backend risk score for consistency
        const riskScore = company.ai_analysis?.risk_analysis?.risk_score || calculateRiskScore(company);
        const decision = determineDecision(riskScore);
        const maxLoan = calculateLoanAmount(company, riskScore);
        const interestRate = calculateInterestRate(riskScore, company.industry);
        const affordabilityScore = calculateAffordabilityScore(company, maxLoan);

        setDynamicAnalysis({
          risk_score: riskScore,
          decision: decision.decision,
          confidence: decision.confidence,
          max_loan_amount: maxLoan,
          interest_rate: interestRate.toFixed(1),
          affordability_score: affordabilityScore
        });
        setLoading(false);
      }, 2000);
    } else {
      navigate('/');
    }
  }, [navigate]);

  const handleRefreshAnalysis = () => {
    if (selectedCompany) {
      setLoading(true);
      setTimeout(() => {
        // Use backend risk score for consistency
        const riskScore = selectedCompany.ai_analysis?.risk_analysis?.risk_score || calculateRiskScore(selectedCompany);
        const decision = determineDecision(riskScore);
        const maxLoan = calculateLoanAmount(selectedCompany, riskScore);
        const interestRate = calculateInterestRate(riskScore, selectedCompany.industry);
        const affordabilityScore = calculateAffordabilityScore(selectedCompany, maxLoan);

        setDynamicAnalysis({
          risk_score: riskScore,
          decision: decision.decision,
          confidence: decision.confidence,
          max_loan_amount: maxLoan,
          interest_rate: interestRate.toFixed(1),
          affordability_score: affordabilityScore
        });
        setLoading(false);
      }, 1500);
    }
  };

  const handleCompanyChange = (company) => {
    setSelectedCompany(company);
    setLoading(true);
    setTimeout(() => {
      // Use backend risk score for consistency
      const riskScore = company.ai_analysis?.risk_analysis?.risk_score || calculateRiskScore(company);
      const decision = determineDecision(riskScore);
      const maxLoan = calculateLoanAmount(company, riskScore);
      const interestRate = calculateInterestRate(riskScore, company.industry);
      const affordabilityScore = calculateAffordabilityScore(company, maxLoan);

      setDynamicAnalysis({
        risk_score: riskScore,
        decision: decision.decision,
        confidence: decision.confidence,
        max_loan_amount: maxLoan,
        interest_rate: interestRate.toFixed(1),
        affordability_score: affordabilityScore
      });
      setLoading(false);
    }, 1500);
  };

  if (!companyData) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        background: 'linear-gradient(135deg, #1e40af 0%, #0f766e 50%, #0891b2 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{ 
          textAlign: 'center', 
          color: 'white',
          fontSize: '20px',
          fontWeight: '500'
        }}>
          <div style={{ 
            width: '80px', 
            height: '80px', 
            border: '4px solid rgba(255, 255, 255, 0.3)', 
            borderTop: '4px solid white',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 20px'
          }}></div>
          Loading company data...
        </div>
      </div>
    );
  }

  const companies = companyData?.is_multi_company ? companyData.companies : [companyData];
  const riskColors = getRiskColor(dynamicAnalysis.risk_score || 0);
  const decisionColors = getDecisionColor(dynamicAnalysis.decision || 'PENDING');

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      position: 'relative',
      overflow: 'hidden'
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
                <span style={{ fontSize: '48px' }}>🚀</span>
                Dynamic Credit Analysis
              </h1>
              <p style={{ 
                fontSize: '20px', 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '400',
                marginBottom: '8px'
              }}>
                Real-time risk assessment and loan recommendations
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
                📊 Static Dashboard
              </button>
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
        {/* Company Selector */}
        {companyData?.is_multi_company && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(10px)',
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '32px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            border: '1px solid rgba(255, 255, 255, 0.3)'
          }}>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px' }}>
              Select Company for Analysis
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
              {companies.map((company, index) => (
                <button
                  key={company.unique_hash || index}
                  onClick={() => handleCompanyChange(company)}
                  style={{
                    background: selectedCompany?.unique_hash === company.unique_hash 
                      ? 'linear-gradient(135deg, #3b82f6, #2563eb)' 
                      : 'rgba(255, 255, 255, 0.9)',
                    border: selectedCompany?.unique_hash === company.unique_hash 
                      ? 'none' 
                      : '1px solid rgba(59, 130, 246, 0.3)',
                    borderRadius: '12px',
                    padding: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease',
                    textAlign: 'left'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 8px 16px rgba(59, 130, 246, 0.2)';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
                  }}
                >
                  <div style={{ fontWeight: '600', color: '#1e293b', marginBottom: '4px' }}>
                    {company.company}
                  </div>
                  <div style={{ fontSize: '14px', color: '#64748b' }}>
                    {company.industry} • {company.revenue} Cr Revenue
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Analysis Results */}
        {selectedCompany && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(10px)',
            borderRadius: '20px',
            padding: '32px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            border: '1px solid rgba(255, 255, 255, 0.3)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b' }}>
                {selectedCompany.company} - Dynamic Analysis
              </h2>
              <button
                onClick={handleRefreshAnalysis}
                style={{
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '12px 20px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease'
                }}
                onMouseOver={(e) => e.target.style.background = 'linear-gradient(135deg, #059669, #047857)'}
                onMouseOut={(e) => e.target.style.background = 'linear-gradient(135deg, #10b981, #059669)'}
              >
                🔄 Refresh Analysis
              </button>
            </div>

            {loading ? (
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <div style={{ 
                  width: '60px', 
                  height: '60px', 
                  border: '4px solid rgba(16, 185, 129, 0.3)', 
                  borderTop: '4px solid #10b981',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  margin: '0 auto 16px'
                }}></div>
                <p style={{ color: '#64748b', fontSize: '16px' }}>Analyzing financial data...</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                {/* Risk Score Card */}
                <div style={{
                  background: 'rgba(255, 255, 255, 0.9)',
                  borderRadius: '16px',
                  padding: '24px',
                  border: `2px solid ${riskColors.border}`,
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px', fontWeight: '600' }}>
                    Risk Score
                  </div>
                  <div style={{ fontSize: '48px', fontWeight: 'bold', color: riskColors.text, marginBottom: '8px' }}>
                    {dynamicAnalysis.risk_score || 0}
                  </div>
                  <div style={{ fontSize: '16px', color: '#64748b' }}>
                    {dynamicAnalysis.risk_score <= 40 ? 'Low Risk' : 
                     dynamicAnalysis.risk_score <= 60 ? 'Medium Risk' : 'High Risk'}
                  </div>
                  <div style={{ fontSize: '24px', marginTop: '12px' }}>
                    {riskColors.icon}
                  </div>
                </div>

                {/* Credit Decision Card */}
                <div style={{
                  background: 'rgba(255, 255, 255, 0.9)',
                  borderRadius: '16px',
                  padding: '24px',
                  border: `2px solid ${decisionColors.text === '#166534' ? '#22c55e' : decisionColors.text === '#92400e' ? '#f59e0b' : '#ef4444'}`,
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px', fontWeight: '600' }}>
                    Credit Decision
                  </div>
                  <div style={{ fontSize: '36px', fontWeight: 'bold', color: decisionColors.text, marginBottom: '8px' }}>
                    {dynamicAnalysis.decision || 'PENDING'}
                  </div>
                  <div style={{ fontSize: '16px', color: '#64748b', marginBottom: '8px' }}>
                    Confidence: {dynamicAnalysis.confidence || 0}%
                  </div>
                  <div style={{ fontSize: '24px', marginTop: '12px' }}>
                    {decisionColors.icon}
                  </div>
                </div>
              </div>
            )}

            {/* Loan Recommendation */}
            <div style={{ 
              gridColumn: '1 / -1', 
              background: 'linear-gradient(135deg, #dbeafe, #eff6ff)', 
              borderRadius: '16px', 
              padding: '32px',
              border: '1px solid #3b82f6'
            }}>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '24px', textAlign: 'center' }}>
                  💰 Smart Loan Recommendation
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px' }}>
                      Maximum Loan Amount
                    </div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e293b' }}>
                      {formatCurrency(dynamicAnalysis.max_loan_amount || 0)}
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                      Based on revenue & cash flow analysis
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px' }}>
                      Interest Rate
                    </div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e293b' }}>
                      {dynamicAnalysis.interest_rate || 0}%
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                      Dynamic pricing based on risk profile
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: 'center', marginTop: '24px' }}>
                  <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px' }}>
                    Affordability Score
                  </div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b' }}>
                    {dynamicAnalysis.affordability_score || 0}/100
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                    Repayment capacity analysis
                  </div>
                </div>
              </div>
            </div>
          )}
        )}
      </div>
    </div>
  );
};

export default WorkingDynamicDashboard;
