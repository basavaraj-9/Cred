import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const CompleteUploadPageFixed = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [message, setMessage] = useState('');

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
  };

  // Add debug function to test backend data
  const testBackendData = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/test-data');
      const result = await response.json();
      
      console.log('Backend test data:', result);
      
      // Store the backend data directly if it exists
      if (result && result.data) {
        localStorage.setItem('companyData', JSON.stringify(result.data));
      } else {
        console.error('Invalid backend response structure:', result);
        throw new Error('Backend returned invalid data structure');
      }
      
      setMessage('Test data loaded! Navigate to dashboard to see results.');
      setUploadProgress(100);
      
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
      
    } catch (error) {
      console.error('Test data error:', error);
      setMessage(`Test data error: ${error.message}`);
    }
  };

  const handleFileUpload = async () => {
    if (files.length === 0) {
      setMessage('Please select files to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      files.forEach((file, index) => {
        formData.append(`files`, file);
      });

      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();
      
      console.log('Backend response:', result);
      
      // Store the backend data directly - it's already in the correct format
      const companyData = result.data;
      
      if (companyData) {
        console.log('Company data to store:', companyData);
        localStorage.setItem('companyData', JSON.stringify(companyData));
      } else {
        console.error('No company data found in response:', result);
        throw new Error('Analysis failed to produce report data');
      }
      
      setMessage('Files uploaded successfully! Analyzing financial data...');
      setUploadProgress(100);
      
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);

    } catch (error) {
      console.error('Upload error:', error);
      setMessage(`Upload failed: ${error.message}`);
      setUploadProgress(0);
      setUploading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(10px)',
        borderRadius: '20px',
        padding: '40px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.3)',
        maxWidth: '500px',
        width: '100%'
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <div style={{
            width: '80px',
            height: '80px',
            background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            boxShadow: '0 4px 14px rgba(59, 130, 246, 0.3)'
          }}>
            <span style={{ color: 'white', fontSize: '32px', fontWeight: 'bold' }}>📄</span>
          </div>
          <h1 style={{ 
            fontSize: '28px', 
            fontWeight: 'bold', 
            color: '#1e293b', 
            marginBottom: '10px',
            textAlign: 'center'
          }}>
            Credit Decisioning Engine
          </h1>
          <p style={{ 
            fontSize: '16px', 
            color: '#64748b', 
            textAlign: 'center',
            marginBottom: '30px'
          }}>
            Upload financial documents for AI-powered credit analysis
          </p>
        </div>

        {/* File Upload */}
        <div style={{ marginBottom: '30px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: '16px', 
            fontWeight: '600', 
            color: '#374151', 
            marginBottom: '10px' 
          }}>
            📁 Select Documents (PDF, Excel, CSV, Word, Images)
          </label>
          <input
            type="file"
            multiple
            accept=".pdf,.xlsx,.xls,.csv,.docx,.doc,.jpg,.jpeg,.png"
            onChange={handleFileChange}
            style={{
              width: '100%',
              padding: '12px',
              border: '2px dashed #d1d5db',
              borderRadius: '8px',
              fontSize: '14px',
              backgroundColor: '#f9fafb',
              cursor: 'pointer',
              transition: 'border-color 0.3s ease'
            }}
            onFocus={(e) => e.target.style.borderColor = '#3b82f6'}
            onBlur={(e) => e.target.style.borderColor = '#d1d5db'}
          />
          {files.length > 0 && (
            <div style={{ marginTop: '10px', fontSize: '14px', color: '#6b7280' }}>
              Selected: {files.map(f => f.name).join(', ')}
            </div>
          )}
        </div>

        {/* Upload Progress */}
        {uploading && (
          <div style={{ marginBottom: '20px' }}>
            <div style={{
              width: '100%',
              height: '8px',
              backgroundColor: '#e5e7eb',
              borderRadius: '4px',
              overflow: 'hidden'
            }}>
              <div style={{
                width: `${uploadProgress}%`,
                height: '100%',
                background: 'linear-gradient(90deg, #3b82f6, #2563eb)',
                transition: 'width 0.3s ease',
                borderRadius: '4px'
              }}></div>
            </div>
            <p style={{ 
              textAlign: 'center', 
              fontSize: '14px', 
              color: '#6b7280', 
              marginTop: '8px' 
            }}>
              Uploading... {uploadProgress}%
            </p>
          </div>
        )}

        {/* Message */}
        {message && (
          <div style={{
            padding: '12px 16px',
            backgroundColor: message.includes('success') ? '#dcfce7' : '#fef2f2',
            color: message.includes('success') ? '#166534' : '#991b1b',
            borderRadius: '8px',
            fontSize: '14px',
            marginBottom: '20px'
          }}>
            {message}
          </div>
        )}

        {/* Debug Test Button */}
        <button
          onClick={testBackendData}
          disabled={uploading}
          style={{
            background: 'linear-gradient(135deg, #ef4444, #dc2626)',
            color: 'white',
            border: 'none',
            padding: '15px 30px',
            borderRadius: '12px',
            fontSize: '16px',
            fontWeight: '600',
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            width: '100%',
            marginBottom: '16px',
            boxShadow: '0 4px 15px rgba(239, 68, 68, 0.3)'
          }}
          onMouseOver={(e) => {
            e.target.style.transform = 'translateY(-2px)';
            e.target.style.boxShadow = '0 6px 20px rgba(239, 68, 68, 0.4)';
          }}
          onMouseOut={(e) => {
            e.target.style.transform = 'translateY(0)';
            e.target.style.boxShadow = '0 4px 15px rgba(239, 68, 68, 0.3)';
          }}
        >
          🐛 Test Backend Data (Debug)
        </button>

        {/* Upload Button */}
        <button
          onClick={handleFileUpload}
          disabled={uploading || files.length === 0}
          style={{
            width: '100%',
            padding: '14px 24px',
            backgroundColor: uploading ? '#9ca3af' : '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            fontSize: '16px',
            fontWeight: '600',
            cursor: uploading ? 'not-allowed' : 'pointer',
            transition: 'all 0.3s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
          onMouseOver={(e) => {
            if (!uploading) {
              e.target.style.backgroundColor = '#2563eb';
              e.target.style.transform = 'translateY(-2px)';
            }
          }}
          onMouseOut={(e) => {
            if (!uploading) {
              e.target.style.backgroundColor = '#3b82f6';
              e.target.style.transform = 'translateY(0)';
            }
          }}
        >
          {uploading ? (
            <>
              <div style={{
                width: '20px',
                height: '20px',
                border: '3px solid rgba(255, 255, 255, 0.3)',
                borderTop: '3px solid white',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                marginRight: '8px'
              }}></div>
              Processing...
            </>
          ) : (
            <>
              📤 Upload & Analyze
            </>
          )}
        </button>

        {/* Analysis trigger is already handled above */}
      </div>
    </div>
  );
};

export default CompleteUploadPageFixed;
