import React from 'react';
import { Shield, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';

const RiskCard = ({ title, data, type = 'score' }) => {
  const getRiskColor = (score) => {
    if (score >= 75) return 'text-red-600 bg-red-100';
    if (score >= 60) return 'text-yellow-600 bg-yellow-100';
    if (score >= 40) return 'text-blue-600 bg-blue-100';
    return 'text-green-600 bg-green-100';
  };

  const getRiskIcon = (score) => {
    if (score >= 75) return <AlertTriangle className="h-5 w-5 text-red-600" />;
    if (score >= 60) return <TrendingDown className="h-5 w-5 text-yellow-600" />;
    if (score >= 40) return <Shield className="h-5 w-5 text-blue-600" />;
    return <TrendingUp className="h-5 w-5 text-green-600" />;
  };

  const getRiskLabel = (score) => {
    if (score >= 75) return 'Very High Risk';
    if (score >= 60) return 'High Risk';
    if (score >= 40) return 'Medium Risk';
    return 'Low Risk';
  };

  const formatScore = (value) => {
    return typeof value === 'number' ? value.toFixed(1) : value;
  };

  if (type === 'component') {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
        
        <div className="space-y-4">
          {data && Object.entries(data).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {getRiskIcon(value)}
                <div>
                  <p className="text-sm font-medium text-gray-900 capitalize">
                    {key.replace('_', ' ')}
                  </p>
                  <p className="text-xs text-gray-500">{getRiskLabel(value)}</p>
                </div>
              </div>
              
              <div className="text-right">
                <p className={`text-lg font-bold ${getRiskColor(value).split(' ')[0]}`}>
                  {formatScore(value)}
                </p>
                <p className="text-xs text-gray-500">/ 100</p>
              </div>
            </div>
          ))}
        </div>

        {/* Risk Gauge */}
        <div className="mt-6 pt-6 border-t">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Overall Risk Profile</span>
            <span className="text-sm font-medium text-gray-900">
              {data ? Object.values(data).reduce((a, b) => a + b, 0) / Object.keys(data).length : 0}/100
            </span>
          </div>
          
          <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
            <div className="h-full flex">
              <div className="bg-green-500" style={{ width: '40%' }}></div>
              <div className="bg-blue-500" style={{ width: '20%' }}></div>
              <div className="bg-yellow-500" style={{ width: '20%' }}></div>
              <div className="bg-red-500" style={{ width: '20%' }}></div>
            </div>
          </div>
          
          <div className="flex justify-between mt-1">
            <span className="text-xs text-gray-500">Low</span>
            <span className="text-xs text-gray-500">Medium</span>
            <span className="text-xs text-gray-500">High</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          {data ? getRiskIcon(data.score || data.risk_score || 0) : (
            <Shield className="h-8 w-8 text-gray-400" />
          )}
          <div>
            <p className="text-2xl font-bold text-gray-900">
              {data ? formatScore(data.score || data.risk_score || 0) : '0'}/100
            </p>
            <p className="text-sm text-gray-600">
              {data ? getRiskLabel(data.score || data.risk_score || 0) : 'No Risk Data'}
            </p>
          </div>
        </div>
        
        {data && (
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${getRiskColor(data.score || data.risk_score || 0)}`}>
            {data.category || data.risk_category || 'Unknown'}
          </div>
        )}
      </div>

      {/* Risk Breakdown */}
      {data && data.breakdown && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-900">Risk Breakdown</h4>
          {Object.entries(data.breakdown).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-gray-600 capitalize">{key.replace('_', ' ')}</span>
              <div className="flex items-center space-x-2">
                <div className="w-24 bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full ${
                      value >= 75 ? 'bg-red-500' :
                      value >= 60 ? 'bg-yellow-500' :
                      value >= 40 ? 'bg-blue-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${value}%` }}
                  ></div>
                </div>
                <span className="text-sm font-medium text-gray-900 w-10 text-right">
                  {formatScore(value)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Risk Factors */}
      {data && data.risk_factors && data.risk_factors.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <h4 className="text-sm font-medium text-gray-900 mb-2">Key Risk Factors</h4>
          <div className="space-y-1">
            {data.risk_factors.slice(0, 3).map((factor, index) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="w-1.5 h-1.5 bg-yellow-500 rounded-full mt-1.5 flex-shrink-0"></div>
                <p className="text-xs text-gray-600">{factor}</p>
              </div>
            ))}
            {data.risk_factors.length > 3 && (
              <p className="text-xs text-gray-500">
                +{data.risk_factors.length - 3} more factors
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default RiskCard;
