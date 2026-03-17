// Smart Loan Amount Recommendation Service
// Recommends optimal loan amount based on repayment capacity

class SmartLoanRecommendationService {
  constructor() {
    this.loanParameters = {
      maxDTIRatio: 0.28, // Maximum debt-to-income ratio (28%)
      riskAdjustmentFactor: 0.8, // Safety factor for risk adjustment
      minCashFlowBuffer: 1.2, // Minimum cash flow buffer
      industryMultipliers: {
        'Technology': 1.2,
        'Manufacturing': 0.9,
        'Healthcare': 1.1,
        'Finance': 0.8,
        'Retail': 0.85,
        'Construction': 0.7,
        'Agriculture': 0.6
      }
    };
  }

  // Calculate optimal loan recommendation
  calculateOptimalLoan(financialData, requestedAmount, loanPurpose) {
    const analysis = {
      repaymentCapacity: this.calculateRepaymentCapacity(financialData),
      cashFlowAnalysis: this.analyzeCashFlow(financialData),
      industryAdjustment: this.getIndustryAdjustment(financialData.industry),
      riskAssessment: this.assessRiskProfile(financialData),
      loanStructure: this.optimizeLoanStructure(financialData, loanPurpose)
    };

    const recommendedLoan = this.calculateRecommendedAmount(analysis, requestedAmount);
    const affordabilityMetrics = this.calculateAffordabilityMetrics(recommendedLoan, financialData);
    const alternativeOptions = this.generateAlternativeOptions(recommendedLoan, financialData);

    return {
      requestedAmount,
      recommendedAmount: recommendedLoan.optimalAmount,
      maxApprovableAmount: recommendedLoan.maxAmount,
      minAcceptableAmount: recommendedLoan.minAmount,
      recommendation: {
        primary: recommendedLoan.optimalAmount,
        reasoning: recommendedLoan.reasoning,
        confidence: recommendedLoan.confidence,
        riskLevel: recommendedLoan.riskLevel
      },
      affordabilityMetrics,
      alternativeOptions,
      loanStructure: analysis.loanStructure,
      keyFactors: analysis,
      warnings: this.generateWarnings(recommendedLoan, financialData)
    };
  }

  // Calculate repayment capacity
  calculateRepaymentCapacity(financialData) {
    const monthlyIncome = financialData.averageMonthlyIncome || 0;
    const monthlyExpenses = financialData.averageMonthlyExpenses || 0;
    const existingEMI = financialData.existingMonthlyEMI || 0;
    const disposableIncome = monthlyIncome - monthlyExpenses - existingEMI;

    // Apply conservative DTI ratio
    const maxEMI = monthlyIncome * this.loanParameters.maxDTIRatio;
    const availableForEMI = Math.min(maxEMI, disposableIncome);

    return {
      monthlyIncome,
      monthlyExpenses,
      existingEMI,
      disposableIncome,
      maxEMICapacity: maxEMI,
      availableForEMI,
      dtiRatio: existingEMI / monthlyIncome,
      repaymentCapacityScore: Math.min(100, (availableForEMI / maxEMI) * 100)
    };
  }

  // Analyze cash flow patterns
  analyzeCashFlow(financialData) {
    const cashFlowHistory = financialData.cashFlowHistory || [];
    
    if (cashFlowHistory.length === 0) {
      return {
        average: 0,
        stability: 0,
        trend: 'stable',
        seasonality: 'none',
        volatility: 0
      };
    }

    const cashFlows = cashFlowHistory.map(cf => cf.amount);
    const average = cashFlows.reduce((sum, cf) => sum + cf, 0) / cashFlows.length;
    
    // Calculate stability (consistency)
    const variance = cashFlows.reduce((sum, cf) => sum + Math.pow(cf - average, 2), 0) / cashFlows.length;
    const stdDev = Math.sqrt(variance);
    const stability = Math.max(0, 100 - (stdDev / Math.abs(average)) * 100);

    // Calculate trend
    const trend = this.calculateCashFlowTrend(cashFlowHistory);
    
    // Calculate seasonality
    const seasonality = this.detectSeasonality(cashFlowHistory);

    return {
      average,
      stability,
      trend,
      seasonality,
      volatility: stdDev
    };
  }

