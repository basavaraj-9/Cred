import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Shield, 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  DollarSign, 
  FileText, 
  ArrowRight,
  CheckCircle,
  Eye,
  Download,
  RefreshCw,
  Activity,
  ArrowLeft
} from 'lucide-react';
import { 
  getRiskScore, 
  getRecommendation, 
  getConsistencyAnalysis 
} from '../api/api';
import RiskCard from '../components/RiskCard';
import FinancialTable from '../components/FinancialTable';
import RiskGauge from '../components/RiskGauge';
import AnimatedCard from '../components/AnimatedCard';
import GradientButton from '../components/GradientButton';
import LoadingSpinner from '../components/LoadingSpinner';

const Dashboard = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [riskFactorsList, setRiskFactorsList] = useState({});

  useEffect(() => {
    const loadData = async () => {
      try {
        // Load company data from localStorage
        const storedCompanyData = localStorage.getItem('companyData');
        const storedDocuments = localStorage.getItem('documents');
        
        if (!storedCompanyData) {
          navigate('/');
          return;
        }

        const companyData = JSON.parse(storedCompanyData);
        const documents = JSON.parse(storedDocuments);
        setCompanyData(companyData);

        // Get risk factors
        const riskFactors = await getRiskFactors();
        setRiskFactorsList(riskFactors.risk_factors);

        // Perform consistency analysis
        const gstData = companyData;
        const bankData = companyData; // Using same data for demo
        
        const consistencyResult = await analyzeConsistency(gstData, bankData);

        // Calculate risk score
        const riskResult = await calculateRiskScore(
          companyData,
          gstData,
          bankData,
          {}, // Research data will be added later
          null // Officer input will be added later
        );

        setRiskAnalysis(riskResult.risk_analysis);

        // Generate recommendation
        const recommendationResult = await generateRecommendation(
          riskResult.risk_analysis,
          companyData
        );

        setRecommendation(recommendationResult.recommendation);

      } catch (err) {
        setError(`Analysis failed: ${err.response?.data?.detail || err.message}`);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [navigate]);

  const getRiskColor = (score) => {
    if (score >= 75) return 'text-red-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getRiskBgColor = (score) => {
    if (score >= 75) return 'bg-red-100';
    if (score >= 60) return 'bg-yellow-100';
    return 'bg-green-100';
  };

  const formatCurrency = (amount) => {
    if (amount >= 10000000) {
      return `₹${(amount / 10000000).toFixed(2)} Cr`;
    } else if (amount >= 100000) {
      return `₹${(amount / 100000).toFixed(2)} L`;
    } else {
      return `₹${amount.toLocaleString()}`;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-12 w-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-lg text-gray-600">Analyzing financial data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-red-600 mx-auto mb-4" />
          <p className="text-lg text-red-600">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Credit Analysis Dashboard
            </h1>
            <p className="text-gray-600 mt-1">
              {companyData?.company || 'Company'} - Risk Assessment & Recommendation
            </p>
          </div>
          <div className="flex space-x-4">
            <button
              onClick={() => navigate('/')}
              className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Upload New</span>
            </button>
            <button
              onClick={() => navigate('/research')}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <span>Research</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Key Metrics */}
        {riskAnalysis && recommendation && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            {/* Risk Score */}
            <div className={`p-6 rounded-lg ${getRiskBgColor(riskAnalysis.risk_score)}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Risk Score</p>
                  <p className={`text-3xl font-bold ${getRiskColor(riskAnalysis.risk_score)}`}>
                    {riskAnalysis.risk_score}/100
                  </p>
                  <p className="text-sm text-gray-600 mt-1">{riskAnalysis.risk_category}</p>
                </div>
                <Shield className={`h-8 w-8 ${getRiskColor(riskAnalysis.risk_score)}`} />
              </div>
            </div>

            {/* Loan Amount */}
            <div className="p-6 bg-white rounded-lg shadow-md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Recommended Loan</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {formatCurrency(recommendation.loan_limit)}
                  </p>
                </div>
                <DollarSign className="h-8 w-8 text-green-600" />
              </div>
            </div>

            {/* Interest Rate */}
            <div className="p-6 bg-white rounded-lg shadow-md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Interest Rate</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {recommendation.interest_rate}%
                  </p>
                  <p className="text-sm text-gray-600 mt-1">per annum</p>
                </div>
                <TrendingUp className="h-8 w-8 text-blue-600" />
              </div>
            </div>

            {/* Decision */}
            <div className={`p-6 rounded-lg ${
              recommendation.decision === 'Approve' ? 'bg-green-100' :
              recommendation.decision === 'Conditional Approval' ? 'bg-yellow-100' : 'bg-red-100'
            }`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Decision</p>
                  <p className={`text-xl font-bold ${
                    recommendation.decision === 'Approve' ? 'text-green-700' :
                    recommendation.decision === 'Conditional Approval' ? 'text-yellow-700' : 'text-red-700'
                  }`}>
                    {recommendation.decision}
                  </p>
                </div>
                <Activity className={`h-8 w-8 ${
                  recommendation.decision === 'Approve' ? 'text-green-600' :
                  recommendation.decision === 'Conditional Approval' ? 'text-yellow-600' : 'text-red-600'
                }`} />
              </div>
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Financial Analysis */}
          <div className="lg:col-span-2 space-y-6">
            {/* Financial Metrics */}
            <FinancialTable 
              title="Financial Metrics"
              data={companyData}
              formatCurrency={formatCurrency}
            />

            {/* Risk Breakdown */}
            {riskAnalysis && (
              <RiskCard
                title="Risk Component Analysis"
                data={riskAnalysis.component_scores}
                type="component"
              />
            )}

            {/* Risk Factors */}
            {riskAnalysis?.risk_factors && riskAnalysis.risk_factors.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <AlertTriangle className="h-5 w-5 text-yellow-500 mr-2" />
                  Key Risk Factors
                </h3>
                <div className="space-y-2">
                  {riskAnalysis.risk_factors.map((factor, index) => (
                    <div key={index} className="flex items-start space-x-2">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full mt-2 flex-shrink-0"></div>
                      <p className="text-sm text-gray-700">{factor}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Recommendation Details */}
            {recommendation && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Loan Details</h3>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-gray-600">Tenure</p>
                    <p className="font-semibold">{recommendation.tenure_months} months</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Processing Fee</p>
                    <p className="font-semibold">{recommendation.risk_adjusted_pricing?.processing_fee || 1.0}%</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Prepayment Penalty</p>
                    <p className="font-semibold">{recommendation.risk_adjusted_pricing?.prepayment_penalty || 2.0}%</p>
                  </div>
                </div>
              </div>
            )}

            {/* Conditions */}
            {recommendation?.conditions && recommendation.conditions.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Conditions</h3>
                <div className="space-y-2">
                  {recommendation.conditions.slice(0, 4).map((condition, index) => (
                    <div key={index} className="flex items-start space-x-2">
                      <FileText className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-gray-700">{condition}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Actions</h3>
              <div className="space-y-3">
                <button
                  onClick={() => navigate('/research')}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  View Research Insights
                </button>
                <button
                  onClick={() => navigate('/cam-preview')}
                  className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  Generate CAM Report
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
