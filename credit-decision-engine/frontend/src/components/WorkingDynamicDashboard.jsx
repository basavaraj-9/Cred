import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useMotionValue, useTransform } from 'framer-motion';

const TiltCard = ({ children, style, className }) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useTransform(y, [-100, 100], [8, -8]);
  const rotateY = useTransform(x, [-100, 100], [-8, 8]);

  function handleMouseMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const xPct = ((event.clientX - rect.left) / rect.width - 0.5) * 200;
    const yPct = ((event.clientY - rect.top) / rect.height - 0.5) * 200;
    x.set(xPct);
    y.set(yPct);
  }

  function handleMouseLeave() { x.set(0); y.set(0); }

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ ...style, rotateX, rotateY, transformStyle: "preserve-3d" }}
      className={className}
      whileHover={{ scale: 1.01, translateZ: 15 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      {children}
    </motion.div>
  );
};

const WorkingDynamicDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [dynamicAnalysis, setDynamicAnalysis] = useState({});
  const [loading, setLoading] = useState(false);

  const calculateRiskScore = (company) => {
    const annualRevenue = parseFloat(company.revenue || '0') * 10000000;
    const monthlyRevenue = parseFloat(company.financial_metrics?.monthly_revenue || '0');
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0');
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0');
    const equity = parseFloat(company.financial_metrics?.equity || '0');
    const revenueGrowthScore = Math.min(100, Math.max(0, 60 + (annualRevenue / 100000000) * 20));
    const cashFlowScore = monthlyProfit > 0 ? Math.min(100, 70 + (monthlyProfit / monthlyRevenue) * 30) : 30;
    const debtRatioScore = totalLiabilities > 0 ? Math.max(20, 100 - (totalLiabilities / equity) * 50) : 80;
    const industryRiskScore = company.industry === 'Technology' ? 85 :
      company.industry === 'Manufacturing' ? 70 :
        company.industry === 'Healthcare' ? 80 :
          company.industry === 'Finance' ? 65 : 75;
    return Math.max(0, Math.min(100, Math.round(
      revenueGrowthScore * 0.3 + cashFlowScore * 0.3 + debtRatioScore * 0.2 + industryRiskScore * 0.2
    )));
  };

  const determineDecision = (riskScore) => {
    if (riskScore >= 75) return { decision: 'APPROVED', confidence: 85 + Math.floor(Math.random() * 10) };
    if (riskScore >= 60) return { decision: 'CONDITIONALLY_APPROVED', confidence: 75 + Math.floor(Math.random() * 10) };
    return { decision: 'REJECTED', confidence: 75 + Math.floor(Math.random() * 10) };
  };

  const calculateLoanAmount = (company, riskScore) => {
    const annualRevenue = parseFloat(company.revenue || '0') * 10000000;
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0');
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0');
    const equity = parseFloat(company.financial_metrics?.equity || '0');
    let loanMultiplier = riskScore >= 80 ? 0.4 : riskScore >= 70 ? 0.35 : riskScore >= 60 ? 0.3 : riskScore >= 50 ? 0.25 : 0.2;
    const revenueBasedAmount = annualRevenue * loanMultiplier;
    const cashFlowCapacity = monthlyProfit * 12 * 0.4;
    const debtServiceCapacity = Math.max(0, (equity - totalLiabilities) * 0.5);
    const optimalAmount = Math.min(revenueBasedAmount, cashFlowCapacity, debtServiceCapacity);
    return Math.round(Math.max(1000000, Math.min(optimalAmount, annualRevenue * 0.5)));
  };

  const calculateInterestRate = (riskScore, industry) => {
    let baseRate = 12.0;
    if (riskScore >= 80) baseRate -= 2.0;
    else if (riskScore >= 70) baseRate -= 1.0;
    else if (riskScore >= 60) baseRate += 0.0;
    else if (riskScore >= 50) baseRate += 1.0;
    else baseRate += 2.0;
    const adj = { 'Technology': -0.5, 'Manufacturing': 0.5, 'Healthcare': -0.3, 'Finance': 0.2, 'Retail': 0.3 };
    return Math.max(8.0, Math.min(18.0, baseRate + (adj[industry] || 0)));
  };

  const calculateAffordabilityScore = (company, loanAmount) => {
    const monthlyRevenue = parseFloat(company.financial_metrics?.monthly_revenue || '0');
    const monthlyProfit = parseFloat(company.financial_metrics?.monthly_profit || '0');
    const totalLiabilities = parseFloat(company.financial_metrics?.total_liabilities || '0');
    const monthlyInterestRate = 0.12 / 12;
    const tenureMonths = 60;
    const monthlyEMI = loanAmount * monthlyInterestRate * Math.pow(1 + monthlyInterestRate, tenureMonths) /
      (Math.pow(1 + monthlyInterestRate, tenureMonths) - 1);
    const dtiRatio = monthlyEMI / monthlyRevenue;
    const cashFlowBuffer = monthlyProfit / monthlyEMI;
    let score = 50;
    if (dtiRatio <= 0.3) score += 20; else if (dtiRatio <= 0.4) score += 10; else if (dtiRatio <= 0.5) score += 5; else score -= 10;
    if (cashFlowBuffer >= 2.0) score += 10; else if (cashFlowBuffer >= 1.5) score += 5; else if (cashFlowBuffer < 1.0) score -= 10;
    const debtToRevenueRatio = totalLiabilities / (monthlyRevenue * 12);
    if (debtToRevenueRatio <= 0.5) score += 10; else if (debtToRevenueRatio <= 0.8) score += 5; else score -= 15;
    return Math.max(0, Math.min(100, score));
  };

  const formatCurrency = (amount) => {
    if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
    if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
    return `₹${amount.toLocaleString()}`;
  };

  const runAnalysis = (company) => {
    setLoading(true);
    setTimeout(() => {
      const riskScore = company.ai_analysis?.risk_analysis?.risk_score || calculateRiskScore(company);
      const decision = determineDecision(riskScore);
      const maxLoan = calculateLoanAmount(company, riskScore);
      const interestRate = calculateInterestRate(riskScore, company.industry);
      const affordabilityScore = calculateAffordabilityScore(company, maxLoan);
      setDynamicAnalysis({
        risk_score: riskScore, decision: decision.decision, confidence: decision.confidence,
        max_loan_amount: maxLoan, interest_rate: interestRate.toFixed(1), affordability_score: affordabilityScore
      });
      setLoading(false);
    }, 1500);
  };

  useEffect(() => {
    const storedCompanyData = localStorage.getItem('companyData');
    if (storedCompanyData) {
      const parsedData = JSON.parse(storedCompanyData);
      const company = parsedData.is_multi_company ? parsedData.companies[0] : parsedData;
      setSelectedCompany(company);
      setCompanyData(parsedData);
      runAnalysis(company);
    } else {
      navigate('/');
    }
  }, [navigate]);

  const handleCompanyChange = (company) => {
    setSelectedCompany(company);
    runAnalysis(company);
  };

  if (!companyData) {
    return (
      <div style={{
        minHeight: '100vh', background: 'var(--dashboard-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          style={{
            width: '60px', height: '60px',
            border: '4px solid rgba(255,255,255,0.2)', borderTop: '4px solid #3b82f6', borderRadius: '50%'
          }}
        />
      </div>
    );
  }

  const companies = companyData?.is_multi_company ? companyData.companies : [companyData];
  const riskScore = dynamicAnalysis.risk_score || 0;
  const riskColor = riskScore <= 40 ? '#10b981' : riskScore <= 60 ? '#f59e0b' : '#ef4444';
  const riskLabel = riskScore <= 40 ? 'Low Risk' : riskScore <= 60 ? 'Medium Risk' : 'High Risk';
  const decisionColor = dynamicAnalysis.decision === 'APPROVED' ? '#10b981' :
    dynamicAnalysis.decision === 'CONDITIONALLY_APPROVED' ? '#f59e0b' : '#ef4444';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mesh-background"
      style={{
        minHeight: '100vh', background: 'var(--dashboard-bg)',
        position: 'relative', overflow: 'hidden', perspective: '1500px'
      }}
    >
      {/* Animated orbs */}
      <motion.div style={{
        position: 'absolute', top: '10%', left: '5%', width: '300px', height: '300px',
        background: 'radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)', borderRadius: '50%',
      }} animate={{ y: [0, -40, 0], opacity: [0.3, 0.6, 0.3] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div style={{
        position: 'absolute', bottom: '20%', right: '10%', width: '250px', height: '250px',
        background: 'radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%)', borderRadius: '50%',
      }} animate={{ y: [0, 50, 0], opacity: [0.2, 0.5, 0.2] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} />

      {/* Header */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--border-color)',
        padding: '32px 0',
        boxShadow: '0 4px 30px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1 style={{
                fontSize: '40px', fontWeight: 'bold', marginBottom: '12px', color: 'white',
                textShadow: '0 2px 10px rgba(0,0,0,0.2)',
                display: 'flex', alignItems: 'center', gap: '16px'
              }}>
                <motion.span
                  animate={{ rotateY: [0, 360] }}
                  transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
                  style={{ fontSize: '48px', display: 'inline-block' }}
                >🚀</motion.span>
                Dynamic Credit Analysis
              </h1>
              <p style={{ fontSize: '20px', color: 'rgba(255, 255, 255, 0.8)', fontWeight: '400' }}>
                Real-time risk assessment and loan recommendations
              </p>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              {[
                { label: '📊 Dashboard', path: '/dashboard' },
                { label: '📈 Research', path: '/research' },
                { label: '📄 CAM', path: '/cam-preview' },
                { label: '📤 Upload', path: '/' },
              ].map(btn => (
                <motion.button
                  key={btn.path}
                  onClick={() => navigate(btn.path)}
                  whileHover={{ scale: 1.05, translateZ: 10 }}
                  whileTap={{ scale: 0.95 }}
                  style={{
                    background: 'var(--card-bg)', backdropFilter: 'var(--glass-blur)',
                    color: 'white', padding: '12px 24px', borderRadius: '12px',
                    border: '1px solid var(--border-color)', cursor: 'pointer',
                    fontSize: '15px', fontWeight: '600', boxShadow: 'var(--card-shadow)'
                  }}
                >
                  {btn.label}
                </motion.button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '40px 24px' }}>

        {/* Company Selector */}
        {companyData?.is_multi_company && (
          <TiltCard style={{
            background: 'var(--card-bg)', backdropFilter: 'var(--glass-blur)',
            borderRadius: '24px', padding: '24px', marginBottom: '32px',
            boxShadow: 'var(--card-shadow)', border: '1px solid var(--border-color)'
          }}>
            <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '16px' }}>
              Select Company for Analysis
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
              {companies.map((company, index) => (
                <motion.button
                  key={company.unique_hash || index}
                  onClick={() => handleCompanyChange(company)}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  style={{
                    background: selectedCompany?.unique_hash === company.unique_hash
                      ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : 'rgba(255, 255, 255, 0.05)',
                    border: `1px solid ${selectedCompany?.unique_hash === company.unique_hash ? '#3b82f6' : 'var(--border-color)'}`,
                    borderRadius: '12px', padding: '16px', cursor: 'pointer', textAlign: 'left',
                    boxShadow: selectedCompany?.unique_hash === company.unique_hash
                      ? '0 8px 24px rgba(59, 130, 246, 0.3)' : 'none'
                  }}
                >
                  <div style={{
                    fontWeight: '600', marginBottom: '4px',
                    color: selectedCompany?.unique_hash === company.unique_hash ? 'white' : 'var(--text-primary)'
                  }}>
                    {company.company}
                  </div>
                  <div style={{
                    fontSize: '14px',
                    color: selectedCompany?.unique_hash === company.unique_hash ? 'rgba(255,255,255,0.8)' : 'var(--text-secondary)'
                  }}>
                    {company.industry} • {company.revenue} Cr Revenue
                  </div>
                </motion.button>
              ))}
            </div>
          </TiltCard>
        )}

        {/* Analysis Results */}
        {selectedCompany && (
          <TiltCard style={{
            background: 'var(--card-bg)', backdropFilter: 'var(--glass-blur)',
            borderRadius: '24px', padding: '32px',
            boxShadow: 'var(--card-shadow)', border: '1px solid var(--border-color)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontSize: '28px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                {selectedCompany.company} — Dynamic Analysis
              </h2>
              <motion.button
                onClick={() => runAnalysis(selectedCompany)}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                style={{
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  color: 'white', border: 'none', borderRadius: '12px',
                  padding: '12px 24px', cursor: 'pointer', fontSize: '14px', fontWeight: '600',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
                }}
              >
                🔄 Refresh Analysis
              </motion.button>
            </div>

            {loading ? (
              <div style={{ textAlign: 'center', padding: '60px' }}>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  style={{
                    width: '60px', height: '60px',
                    border: '4px solid rgba(16, 185, 129, 0.2)',
                    borderTop: '4px solid #10b981', borderRadius: '50%', margin: '0 auto 16px'
                  }}
                />
                <p style={{ color: 'var(--text-secondary)', fontSize: '16px' }}>Analyzing financial data...</p>
              </div>
            ) : (
              <>
                {/* Risk & Decision Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
                  {/* Risk Score */}
                  <motion.div
                    whileHover={{ scale: 1.02, translateZ: 10 }}
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      borderRadius: '20px', padding: '32px',
                      border: `2px solid ${riskColor}`,
                      textAlign: 'center', position: 'relative', overflow: 'hidden'
                    }}
                  >
                    <div style={{
                      position: 'absolute', top: 0, left: 0, right: 0, height: '4px',
                      background: `linear-gradient(90deg, ${riskColor}, transparent)`,
                    }}></div>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px', fontWeight: '600' }}>
                      Risk Score
                    </div>
                    <div style={{ fontSize: '56px', fontWeight: 'bold', color: riskColor, marginBottom: '8px' }}>
                      {riskScore}
                    </div>
                    <div style={{
                      fontSize: '16px', color: riskColor, fontWeight: '600',
                      padding: '6px 16px', borderRadius: '20px',
                      background: `${riskColor}15`, display: 'inline-block'
                    }}>
                      {riskLabel}
                    </div>
                  </motion.div>

                  {/* Credit Decision */}
                  <motion.div
                    whileHover={{ scale: 1.02, translateZ: 10 }}
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      borderRadius: '20px', padding: '32px',
                      border: `2px solid ${decisionColor}`,
                      textAlign: 'center', position: 'relative', overflow: 'hidden'
                    }}
                  >
                    <div style={{
                      position: 'absolute', top: 0, left: 0, right: 0, height: '4px',
                      background: `linear-gradient(90deg, ${decisionColor}, transparent)`,
                    }}></div>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px', fontWeight: '600' }}>
                      Credit Decision
                    </div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: decisionColor, marginBottom: '8px' }}>
                      {(dynamicAnalysis.decision || 'PENDING').replace('_', ' ')}
                    </div>
                    <div style={{
                      fontSize: '16px', color: 'var(--text-secondary)', marginBottom: '12px'
                    }}>
                      Confidence: {dynamicAnalysis.confidence || 0}%
                    </div>
                    <div style={{ fontSize: '28px' }}>
                      {dynamicAnalysis.decision === 'APPROVED' ? '✅' :
                        dynamicAnalysis.decision === 'CONDITIONALLY_APPROVED' ? '⚠️' : '❌'}
                    </div>
                  </motion.div>
                </div>

                {/* Loan Recommendation */}
                <TiltCard style={{
                  background: 'rgba(59, 130, 246, 0.08)',
                  borderRadius: '20px', padding: '32px',
                  border: '1px solid rgba(59, 130, 246, 0.2)'
                }}>
                  <h3 style={{
                    fontSize: '22px', fontWeight: 'bold', color: 'var(--text-primary)',
                    marginBottom: '28px', textAlign: 'center'
                  }}>
                    💰 Smart Loan Recommendation
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Maximum Loan Amount
                      </div>
                      <div style={{ fontSize: '36px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {formatCurrency(dynamicAnalysis.max_loan_amount || 0)}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        Based on revenue & cash flow analysis
                      </div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Interest Rate
                      </div>
                      <div style={{ fontSize: '36px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {dynamicAnalysis.interest_rate || 0}%
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        Dynamic pricing based on risk profile
                      </div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                      Affordability Score
                    </div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                      {dynamicAnalysis.affordability_score || 0}/100
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      Repayment capacity analysis
                    </div>
                  </div>
                </TiltCard>
              </>
            )}
          </TiltCard>
        )}
      </div>
    </motion.div>
  );
};

export default WorkingDynamicDashboard;