  // Get industry-specific adjustments
  getIndustryAdjustment(industry) {
    const multiplier = this.loanParameters.industryMultipliers[industry] || 1.0;
    
    const industryRisks = {
      'Technology': { risk: 'Medium', growth: 'High', stability: 'Medium' },
      'Manufacturing': { risk: 'Medium', growth: 'Low', stability: 'High' },
      'Healthcare': { risk: 'Low', growth: 'Medium', stability: 'High' },
      'Finance': { risk: 'High', growth: 'Medium', stability: 'Medium' },
      'Retail': { risk: 'High', growth: 'Low', stability: 'Medium' },
      'Construction': { risk: 'High', growth: 'Medium', stability: 'Low' },
      'Agriculture': { risk: 'Very High', growth: 'Low', stability: 'Very Low' }
    };

    return {
      multiplier,
      riskProfile: industryRisks[industry] || { risk: 'Medium', growth: 'Medium', stability: 'Medium' }
    };
  }

  // Assess risk profile
  assessRiskProfile(financialData) {
    const creditScore = financialData.creditScore || 500;
    const businessAge = financialData.businessAge || 0;
    const profitMargin = financialData.profitMargin || 0;
    const debtToEquity = financialData.debtToEquity || 0;

    let riskScore = 50; // Base score

    // Credit score impact
    if (creditScore > 750) riskScore -= 20;
    else if (creditScore > 700) riskScore -= 10;
    else if (creditScore < 600) riskScore += 15;
    else if (creditScore < 500) riskScore += 25;

    // Business age impact
    if (businessAge > 10) riskScore -= 10;
    else if (businessAge > 5) riskScore -= 5;
    else if (businessAge < 2) riskScore += 15;

    // Profit margin impact
    if (profitMargin > 0.15) riskScore -= 15;
    else if (profitMargin > 0.10) riskScore -= 8;
    else if (profitMargin < 0) riskScore += 20;

    // Debt-to-equity impact
    if (debtToEquity < 0.5) riskScore -= 10;
    else if (debtToEquity < 1.0) riskScore -= 5;
    else if (debtToEquity > 2.0) riskScore += 20;

    return {
      riskScore: Math.max(0, Math.min(100, riskScore)),
      riskLevel: this.getRiskLevel(riskScore),
      factors: {
        creditScore,
        businessAge,
        profitMargin,
        debtToEquity
      }
    };
  }

  // Optimize loan structure
  optimizeLoanStructure(financialData, loanPurpose) {
    const purposeAnalysis = this.analyzeLoanPurpose(loanPurpose);
    const termOptimization = this.optimizeLoanTerm(financialData, loanPurpose);
    const interestRateOptimization = this.optimizeInterestRate(financialData);

    return {
      purpose: purposeAnalysis,
      recommendedTerm: termOptimization.optimalTerm,
      termReasoning: termOptimization.reasoning,
      recommendedInterestRate: interestRateOptimization.rate,
      interestRateReasoning: interestRateOptimization.reasoning,
      repaymentFrequency: this.optimizeRepaymentFrequency(financialData),
      collateralRequirements: this.suggestCollateralRequirements(financialData, loanPurpose)
    };
  }

  // Calculate recommended loan amount
  calculateRecommendedAmount(analysis, requestedAmount) {
    const { repaymentCapacity, cashFlowAnalysis, industryAdjustment, riskAssessment } = analysis;

    // Base calculation on repayment capacity
    let maxAmount = this.calculateMaxLoanFromEMI(
      repaymentCapacity.availableForEMI,
      analysis.loanStructure.recommendedTerm,
      analysis.loanStructure.recommendedInterestRate
    );

    // Apply industry adjustment
    maxAmount *= industryAdjustment.multiplier;

    // Apply risk adjustment
    maxAmount *= (1 - (riskAssessment.riskScore / 100) * 0.3);

    // Apply cash flow stability adjustment
    maxAmount *= (cashFlowAnalysis.stability / 100);

    // Calculate optimal amount (more conservative than max)
    const optimalAmount = maxAmount * this.loanParameters.riskAdjustmentFactor;

    // Calculate minimum acceptable amount
    const minAmount = optimalAmount * 0.3;

    // Generate reasoning
    const reasoning = this.generateRecommendationReasoning(
      analysis,
      optimalAmount,
      requestedAmount,
      maxAmount
    );

    return {
      optimalAmount: Math.round(optimalAmount),
      maxAmount: Math.round(maxAmount),
      minAmount: Math.round(minAmount),
      reasoning,
      confidence: this.calculateConfidence(analysis, optimalAmount, requestedAmount),
      riskLevel: riskAssessment.riskLevel
    };
  }

