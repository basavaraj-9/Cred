// Financial Inclusion Credit Scoring Service
// Alternative credit scoring for MSMEs and individuals without traditional credit history

class FinancialInclusionService {
  constructor() {
    this.gstData = [];
    this.upiTransactions = [];
    this.supplierPayments = [];
    this.marketplaceSales = [];
  }

  // Alternative Credit Scoring Model
  calculateAlternativeCreditScore(borrowerData) {
    const {
      gstTransactionHistory = [],
      upiTransactions = [],
      supplierPaymentRecords = [],
      marketplaceSalesData = [],
      businessAge = 0
    } = borrowerData;

    // GST Transaction Analysis (Weight: 30%)
    const gstScore = this.analyzeGSTTransactions(gstTransactionHistory);
    
    // Digital Payments Analysis (Weight: 25%)
    const upiScore = this.analyzeUPITransactions(upiTransactions);
    
    // Supplier Payment History (Weight: 20%)
    const supplierScore = this.analyzeSupplierPayments(supplierPaymentRecords);
    
    // Marketplace Sales Analysis (Weight: 15%)
    const marketplaceScore = this.analyzeMarketplaceSales(marketplaceSalesData);
    
    // Business Stability (Weight: 10%)
    const stabilityScore = this.analyzeBusinessStability(businessAge);

    // Calculate weighted score
    const alternativeScore = Math.round(
      (gstScore * 0.30) + 
      (upiScore * 0.25) + 
      (supplierScore * 0.20) + 
      (marketplaceScore * 0.15) + 
      (stabilityScore * 0.10)
    );

    return {
      alternativeCreditScore: alternativeScore,
      riskCategory: this.getRiskCategory(alternativeScore),
      components: {
        gstScore,
        upiScore,
        supplierScore,
        marketplaceScore,
        stabilityScore
      },
      insights: this.generateCreditInsights(borrowerData, alternativeScore)
    };
  }

  analyzeGSTTransactions(transactions) {
    if (!transactions || transactions.length === 0) return 40;

    const monthlyGST = this.calculateMonthlyAverage(transactions);
    const consistencyScore = this.calculateConsistencyScore(transactions);
    const growthScore = this.calculateGrowthScore(transactions);
    
    // GST Score Calculation
    let score = 50;
    
    // Monthly GST compliance (max 30 points)
    if (monthlyGST > 100000) score += 20;
    else if (monthlyGST > 50000) score += 15;
    else if (monthlyGST > 10000) score += 10;
    
    // Consistency (max 20 points)
    score += consistencyScore * 0.2;
    
    // Growth trend (max 30 points)
    score += growthScore * 0.3;
    
    return Math.min(100, Math.max(0, Math.round(score)));
  }

  analyzeUPITransactions(transactions) {
    if (!transactions || transactions.length === 0) return 40;

    const avgTransaction = transactions.reduce((sum, t) => sum + t.amount, 0) / transactions.length;
    const frequency = transactions.length;
    const positiveFlow = transactions.filter(t => t.amount > 0).length;
    const consistency = this.calculateConsistencyScore(transactions);
    
    let score = 50;
    
    // Transaction frequency (max 25 points)
    if (frequency > 100) score += 20;
    else if (frequency > 50) score += 15;
    else if (frequency > 20) score += 10;
    
    // Average transaction size (max 25 points)
    if (avgTransaction > 5000) score += 15;
    else if (avgTransaction > 2000) score += 10;
    else if (avgTransaction > 500) score += 5;
    
    // Positive cash flow ratio (max 25 points)
    const positiveRatio = (positiveFlow / frequency) * 100;
    if (positiveRatio > 70) score += 20;
    else if (positiveRatio > 50) score += 15;
    else if (positiveRatio > 30) score += 10;
    
    // Consistency (max 25 points)
    score += consistency * 0.25;
    
    return Math.min(100, Math.max(0, Math.round(score)));
  }

  analyzeSupplierPayments(payments) {
    if (!payments || payments.length === 0) return 40;

    const onTimePayments = payments.filter(p => p.status === 'on_time').length;
    const latePayments = payments.filter(p => p.status === 'late').length;
    const avgPaymentAmount = payments.reduce((sum, p) => sum + p.amount, 0) / payments.length;
    
    let score = 50;
    
    // Payment punctuality (max 40 points)
    const onTimeRatio = (onTimePayments / payments.length) * 100;
    if (onTimeRatio > 90) score += 30;
    else if (onTimeRatio > 75) score += 20;
    else if (onTimeRatio > 60) score += 10;
    
    // Payment consistency (max 30 points)
    if (avgPaymentAmount > 10000) score += 15;
    else if (avgPaymentAmount > 5000) score += 10;
    else if (avgPaymentAmount > 2000) score += 5;
    
    // Supplier diversity (max 30 points)
    const uniqueSuppliers = new Set(payments.map(p => p.supplier_id)).size;
    if (uniqueSuppliers > 20) score += 20;
    else if (uniqueSuppliers > 10) score += 15;
    else if (uniqueSuppliers > 5) score += 10;
    
    return Math.min(100, Math.max(0, Math.round(score)));
  }

