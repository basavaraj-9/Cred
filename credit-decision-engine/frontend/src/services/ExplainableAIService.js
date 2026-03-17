// Explainable AI Credit Decision Service
// Makes AI credit decisions transparent and understandable

class ExplainableAIService {
  constructor() {
    this.decisionFactors = [];
    this.importanceWeights = {
      debt_to_equity: 0.25,
      revenue_trend: 0.20,
      cash_flow_adequacy: 0.20,
      industry_risk: 0.15,
      legal_compliance: 0.10,
      market_position: 0.10
    };
  }

  // Generate explainable credit decision
  generateExplainableDecision(loanApplication, financialData, riskScore) {
    const decision = this.makeDecision(riskScore);
    const explanations = this.generateExplanations(loanApplication, financialData, riskScore);
    const regulatoryCompliance = this.checkRegulatoryCompliance(explanations);
    
    return {
      loanDecision: decision.status,
      confidence: decision.confidence,
      reasons: explanations.primaryReasons,
      contributingFactors: explanations.contributingFactors,
      riskBreakdown: explanations.riskBreakdown,
      regulatoryCompliance,
      improvementSuggestions: this.generateImprovementSuggestions(explanations),
      alternativeOptions: this.generateAlternativeOptions(decision, financialData)
    };
  }

  makeDecision(riskScore) {
    if (riskScore <= 35) {
      return {
        status: 'APPROVED',
        confidence: 85 + Math.floor(Math.random() * 10),
        riskLevel: 'LOW'
      };
    } else if (riskScore <= 60) {
      return {
        status: 'CONDITIONAL_APPROVAL',
        confidence: 70 + Math.floor(Math.random() * 10),
        riskLevel: 'MODERATE'
      };
    } else if (riskScore <= 80) {
      return {
        status: 'REVIEW_REQUIRED',
        confidence: 60 + Math.floor(Math.random() * 10),
        riskLevel: 'HIGH'
      };
    } else {
      return {
        status: 'REJECTED',
        confidence: 75 + Math.floor(Math.random() * 10),
        riskLevel: 'VERY_HIGH'
      };
    }
  }

  generateExplanations(application, financialData, riskScore) {
    const explanations = {
      primaryReasons: [],
      contributingFactors: [],
      riskBreakdown: {}
    };

    // Analyze debt-to-equity ratio
    const debtToEquity = financialData.totalLiabilities / financialData.equity;
    if (debtToEquity > 2.0) {
      explanations.primaryReasons.push({
        factor: 'High debt-to-equity ratio',
        value: debtToEquity.toFixed(2),
        impact: 'HIGH',
        description: `Company's debt (${(debtToEquity * 100).toFixed(0)}% of equity) exceeds acceptable limits`
      });
    } else if (debtToEquity > 1.5) {
      explanations.contributingFactors.push({
        factor: 'Moderate debt-to-equity ratio',
        value: debtToEquity.toFixed(2),
        impact: 'MEDIUM',
        description: `Debt ratio of ${(debtToEquity * 100).toFixed(0)}% requires monitoring`
      });
    }

    // Analyze revenue trend
    const revenueTrend = this.analyzeRevenueTrend(financialData.revenueHistory);
    if (revenueTrend.trend === 'declining' && revenueTrend.change < -20) {
      explanations.primaryReasons.push({
        factor: 'Declining revenue trend',
        value: `${revenueTrend.change.toFixed(1)}%`,
        impact: 'HIGH',
        description: `Revenue has declined by ${Math.abs(revenueTrend.change).toFixed(1)}% over recent periods`
      });
    } else if (revenueTrend.trend === 'volatile') {
      explanations.contributingFactors.push({
        factor: 'Revenue volatility',
        value: `${revenueTrend.volatility.toFixed(1)}%`,
        impact: 'MEDIUM',
        description: `Revenue shows high volatility of ${revenueTrend.volatility.toFixed(1)}%`
      });
    }

    // Analyze cash flow adequacy
    const cashFlowRatio = financialData.monthlyCashFlow / financialData.proposedMonthlyPayment;
    if (cashFlowRatio < 1.2) {
      explanations.primaryReasons.push({
        factor: 'Insufficient cash flow coverage',
        value: cashFlowRatio.toFixed(2),
        impact: 'HIGH',
        description: `Cash flow covers only ${(cashFlowRatio * 100).toFixed(0)}% of proposed payment`
      });
    }

    // Analyze industry risk
    const industryRisk = this.getIndustryRisk(financialData.industry);
    if (industryRisk.riskLevel === 'HIGH') {
      explanations.contributingFactors.push({
        factor: 'High industry risk',
        value: industryRisk.riskScore,
        impact: 'MEDIUM',
        description: `${financialData.industry} industry currently facing high market volatility`
      });
    }

    // Analyze legal compliance
    const legalIssues = this.checkLegalCompliance(financialData);
    if (legalIssues.hasIssues) {
      explanations.primaryReasons.push({
        factor: 'Legal and compliance issues',
        value: legalIssues.issueCount,
        impact: 'HIGH',
        description: `${legalIssues.issueCount} pending legal or regulatory issues detected`
      });
    }

    // Analyze market position
    const marketPosition = this.assessMarketPosition(financialData);
    if (marketPosition.score < 50) {
      explanations.contributingFactors.push({
        factor: 'Weak market position',
        value: marketPosition.score,
        impact: 'MEDIUM',
        description: `Company holds ${marketPosition.marketShare.toFixed(1)}% market share`
      });
    }

    // Generate risk breakdown
    explanations.riskBreakdown = {
      financialRisk: this.calculateFinancialRisk(financialData),
      operationalRisk: this.calculateOperationalRisk(financialData),
      marketRisk: this.calculateMarketRisk(financialData),
      complianceRisk: this.calculateComplianceRisk(financialData)
    };

    return explanations;
  }

