// Dynamic Credit Analysis Service
// Fetches real-time credit analysis from backend API

class DynamicCreditService {
  constructor() {
    this.apiBaseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
  }

  // Fetch credit analysis from backend
  async fetchCreditAnalysis(companyId, financialData) {
    try {
      // Check cache first
      const cacheKey = `credit_analysis_${companyId}`;
      if (this.cache.has(cacheKey)) {
        const cached = this.cache.get(cacheKey);
        if (Date.now() - cached.timestamp < this.cacheTimeout) {
          return cached.data;
        }
      }

      const response = await fetch(`${this.apiBaseUrl}/api/credit-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify({
          company_id: companyId,
          financial_data: financialData,
          analysis_type: 'comprehensive'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Cache the response
      this.cache.set(cacheKey, {
        data: data,
        timestamp: Date.now()
      });

      return data;
    } catch (error) {
      console.error('Error fetching credit analysis:', error);
      // Return fallback data for demo purposes
      return this.generateFallbackAnalysis(financialData);
    }
  }

  // Calculate risk score dynamically
  calculateDynamicRiskScore(financialData) {
    const weights = {
      revenue_growth: 0.25,
      cash_flow_stability: 0.30,
      debt_ratio: 0.20,
      industry_risk: 0.15,
      litigation_exposure: 0.10
    };

    const scores = {
      revenue_growth: this.calculateRevenueGrowthScore(financialData.revenue_history || []),
      cash_flow_stability: this.calculateCashFlowStability(financialData.cash_flow_history || []),
      debt_ratio: this.calculateDebtRatioScore(financialData.total_liabilities, financialData.total_equity),
      industry_risk: this.calculateIndustryRiskScore(financialData.industry),
      litigation_exposure: this.calculateLitigationScore(financialData.litigation_count || 0)
    };

    const riskScore = Object.entries(weights).reduce((total, [factor, weight]) => {
      return total + (scores[factor] || 50) * weight;
    }, 0);

    return Math.max(0, Math.min(100, Math.round(riskScore)));
  }

  // Calculate revenue growth score
  calculateRevenueGrowthScore(revenueHistory) {
    if (!revenueHistory || revenueHistory.length < 3) return 50;

    const recent = revenueHistory.slice(-3);
    const earlier = revenueHistory.slice(-6, -3);
    
    const recentAvg = recent.reduce((sum, r) => sum + r.amount, 0) / recent.length;
    const earlierAvg = earlier.reduce((sum, r) => sum + r.amount, 0) / earlier.length;
    
    const growthRate = ((recentAvg - earlierAvg) / earlierAvg) * 100;
    
    if (growthRate > 15) return 85; // Strong growth
    if (growthRate > 5) return 70;  // Moderate growth
    if (growthRate > -5) return 40;  // Declining
    return 25; // Stagnant or declining
  }

  // Calculate cash flow stability score
  calculateCashFlowStability(cashFlowHistory) {
    if (!cashFlowHistory || cashFlowHistory.length < 3) return 50;

    const cashFlows = cashFlowHistory.map(cf => cf.amount);
    const mean = cashFlows.reduce((sum, cf) => sum + cf, 0) / cashFlows.length;
    const variance = cashFlows.reduce((sum, cf) => sum + Math.pow(cf - mean, 2), 0) / cashFlows.length;
    const stdDev = Math.sqrt(variance);
    
    const stability = Math.max(0, 100 - (stdDev / Math.abs(mean)) * 100);
    
    if (stability > 80) return 85;
    if (stability > 60) return 70;
    if (stability > 40) return 55;
    return 30;
  }

  // Calculate debt ratio score
  calculateDebtRatioScore(totalLiabilities, totalEquity) {
    if (!totalLiabilities || !totalEquity) return 50;

    const debtRatio = totalLiabilities / totalEquity;
    
    if (debtRatio < 0.5) return 85;
    if (debtRatio < 1.0) return 70;
    if (debtRatio < 2.0) return 50;
    if (debtRatio < 3.0) return 30;
    return 15;
  }

  // Calculate industry risk score
  calculateIndustryRiskScore(industry) {
    const industryRisks = {
      'Technology': { risk: 35, growth: 'High', stability: 'Medium' },
      'Manufacturing': { risk: 45, growth: 'Low', stability: 'High' },
      'Healthcare': { risk: 25, growth: 'Medium', stability: 'High' },
      'Finance': { risk: 40, growth: 'Medium', stability: 'Medium' },
      'Retail': { risk: 50, growth: 'Low', stability: 'Medium' },
      'Construction': { risk: 55, growth: 'Medium', stability: 'Low' },
      'Agriculture': { risk: 60, growth: 'Low', stability: 'Very Low' }
    };

    const industryData = industryRisks[industry] || { risk: 40, growth: 'Medium', stability: 'Medium' };
    return 100 - industryData.risk; // Invert so lower risk = higher score
  }

  // Calculate litigation score
  calculateLitigationScore(litigationCount) {
    if (litigationCount === 0) return 90;
    if (litigationCount === 1) return 70;
    if (litigationCount === 2) return 50;
    if (litigationCount === 3) return 30;
    return 10;
  }

  // Determine credit decision based on risk score
  determineCreditDecision(riskScore) {
    if (riskScore >= 75) {
      return {
        decision: 'APPROVED',
        confidence: 85 + Math.floor(Math.random() * 10),
        reasoning: 'Strong financial profile with low risk indicators'
      };
    } else if (riskScore >= 55) {
      return {
        decision: 'REVIEW_REQUIRED',
        confidence: 70 + Math.floor(Math.random() * 10),
        reasoning: 'Moderate risk profile requires additional review'
      };
    } else {
      return {
        decision: 'REJECTED',
        confidence: 80 + Math.floor(Math.random() * 10),
        reasoning: 'High risk profile does not meet lending criteria'
      };
    }
  }

  // Calculate optimal loan amount
  calculateOptimalLoanAmount(financialData, riskScore) {
    const annualRevenue = financialData.annual_revenue || 0;
    const monthlyCashFlow = financialData.monthly_cash_flow || 0;
    
    // Base calculation: 30% of annual revenue, adjusted for risk
    let loanMultiplier = 0.3;
    
    if (riskScore < 30) {
      loanMultiplier = 0.5; // Low risk can support higher loan
    } else if (riskScore < 60) {
      loanMultiplier = 0.35;
    } else if (riskScore < 80) {
      loanMultiplier = 0.25;
    } else {
      loanMultiplier = 0.15; // High risk reduces loan amount
    }

    // Consider cash flow capacity (maximum 40% of monthly cash flow for EMI)
    const cashFlowCapacity = monthlyCashFlow * 12 * 0.4;
    const revenueBasedAmount = annualRevenue * loanMultiplier;
    
    const optimalAmount = Math.min(revenueBasedAmount, cashFlowCapacity);
    
    return Math.round(optimalAmount);
  }

  // Calculate dynamic interest rate
  calculateDynamicInterestRate(riskScore, industry) {
    let baseRate = 12.0; // Base rate of 12%
    
    // Adjust for risk score
    if (riskScore < 30) {
      baseRate -= 2.0; // Low risk gets better rate
    } else if (riskScore < 60) {
      baseRate -= 1.0;
    } else if (riskScore < 80) {
      baseRate += 1.0; // Higher risk increases rate
    } else {
      baseRate += 3.0; // High risk gets much higher rate
    }

    // Industry-specific adjustments
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
  }

  // Calculate affordability score
  calculateAffordabilityScore(financialData, loanAmount) {
    const monthlyEMI = this.calculateEMI(loanAmount, 12.0, 60); // 5-year term
    const monthlyIncome = financialData.monthly_income || 0;
    
    const dtiRatio = monthlyEMI / monthlyIncome;
    const cashFlowBuffer = (financialData.monthly_cash_flow || 0) / monthlyEMI;
    
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
  }

  // Calculate EMI
  calculateEMI(principal, annualRate, months) {
    const monthlyRate = annualRate / 12 / 100;
    if (monthlyRate === 0) return principal / months;
    
    return principal * monthlyRate * Math.pow(1 + monthlyRate, months) / 
           (Math.pow(1 + monthlyRate, months) - 1);
  }

  // Get auth token
  getAuthToken() {
    return localStorage.getItem('authToken') || 'demo-token';
  }

  // Generate fallback analysis for demo purposes
  generateFallbackAnalysis(financialData) {
    const riskScore = this.calculateDynamicRiskScore(financialData);
    const decision = this.determineCreditDecision(riskScore);
    const maxLoan = this.calculateOptimalLoanAmount(financialData, riskScore);
    const interestRate = this.calculateDynamicInterestRate(riskScore, financialData.industry);
    const affordabilityScore = this.calculateAffordabilityScore(financialData, maxLoan);

    return {
      risk_score: riskScore,
      decision: decision.decision,
      confidence: decision.confidence,
      reasoning: decision.reasoning,
      max_loan_amount: maxLoan,
      interest_rate: interestRate.toFixed(1),
      affordability_score: affordabilityScore,
      financial_health_metrics: {
        revenue_growth_score: this.calculateRevenueGrowthScore(financialData.revenue_history || []),
        cash_flow_stability: this.calculateCashFlowStability(financialData.cash_flow_history || []),
        debt_ratio: this.calculateDebtRatioScore(financialData.total_liabilities, financialData.total_equity)
      }
    };
  }

  // Fetch multiple company analyses
  async fetchMultipleCompanyAnalyses(companies) {
    const analyses = [];
    
    for (const company of companies) {
      const analysis = await this.fetchCreditAnalysis(company.unique_hash, {
        annual_revenue: company.revenue ? parseFloat(company.revenue) * 1000000 : 0,
        monthly_income: company.financial_metrics?.monthly_revenue ? parseFloat(company.financial_metrics.monthly_revenue) * 1000000 : 0,
        monthly_cash_flow: company.financial_metrics?.cash_flow ? parseFloat(company.financial_metrics.cash_flow) * 1000000 : 0,
        total_liabilities: company.financial_metrics?.total_liabilities ? parseFloat(company.financial_metrics.total_liabilities) * 1000000 : 0,
        total_equity: company.financial_metrics?.equity ? parseFloat(company.financial_metrics.equity) * 1000000 : 0,
        industry: company.industry,
        revenue_history: this.generateMockRevenueHistory(),
        cash_flow_history: this.generateMockCashFlowHistory(),
        litigation_count: Math.floor(Math.random() * 3)
      });
      
      analyses.push({
        company_id: company.unique_hash,
        ...analysis
      });
    }
    
    return analyses;
  }

  // Generate mock revenue history for demo
  generateMockRevenueHistory() {
    const history = [];
    const baseRevenue = 5000000 + Math.random() * 3000000;
    
    for (let i = 11; i >= 0; i--) {
      const growth = (Math.random() - 0.5) * 0.2; // -10% to +10% growth
      const amount = baseRevenue * (1 + growth * (11 - i) / 11);
      
      history.push({
        month: new Date(2024, i, 1).toISOString(),
        amount: Math.round(amount)
      });
    }
    
    return history;
  }

  // Generate mock cash flow history for demo
  generateMockCashFlowHistory() {
    const history = [];
    const baseCashFlow = 500000 + Math.random() * 300000;
    
    for (let i = 11; i >= 0; i--) {
      const volatility = (Math.random() - 0.5) * 0.3; // ±15% volatility
      const amount = baseCashFlow * (1 + volatility * Math.sin(i / 2));
      
      history.push({
        month: new Date(2024, i, 1).toISOString(),
        amount: Math.round(amount)
      });
    }
    
    return history;
  }

  // Clear cache
  clearCache() {
    this.cache.clear();
  }

  // Get cached analysis
  getCachedAnalysis(companyId) {
    const cacheKey = `credit_analysis_${companyId}`;
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data;
    }
    
    return null;
  }
}

export default DynamicCreditService;