  analyzeMarketplaceSales(sales) {
    if (!sales || sales.length === 0) return 40;

    const totalRevenue = sales.reduce((sum, s) => sum + s.revenue, 0);
    const avgMonthlyRevenue = totalRevenue / Math.max(1, sales.length);
    const growthRate = this.calculateGrowthScore(sales);
    const customerSatisfaction = this.calculateCustomerSatisfaction(sales);
    
    let score = 50;
    
    // Revenue volume (max 30 points)
    if (avgMonthlyRevenue > 500000) score += 25;
    else if (avgMonthlyRevenue > 200000) score += 20;
    else if (avgMonthlyRevenue > 50000) score += 15;
    else if (avgMonthlyRevenue > 10000) score += 10;
    
    // Growth rate (max 35 points)
    score += growthRate * 0.35;
    
    // Customer satisfaction (max 35 points)
    score += customerSatisfaction * 0.35;
    
    return Math.min(100, Math.max(0, Math.round(score)));
  }

  analyzeBusinessStability(businessAge) {
    let score = 50;
    
    // Business age stability (max 50 points)
    if (businessAge > 10) score += 40;
    else if (businessAge > 5) score += 30;
    else if (businessAge > 3) score += 20;
    else if (businessAge > 1) score += 10;
    
    return Math.min(100, Math.max(0, Math.round(score)));
  }

  // Helper methods
  calculateMonthlyAverage(transactions) {
    if (!transactions || transactions.length === 0) return 0;
    const total = transactions.reduce((sum, t) => sum + t.amount, 0);
    return total / Math.max(1, transactions.length);
  }

  calculateConsistencyScore(transactions) {
    if (!transactions || transactions.length < 2) return 50;
    
    const amounts = transactions.map(t => t.amount);
    const mean = amounts.reduce((sum, a) => sum + a, 0) / amounts.length;
    const variance = amounts.reduce((sum, a) => sum + Math.pow(a - mean, 2), 0) / amounts.length;
    const stdDev = Math.sqrt(variance);
    
    // Lower standard deviation = higher consistency
    const consistency = Math.max(0, 100 - (stdDev / mean) * 100);
    return Math.min(100, Math.round(consistency));
  }

  calculateGrowthScore(transactions) {
    if (!transactions || transactions.length < 2) return 50;
    
    const sorted = transactions.sort((a, b) => new Date(a.date) - new Date(b.date));
    const firstHalf = sorted.slice(0, Math.floor(sorted.length / 2));
    const secondHalf = sorted.slice(Math.floor(sorted.length / 2));
    
    const firstAvg = firstHalf.reduce((sum, t) => sum + t.amount, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((sum, t) => sum + t.amount, 0) / secondHalf.length;
    
    const growthRate = ((secondAvg - firstAvg) / firstAvg) * 100;
    return Math.max(-50, Math.min(50, Math.round(growthRate)));
  }

  calculateCustomerSatisfaction(sales) {
    if (!sales || sales.length === 0) return 50;
    
    const avgRating = sales.reduce((sum, s) => sum + (s.rating || 3), 0) / sales.length;
    return Math.max(0, Math.min(100, Math.round(avgRating * 20)));
  }

  getRiskCategory(score) {
    if (score >= 75) return 'LOW';
    if (score >= 60) return 'MODERATE';
    if (score >= 45) return 'MEDIUM';
    if (score >= 30) return 'HIGH';
    return 'VERY_HIGH';
  }

  generateCreditInsights(borrowerData, score) {
    const insights = [];
    
    if (borrowerData.gstTransactionHistory && borrowerData.gstTransactionHistory.length > 0) {
      const monthlyGST = this.calculateMonthlyAverage(borrowerData.gstTransactionHistory);
      if (monthlyGST > 50000) {
        insights.push("Strong GST compliance indicates stable business operations");
      }
    }
    
    if (borrowerData.upiTransactions && borrowerData.upiTransactions.length > 50) {
      insights.push("High frequency digital payments show good cash flow management");
    }
    
    if (score >= 70) {
      insights.push("Alternative data suggests good creditworthiness despite limited traditional history");
    } else if (score < 40) {
      insights.push("Limited alternative credit signals - recommend building digital payment history");
    }
    
    return insights;
  }

  // Generate mock data for demonstration
  generateMockAlternativeData() {
    return {
      gstTransactionHistory: Array.from({ length: 24 }, (_, i) => ({
        month: new Date(2024, i, 1).toISOString(),
        amount: Math.random() * 200000 + 50000,
        status: 'filed'
      })),
      upiTransactions: Array.from({ length: 150 }, (_, i) => ({
        date: new Date(2024, Math.floor(i / 5), (i % 30) + 1).toISOString(),
        amount: Math.random() * 10000 - 3000,
        type: Math.random() > 0.3 ? 'credit' : 'debit'
      })),
      supplierPaymentRecords: Array.from({ length: 20 }, (_, i) => ({
        supplier_id: `SUP${Math.floor(Math.random() * 50) + 1}`,
        amount: Math.random() * 50000 + 10000,
        status: Math.random() > 0.2 ? 'on_time' : 'late',
        date: new Date(2024, Math.floor(i / 2), (i % 15) + 1).toISOString()
      })),
      marketplaceSalesData: Array.from({ length: 12 }, (_, i) => ({
        month: new Date(2024, i, 1).toISOString(),
        revenue: Math.random() * 300000 + 100000,
        orders: Math.floor(Math.random() * 100) + 20,
        rating: Math.random() * 2 + 3
      })),
      businessAge: Math.floor(Math.random() * 8) + 2
    };
  }
}

export default FinancialInclusionService;
