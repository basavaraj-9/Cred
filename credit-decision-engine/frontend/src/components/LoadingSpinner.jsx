import React from 'react';

const LoadingSpinner = ({ 
  size = 'md', 
  text = '', 
  fullScreen = false,
  className = '' 
}) => {
  const getSizeClasses = () => {
    const sizes = {
      sm: 'h-4 w-4',
      md: 'h-8 w-8',
      lg: 'h-12 w-12',
      xl: 'h-16 w-16'
    };
    return sizes[size] || sizes.md;
  };

  const spinner = (
    <div className="flex flex-col items-center justify-center">
      <div className="relative">
        <div className={`${getSizeClasses()} border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin`}></div>
        <div className={`absolute inset-0 ${getSizeClasses()} border-4 border-transparent border-l-purple-600 rounded-full animate-spin animation-delay-150`}></div>
      </div>
      {text && (
        <p className="mt-4 text-sm text-gray-600 font-medium animate-pulse">
          {text}
        </p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-white bg-opacity-90 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="bg-white rounded-xl shadow-2xl p-8 border border-gray-100">
          {spinner}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center justify-center ${className}`}>
      {spinner}
    </div>
  );
};

export default LoadingSpinner;