  // Calculate affordability metrics
  calculateAffordabilityMetrics(recommendedLoan, financialData) {
    const monthlyEMI = this.calculateEMI(
      recommendedLoan.optimalAmount,
      recommendedLoan.loanStructure.recommendedTerm,
      recommendedLoan.loanStructure.recommendedInterestRate
    );

    const dtiRatio = monthlyEMI / financialData.averageMonthlyIncome;
    const cashFlowBuffer = financialData.averageMonthlyCashFlow / monthlyEMI;
    const stressTestResult = this.stressTestLoan(
      recommendedLoan.optimalAmount,
      financialData
    );

    return {
      monthlyEMI,
      dtiRatio: dtiRatio * 100,
      cashFlowBuffer: cashFlowBuffer,
      stressTest: stressTestResult,
      affordabilityScore: this.calculateAffordabilityScore(dtiRatio, cashFlowBuffer),
      monthlyIncomeShare: (monthlyEMI / financialData.averageMonthlyIncome) * 100
    };
  }

  // Generate alternative options
  generateAlternativeOptions(recommendedLoan, financialData) {
    const alternatives = [];

    // Option 1: Lower amount with better terms
    alternatives.push({
      type: 'REDUCED_AMOUNT',
      amount: recommendedLoan.optimalAmount * 0.75,
      term: recommendedLoan.loanStructure.recommendedTerm + 12,
      interestRate: recommendedLoan.loanStructure.recommendedInterestRate - 0.5,
      reasoning: 'Lower amount with longer term and better rate',
      approvalProbability: 95
    });

    // Option 2: Same amount with collateral
    alternatives.push({
      type: 'SECURED_LOAN',
      amount: recommendedLoan.optimalAmount * 1.2,
      term: recommendedLoan.loanStructure.recommendedTerm,
      interestRate: recommendedLoan.loanStructure.recommendedInterestRate - 1.0,
      reasoning: 'Higher amount with collateral security',
      approvalProbability: 90,
      collateralRequired: true
    });

    // Option 3: Step-up financing
    alternatives.push({
      type: 'STEP_UP_FINANCING',
      amount: recommendedLoan.optimalAmount,
      term: recommendedLoan.loanStructure.recommendedTerm,
      interestRate: recommendedLoan.loanStructure.recommendedInterestRate,
      reasoning: 'Gradual disbursement based on milestones',
      approvalProbability: 85,
      structure: 'Step-up disbursement'
    });

    return alternatives;
  }

  // Helper methods
  calculateMaxLoanFromEMI(emi, termMonths, annualRate) {
    const monthlyRate = annualRate / 12 / 100;
    if (monthlyRate === 0) return emi * termMonths;
    
    return emi * (1 - Math.pow(1 + monthlyRate, -termMonths)) / monthlyRate;
  }

  calculateEMI(principal, termMonths, annualRate) {
    const monthlyRate = annualRate / 12 / 100;
    if (monthlyRate === 0) return principal / termMonths;
    
    return principal * monthlyRate * Math.pow(1 + monthlyRate, termMonths) / 
           (Math.pow(1 + monthlyRate, termMonths) - 1);
  }

  calculateCashFlowTrend(cashFlowHistory) {
    if (cashFlowHistory.length < 6) return 'stable';
    
    const recent = cashFlowHistory.slice(-3);
    const earlier = cashFlowHistory.slice(-6, -3);
    
    const recentAvg = recent.reduce((sum, cf) => sum + cf.amount, 0) / recent.length;
    const earlierAvg = earlier.reduce((sum, cf) => sum + cf.amount, 0) / earlier.length;
    
    const change = ((recentAvg - earlierAvg) / earlierAvg) * 100;
    
    if (change > 10) return 'growing';
    if (change < -10) return 'declining';
    return 'stable';
  }

  detectSeasonality(cashFlowHistory) {
    // Simplified seasonality detection
    const months = cashFlowHistory.map(cf => new Date(cf.date).getMonth());
    const amounts = cashFlowHistory.map(cf => cf.amount);
    
    // Calculate monthly averages
    const monthlyAverages = {};
    months.forEach((month, index) => {
      if (!monthlyAverages[month]) {
        monthlyAverages[month] = [];
      }
      monthlyAverages[month].push(amounts[index]);
    });

    Object.keys(monthlyAverages).forEach(month => {
      monthlyAverages[month] = monthlyAverages[month].reduce((sum, a) => sum + a, 0) / monthlyAverages[month].length;
    });

    const avgValues = Object.values(monthlyAverages);
    const maxAvg = Math.max(...avgValues);
    const minAvg = Math.min(...avgValues);
    const seasonalityStrength = (maxAvg - minAvg) / (maxAvg + minAvg);

    if (seasonalityStrength > 0.3) return 'high';
    if (seasonalityStrength > 0.15) return 'moderate';
    return 'low';
  }

