import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ProfessionalLoading from './components/ProfessionalLoading';

const CompleteUploadPage = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    // Clear any existing data on mount
    localStorage.removeItem('companyData');
  }, []);

  const generateMockData = (uploadedFiles) => {
    const companies = uploadedFiles.map((file, index) => ({
      unique_hash: `company_${index}_${Date.now()}`,
      company: `Company ${index + 1}`,
      industry: ['Technology', 'Manufacturing', 'Healthcare', 'Finance', 'Retail'][index % 5],
      revenue: `${(Math.random() * 900 + 100).toFixed(1)}M`,
      employees: Math.floor(Math.random() * 10000 + 100),
      founded: Math.floor(Math.random() * 50 + 1970),
      ai_analysis: {
        risk_analysis: {
          risk_score: Math.floor(Math.random() * 40 + 30),
          risk_category: ['LOW', 'MEDIUM', 'HIGH'][Math.floor(Math.random() * 3)],
          factors: {
            financial_health: Math.floor(Math.random() * 40 + 60),
            market_position: Math.floor(Math.random() * 30 + 70),
            operational_efficiency: Math.floor(Math.random() * 20 + 80),
            debt_ratio: (Math.random() * 0.6 + 0.1).toFixed(2)
          }
        },
        decision_result: {
          decision: ['APPROVE', 'REVIEW', 'DECLINE'][Math.floor(Math.random() * 3)],
          confidence: Math.floor(Math.random() * 25 + 75),
          recommended_amount: `${(Math.random() * 900 + 100).toFixed(1)}M`,
          reasoning: `Based on comprehensive financial analysis and risk assessment`
        }
      }
    }));

    return {
      is_multi_company: uploadedFiles.length > 1,
      companies: uploadedFiles.length > 1 ? companies : companies[0],
      uploaded_files: uploadedFiles.map(f => f.name),
      analysis_timestamp: new Date().toISOString()
    };
  };

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    const validFiles = selectedFiles.filter(file => {
      if (file.type !== 'application/pdf') {
        setError(`Invalid file type: ${file.name}. Only PDF files are allowed.`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) {
        setError(`File too large: ${file.name}. Maximum size is 10MB.`);
        return false;
      }
      return true;
    });

    if (validFiles.length > 0) {
      setFiles(prevFiles => [...prevFiles, ...validFiles.map(file => ({
        id: Math.random().toString(36).substr(2, 9),
        file: file,
        name: file.name,
        size: (file.size / 1024 / 1024).toFixed(2) + 'MB'
      }))]);
      setError('');
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = droppedFiles.filter(file => {
      if (file.type !== 'application/pdf') {
        setError(`Invalid file type: ${file.name}. Only PDF files are allowed.`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) {
        setError(`File too large: ${file.name}. Maximum size is 10MB.`);
        return false;
      }
      return true;
    });

    if (validFiles.length > 0) {
      setFiles(prevFiles => [...prevFiles, ...validFiles.map(file => ({
        id: Math.random().toString(36).substr(2, 9),
        file: file,
        name: file.name,
        size: (file.size / 1024 / 1024).toFixed(2) + 'MB'
      }))]);
      setError('');
    }
  };

  const removeFile = (fileId) => {
    setFiles(prevFiles => prevFiles.filter(f => f.id !== fileId));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select at least one file to upload.');
      return;
    }

    setUploading(true);
    setError('');
    
    try {
      // Simulate upload delay
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const mockData = generateMockData(files.map(f => f.file));
      localStorage.setItem('companyData', JSON.stringify(mockData));
      navigate('/dashboard');
    } catch (error) {
      setError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  if (uploading) {
    return <ProfessionalLoading message="Analyzing documents..." fullScreen />;
  }

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #1e40af 0%, #0f766e 50%, #0891b2 100%)',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Enhanced Animated background elements */}
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
      <div style={{
        position: 'absolute',
        bottom: '20%',
        left: '15%',
        width: '200px',
        height: '200px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 10s ease-in-out infinite'
      }}></div>

      {/* Main Content */}
      <div style={{ flex: 1, maxWidth: '1400px', margin: '0 auto', padding: '40px 24px', width: '100%' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '48px', animation: 'fadeIn 0.8s ease-out' }}>
          <div style={{ fontSize: '72px', marginBottom: '24px', animation: 'pulse 2s infinite' }}>📤</div>
          <h1 style={{ 
            fontSize: '48px', 
            fontWeight: 'bold', 
            marginBottom: '16px', 
            color: 'white',
            textShadow: '0 2px 4px rgba(0,0,0,0.1)',
            animation: 'slideInUp 0.6s ease-out'
          }}>
            AI Credit Decisioning Engine
          </h1>
          <p style={{ 
            fontSize: '20px', 
            color: 'rgba(255, 255, 255, 0.95)',
            fontWeight: '400',
            maxWidth: '600px',
            margin: '0 auto',
            animation: 'slideInUp 0.8s ease-out'
          }}>
            Upload company documents for AI-powered credit analysis with individual research insights
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '16px',
            padding: '16px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            animation: 'slideInUp 0.3s ease-out'
          }}>
            <span style={{ fontSize: '20px' }}>⚠️</span>
            <p style={{ color: '#fecaca', margin: 0, fontSize: '14px' }}>
              {error}
            </p>
          </div>
        )}

        {/* Upload Card */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.98)',
          backdropFilter: 'blur(25px)',
          borderRadius: '28px',
          padding: '48px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          border: '1px solid rgba(255, 255, 255, 0.4)',
          textAlign: 'center',
          animation: 'scaleIn 0.6s ease-out',
          position: 'relative',
          overflow: 'hidden'
        }}>
          {/* Card decoration */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '4px',
            background: 'linear-gradient(90deg, #1e40af, #0f766e, #0891b2, #1e40af)',
            borderRadius: '28px 28px 0 0'
          }}></div>
          
          <div style={{ fontSize: '64px', marginBottom: '24px', animation: 'pulse 2s infinite' }}>📁</div>
          <h2 style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px' }}>
            Upload Company Documents
          </h2>
          <p style={{ fontSize: '18px', color: '#475569', marginBottom: '32px', lineHeight: '1.5' }}>
            Upload multiple company files to generate individual research insights for each company
          </p>

          {/* Upload Area */}
          <div
            style={{
              border: dragOver ? '3px solid #1e40af' : '3px dashed #cbd5e1',
              borderRadius: '20px',
              padding: '48px',
              marginBottom: '32px',
              background: dragOver 
                ? 'linear-gradient(135deg, #eff6ff, #f0fdfa)' 
                : 'linear-gradient(135deg, #f8fafc, #f0fdfa)',
              transition: 'all 0.3s ease',
              cursor: 'pointer',
              position: 'relative',
              overflow: 'hidden'
            }}
            onClick={() => document.getElementById('fileInput').click()}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {dragOver && (
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(30, 64, 175, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '24px',
                fontWeight: 'bold',
                color: '#1e40af'
              }}>
                Drop files here
              </div>
            )}
            <div style={{ fontSize: '48px', marginBottom: '16px', animation: dragOver ? 'bounce 0.5s' : 'none' }}>📄</div>
            <p style={{ fontSize: '18px', color: '#475569', marginBottom: '8px' }}>
              {dragOver ? 'Release to upload files' : 'Click to upload or drag and drop'}
            </p>
            <p style={{ fontSize: '14px', color: '#94a3b8' }}>
              PDF files (MAX. 10MB per file)
            </p>
            <input
              id="fileInput"
              type="file"
              multiple
              accept=".pdf"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div style={{ marginBottom: '32px', animation: 'slideInUp 0.4s ease-out' }}>
              <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px' }}>
                Selected Files ({files.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {files.map((file, index) => (
                  <div
                    key={file.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '16px',
                      background: 'white',
                      borderRadius: '16px',
                      border: '1px solid #e2e8f0',
                      animation: `slideInUp ${0.3 + index * 0.1}s ease-out`,
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '4px',
                      height: '100%',
                      background: 'linear-gradient(135deg, #1e40af, #0f766e)'
                    }}></div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '24px' }}>📄</span>
                      <div>
                        <p style={{ fontWeight: '600', color: '#1e293b', margin: '0 0 4px 0' }}>
                          {file.name}
                        </p>
                        <p style={{ fontSize: '14px', color: '#64748b', margin: 0 }}>
                          {file.size}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(file.id)}
                      style={{
                        backgroundColor: '#ef4444',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        padding: '10px 18px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '600',
                        transition: 'all 0.3s ease',
                        boxShadow: '0 4px 6px rgba(239, 68, 68, 0.2)'
                      }}
                      onMouseOver={(e) => e.target.style.backgroundColor = '#dc2626'}
                      onMouseOut={(e) => e.target.style.backgroundColor = '#ef4444'}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Enhanced Upload Button */}
          <button
            onClick={handleUpload}
            disabled={files.length === 0 || uploading}
            style={{
              background: files.length === 0 || uploading 
                ? 'linear-gradient(135deg, #94a3b8, #64748b)' 
                : 'linear-gradient(135deg, #1e40af, #0f766e)',
              color: 'white',
              border: 'none',
              borderRadius: '16px',
              padding: '18px 36px',
              fontSize: '18px',
              fontWeight: 'bold',
              cursor: files.length === 0 || uploading ? 'not-allowed' : 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: files.length === 0 || uploading 
                ? '0 4px 6px rgba(0, 0, 0, 0.1)' 
                : '0 10px 25px rgba(30, 64, 175, 0.4), 0 4px 6px rgba(0, 0, 0, 0.1)',
              opacity: files.length === 0 || uploading ? 0.7 : 1,
              animation: 'fadeIn 0.8s ease-out',
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            {uploading ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '20px',
                  height: '20px',
                  border: '2px solid white',
                  borderTop: '2px solid transparent',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }}></div>
                Processing...
              </div>
            ) : (
              `Analyze ${files.length} Company${files.length !== 1 ? 'ies' : ''}`
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CompleteUploadPage;
