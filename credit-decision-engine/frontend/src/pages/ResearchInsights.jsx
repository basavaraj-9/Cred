import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  getResearchInsights, 
  getSectorOutlook, 
  getNewsSentiment, 
  checkLitigation 
} from '../api/api';
import { 
  Search, 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  AlertTriangle,
  Globe,
  Newspaper,
  Scale,
  ArrowLeft,
  ArrowRight,
  RefreshCw
} from 'lucide-react';

const ResearchInsights = () => {
  const navigate = useNavigate();
  const [companyData, setCompanyData] = useState(null);
  const [researchData, setResearchData] = useState(null);
  const [sectorOutlook, setSectorOutlook] = useState(null);
  const [newsSentiment, setNewsSentiment] = useState(null);
  const [litigationData, setLitigationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadResearchData = async () => {
      try {
        // Load company data from localStorage
        const storedCompanyData = localStorage.getItem('companyData');
        
        if (!storedCompanyData) {
          navigate('/');
          return;
        }

        const companyData = JSON.parse(storedCompanyData);
        setCompanyData(companyData);

        // Perform research
        const researchResult = await getResearchInsights(
          companyData.company || 'Sample Company',
          'John Doe', // Sample promoter name
          'Manufacturing' // Sample sector
        );

        setResearchData(researchResult.research_data);

        // Get sector outlook
        if (researchResult.research_data.sector) {
          const outlookResult = await getSectorOutlook(researchResult.research_data.sector);
          setSectorOutlook(outlookResult.outlook);
        }

        // Get news sentiment
        const sentimentResult = await getNewsSentiment(companyData.company || 'Sample Company');
        setNewsSentiment(sentimentResult.sentiment_analysis);

        // Check litigation
        const litigationResult = await checkLitigation(companyData.company || 'Sample Company');
        setLitigationData(litigationResult.litigation_data);

      } catch (err) {
        setError(`Research failed: ${err.response?.data?.detail || err.message}`);
      } finally {
        setLoading(false);
      }
    };

    loadResearchData();
  }, [navigate]);

  const getSentimentIcon = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return <TrendingUp className="h-5 w-5 text-green-600" />;
      case 'negative':
        return <TrendingDown className="h-5 w-5 text-red-600" />;
      default:
        return <Minus className="h-5 w-5 text-yellow-600" />;
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'text-green-600 bg-green-100';
      case 'negative':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-yellow-600 bg-yellow-100';
    }
  };

  const getRiskColor = (risk) => {
    switch (risk?.toLowerCase()) {
      case 'high':
        return 'text-red-600 bg-red-100';
      case 'medium':
        return 'text-yellow-600 bg-yellow-100';
      default:
        return 'text-green-600 bg-green-100';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-12 w-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-lg text-gray-600">Conducting research...</p>
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
              Research Insights
            </h1>
            <p className="text-gray-600 mt-1">
              Market research and risk indicators for {companyData?.company || 'Company'}
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
              onClick={() => navigate('/cam-preview')}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <span>Generate CAM</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Key Insights */}
        {researchData && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            {/* Promoter Risk */}
            <div className={`p-6 rounded-lg ${getRiskColor(researchData.promoter_risk)}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Promoter Risk</p>
                  <p className="text-xl font-bold">{researchData.promoter_risk}</p>
                </div>
                <Scale className="h-8 w-8" />
              </div>
            </div>

            {/* Sector Outlook */}
            <div className={`p-6 rounded-lg ${getSentimentColor(researchData.sector_outlook)}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Sector Outlook</p>
                  <p className="text-xl font-bold">{researchData.sector_outlook}</p>
                </div>
                <Globe className="h-8 w-8" />
              </div>
            </div>

            {/* News Sentiment */}
            <div className={`p-6 rounded-lg ${getSentimentColor(researchData.news_sentiment)}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">News Sentiment</p>
                  <p className="text-xl font-bold">{researchData.news_sentiment}</p>
                </div>
                {getSentimentIcon(researchData.news_sentiment)}
              </div>
            </div>

            {/* Litigation Cases */}
            <div className="p-6 bg-white rounded-lg shadow-md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Litigation Cases</p>
                  <p className="text-xl font-bold text-gray-900">{researchData.litigation_cases}</p>
                </div>
                <AlertTriangle className={`h-8 w-8 ${researchData.litigation_cases > 0 ? 'text-red-600' : 'text-green-600'}`} />
              </div>
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Research Summary */}
          <div className="lg:col-span-2 space-y-6">
            {/* Research Summary */}
            {researchData && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Research Summary</h3>
                <p className="text-gray-700 leading-relaxed">
                  {researchData.research_summary || 'No research summary available.'}
                </p>
                
                {researchData.confidence_score && (
                  <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-blue-900">Confidence Score</span>
                      <span className="text-lg font-bold text-blue-900">
                        {researchData.confidence_score}%
                      </span>
                    </div>
                    <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${researchData.confidence_score}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* News Articles */}
            {researchData?.news_articles && researchData.news_articles.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Newspaper className="h-5 w-5 text-blue-500 mr-2" />
                  Recent News Articles
                </h3>
                <div className="space-y-4">
                  {researchData.news_articles.slice(0, 5).map((article, index) => (
                    <div key={index} className="border-l-4 border-blue-500 pl-4">
                      <h4 className="font-medium text-gray-900">{article.title}</h4>
                      <p className="text-sm text-gray-600 mt-1">{article.snippet}</p>
                      <p className="text-xs text-gray-500 mt-2">Source: {article.source}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Sector Analysis */}
            {sectorOutlook && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Sector Analysis</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2">Growth Rate</h4>
                    <p className="text-2xl font-bold text-green-600">{sectorOutlook.growth_rate}</p>
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2">Key Drivers</h4>
                    <ul className="space-y-1">
                      {sectorOutlook.key_drivers?.map((driver, index) => (
                        <li key={index} className="text-sm text-gray-700 flex items-start">
                          <span className="text-green-500 mr-2">•</span>
                          {driver}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="md:col-span-2">
                    <h4 className="font-medium text-gray-900 mb-2">Challenges</h4>
                    <ul className="space-y-1">
                      {sectorOutlook.challenges?.map((challenge, index) => (
                        <li key={index} className="text-sm text-gray-700 flex items-start">
                          <span className="text-red-500 mr-2">•</span>
                          {challenge}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Litigation Details */}
            {litigationData && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Scale className="h-5 w-5 text-red-500 mr-2" />
                  Litigation Details
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Total Cases</span>
                    <span className="font-medium">{litigationData.total_cases}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Active Cases</span>
                    <span className="font-medium">{litigationData.active_cases}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Settled Cases</span>
                    <span className="font-medium">{litigationData.settled_cases}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Risk Assessment</span>
                    <span className={`font-medium ${getRiskColor(litigationData.risk_assessment)}`}>
                      {litigationData.risk_assessment}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Risk Indicators */}
            {researchData?.risk_factors && researchData.risk_factors.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Risk Indicators</h3>
                <div className="space-y-2">
                  {researchData.risk_factors.slice(0, 6).map((factor, index) => (
                    <div key={index} className="flex items-start space-x-2">
                      <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-gray-700">{factor}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Positive Indicators */}
            {researchData?.positive_indicators && researchData.positive_indicators.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Positive Indicators</h3>
                <div className="space-y-2">
                  {researchData.positive_indicators.slice(0, 6).map((indicator, index) => (
                    <div key={index} className="flex items-start space-x-2">
                      <TrendingUp className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-gray-700">{indicator}</p>
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
                  onClick={() => navigate('/dashboard')}
                  className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                >
                  Back to Dashboard
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

export default ResearchInsights;