  analyzeLoanPurpose(loanPurpose) {
    const purposeAnalysis = {
      'Working Capital': { risk: 'Low', term: 12, multiplier: 1.0 },
      'Machinery Purchase': { risk: 'Medium', term: 36, multiplier: 0.9 },
      'Business Expansion': { risk: 'Medium', term: 48, multiplier: 0.85 },
      'Debt Consolidation': { risk: 'High', term: 60, multiplier: 0.8 },
      'Real Estate': { risk: 'Low', term: 240, multiplier: 1.2 },
      'Inventory Purchase': { risk: 'Medium', term: 24, multiplier: 0.95 }
    };

    return purposeAnalysis[loanPurpose] || { risk: 'Medium', term: 36, multiplier: 1.0 };
  }

  optimizeLoanTerm(financialData, loanPurpose) {
    const purpose = this.analyzeLoanPurpose(loanPurpose);
    const cashFlowStability = financialData.cashFlowStability || 50;
    
    let optimalTerm = purpose.term;
    
    // Adjust based on cash flow stability
    if (cashFlowStability > 80) {
      optimalTerm = Math.max(12, purpose.term - 12);
    } else if (cashFlowStability < 50) {
      optimalTerm = Math.min(84, purpose.term + 12);
    }

    return {
      optimalTerm,
      reasoning: `Term optimized based on cash flow stability and loan purpose`
    };
  }

  optimizeInterestRate(financialData) {
    const creditScore = financialData.creditScore || 500;
    const riskScore = financialData.riskScore || 50;
    
    let baseRate = 12.0; // Base rate
    
    // Adjust for credit score
    if (creditScore > 750) baseRate -= 2.0;
    else if (creditScore > 700) baseRate -= 1.0;
    else if (creditScore < 600) baseRate += 2.0;
    else if (creditScore < 500) baseRate += 4.0;

    // Adjust for risk score
    if (riskScore < 30) baseRate -= 1.0;
    else if (riskScore > 70) baseRate += 2.0;

    return {
      rate: Math.max(6.0, Math.min(18.0, baseRate)),
      reasoning: `Rate adjusted for credit score and risk profile`
    };
  }

  optimizeRepaymentFrequency(financialData) {
    const businessType = financialData.businessType || 'service';
    
    if (businessType === 'manufacturing') return 'monthly';
    if (businessType === 'retail') return 'weekly';
    if (businessType === 'agriculture') return 'quarterly';
    
    return 'monthly';
  }

  suggestCollateralRequirements(financialData, loanPurpose) {
    const purpose = this.analyzeLoanPurpose(loanPurpose);
    
    if (purpose.risk === 'Low') {
      return { required: false, type: 'none' };
    } else if (purpose.risk === 'Medium') {
      return { required: true, type: 'partial_collateral', percentage: 25 };
    } else {
      return { required: true, type: 'full_collateral', percentage: 50 };
    }
  }

  stressTestLoan(loanAmount, financialData) {
    const stressScenarios = [
      { name: 'Revenue Decline 20%', factor: 0.8 },
      { name: 'Interest Rate Increase 2%', factor: 1.15 },
      { name: 'Expense Increase 15%', factor: 1.1 }
    ];

    const results = stressScenarios.map(scenario => {
      const stressedCashFlow = financialData.averageMonthlyCashFlow * scenario.factor;
      const emi = this.calculateEMI(loanAmount, 60, 12.0);
      const stressTestPass = stressedCashFlow > emi * 1.2;

      return {
        scenario: scenario.name,
        stressedCashFlow,
        emi,
        stressTestPass,
        buffer: stressedCashFlow / emi
      };
    });

    const passedScenarios = results.filter(r => r.stressTestPass).length;
    const stressTestScore = (passedScenarios / stressScenarios.length) * 100;

    return {
      overallScore: stressTestScore,
      results,
      recommendation: stressTestScore > 66 ? 'Pass' : 'Fail'
    };
  }

