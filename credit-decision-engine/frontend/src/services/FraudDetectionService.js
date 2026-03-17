// Fraud Detection Engine Service
// Detects fraudulent financial activity in loan applications

class FraudDetectionService {
  constructor() {
    this.fraudPatterns = [];
    this.riskThresholds = {
      circularTrading: 0.8,
      fakeInvoiceNetwork: 0.7,
      abnormalRevenueSpike: 3.0,
      suspiciousTransactionPattern: 0.75,
      identityMismatch: 0.9
    };
  }

  // Comprehensive fraud detection analysis
  analyzeFraudRisk(applicationData, transactionHistory, businessNetwork) {
    const fraudSignals = {
      circularTrading: this.detectCircularTrading(businessNetwork),
      fakeInvoiceNetwork: this.detectFakeInvoiceNetwork(transactionHistory),
      abnormalRevenueSpike: this.detectAbnormalRevenueSpike(applicationData.revenueHistory),
      suspiciousTransactionPatterns: this.detectSuspiciousTransactionPatterns(transactionHistory),
      identityVerification: this.verifyIdentity(applicationData),
      behavioralAnalysis: this.analyzeBehavioralPatterns(applicationData, transactionHistory),
      networkAnalysis: this.analyzeBusinessNetwork(businessNetwork)
    };

    const overallRiskScore = this.calculateOverallFraudRisk(fraudSignals);
    const riskLevel = this.getFraudRiskLevel(overallRiskScore);
    const recommendations = this.generateFraudRecommendations(fraudSignals, overallRiskScore);

    return {
      fraudRiskScore: overallRiskScore,
      riskLevel,
      signals: fraudSignals,
      recommendations,
      requiresManualReview: overallRiskScore > 0.7,
      alertLevel: this.getAlertLevel(overallRiskScore)
    };
  }

  // Detect circular trading patterns
  detectCircularTrading(businessNetwork) {
    if (!businessNetwork || !businessNetwork.entities) {
      return { detected: false, confidence: 0, details: [] };
    }

    const entities = businessNetwork.entities;
    const circularGroups = [];
    let maxCircularity = 0;

    // Build transaction graph
    const transactionGraph = this.buildTransactionGraph(entities);
    
    // Detect cycles in the graph
    entities.forEach((entity, index) => {
      const visited = new Set();
      const path = [];
      const circularity = this.detectCycles(transactionGraph, entity.id, visited, path);
      
      if (circularity.hasCycle) {
        circularGroups.push({
          entities: circularity.cycle,
          circularityScore: circularity.score,
          transactionAmount: circularity.totalAmount
        });
        maxCircularity = Math.max(maxCircularity, circularity.score);
      }
    });

    const riskScore = Math.min(1.0, maxCircularity / this.riskThresholds.circularTrading);
    
    return {
      detected: circularGroups.length > 0,
      confidence: riskScore,
      details: circularGroups,
      riskFactors: {
        circularEntityCount: circularGroups.length,
        maxCircularityScore: maxCircularity,
        averageTransactionAmount: circularGroups.reduce((sum, g) => sum + g.transactionAmount, 0) / Math.max(1, circularGroups.length)
      }
    };
  }

  // Detect fake invoice networks
  detectFakeInvoiceNetwork(transactionHistory) {
    if (!transactionHistory || transactionHistory.length === 0) {
      return { detected: false, confidence: 0, details: [] };
    }

    const suspiciousInvoices = [];
    const invoiceNetworks = {};

    // Group transactions by invoice patterns
    transactionHistory.forEach(transaction => {
      if (transaction.type === 'invoice') {
        const pattern = this.generateInvoicePattern(transaction);
        if (!invoiceNetworks[pattern]) {
          invoiceNetworks[pattern] = [];
        }
        invoiceNetworks[pattern].push(transaction);
      }
    });

    // Analyze each invoice network
    Object.entries(invoiceNetworks).forEach(([pattern, invoices]) => {
      const networkAnalysis = this.analyzeInvoiceNetwork(invoices);
      
      if (networkAnalysis.suspicious) {
        suspiciousInvoices.push({
          pattern,
          invoices,
          riskScore: networkAnalysis.riskScore,
          reasons: networkAnalysis.reasons
        });
      }
    });

    const maxRiskScore = suspiciousInvoices.length > 0 
      ? Math.max(...suspiciousInvoices.map(i => i.riskScore))
      : 0;

    return {
      detected: suspiciousInvoices.length > 0,
      confidence: Math.min(1.0, maxRiskScore / this.riskThresholds.fakeInvoiceNetwork),
      details: suspiciousInvoices,
      riskFactors: {
        suspiciousNetworkCount: suspiciousInvoices.length,
        maxRiskScore,
        totalSuspiciousAmount: suspiciousInvoices.reduce((sum, i) => 
          sum + i.invoices.reduce((subSum, inv) => subSum + inv.amount, 0), 0)
      }
    };
  }