  analyzeRevenueTrend(revenueHistory) {
    if (!revenueHistory || revenueHistory.length < 3) {
      return { trend: 'insufficient_data', change: 0, volatility: 0 };
    }

    const recent = revenueHistory.slice(-3);
    const earlier = revenueHistory.slice(-6, -3);
    
    const recentAvg = recent.reduce((sum, r) => sum + r.amount, 0) / recent.length;
    const earlierAvg = earlier.reduce((sum, r) => sum + r.amount, 0) / earlier.length;
    
    const change = ((recentAvg - earlierAvg) / earlierAvg) * 100;
    
    // Calculate volatility
    const allValues = revenueHistory.map(r => r.amount);
    const mean = allValues.reduce((sum, v) => sum + v, 0) / allValues.length;
    const variance = allValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / allValues.length;
    const volatility = Math.sqrt(variance) / mean * 100;

    let trend = 'stable';
    if (change < -10) trend = 'declining';
    else if (change > 10) trend = 'growing';
    else if (volatility > 30) trend = 'volatile';

    return { trend, change, volatility };
  }

  getIndustryRisk(industry) {
    const industryRisks = {
      'Technology': { riskScore: 35, riskLevel: 'MEDIUM', factors: ['High competition', 'Rapid change'] },
      'Manufacturing': { riskScore: 45, riskLevel: 'MEDIUM', factors: ['Capital intensive', 'Cyclical demand'] },
      'Healthcare': { riskScore: 25, riskLevel: 'LOW', factors: ['Stable demand', 'Regulatory barriers'] },
      'Finance': { riskScore: 40, riskLevel: 'MEDIUM', factors: ['Regulatory scrutiny', 'Market volatility'] },
      'Retail': { riskScore: 50, riskLevel: 'HIGH', factors: ['Low margins', 'High competition'] },
      'Construction': { riskScore: 55, riskLevel: 'HIGH', factors: ['Economic sensitivity', 'Project risks'] },
      'Agriculture': { riskScore: 60, riskLevel: 'HIGH', factors: ['Weather dependency', 'Price volatility'] }
    };

    return industryRisks[industry] || { riskScore: 40, riskLevel: 'MEDIUM', factors: ['Unknown industry'] };
  }

