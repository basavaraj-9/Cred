import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { generateCAM, downloadCAM, getCAMPreview } from '../api/api';
import { 
  FileText, 
  Download, 
  Eye, 
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  FileDown
} from 'lucide-react';

const CAMPreview = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [researchData, setResearchData] = useState(null);
  const [camData, setCamData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        // Load data from localStorage
        const storedCompanyData = localStorage.getItem('companyData');
        const storedRiskAnalysis = localStorage.getItem('riskAnalysis');
        const storedRecommendation = localStorage.getItem('recommendation');
        const storedResearchData = localStorage.getItem('researchData');
        
        if (!storedCompanyData || !storedRiskAnalysis || !storedRecommendation) {
          navigate('/dashboard');
          return;
        }

        const companyData = JSON.parse(storedCompanyData);
        const riskAnalysis = JSON.parse(storedRiskAnalysis);
        const recommendation = JSON.parse(storedRecommendation);
        const researchData = storedResearchData ? JSON.parse(storedResearchData) : {};

        setCompanyData(companyData);
        setRiskAnalysis(riskAnalysis);
        setRecommendation(recommendation);
        setResearchData(researchData);

      } catch (err) {
        setError(`Failed to load data: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [navigate]);

  const generateCAMReport = async () => {
    if (!companyData || !riskAnalysis || !recommendation) {
      setError('Missing required data for CAM generation');
      return;
    }

    setGenerating(true);
    setError('');

    try {
      const camResult = await generateCAM(
        companyData,
        companyData, // Using companyData as financialData for demo
        riskAnalysis,
        researchData,
        recommendation
      );

      setCamData(camResult.cam_files);
      
      // Store CAM data in localStorage
      localStorage.setItem('camData', JSON.stringify(camResult.cam_files));

    } catch (err) {
      setError(`CAM generation failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const downloadFile = async (filename, fileType) => {
    try {
      await downloadCAM(filename, fileType);
    } catch (err) {
      setError(`Download failed: ${err.response?.data?.detail || err.message}`);
    }
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
          <p className="text-lg text-gray-600">Loading data...</p>
        </div>
      </div>
    );
  }

  if (error && !camData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-red-600 mx-auto mb-4" />
          <p className="text-lg text-red-600">{error}</p>
          <button
            onClick={() => navigate('/dashboard')}
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
              Credit Appraisal Memo (CAM)
            </h1>
            <p className="text-gray-600 mt-1">
              {companyData?.company || 'Company'} - Final Credit Assessment Report
            </p>
          </div>
          <div className="flex space-x-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Dashboard</span>
            </button>
            <button
              onClick={() => navigate('/research')}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <span>Research</span>
            </button>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="bg-white rounded-lg shadow-md p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Executive Summary</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-600 font-medium">Company</p>
              <p className="text-lg font-bold text-blue-900">{companyData?.company || 'N/A'}</p>
            </div>
            
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-sm text-green-600 font-medium">Risk Score</p>
              <p className="text-lg font-bold text-green-900">{riskAnalysis?.risk_score || 0}/100</p>
            </div>
            
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <p className="text-sm text-yellow-600 font-medium">Recommended Loan</p>
              <p className="text-lg font-bold text-yellow-900">
                {formatCurrency(recommendation?.loan_limit || 0)}
              </p>
            </div>
            
            <div className="text-center p-4 bg-purple-50 rounded-lg">
              <p className="text-sm text-purple-600 font-medium">Decision</p>
              <p className="text-lg font-bold text-purple-900">
                {recommendation?.decision || 'Pending'}
              </p>
            </div>
          </div>

          <div className="border-t pt-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Key Findings</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Financial Metrics</h4>
                <ul className="space-y-1 text-sm text-gray-600">
                  <li>• Revenue: {formatCurrency(companyData?.revenue || 0)}</li>
                  <li>• Existing Loans: {formatCurrency(companyData?.existing_loans || 0)}</li>
                  <li>• Assets: {formatCurrency(companyData?.assets || 0)}</li>
                  <li>• Profit: {formatCurrency(companyData?.profit || 0)}</li>
                </ul>
              </div>
              
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Risk Assessment</h4>
                <ul className="space-y-1 text-sm text-gray-600">
                  <li>• Risk Category: {riskAnalysis?.risk_category || 'Medium'}</li>
                  <li>• Interest Rate: {recommendation?.interest_rate || 0}% p.a.</li>
                  <li>• Tenure: {recommendation?.tenure_months || 0} months</li>
                  <li>• Conditions: {recommendation?.conditions?.length || 0} applied</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* CAM Generation Section */}
        {!camData ? (
          <div className="bg-white rounded-lg shadow-md p-8">
            <div className="text-center">
              <FileText className="h-16 w-16 text-gray-400 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Generate Credit Appraisal Memo</h2>
              <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
                Generate a comprehensive Credit Appraisal Memo (CAM) report with detailed analysis, 
                risk assessment, and recommendation in both Word and PDF formats.
              </p>
              
              <button
                onClick={generateCAMReport}
                disabled={generating}
                className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                {generating ? (
                  <div className="flex items-center space-x-2">
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    <span>Generating CAM...</span>
                  </div>
                ) : (
                  'Generate CAM Report'
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-md p-8">
            <div className="text-center mb-6">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-2">CAM Generated Successfully!</h2>
              <p className="text-gray-600">Your Credit Appraisal Memo is ready for download</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              {/* Word Document */}
              <div className="border-2 border-gray-200 rounded-lg p-6 hover:border-blue-300 transition-colors">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <FileText className="h-8 w-8 text-blue-600" />
                    <div>
                      <h3 className="font-semibold text-gray-900">Word Document</h3>
                      <p className="text-sm text-gray-600">Editable format</p>
                    </div>
                  </div>
                  <Eye className="h-5 w-5 text-gray-400" />
                </div>
                <button
                  onClick={() => downloadFile(camData.filename, 'word')}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center space-x-2"
                >
                  <Download className="h-4 w-4" />
                  <span>Download Word</span>
                </button>
              </div>

              {/* PDF Document */}
              <div className="border-2 border-gray-200 rounded-lg p-6 hover:border-red-300 transition-colors">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <FileDown className="h-8 w-8 text-red-600" />
                    <div>
                      <h3 className="font-semibold text-gray-900">PDF Document</h3>
                      <p className="text-sm text-gray-600">Final format</p>
                    </div>
                  </div>
                  <Eye className="h-5 w-5 text-gray-400" />
                </div>
                <button
                  onClick={() => downloadFile(camData.filename, 'pdf')}
                  className="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center justify-center space-x-2"
                >
                  <Download className="h-4 w-4" />
                  <span>Download PDF</span>
                </button>
              </div>
            </div>

            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">Report Details</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Filename:</span>
                  <p className="font-medium">{camData.filename}</p>
                </div>
                <div>
                  <span className="text-gray-600">Company:</span>
                  <p className="font-medium">{companyData?.company}</p>
                </div>
                <div>
                  <span className="text-gray-600">Risk Score:</span>
                  <p className="font-medium">{riskAnalysis?.risk_score}/100</p>
                </div>
                <div>
                  <span className="text-gray-600">Decision:</span>
                  <p className="font-medium">{recommendation?.decision}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* CAM Structure Preview */}
        <div className="mt-8 bg-white rounded-lg shadow-md p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">CAM Structure</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-900 mb-3">Main Sections</h3>
              <ol className="space-y-2">
                <li className="flex items-start space-x-2">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">1</span>
                  <span className="text-sm text-gray-700">Borrower Overview</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">2</span>
                  <span className="text-sm text-gray-700">Industry Analysis</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">3</span>
                  <span className="text-sm text-gray-700">Financial Analysis</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">4</span>
                  <span className="text-sm text-gray-700">Risk Assessment</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">5</span>
                  <span className="text-sm text-gray-700">Five Cs of Credit</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">6</span>
                  <span className="text-sm text-gray-700">Recommendation</span>
                </li>
              </ol>
            </div>
            
            <div>
              <h3 className="font-semibold text-gray-900 mb-3">Five Cs Analysis</h3>
              <ul className="space-y-2">
                <li className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-gray-700"><strong>Character:</strong> Management quality & reputation</span>
                </li>
                <li className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-gray-700"><strong>Capacity:</strong> Repayment ability</span>
                </li>
                <li className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-gray-700"><strong>Capital:</strong> Financial strength</span>
                </li>
                <li className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-gray-700"><strong>Collateral:</strong> Security assets</span>
                </li>
                <li className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-gray-700"><strong>Conditions:</strong> Economic & market factors</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CAMPreview;