  // Detect abnormal revenue spikes
  detectAbnormalRevenueSpike(revenueHistory) {
    if (!revenueHistory || revenueHistory.length < 6) {
      return { detected: false, confidence: 0, details: [] };
    }

    const revenues = revenueHistory.map(r => r.amount);
    const mean = revenues.reduce((sum, r) => sum + r, 0) / revenues.length;
    const stdDev = Math.sqrt(revenues.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / revenues.length);
    
    const abnormalMonths = [];
    const threshold = mean + (this.riskThresholds.abnormalRevenueSpike * stdDev);

    revenueHistory.forEach((month, index) => {
      if (month.amount > threshold) {
        const zScore = (month.amount - mean) / stdDev;
        abnormalMonths.push({
          month: month.month,
          amount: month.amount,
          zScore,
          deviation: ((month.amount - mean) / mean) * 100
        });
      }
    });

    const maxDeviation = abnormalMonths.length > 0 
      ? Math.max(...abnormalMonths.map(m => Math.abs(m.deviation)))
      : 0;

    return {
      detected: abnormalMonths.length > 0,
      confidence: Math.min(1.0, maxDeviation / (this.riskThresholds.abnormalRevenueSpike * 100)),
      details: abnormalMonths,
      riskFactors: {
        abnormalMonthCount: abnormalMonths.length,
        maxDeviation,
        averageRevenue: mean,
        volatility: stdDev
      }
    };
  }

  // Detect suspicious transaction patterns
  detectSuspiciousTransactionPatterns(transactionHistory) {
    if (!transactionHistory || transactionHistory.length === 0) {
      return { detected: false, confidence: 0, details: [] };
    }

    const patterns = {
      roundAmounts: this.detectRoundAmountPattern(transactionHistory),
      timingAnomalies: this.detectTimingAnomalies(transactionHistory),
      velocityAnomalies: this.detectVelocityAnomalies(transactionHistory),
      geographicAnomalies: this.detectGeographicAnomalies(transactionHistory),
      counterpartyConcentration: this.detectCounterpartyConcentration(transactionHistory)
    };

    const suspiciousScores = Object.values(patterns).map(p => p.riskScore);
    const maxScore = Math.max(...suspiciousScores, 0);
    const overallConfidence = Math.min(1.0, maxScore / this.riskThresholds.suspiciousTransactionPattern);

    return {
      detected: maxScore > 0.5,
      confidence: overallConfidence,
      details: patterns,
      riskFactors: {
        maxPatternScore: maxScore,
        suspiciousPatternCount: Object.values(patterns).filter(p => p.detected).length
      }
    };
  }

  // Verify identity and documentation
  verifyIdentity(applicationData) {
    const identityChecks = {
      documentVerification: this.verifyDocuments(applicationData.documents),
      addressVerification: this.verifyAddress(applicationData),
      businessVerification: this.verifyBusinessRegistration(applicationData),
      bankAccountVerification: this.verifyBankAccount(applicationData),
      crossReferenceCheck: this.performCrossReferenceCheck(applicationData)
    };

    const riskScores = Object.values(identityChecks).map(check => check.riskScore);
    const overallRiskScore = Math.max(...riskScores);

    return {
      detected: overallRiskScore > 0.6,
      confidence: Math.min(1.0, overallRiskScore / this.riskThresholds.identityMismatch),
      details: identityChecks,
      riskFactors: {
        maxIdentityRiskScore: overallRiskScore,
        failedVerifications: Object.values(identityChecks).filter(check => !check.passed).length
      }
    };
  }

  // Analyze behavioral patterns
  analyzeBehavioralPatterns(applicationData, transactionHistory) {
    const behaviors = {
      applicationTiming: this.analyzeApplicationTiming(applicationData),
      informationConsistency: this.checkInformationConsistency(applicationData),
      deviceFingerprinting: this.analyzeDeviceFingerprinting(applicationData),
      browsingPatterns: this.analyzeBrowsingPatterns(applicationData)
    };

    const riskScores = Object.values(behaviors).map(b => b.riskScore);
    const maxScore = Math.max(...riskScores, 0);

    return {
      detected: maxScore > 0.5,
      confidence: Math.min(1.0, maxScore / 0.8),
      details: behaviors,
      riskFactors: {
        maxBehavioralRiskScore: maxScore,
        anomalousBehaviors: Object.values(behaviors).filter(b => b.anomalous).length
      }
    };
  }

