import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FinancialInclusionService from '../services/FinancialInclusionService';
import ExplainableAIService from '../services/ExplainableAIService';
import FraudDetectionService from '../services/FraudDetectionService';
import SmartLoanRecommendationService from '../services/SmartLoanRecommendationService';

const EnhancedCreditDashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [enhancedAnalysis, setEnhancedAnalysis] = useState({});

  useEffect(() => {
    const data = localStorage.getItem('companyData');
    if (data) {
      const parsedData = JSON.parse(data);
      setCompanyData(parsedData);
      
      const company = parsedData.is_multi_company ? parsedData.companies[0] : parsedData;
      setSelectedCompany(company);
      
      // Generate enhanced analysis
      generateEnhancedAnalysis(company);
    } else {
      navigate('/');
    }
  }, [navigate]);

  const generateEnhancedAnalysis = (company) => {
    // Initialize services
    const financialInclusion = new FinancialInclusionService();
    const explainableAI = new ExplainableAIService();
    const fraudDetection = new FraudDetectionService();
    const smartLoanRecommendation = new SmartLoanRecommendationService();

    // Generate mock data for demonstration
    const alternativeData = financialInclusion.generateMockAlternativeData();
    const explainableData = explainableAI.generateMockExplainableData();
    const fraudData = fraudDetection.generateMockFraudData();
    const loanRecData = smartLoanRecommendation.generateMockLoanRecommendationData();

    // Calculate analyses
    const alternativeCreditScore = financialInclusion.calculateAlternativeCreditScore(alternativeData);
    const explainableDecision = explainableAI.generateExplainableDecision(
      explainableData.loanApplication,
      explainableData.financialData,
      company?.ai_analysis?.risk_analysis?.risk_score || 50
    );
    const fraudAnalysis = fraudDetection.analyzeFraudRisk(
      fraudData.applicationData,
      fraudData.transactionHistory,
      fraudData.businessNetwork
    );
    const loanRecommendation = smartLoanRecommendation.calculateOptimalLoan(
      loanRecData.financialData,
      loanRecData.requestedAmount,
      loanRecData.loanPurpose
    );

    setEnhancedAnalysis({
      alternativeCreditScore,
      explainableDecision,
      fraudAnalysis,
      loanRecommendation,
      alternativeData,
      explainableData,
      fraudData,
      loanData: loanRecData
    });
  };

  const getRiskColor = (score) => {
    if (score <= 40) return { bg: '#dcfce7', text: '#166534', border: '#22c55e', icon: '🟢' };
    if (score <= 70) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b', icon: '🟡' };
    return { bg: '#fef2f2', text: '#991b1b', border: '#ef4444', icon: '🔴' };
  };

  const getFraudColor = (level) => {
    const colors = {
      'VERY_LOW': { bg: '#dcfce7', text: '#166534', border: '#22c55e' },
      'LOW': { bg: '#f0f9ff', text: '#1e40af', border: '#3b82f6' },
      'MEDIUM': { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' },
      'HIGH': { bg: '#fee2e2', text: '#ea580c', border: '#f97316' },
      'CRITICAL': { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' }
    };
    return colors[level] || colors['MEDIUM'];
  };

  const renderOverviewTab = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
      
      {/* Financial Inclusion Score */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '28px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          🌍 Financial Inclusion Score
        </h3>
        <div style={{
          background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
          borderRadius: '16px',
          padding: '24px',
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <div style={{ fontSize: '48px', fontWeight: 'bold', color: 'white' }}>
            {enhancedAnalysis.alternativeCreditScore?.alternativeCreditScore || 72}
          </div>
          <div style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', marginTop: '8px' }}>
            Alternative Credit Score
          </div>
        </div>
        <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Risk Category:</span>
            <span style={{ fontWeight: '600', color: '#059669' }}>
              {enhancedAnalysis.alternativeCreditScore?.riskCategory || 'MODERATE'}
            </span>
          </div>
          <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', marginTop: '12px' }}>
            <div style={{ fontWeight: '600', marginBottom: '8px', color: '#1e293b' }}>Key Insights:</div>
            {enhancedAnalysis.alternativeCreditScore?.insights?.map((insight, index) => (
              <div key={index} style={{ marginBottom: '4px', paddingLeft: '8px' }}>
                • {insight}
              </div>
            )) || []}
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '16px' }}>
          {Object.entries(enhancedAnalysis.alternativeCreditScore?.components || {}).map(([key, value]) => (
            <div key={key} style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                {key.replace(/_/g, ' ').toUpperCase()}
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b' }}>
                {value}/100
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Fraud Detection */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '28px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          🛡️ Fraud Detection Analysis
        </h3>
        <div style={{
          background: getFraudColor(enhancedAnalysis.fraudAnalysis?.riskLevel).bg,
          borderRadius: '16px',
          padding: '24px',
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <div style={{ fontSize: '36px', fontWeight: 'bold', color: getFraudColor(enhancedAnalysis.fraudAnalysis?.riskLevel).text }}>
            {enhancedAnalysis.fraudAnalysis?.fraudRiskScore?.toFixed(2) || '0.35'}
          </div>
          <div style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', marginTop: '8px' }}>
            Fraud Risk Score
          </div>
        </div>
        <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Risk Level:</span>
            <span style={{ fontWeight: '600', color: getFraudColor(enhancedAnalysis.fraudAnalysis?.riskLevel).text }}>
              {enhancedAnalysis.fraudAnalysis?.riskLevel || 'LOW'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Alert Level:</span>
            <span style={{ fontWeight: '600', color: '#dc2626' }}>
              {enhancedAnalysis.fraudAnalysis?.alertLevel || 'LOW_PRIORITY_ALERT'}
            </span>
          </div>
        </div>
        {enhancedAnalysis.fraudAnalysis?.recommendations?.length > 0 && (
          <div style={{ background: '#fef2f2', padding: '12px', borderRadius: '8px', marginTop: '12px' }}>
            <div style={{ fontWeight: '600', marginBottom: '8px', color: '#991b1b' }}>Recommendations:</div>
            {enhancedAnalysis.fraudAnalysis.recommendations.map((rec, index) => (
              <div key={index} style={{ marginBottom: '8px', paddingLeft: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ 
                    background: rec.priority === 'HIGH' ? '#ef4444' : '#f59e0b', 
                    color: 'white', 
                    padding: '2px 8px', 
                    borderRadius: '12px', 
                    fontSize: '12px' 
                  }}>
                    {rec.priority}
                  </span>
                  <span style={{ fontWeight: '600' }}>{rec.action}</span>
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280', paddingLeft: '16px' }}>
                  {rec.description}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const renderExplainableAITab = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
      
      {/* Decision Explanation */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '28px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          🤖 Explainable AI Decision
        </h3>
        <div style={{
          background: enhancedAnalysis.explainableDecision?.decision?.status === 'APPROVED' ? '#dcfce7' : '#fef2f2',
          borderRadius: '16px',
          padding: '24px',
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <div style={{ fontSize: '32px', fontWeight: 'bold', color: enhancedAnalysis.explainableDecision?.decision?.status === 'APPROVED' ? '#166534' : '#991b1b' }}>
            {enhancedAnalysis.explainableDecision?.decision?.status || 'REVIEW_REQUIRED'}
          </div>
          <div style={{ fontSize: '16px', color: 'rgba(0,0,0,0.7)', marginTop: '8px' }}>
            Loan Decision
          </div>
          <div style={{ fontSize: '14px', color: 'rgba(0,0,0,0.6)', marginTop: '4px' }}>
            Confidence: {enhancedAnalysis.explainableDecision?.decision?.confidence || 75}%
          </div>
        </div>
        
        {/* Primary Reasons */}
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
            Primary Reasons for Decision:
          </h4>
          {enhancedAnalysis.explainableDecision?.reasons?.primaryReasons?.map((reason, index) => (
            <div key={index} style={{
              background: reason.impact === 'HIGH' ? '#fef2f2' : '#f8fafc',
              border: `1px solid ${reason.impact === 'HIGH' ? '#ef4444' : '#e5e7eb'}`,
              borderRadius: '8px',
              padding: '12px',
              marginBottom: '8px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ fontWeight: '600' }}>{reason.factor}</span>
                <span style={{ 
                  background: reason.impact === 'HIGH' ? '#ef4444' : '#f59e0b',
                  color: 'white',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontSize: '12px'
                }}>
                  {reason.impact}
                </span>
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280' }}>
                {reason.description}
              </div>
            </div>
          )) || []}
        </div>

        {/* Contributing Factors */}
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
            Contributing Factors:
          </h4>
          {enhancedAnalysis.explainableDecision?.reasons?.contributingFactors?.map((factor, index) => (
            <div key={index} style={{
              background: '#f8fafc',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '12px',
              marginBottom: '8px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: '600' }}>{factor.factor}</span>
                <span style={{ 
                  background: factor.impact === 'MEDIUM' ? '#f59e0b' : '#64748b',
                  color: 'white',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontSize: '12px'
                }}>
                  {factor.impact}
                </span>
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                {factor.description}
              </div>
            </div>
          )) || []}
        </div>

        {/* Risk Breakdown */}
        <div>
          <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
            Risk Assessment Breakdown:
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {Object.entries(enhancedAnalysis.explainableDecision?.reasons?.riskBreakdown || {}).map(([risk, score]) => (
              <div key={risk} style={{
                background: '#f8fafc',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '12px'
              }}>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                  {risk.replace(/_/g, ' ').toUpperCase()}
                </div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b' }}>
                  {score}/100
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Improvement Suggestions */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '28px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          💡 Improvement Suggestions
        </h3>
        {enhancedAnalysis.explainableDecision?.improvementSuggestions?.map((suggestion, index) => (
          <div key={index} style={{
            background: suggestion.priority === 'HIGH' ? '#fef2f2' : '#f8fafc',
            border: `1px solid ${suggestion.priority === 'HIGH' ? '#ef4444' : '#e5e7eb'}`,
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '12px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '4px' }}>
                  {suggestion.area}
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                  {suggestion.suggestion}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ 
                  background: suggestion.priority === 'HIGH' ? '#ef4444' : '#f59e0b',
                  color: 'white',
                  padding: '4px 8px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  marginBottom: '4px'
                }}>
                  {suggestion.priority}
                </div>
                <div style={{ fontSize: '11px', color: '#059669', fontWeight: '600' }}>
                  {suggestion.potentialImpact}
                </div>
              </div>
            </div>
          </div>
        )) || []}

        {/* Alternative Options */}
        {enhancedAnalysis.explainableDecision?.alternativeOptions?.length > 0 && (
          <div style={{ marginTop: '20px' }}>
            <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
              Alternative Options:
            </h4>
            {enhancedAnalysis.explainableDecision.alternativeOptions.map((option, index) => (
              <div key={index} style={{
                background: '#f0f9ff',
                border: '1px solid #3b82f6',
                borderRadius: '8px',
                padding: '12px',
                marginBottom: '8px'
              }}>
                <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e40af', marginBottom: '4px' }}>
                  {option.option}
                </div>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                  {option.description}
                </div>
                <div style={{ fontSize: '12px', color: '#059669' }}>
                  Est. Approval: {option.estimatedApproval}%
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const renderLoanRecommendationTab = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
      
      {/* Smart Recommendation */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '28px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          🎯 Smart Loan Recommendation
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
          <div style={{
            background: 'linear-gradient(135deg, #10b981, #059669)',
            borderRadius: '16px',
            padding: '20px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.9)', marginBottom: '8px' }}>
              Requested Amount
            </div>
            <div style={{ fontSize: '48px', fontWeight: 'bold', color: 'white' }}>
              ₹{((enhancedAnalysis.loanRecommendation?.requestedAmount || 0) / 100000).toFixed(1)}L
            </div>
            <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.9)', marginTop: '8px' }}>
              Requested Amount
            </div>
          </div>
          <div style={{
            background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
            borderRadius: '16px',
            padding: '20px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.9)', marginBottom: '8px' }}>
              Recommended Amount
            </div>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: 'white' }}>
              ₹{((enhancedAnalysis.loanRecommendation?.recommendation?.primary || 0) / 100000).toFixed(1)}L
            </div>
            <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.8)', marginTop: '4px' }}>
              Confidence: {enhancedAnalysis.loanRecommendation?.recommendation?.confidence || 75}%
            </div>
          </div>
        </div>

        <div style={{
          background: '#f8fafc',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '20px'
        }}>
          <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
            Recommendation Reasoning:
          </h4>
          <div style={{ fontSize: '14px', color: '#64748b', lineHeight: '1.6' }}>
            {enhancedAnalysis.loanRecommendation?.recommendation?.reasoning || 'Based on comprehensive financial analysis'}
          </div>
        </div>

        {/* Affordability Metrics */}
        <div>
          <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
            Affordability Analysis:
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Monthly EMI</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b' }}>
                ₹{((enhancedAnalysis.loanRecommendation?.affordabilityMetrics?.monthlyEMI || 0) / 1000).toFixed(0)}K
              </div>
            </div>
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>DTI Ratio</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: enhancedAnalysis.loanRecommendation?.affordabilityMetrics?.dtiRatio > 25 ? '#dc2626' : '#059669' }}>
                {enhancedAnalysis.loanRecommendation?.affordabilityMetrics?.dtiRatio?.toFixed(1) || 0}%
              </div>
            </div>
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Cash Flow Buffer</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: enhancedAnalysis.loanRecommendation?.affordabilityMetrics?.cashFlowBuffer > 1.2 ? '#059669' : '#f59e0b' }}>
                {enhancedAnalysis.loanRecommendation?.affordabilityMetrics?.cashFlowBuffer?.toFixed(2) || 0}x
              </div>
            </div>
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Affordability Score</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b' }}>
                {enhancedAnalysis.loanRecommendation?.affordabilityMetrics?.affordabilityScore || 75}/100
              </div>
            </div>
          </div>
        </div>

        {/* Warnings */}
        {enhancedAnalysis.loanRecommendation?.warnings?.length > 0 && (
          <div style={{ marginTop: '20px' }}>
            <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '12px' }}>
              Important Warnings:
            </h4>
            {enhancedAnalysis.loanRecommendation.warnings.map((warning, index) => (
              <div key={index} style={{
                background: warning.severity === 'HIGH' ? '#fef2f2' : '#fef3c7',
                border: `1px solid ${warning.severity === 'HIGH' ? '#ef4444' : '#f59e0b'}`,
                borderRadius: '8px',
                padding: '12px',
                marginBottom: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ 
                    background: warning.severity === 'HIGH' ? '#ef4444' : '#f59e0b',
                    color: 'white',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontSize: '12px'
                  }}>
                    {warning.severity}
                  </span>
                  <span style={{ fontWeight: '600' }}>{warning.type.replace(/_/g, ' ')}</span>
                </div>
                <div style={{ fontSize: '13px', color: '#6b7280' }}>
                  {warning.message}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Alternative Options */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '28px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          🔄 Alternative Financing Options
        </h3>
        {enhancedAnalysis.loanRecommendation?.alternativeOptions?.map((option, index) => (
          <div key={index} style={{
            background: '#f8fafc',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            padding: '16px',
            marginBottom: '12px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <div style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '4px' }}>
                  {option.type.replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '4px' }}>
                  {option.description}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '4px' }}>
                  ₹{((option.amount || 0) / 100000).toFixed(1)}L
                </div>
                <div style={{ fontSize: '12px', color: '#059669' }}>
                  {option.approvalProbability}% approval
                </div>
                {option.collateralRequired && (
                  <div style={{ fontSize: '12px', color: '#f59e0b', marginTop: '4px' }}>
                    Collateral Required
                  </div>
                )}
              </div>
            </div>
          </div>
        )) || []}
      </div>
    </div>
  );

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
          <p>Loading Enhanced Credit Analysis...</p>
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
                Enhanced AI Credit Decisioning Engine
              </h1>
              <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', margin: '4px 0 0 0' }}>
                Advanced Financial Inclusion • Explainable AI • Fraud Detection • Smart Recommendations
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
              📊 Dashboard
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
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: 'white', marginBottom: '16px' }}>
              Select Company for Enhanced Analysis:
            </h3>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {companyData.companies.map((company, index) => (
                <button
                  key={company.unique_hash || index}
                  onClick={() => {
                    setSelectedCompany(company);
                    generateEnhancedAnalysis(company);
                  }}
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

        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid rgba(255,255,255,0.2)' }}>
          {[
            { id: 'overview', label: '🌍 Overview', icon: '🌍' },
            { id: 'explainable', label: '🤖 Explainable AI', icon: '🤖' },
            { id: 'recommendation', label: '🎯 Smart Recommendations', icon: '🎯' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: activeTab === tab.id 
                  ? 'rgba(255, 255, 255, 0.2)' 
                  : 'transparent',
                color: 'white',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid white' : '2px solid transparent',
                borderRadius: '8px 8px 0 0',
                padding: '12px 20px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '600',
                transition: 'all 0.3s ease'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === 'overview' && renderOverviewTab()}
          {activeTab === 'explainable' && renderExplainableAITab()}
          {activeTab === 'recommendation' && renderLoanRecommendationTab()}
        </div>
      </div>
    </div>
  );
};

export default EnhancedCreditDashboard;