  checkLegalCompliance(financialData) {
    const issues = [];
    
    // Check for common legal issues
    if (financialData.pendingLitigation > 0) {
      issues.push({
        type: 'Litigation',
        count: financialData.pendingLitigation,
        severity: 'HIGH'
      });
    }

    if (financialData.regulatoryViolations > 0) {
      issues.push({
        type: 'Regulatory Violations',
        count: financialData.regulatoryViolations,
        severity: 'MEDIUM'
      });
    }

    if (financialData.taxComplianceScore < 70) {
      issues.push({
        type: 'Tax Compliance',
        score: financialData.taxComplianceScore,
        severity: 'MEDIUM'
      });
    }

    return {
      hasIssues: issues.length > 0,
      issueCount: issues.length,
      issues: issues
    };
  }

  assessMarketPosition(financialData) {
    // Simplified market position assessment
    const marketShare = financialData.marketShare || Math.random() * 10;
    const competitorCount = financialData.competitorCount || Math.floor(Math.random() * 20) + 5;
    const growthRate = financialData.growthRate || Math.random() * 20 - 5;

    let score = 50;
    
    if (marketShare > 15) score += 20;
    else if (marketShare > 5) score += 10;
    
    if (competitorCount < 10) score += 15;
    else if (competitorCount < 20) score += 8;
    
    if (growthRate > 10) score += 15;
    else if (growthRate > 0) score += 8;

    return {
      score: Math.min(100, Math.max(0, score)),
      marketShare,
      competitorCount,
      growthRate
    };
  }

  calculateFinancialRisk(financialData) {
    const debtRatio = financialData.totalLiabilities / financialData.totalAssets;
    const currentRatio = financialData.currentAssets / financialData.currentLiabilities;
    const profitMargin = financialData.netProfit / financialData.revenue;

    let riskScore = 50;
    
    if (debtRatio > 0.7) riskScore += 20;
    else if (debtRatio > 0.5) riskScore += 10;
    
    if (currentRatio < 1.0) riskScore += 15;
    else if (currentRatio < 1.5) riskScore += 8;
    
    if (profitMargin < 0) riskScore += 15;
    else if (profitMargin < 0.05) riskScore += 8;

    return Math.min(100, Math.max(0, riskScore));
  }

  calculateOperationalRisk(financialData) {
    const employeeTurnover = financialData.employeeTurnover || Math.random() * 30;
    const operationalEfficiency = financialData.operationalEfficiency || Math.random() * 100;
    const supplierDiversity = financialData.supplierCount || Math.floor(Math.random() * 50);

    let riskScore = 50;
    
    if (employeeTurnover > 25) riskScore += 15;
    else if (employeeTurnover > 15) riskScore += 8;
    
    if (operationalEfficiency < 60) riskScore += 12;
    else if (operationalEfficiency < 80) riskScore += 6;
    
    if (supplierDiversity < 5) riskScore += 10;

    return Math.min(100, Math.max(0, riskScore));
  }

  calculateMarketRisk(financialData) {
    const industryRisk = this.getIndustryRisk(financialData.industry);
    const marketVolatility = financialData.marketVolatility || Math.random() * 40;
    const customerConcentration = financialData.customerConcentration || Math.random() * 80;

    let riskScore = industryRisk.riskScore;
    
    if (marketVolatility > 30) riskScore += 15;
    else if (marketVolatility > 20) riskScore += 8;
    
    if (customerConcentration > 60) riskScore += 12;
    else if (customerConcentration > 40) riskScore += 6;

    return Math.min(100, Math.max(0, riskScore));
  }

  calculateComplianceRisk(financialData) {
    const legalIssues = this.checkLegalCompliance(financialData);
    const auditScore = financialData.auditScore || Math.random() * 100;
    const environmentalCompliance = financialData.environmentalCompliance || Math.random() * 100;

    let riskScore = 50;
    
    if (legalIssues.hasIssues) riskScore += legalIssues.issueCount * 10;
    
    if (auditScore < 70) riskScore += 15;
    else if (auditScore < 85) riskScore += 8;
    
    if (environmentalCompliance < 80) riskScore += 10;

    return Math.min(100, Math.max(0, riskScore));
  }