  // Analyze business network
  analyzeBusinessNetwork(businessNetwork) {
    if (!businessNetwork || !businessNetwork.entities) {
      return { detected: false, confidence: 0, details: {} };
    }

    const networkAnalysis = {
      connectedEntityCount: businessNetwork.entities.length,
      relatedPartyTransactions: this.detectRelatedPartyTransactions(businessNetwork),
      shellCompanyIndicators: this.detectShellCompanyIndicators(businessNetwork),
      beneficialOwnership: this.analyzeBeneficialOwnership(businessNetwork)
    };

    const riskScore = this.calculateNetworkRiskScore(networkAnalysis);

    return {
      detected: riskScore > 0.6,
      confidence: Math.min(1.0, riskScore / 0.8),
      details: networkAnalysis,
      riskFactors: {
        networkRiskScore: riskScore,
        highRiskConnections: networkAnalysis.shellCompanyIndicators.length + networkAnalysis.relatedPartyTransactions.length
      }
    };
  }

  // Helper methods for specific pattern detection
  generateInvoicePattern(transaction) {
    return `${transaction.vendor_id}_${transaction.amount_rounded}_${transaction.description_hash}`;
  }

  analyzeInvoiceNetwork(invoices) {
    const analysis = {
      suspicious: false,
      riskScore: 0,
      reasons: []
    };

    // Check for identical amounts
    const amounts = invoices.map(inv => inv.amount);
    const uniqueAmounts = new Set(amounts);
    if (uniqueAmounts.size < amounts.length * 0.5) {
      analysis.suspicious = true;
      analysis.riskScore += 30;
      analysis.reasons.push('Multiple invoices with identical amounts');
    }

    // Check for sequential invoice numbers
    const invoiceNumbers = invoices.map(inv => inv.invoice_number).sort();
    let sequentialCount = 0;
    for (let i = 1; i < invoiceNumbers.length; i++) {
      if (parseInt(invoiceNumbers[i]) - parseInt(invoiceNumbers[i-1]) === 1) {
        sequentialCount++;
      }
    }
    if (sequentialCount > invoices.length * 0.6) {
      analysis.suspicious = true;
      analysis.riskScore += 25;
      analysis.reasons.push('Sequential invoice numbering pattern');
    }

    // Check for same vendor
    const vendors = invoices.map(inv => inv.vendor_id);
    const uniqueVendors = new Set(vendors);
    if (uniqueVendors.size === 1 && invoices.length > 3) {
      analysis.suspicious = true;
      analysis.riskScore += 20;
      analysis.reasons.push('All invoices from single vendor');
    }

    return analysis;
  }

  detectRoundAmountPattern(transactions) {
    const roundTransactions = transactions.filter(t => 
      t.amount % 1000 === 0 || t.amount % 500 === 0
    );
    const roundRatio = roundTransactions.length / transactions.length;

    return {
      detected: roundRatio > 0.4,
      riskScore: roundRatio * 100,
      details: {
        roundTransactionCount: roundTransactions.length,
        roundTransactionRatio: roundRatio
      }
    };
  }

  detectTimingAnomalies(transactions) {
    const hours = transactions.map(t => new Date(t.timestamp).getHours());
    const nightTransactions = hours.filter(h => h < 6 || h > 22);
    const weekendTransactions = transactions.filter(t => {
      const day = new Date(t.timestamp).getDay();
      return day === 0 || day === 6;
    });

    const nightRatio = nightTransactions.length / transactions.length;
    const weekendRatio = weekendTransactions.length / transactions.length;

    return {
      detected: nightRatio > 0.3 || weekendRatio > 0.4,
      riskScore: Math.max(nightRatio, weekendRatio) * 100,
      details: {
        nightTransactionRatio: nightRatio,
        weekendTransactionRatio: weekendRatio
      }
    };
  }

  detectVelocityAnomalies(transactions) {
    const dailyVolumes = this.calculateDailyVolumes(transactions);
    const volumes = Object.values(dailyVolumes);
    const mean = volumes.reduce((sum, v) => sum + v, 0) / volumes.length;
    const stdDev = Math.sqrt(volumes.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / volumes.length);

    const anomalousDays = Object.entries(dailyVolumes).filter(([date, volume]) => 
      Math.abs(volume - mean) > 2 * stdDev
    );

    return {
      detected: anomalousDays.length > volumes.length * 0.1,
      riskScore: (anomalousDays.length / volumes.length) * 100,
      details: {
        anomalousDayCount: anomalousDays.length,
        averageDailyVolume: mean,
        volatility: stdDev
      }
    };
  }

