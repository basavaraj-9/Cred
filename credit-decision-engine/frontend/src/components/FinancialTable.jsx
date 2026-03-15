import React from 'react';
import { TrendingUp, TrendingDown, DollarSign, Building, CreditCard, PiggyBank } from 'lucide-react';

const FinancialTable = ({ title, data, formatCurrency }) => {
  const financialMetrics = [
    {
      label: 'Revenue',
      value: data?.revenue || 0,
      icon: <TrendingUp className="h-5 w-5 text-green-600" />,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      label: 'Total Assets',
      value: data?.assets || 0,
      icon: <Building className="h-5 w-5 text-blue-600" />,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      label: 'Total Liabilities',
      value: data?.liabilities || 0,
      icon: <CreditCard className="h-5 w-5 text-red-600" />,
      color: 'text-red-600',
      bgColor: 'bg-red-50'
    },
    {
      label: 'Existing Loans',
      value: data?.existing_loans || 0,
      icon: <PiggyBank className="h-5 w-5 text-yellow-600" />,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50'
    },
    {
      label: 'Net Profit',
      value: data?.profit || 0,
      icon: <DollarSign className="h-5 w-5 text-purple-600" />,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50'
    },
    {
      label: 'GST Revenue',
      value: data?.gst_revenue || 0,
      icon: <TrendingUp className="h-5 w-5 text-indigo-600" />,
      color: 'text-indigo-600',
      bgColor: 'bg-indigo-50'
    }
  ];

  const calculateRatios = () => {
    const revenue = data?.revenue || 0;
    const assets = data?.assets || 0;
    const liabilities = data?.liabilities || 0;
    const profit = data?.profit || 0;
    const existingLoans = data?.existing_loans || 0;

    const ratios = [];

    if (revenue > 0) {
      ratios.push({
        label: 'Debt to Revenue',
        value: (existingLoans / revenue).toFixed(2),
        unit: 'x',
        status: existingLoans / revenue > 1.5 ? 'high' : existingLoans / revenue > 0.7 ? 'medium' : 'low'
      });

      ratios.push({
        label: 'Profit Margin',
        value: ((profit / revenue) * 100).toFixed(1),
        unit: '%',
        status: profit / revenue < 0 ? 'high' : profit / revenue < 0.05 ? 'medium' : 'low'
      });
    }

    if (assets > 0) {
      ratios.push({
        label: 'Debt to Assets',
        value: (liabilities / assets).toFixed(2),
        unit: 'x',
        status: liabilities / assets > 0.8 ? 'high' : liabilities / assets > 0.5 ? 'medium' : 'low'
      });
    }

    if (revenue > 0 && assets > 0) {
      ratios.push({
        label: 'Asset Turnover',
        value: (revenue / assets).toFixed(2),
        unit: 'x',
        status: 'low' // Generally positive metric
      });
    }

    return ratios;
  };

  const getRatioColor = (status) => {
    switch (status) {
      case 'high':
        return 'text-red-600 bg-red-50';
      case 'medium':
        return 'text-yellow-600 bg-yellow-50';
      default:
        return 'text-green-600 bg-green-50';
    }
  };

  const ratios = calculateRatios();

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-6">{title}</h3>
      
      {/* Financial Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {financialMetrics.map((metric, index) => (
          <div key={index} className={`p-4 rounded-lg ${metric.bgColor} border border-gray-200`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">{metric.label}</span>
              {metric.icon}
            </div>
            <p className={`text-xl font-bold ${metric.color}`}>
              {formatCurrency ? formatCurrency(metric.value) : `₹${metric.value.toLocaleString()}`}
            </p>
          </div>
        ))}
      </div>

      {/* Financial Ratios */}
      {ratios.length > 0 && (
        <div className="border-t pt-6">
          <h4 className="text-md font-semibold text-gray-900 mb-4">Key Financial Ratios</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ratio
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Value
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Benchmark
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {ratios.map((ratio, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {ratio.label}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {ratio.value} {ratio.unit}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getRatioColor(ratio.status)}`}>
                        {ratio.status.charAt(0).toUpperCase() + ratio.status.slice(1)} Risk
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {getBenchmark(ratio.label)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Document Summary */}
      {data?.documents_summary && data.documents_summary.length > 0 && (
        <div className="border-t pt-6 mt-6">
          <h4 className="text-md font-semibold text-gray-900 mb-4">Document Summary</h4>
          <div className="space-y-2">
            {data.documents_summary.map((doc, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                    <p className="text-xs text-gray-500 capitalize">{doc.document_type.replace('_', ' ')}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-900">
                    {formatCurrency ? formatCurrency(doc.revenue) : `₹${doc.revenue.toLocaleString()}`}
                  </p>
                  <p className="text-xs text-gray-500">Revenue</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Additional Insights */}
      <div className="mt-6 p-4 bg-blue-50 rounded-lg">
        <h4 className="text-sm font-semibold text-blue-900 mb-2">Quick Insights</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-blue-800">
          <div>
            <span className="font-medium">Revenue Growth:</span> 
            <span className="ml-1">
              {data?.revenue > 100000000 ? 'Strong' : data?.revenue > 10000000 ? 'Moderate' : 'Limited'}
            </span>
          </div>
          <div>
            <span className="font-medium">Debt Burden:</span>
            <span className="ml-1">
              {data?.existing_loans > data?.revenue ? 'High' : 
               data?.existing_loans > data?.revenue * 0.5 ? 'Medium' : 'Low'}
            </span>
          </div>
          <div>
            <span className="font-medium">Profitability:</span>
            <span className="ml-1">
              {data?.profit > 0 ? 'Positive' : 'Negative'}
            </span>
          </div>
          <div>
            <span className="font-medium">Asset Base:</span>
            <span className="ml-1">
              {data?.assets > 50000000 ? 'Strong' : data?.assets > 10000000 ? 'Moderate' : 'Limited'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

const getBenchmark = (ratioLabel) => {
  const benchmarks = {
    'Debt to Revenue': '< 1.0x',
    'Profit Margin': '> 10%',
    'Debt to Assets': '< 0.7x',
    'Asset Turnover': '> 1.0x'
  };
  return benchmarks[ratioLabel] || 'N/A';
};

export default FinancialTable;
