import React, { useState } from 'react';

const TestUploadPage = () => {
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const testUpload = async () => {
    setStatus('Testing upload...');
    setError('');
    
    try {
      // Create a simple test file
      const testFile = new File(['test content'], 'test.txt', { type: 'text/plain' });
      
      // Test direct fetch to backend
      const formData = new FormData();
      formData.append('files', testFile);
      
      const response = await fetch('http://localhost:8000/api/upload-documents', {
        method: 'POST',
        body: formData,
        mode: 'cors'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setStatus('SUCCESS: ' + JSON.stringify(data, null, 2));
      
    } catch (err) {
      setError('ERROR: ' + err.message);
      console.error('Test upload error:', err);
    }
  };

  const testAPI = async () => {
    setStatus('Testing API...');
    setError('');
    
    try {
      // Test via axios API
      const { uploadDocuments } = await import('../api/api');
      
      const testFile = new File(['test content'], 'test.txt', { type: 'text/plain' });
      const response = await uploadDocuments([testFile]);
      
      setStatus('API SUCCESS: ' + JSON.stringify(response, null, 2));
      
    } catch (err) {
      setError('API ERROR: ' + err.message);
      console.error('API test error:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Upload Test Page</h1>
        
        <div className="space-y-4">
          <button
            onClick={testUpload}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded"
          >
            Test Direct Fetch
          </button>
          
          <button
            onClick={testAPI}
            className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded"
          >
            Test API Function
          </button>
        </div>
        
        {status && (
          <div className="mt-8 bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="font-semibold text-green-800 mb-2">Status:</h3>
            <pre className="text-sm text-green-700 whitespace-pre-wrap">{status}</pre>
          </div>
        )}
        
        {error && (
          <div className="mt-8 bg-red-50 border border-red-200 rounded-lg p-4">
            <h3 className="font-semibold text-red-800 mb-2">Error:</h3>
            <pre className="text-sm text-red-700 whitespace-pre-wrap">{error}</pre>
          </div>
        )}
        
        <div className="mt-8 bg-gray-100 rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-2">Debug Info:</h3>
          <p className="text-sm text-gray-700">Current URL: {window.location.href}</p>
          <p className="text-sm text-gray-700">Backend URL: http://localhost:8000</p>
          <p className="text-sm text-gray-700">Check browser console for more details</p>
        </div>
      </div>
    </div>
  );
};

export default TestUploadPage;