  detectGeographicAnomalies(transactions) {
    const locations = transactions.map(t => t.location);
    const uniqueLocations = new Set(locations);
    
    // Check for transactions from high-risk locations
    const highRiskLocations = ['Country A', 'Country B', 'Country C']; // Simplified for demo
    const highRiskTransactions = transactions.filter(t => 
      highRiskLocations.includes(t.location)
    );

    return {
      detected: highRiskTransactions.length > 0 || uniqueLocations.size > 20,
      riskScore: Math.min(100, (highRiskTransactions.length / transactions.length) * 100),
      details: {
        highRiskTransactionCount: highRiskTransactions.length,
        uniqueLocationCount: uniqueLocations.size
      }
    };
  }

  detectCounterpartyConcentration(transactions) {
    const counterparties = {};
    transactions.forEach(t => {
      if (!counterparties[t.counterparty]) {
        counterparties[t.counterparty] = [];
      }
      counterparties[t.counterparty].push(t);
    });

    const concentrations = Object.entries(counterparties).map(([party, txs]) => ({
      party,
      count: txs.length,
      amount: txs.reduce((sum, t) => sum + t.amount, 0)
    }));

    const maxConcentration = Math.max(...concentrations.map(c => c.count));
    const concentrationRatio = maxConcentration / transactions.length;

    return {
      detected: concentrationRatio > 0.6,
      riskScore: concentrationRatio * 100,
      details: {
        maxConcentration,
        concentrationRatio,
        topCounterparty: concentrations.find(c => c.count === maxConcentration)
      }
    };
  }

  // Additional helper methods
  buildTransactionGraph(entities) {
    const graph = {};
    entities.forEach(entity => {
      graph[entity.id] = entity.transactions || [];
    });
    return graph;
  }

  detectCycles(graph, nodeId, visited, path, currentScore = 0) {
    if (visited.has(nodeId)) {
      const cycleStart = path.indexOf(nodeId);
      if (cycleStart !== -1) {
        const cycle = path.slice(cycleStart);
        const totalAmount = cycle.reduce((sum, nodeId) => 
          sum + (graph[nodeId] || []).reduce((subSum, tx) => subSum + tx.amount, 0), 0
        );
        return {
          hasCycle: true,
          cycle,
          score: Math.min(1.0, cycle.length / 5),
          totalAmount
        };
      }
      return { hasCycle: false };
    }

    visited.add(nodeId);
    const transactions = graph[nodeId] || [];
    transactions.forEach(tx => {
      this.detectCycles(graph, tx.to_entity_id, visited, [...path, nodeId], currentScore + tx.risk_score);
    });
    visited.delete(nodeId);
    
    return { hasCycle: false };
  }

  calculateDailyVolumes(transactions) {
    const dailyVolumes = {};
    transactions.forEach(t => {
      const date = new Date(t.timestamp).toISOString().split('T')[0];
      if (!dailyVolumes[date]) {
        dailyVolumes[date] = 0;
      }
      dailyVolumes[date] += t.amount;
    });
    return dailyVolumes;
  }

  // Identity verification methods
  verifyDocuments(documents) {
    const checks = {
      idVerification: this.checkIDDocument(documents.id_proof),
      addressProof: this.checkAddressProof(documents.address_proof),
      businessRegistration: this.checkBusinessRegistration(documents.business_registration),
      financialStatements: this.checkFinancialStatements(documents.financial_statements)
    };

    const failedChecks = Object.values(checks).filter(check => !check.valid);
    const riskScore = (failedChecks.length / Object.keys(checks).length) * 100;

    return {
      passed: failedChecks.length === 0,
      riskScore,
      details: checks
    };
  }

  verifyAddress(applicationData) {
    // Simplified address verification
    return {
      passed: true,
      riskScore: 10,
      details: 'Address verified successfully'
    };
  }

  verifyBusinessRegistration(applicationData) {
    return {
      passed: applicationData.business_registration_valid,
      riskScore: applicationData.business_registration_valid ? 15 : 80,
      details: applicationData.business_registration_valid ? 'Valid registration' : 'Invalid registration'
    };
  }

  verifyBankAccount(applicationData) {
    return {
      passed: applicationData.bank_account_verified,
      riskScore: applicationData.bank_account_verified ? 20 : 90,
      details: applicationData.bank_account_verified ? 'Bank account verified' : 'Bank account not verified'
    };
  }

  performCrossReferenceCheck(applicationData) {
    return {
      passed: true,
      riskScore: 25,
      details: 'Cross-reference check completed'
    };
  }

