import React from 'react';
import { motion } from 'framer-motion';

const RiskGauge = ({ score, size = 200, showLabel = true, animated = true }) => {
  const getRiskColor = (score) => {
    if (score >= 75) return '#ef4444'; // red-500
    if (score >= 60) return '#f59e0b'; // amber-500
    if (score >= 40) return '#3b82f6'; // blue-500
    return '#10b981'; // green-500
  };

  const getRiskLabel = (score) => {
    if (score >= 75) return 'Very High Risk';
    if (score >= 60) return 'High Risk';
    if (score >= 40) return 'Medium Risk';
    if (score >= 25) return 'Low Risk';
    return 'Very Low Risk';
  };

  const getRiskCategory = (score) => {
    if (score >= 75) return 'danger';
    if (score >= 60) return 'warning';
    if (score >= 40) return 'info';
    return 'success';
  };

  const calculateRotation = (score) => {
    // Convert score (0-100) to rotation angle (0-180 degrees)
    return (score / 100) * 180 - 90;
  };

  const riskColor = getRiskColor(score);
  const rotation = calculateRotation(score);
  const riskCategory = getRiskCategory(score);

  const circumference = 2 * Math.PI * 45; // radius = 45
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Background circle */}
        <svg
          width={size}
          height={size}
          className="transform -rotate-90"
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={size / 2 - 10}
            stroke="#e5e7eb"
            strokeWidth="10"
            fill="none"
          />
          
          {/* Progress arc */}
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={size / 2 - 10}
            stroke={riskColor}
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: strokeDashoffset }}
            transition={{ duration: animated ? 1.5 : 0, ease: "easeInOut" }}
          />
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            className="text-3xl font-bold"
            style={{ color: riskColor }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.5 }}
          >
            {score}
          </motion.span>
          <span className="text-sm text-gray-500">/100</span>
        </div>

        {/* Decorative elements */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-2 left-1/2 transform -translate-x-1/2 text-xs text-gray-400">100</div>
          <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 text-xs text-gray-400">0</div>
          <div className="absolute left-2 top-1/2 transform -translate-y-1/2 text-xs text-gray-400">50</div>
          <div className="absolute right-2 top-1/2 transform -translate-y-1/2 text-xs text-gray-400">50</div>
        </div>
      </div>

      {showLabel && (
        <motion.div
          className={`mt-4 px-4 py-2 rounded-full text-sm font-medium text-white shadow-lg`}
          style={{ backgroundColor: riskColor }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.8 }}
        >
          {getRiskLabel(score)}
        </motion.div>
      )}
    </div>
  );
};

export default RiskGauge;
