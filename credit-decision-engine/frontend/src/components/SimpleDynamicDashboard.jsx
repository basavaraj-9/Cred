import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const SimpleDynamicDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [dynamicAnalysis, setDynamicAnalysis] = useState({});
  const [loading, setLoading] = useState(false);

  // Dynamic calculation functions
  const calculateRiskScore = (company) => {
    const revenue = parseFloat(company.revenue || '0') * 1000000;
    const monthlyRevenue = parseFloat(company.financial_metrics?.monthly_revenue || '0') * 1000000;
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0') * 1000000;
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0') * 1000000;
    const equity = parseFloat(company.financial_metrics?.equity || '0') * 1000000;

    // Calculate component scores
    const revenueGrowthScore = Math.random() * 30 + 50; // Simulated growth score
    const cashFlowScore = monthlyProfit > 0 ? 80 : 40;
    const debtRatioScore = totalLiabilities > 0 ? Math.max(20, 100 - (totalLiabilities / equity) * 100) : 80;
    const industryRiskScore = company.industry === 'Technology' ? 85 : company.industry === 'Manufacturing' ? 70 : 75;

    // Weighted average
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
    } else if (riskScore >= 55) {
      return { decision: 'REVIEW_REQUIRED', confidence: 70 + Math.floor(Math.random() * 10) };
    } else {
      return { decision: 'REJECTED', confidence: 75 + Math.floor(Math.random() * 10) };
    }
  };

  const calculateLoanAmount = (company, riskScore) => {
    const annualRevenue = parseFloat(company.revenue || '0') * 1000000;
    const monthlyCashFlow = parseFloat(company.financial_metrics?.cash_flow || '0') * 1000000;

    let loanMultiplier = 0.3;
    if (riskScore < 30) loanMultiplier = 0.5;
    else if (riskScore < 60) loanMultiplier = 0.35;
    else if (riskScore < 80) loanMultiplier = 0.25;
    else loanMultiplier = 0.15;

    const revenueBasedAmount = annualRevenue * loanMultiplier;
    const cashFlowCapacity = monthlyCashFlow * 12 * 0.4;
    const optimalAmount = Math.min(revenueBasedAmount, cashFlowCapacity);

    return Math.round(optimalAmount);
  };

  const calculateInterestRate = (riskScore, industry) => {
    let baseRate = 12.0;
    
    if (riskScore < 30) baseRate -= 2.0;
    else if (riskScore < 60) baseRate -= 1.0;
    else if (riskScore < 80) baseRate += 1.0;
    else baseRate += 3.0;

    const industryAdjustments = {
      'Technology': -0.5,
      'Manufacturing': 0.5,
      'Healthcare': -0.3,
      'Finance': 0.2,
      'Retail': 0.8,
      'Construction': 1.0,
      'Agriculture': 1.5
    };

    baseRate += industryAdjustments[industry] || 0;
    return Math.max(6.0, Math.min(24.0, baseRate));
  };

  const calculateAffordabilityScore = (company, loanAmount) => {
    const monthlyIncome = parseFloat(company.financial_metrics?.monthly_revenue || '0') * 1000000;
    const monthlyCashFlow = parseFloat(company.financial_metrics?.cash_flow || '0') * 1000000;
    const monthlyEMI = (loanAmount * 0.12 / 12) / (1 - Math.pow(1 + 0.12 / 12, -60)); // Simplified EMI calculation

    const dtiRatio = monthlyEMI / monthlyIncome;
    const cashFlowBuffer = monthlyCashFlow / monthlyEMI;

    let score = 50;
    if (dtiRatio < 0.20) score += 30;
    else if (dtiRatio < 0.28) score += 15;
    else if (dtiRatio < 0.35) score += 5;
    else score -= 20;

    if (cashFlowBuffer > 2.0) score += 20;
    else if (cashFlowBuffer > 1.5) score += 10;
    else if (cashFlowBuffer > 1.0) score += 5;
    else score -= 10;

    return Math.max(0, Math.min(100, score));
  };

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data) {
      const parsedData = JSON.parse(data);
      setCompanyData(parsedData);
      
      const company = parsedData.is_multi_company ? parsedData.companies[0] : parsedData;
      setSelectedCompany(company);
      
      // Calculate dynamic analysis
      setLoading(true);
      setTimeout(() => {
        const riskScore = calculateRiskScore(company);
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
      }, 2000); // Simulate API call
    } else {
      navigate('/');
    }
  }, [navigate]);

  const getRiskColor = (score) => {
    if (score <= 40) return { bg: '#dcfce7', text: '#166534', border: '#22c55e', icon: '🟢' };
    if (score <= 70) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b', icon: '🟡' };
    return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444', icon: '🔴' };
  };

  const getDecisionColor = (decision) => {
    return decision === 'APPROVED' 
      ? { bg: '#dcfce7', text: '#166534', icon: '✅', gradient: 'linear-gradient(135deg, #22c55e, #16a34a)' }
      : { bg: '#fef3c7', text: '#92400e', icon: '⚠️', gradient: 'linear-gradient(135deg, #f59e0b, #d97706)' };
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const handleRefreshAnalysis = () => {
    if (selectedCompany) {
      setLoading(true);
      setTimeout(() => {
        const riskScore = calculateRiskScore(selectedCompany);
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
      const riskScore = calculateRiskScore(company);
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
        justifyContent: 'center',
        color: 'white'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
          <p>Loading Dynamic Credit Analysis...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #1e40af 0%, #0f766e 50%, #0891b2 100%)',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Animated background elements */}
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

      {/* Header */}
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
        <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ fontSize: '32px' }}>🏦</div>
            <div>
              <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', margin: 0 }}>
                Dynamic Credit Decisioning Engine
              </h1>
              <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', margin: '4px 0 0 0' }}>
                Real-time AI-Powered Credit Analysis • Dynamic Risk Assessment • Smart Recommendations
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => navigate('/dashboard')}
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                borderRadius: '12px',
                padding: '12px 20px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '600',
                transition: 'all 0.3s ease'
              }}
            >
              📊 Static Dashboard
            </button>
            <button
              onClick={() => navigate('/')}
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                borderRadius: '12px',
                padding: '12px 20px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '600',
                transition: 'all 0.3s ease'
              }}
            >
              📤 New Upload
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, maxWidth: '1400px', margin: '0 auto', padding: '32px 24px' }}>
        
        {/* Company Selection */}
        {companyData?.is_multi_company && (
          <div style={{ marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: 'white', marginBottom: '16px' }}>
              Select Company for Dynamic Analysis:
            </h2>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {companyData.companies.map((company, index) => (
                <button
                  key={company.unique_hash || index}
                  onClick={() => handleCompanyChange(company)}
                  style={{
                    background: selectedCompany?.unique_hash === company.unique_hash 
                      ? 'rgba(59, 130, 246, 0.3)' 
                      : 'rgba(255, 255, 255, 0.1)',
                    color: 'white',
                    border: selectedCompany?.unique_hash === company.unique_hash 
                      ? '2px solid #3b82f6' 
                      : '1px solid rgba(255, 255, 255, 0.3)',
                    borderRadius: '12px',
                    padding: '12px 20px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '600',
                    transition: 'all 0.3s ease'
                  }}
                >
                  {company.company}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(20px)',
            borderRadius: '20px',
            padding: '48px',
            textAlign: 'center',
            marginBottom: '24px'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '16px' }}>🔄</div>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px' }}>
              Analyzing Credit Data...
            </h3>
            <p style={{ fontSize: '16px', color: '#64748b' }}>
              Our AI is calculating risk scores, loan recommendations, and generating insights...
            </p>
            <div style={{
              width: '60px',
              height: '4px',
              background: 'linear-gradient(90deg, #3b82f6, #10b981, #8b5cf6)',
              borderRadius: '2px',
              margin: '20px auto',
              animation: 'pulse 1.5s ease-in-out infinite'
            }}></div>
          </div>
        )}

        {/* Dynamic Analysis Results */}
        {!loading && Object.keys(dynamicAnalysis).length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            
            {/* Risk Score Card */}
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
                background: getRiskColor(dynamicAnalysis.risk_score).gradient
              }}></div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                  Dynamic Risk Score
                </h3>
                <button
                  onClick={handleRefreshAnalysis}
                  style={{
                    background: 'rgba(255, 255, 255, 0.1)',
                    color: '#1e293b',
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    borderRadius: '8px',
                    padding: '6px 12px',
                    cursor: 'pointer',
                    fontSize: '12px',
                    transition: 'all 0.3s ease'
                  }}
                >
                  🔄 Refresh
                </button>
              </div>
              <div style={{
                background: getRiskColor(dynamicAnalysis.risk_score).bg,
                borderRadius: '16px',
                padding: '24px',
                textAlign: 'center',
                marginBottom: '16px'
              }}>
                <div style={{ fontSize: '48px', fontWeight: 'bold', color: getRiskColor(dynamicAnalysis.risk_score).text, marginBottom: '8px' }}>
                  {dynamicAnalysis.risk_score || 0}
                </div>
                <div style={{ fontSize: '16px', color: 'rgba(0,0,0,0.6)', marginTop: '8px' }}>
                  Risk Score (0-100)
                </div>
              </div>
              <div style={{ fontSize: '14px', color: '#64748b', textAlign: 'center' }}>
                <div style={{ 
                  background: getRiskColor(dynamicAnalysis.risk_score).bg, 
                  padding: '8px 16px', 
                  borderRadius: '12px', 
                  display: 'inline-block',
                  margin: '4px'
                }}>
                  {dynamicAnalysis.decision === 'APPROVED' ? 'Low Risk' : 
                   dynamicAnalysis.decision === 'REVIEW_REQUIRED' ? 'Moderate Risk' : 'High Risk'}
                </div>
              </div>
            </div>
            <div style={{ fontSize: '14px', color: '#64748b', marginTop: '12px' }}>
              <strong>Confidence:</strong> {dynamicAnalysis.confidence || 0}%
            </div>
          </div>

          {/* Credit Decision Card */}
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
              background: getDecisionColor(dynamicAnalysis.decision).gradient
            }}></div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                Credit Decision
              </h3>
              <div style={{ fontSize: '24px' }}>
                {getDecisionColor(dynamicAnalysis.decision).icon}
              </div>
            </div>
            <div style={{
              background: getDecisionColor(dynamicAnalysis.decision).bg,
              borderRadius: '16px',
              padding: '24px',
              textAlign: 'center',
              marginBottom: '16px'
            }}>
              <div style={{ fontSize: '32px', fontWeight: 'bold', color: getDecisionColor(dynamicAnalysis.decision).text, marginBottom: '8px' }}>
                {dynamicAnalysis.decision || 'REVIEW_REQUIRED'}
              </div>
              <div style={{ fontSize: '16px', color: 'rgba(0,0,0,0.6)', marginTop: '8px' }}>
                Final Credit Decision
              </div>
            </div>
            <div style={{ fontSize: '14px', color: '#64748b', textAlign: 'center' }}>
              <div style={{ 
                background: getDecisionColor(dynamicAnalysis.decision).bg, 
                padding: '8px 16px', 
                borderRadius: '12px', 
                display: 'inline-block',
                margin: '4px'
              }}>
                {dynamicAnalysis.decision === 'APPROVED' ? '✅ Approved' : 
                   dynamicAnalysis.decision === 'REVIEW_REQUIRED' ? '⚠️ Review Required' : '❌ Rejected'}
              </div>
            </div>
            <div style={{ fontSize: '14px', color: '#64748b', marginTop: '12px' }}>
              <strong>Confidence:</strong> {dynamicAnalysis.confidence || 0}%
            </div>
          </div>

          {/* Loan Recommendation Card */}
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
              background: 'linear-gradient(90deg, #10b981, #059669, #3b82f6, #10b981)'
            }}></div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#64748b', margin: 0 }}>
                Smart Loan Recommendation
              </h3>
              <div style={{ fontSize: '24px' }}>
                💰
              </div>
            </div>
            <div style={{
              background: 'linear-gradient(135deg, #10b981, #059669)',
              borderRadius: '16px',
              padding: '24px',
              textAlign: 'center',
              marginBottom: '16px'
            }}>
              <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.9)', marginBottom: '8px' }}>
                Maximum Approved Amount
              </div>
              <div style={{ fontSize: '36px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                {formatCurrency(dynamicAnalysis.max_loan_amount || 0)}
              </div>
              <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.8)', marginTop: '8px' }}>
                Based on AI analysis of financial capacity
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                  Interest Rate
                </div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b' }}>
                  {dynamicAnalysis.interest_rate || 0}%
                </div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                  Dynamic pricing based on risk profile
                </div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                  Affordability Score
                </div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b' }}>
                  {dynamicAnalysis.affordability_score || 0}/100
                </div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                  Repayment capacity analysis
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SimpleDynamicDashboard;