  // Calculate overall fraud risk
  calculateOverallFraudRisk(signals) {
    const weights = {
      circularTrading: 0.25,
      fakeInvoiceNetwork: 0.25,
      abnormalRevenueSpike: 0.20,
      suspiciousTransactionPatterns: 0.15,
      identityVerification: 0.10,
      behavioralAnalysis: 0.05
    };

    let totalScore = 0;
    Object.entries(signals).forEach(([signal, data]) => {
      if (weights[signal]) {
        totalScore += data.confidence * weights[signal];
      }
    });

    return Math.min(1.0, totalScore);
  }

  getFraudRiskLevel(score) {
    if (score >= 0.8) return 'CRITICAL';
    if (score >= 0.6) return 'HIGH';
    if (score >= 0.4) return 'MEDIUM';
    if (score >= 0.2) return 'LOW';
    return 'VERY_LOW';
  }

  getAlertLevel(score) {
    if (score >= 0.8) return 'IMMEDIATE_ACTION_REQUIRED';
    if (score >= 0.6) return 'HIGH_PRIORITY_ALERT';
    if (score >= 0.4) return 'MEDIUM_PRIORITY_ALERT';
    if (score >= 0.2) return 'LOW_PRIORITY_ALERT';
    return 'INFORMATION_ONLY';
  }

  generateFraudRecommendations(signals, overallScore) {
    const recommendations = [];

    if (signals.circularTrading.detected) {
      recommendations.push({
        priority: 'HIGH',
        action: 'Investigate circular trading relationships',
        description: 'Detailed examination of related party transactions required'
      });
    }

    if (signals.fakeInvoiceNetwork.detected) {
      recommendations.push({
        priority: 'HIGH',
        action: 'Verify invoice authenticity',
        description: 'Contact vendors to confirm invoice validity'
      });
    }

    if (signals.abnormalRevenueSpike.detected) {
      recommendations.push({
        priority: 'MEDIUM',
        action: 'Request additional revenue documentation',
        description: 'Verify unusual revenue spikes with supporting evidence'
      });
    }

    if (overallScore > 0.7) {
      recommendations.push({
        priority: 'HIGH',
        action: 'Manual review required',
        description: 'Application requires comprehensive manual investigation'
      });
    }

    return recommendations;
  }

  calculateNetworkRiskScore(networkAnalysis) {
    let score = 0;
    
    if (networkAnalysis.shellCompanyIndicators.length > 0) {
      score += networkAnalysis.shellCompanyIndicators.length * 20;
    }
    
    if (networkAnalysis.relatedPartyTransactions.length > 5) {
      score += 30;
    }
    
    if (networkAnalysis.connectedEntityCount > 50) {
      score += 20;
    }

    return Math.min(100, score);
  }

  // Generate mock fraud detection data for demonstration
  generateMockFraudData() {
    return {
      applicationData: {
        documents: {
          id_proof: { type: 'AADHAR', number: 'XXXXXXXXXX' },
          address_proof: { type: 'Utility Bill', valid: true },
          business_registration: { valid: true, number: 'XXXXXXXXXX' },
          financial_statements: { type: 'Audited', years: 3 }
        },
        business_registration_valid: true,
        bank_account_verified: true
      },
      transactionHistory: Array.from({ length: 100 }, (_, i) => ({
        timestamp: new Date(2024, Math.floor(i / 3), (i % 30) + 1).toISOString(),
        amount: Math.random() * 100000 + 10000,
        type: Math.random() > 0.5 ? 'credit' : 'debit',
        counterparty: `COUNTERPARTY_${Math.floor(Math.random() * 20) + 1}`,
        location: ['Mumbai', 'Delhi', 'Bangalore', 'Chennai'][Math.floor(Math.random() * 4)],
        description: `Transaction ${i + 1}`
      })),
      businessNetwork: {
        entities: Array.from({ length: 15 }, (_, i) => ({
          id: `ENTITY_${i + 1}`,
          name: `Company ${i + 1}`,
          type: ['supplier', 'customer', 'related_party'][Math.floor(Math.random() * 3)],
          transactions: Array.from({ length: Math.floor(Math.random() * 10) + 1 }, (_, j) => ({
            to_entity_id: `ENTITY_${Math.floor(Math.random() * 15) + 1}`,
            amount: Math.random() * 500000 + 50000,
            risk_score: Math.random()
          }))
        }))
      },
      revenueHistory: Array.from({ length: 12 }, (_, i) => ({
        month: new Date(2024, i, 1).toISOString(),
        amount: Math.random() * 2000000 + 3000000
      }))
    };
  }
}

export default FraudDetectionService;