  generateRecommendationReasoning(analysis, optimalAmount, requestedAmount, maxAmount) {
    const reasons = [];

    if (optimalAmount < requestedAmount) {
      reasons.push(`Recommended amount is ${((requestedAmount - optimalAmount) / requestedAmount * 100).toFixed(1)}% lower than requested to ensure manageable repayments`);
    }

    if (analysis.cashFlowAnalysis.stability < 60) {
      reasons.push(`Reduced amount due to cash flow volatility (stability: ${analysis.cashFlowAnalysis.stability.toFixed(1)}%)`);
    }

    if (analysis.riskAssessment.riskScore > 60) {
      reasons.push(`Conservative recommendation due to risk profile (score: ${analysis.riskAssessment.riskScore})`);
    }

    if (analysis.industryAdjustment.multiplier < 1.0) {
      reasons.push(`Industry adjustment applied for ${analysis.industryAdjustment.riskProfile.industry} sector`);
    }

    if (reasons.length === 0) {
      reasons.push('Recommended based on strong repayment capacity and favorable risk profile');
    }

    return reasons.join('. ');
  }

  calculateConfidence(analysis, optimalAmount, requestedAmount) {
    let confidence = 75; // Base confidence

    // Adjust based on data quality
    if (analysis.cashFlowAnalysis.stability > 80) confidence += 10;
    if (analysis.repaymentCapacity.repaymentCapacityScore > 80) confidence += 10;
    if (analysis.riskAssessment.riskScore < 40) confidence += 10;

    // Adjust based on request alignment
    const alignment = 1 - Math.abs(optimalAmount - requestedAmount) / requestedAmount;
    confidence += alignment * 15;

    return Math.min(95, Math.max(50, confidence));
  }

  calculateAffordabilityScore(dtiRatio, cashFlowBuffer) {
    let score = 50;

    if (dtiRatio < 0.20) score += 25;
    else if (dtiRatio < 0.28) score += 15;
    else score -= 20;

    if (cashFlowBuffer > 1.5) score += 25;
    else if (cashFlowBuffer > 1.2) score += 15;
    else score -= 15;

    return Math.max(0, Math.min(100, score));
  }

  generateWarnings(recommendedLoan, financialData) {
    const warnings = [];

    if (recommendedLoan.affordabilityMetrics.dtiRatio > 25) {
      warnings.push({
        type: 'HIGH_DTI',
        severity: 'HIGH',
        message: 'Debt-to-income ratio exceeds recommended 25% threshold'
      });
    }

    if (recommendedLoan.affordabilityMetrics.cashFlowBuffer < 1.2) {
      warnings.push({
        type: 'LOW_CASH_FLOW_BUFFER',
        severity: 'MEDIUM',
        message: 'Limited cash flow buffer for unexpected expenses'
      });
    }

    if (recommendedLoan.stressTest.recommendation === 'Fail') {
      warnings.push({
        type: 'STRESS_TEST_FAILURE',
        severity: 'HIGH',
        message: 'Loan may not withstand adverse scenarios'
      });
    }

    return warnings;
  }

  getRiskLevel(score) {
    if (score <= 30) return 'LOW';
    if (score <= 50) return 'MEDIUM';
    if (score <= 70) return 'HIGH';
    return 'VERY_HIGH';
  }

  // Generate mock data for demonstration
  generateMockLoanRecommendationData() {
    return {
      financialData: {
        averageMonthlyIncome: 500000,
        averageMonthlyExpenses: 300000,
        existingMonthlyEMI: 50000,
        averageMonthlyCashFlow: 150000,
        cashFlowHistory: Array.from({ length: 12 }, (_, i) => ({
          date: new Date(2024, i, 1).toISOString(),
          amount: Math.random() * 100000 + 100000
        })),
        cashFlowStability: 75,
        creditScore: Math.floor(Math.random() * 300) + 500,
        businessAge: Math.floor(Math.random() * 10) + 2,
        profitMargin: Math.random() * 0.2 + 0.05,
        debtToEquity: Math.random() * 1.5 + 0.2,
        riskScore: Math.floor(Math.random() * 60) + 20,
        industry: ['Technology', 'Manufacturing', 'Healthcare', 'Finance', 'Retail'][Math.floor(Math.random() * 5)],
        businessType: 'service'
      },
      requestedAmount: 10000000,
      loanPurpose: 'Working Capital'
    };
  }
}

export default SmartLoanRecommendationService;