  checkRegulatoryCompliance(explanations) {
    return {
      fairLendingAct: true, // Simplified for demo
      equalCreditOpportunity: true,
      truthInLending: true,
      riskBasedPricing: true,
      documentation: 'All decision factors documented and traceable'
    };
  }

  generateImprovementSuggestions(explanations) {
    const suggestions = [];

    explanations.primaryReasons.forEach(reason => {
      switch (reason.factor) {
        case 'High debt-to-equity ratio':
          suggestions.push({
            area: 'Financial Structure',
            suggestion: 'Consider equity infusion or debt restructuring',
            priority: 'HIGH',
            potentialImpact: '+15-25 points to credit score'
          });
          break;
        case 'Declining revenue trend':
          suggestions.push({
            area: 'Revenue Growth',
            suggestion: 'Implement diversification strategy and cost optimization',
            priority: 'HIGH',
            potentialImpact: '+10-20 points to credit score'
          });
          break;
        case 'Insufficient cash flow coverage':
          suggestions.push({
            area: 'Cash Flow Management',
            suggestion: 'Improve working capital management and reduce expenses',
            priority: 'HIGH',
            potentialImpact: '+20-30 points to credit score'
          });
          break;
      }
    });

    return suggestions;
  }

  generateAlternativeOptions(decision, financialData) {
    if (decision.status === 'REJECTED') {
      return [
        {
          option: 'Reduced Loan Amount',
          description: 'Consider a smaller loan amount that matches cash flow capacity',
          estimatedApproval: '70%'
        },
        {
          option: 'Secured Loan',
          description: 'Offer collateral to secure the loan',
          estimatedApproval: '80%'
        },
        {
          option: 'Government Guarantee',
          description: 'Explore government-backed loan programs',
          estimatedApproval: '85%'
        }
      ];
    } else if (decision.status === 'CONDITIONAL_APPROVAL') {
      return [
        {
          option: 'Additional Documentation',
          description: 'Provide supplementary financial statements',
          estimatedApproval: '90%'
        },
        {
          option: 'Personal Guarantee',
          description: 'Add personal guarantee from promoters',
          estimatedApproval: '95%'
        }
      ];
    }

    return [];
  }

  // Generate mock explainable data for demonstration
  generateMockExplainableData() {
    return {
      loanApplication: {
        requestedAmount: 10000000,
        purpose: 'Working Capital',
        term: 36,
        collateral: 'None'
      },
      financialData: {
        totalAssets: 50000000,
        totalLiabilities: 30000000,
        equity: 20000000,
        currentAssets: 25000000,
        currentLiabilities: 15000000,
        revenue: 60000000,
        netProfit: 4800000,
        monthlyCashFlow: 800000,
        proposedMonthlyPayment: 300000,
        industry: 'Manufacturing',
        revenueHistory: Array.from({ length: 12 }, (_, i) => ({
          month: new Date(2024, i, 1).toISOString(),
          amount: Math.random() * 1000000 + 4000000
        })),
        pendingLitigation: Math.random() > 0.7 ? 1 : 0,
        regulatoryViolations: Math.random() > 0.8 ? 1 : 0,
        taxComplianceScore: Math.random() * 30 + 70,
        marketShare: Math.random() * 8 + 2,
        competitorCount: Math.floor(Math.random() * 15) + 5,
        growthRate: Math.random() * 15 - 2,
        employeeTurnover: Math.random() * 25 + 5,
        operationalEfficiency: Math.random() * 40 + 60,
        supplierCount: Math.floor(Math.random() * 30) + 10,
        marketVolatility: Math.random() * 30 + 10,
        customerConcentration: Math.random() * 60 + 20,
        auditScore: Math.random() * 30 + 70,
        environmentalCompliance: Math.random() * 25 + 75
      }
    };
  }
}

export default ExplainableAIService;
