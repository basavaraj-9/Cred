import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useMotionValue, useTransform } from 'framer-motion';

const TiltCard = ({ children, style, className }) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useTransform(y, [-100, 100], [10, -10]);
  const rotateY = useTransform(x, [-100, 100], [-10, 10]);

  function handleMouseMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const xPct = ((event.clientX - rect.left) / rect.width - 0.5) * 200;
    const yPct = ((event.clientY - rect.top) / rect.height - 0.5) * 200;
    x.set(xPct);
    y.set(yPct);
  }

  function handleMouseLeave() { x.set(0); y.set(0); }

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ ...style, rotateX, rotateY, transformStyle: "preserve-3d" }}
      className={className}
      whileHover={{ scale: 1.02, translateZ: 20 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      {children}
    </motion.div>
  );
};

const CompleteUploadPageFixed = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
  };

  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = () => setDragOver(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles(droppedFiles);
  };

  const testBackendData = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/test-data');
      const result = await response.json();
      if (result && result.data) {
        localStorage.setItem('companyData', JSON.stringify(result.data));
      } else {
        throw new Error('Backend returned invalid data structure');
      }
      setMessage('Test data loaded! Navigate to dashboard to see results.');
      setUploadProgress(100);
      setTimeout(() => navigate('/dashboard'), 2000);
    } catch (error) {
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
      files.forEach((file) => formData.append('files', file));
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 300);
      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });
      clearInterval(progressInterval);
      if (!response.ok) throw new Error(`Upload failed: ${response.statusText}`);
      const result = await response.json();
      const companyData = result.data;
      if (companyData) {
        localStorage.setItem('companyData', JSON.stringify(companyData));
      } else {
        throw new Error('Analysis failed to produce report data');
      }
      setMessage('Files uploaded successfully! Analyzing financial data...');
      setUploadProgress(100);
      setTimeout(() => navigate('/dashboard'), 2000);
    } catch (error) {
      setMessage(`Upload failed: ${error.message}`);
      setUploadProgress(0);
      setUploading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mesh-background"
      style={{
        minHeight: '100vh',
        background: 'var(--dashboard-bg)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        perspective: '1500px',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Animated background orbs */}
      <motion.div style={{
        position: 'absolute', top: '10%', left: '10%', width: '350px', height: '350px',
        background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)',
        borderRadius: '50%',
      }} animate={{ y: [0, -40, 0], scale: [1, 1.15, 1], opacity: [0.3, 0.6, 0.3] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div style={{
        position: 'absolute', bottom: '15%', right: '10%', width: '280px', height: '280px',
        background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)',
        borderRadius: '50%',
      }} animate={{ y: [0, 50, 0], x: [0, 30, 0], opacity: [0.2, 0.5, 0.2] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div style={{
        position: 'absolute', top: '50%', left: '50%', width: '200px', height: '200px',
        background: 'radial-gradient(circle, rgba(236,72,153,0.1) 0%, transparent 70%)',
        borderRadius: '50%',
      }} animate={{ y: [0, -30, 0], x: [0, -20, 0], opacity: [0.1, 0.3, 0.1] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }} />

      <TiltCard style={{
        background: 'var(--card-bg)',
        backdropFilter: 'var(--glass-blur)',
        borderRadius: '28px',
        padding: '48px',
        boxShadow: 'var(--card-shadow)',
        border: '1px solid var(--border-color)',
        maxWidth: '560px',
        width: '100%',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Top gradient bar */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '4px',
          background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f59e0b)',
          borderRadius: '28px 28px 0 0'
        }}></div>

        {/* Header */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{ textAlign: 'center', marginBottom: '36px' }}
        >
          <motion.div
            animate={{ rotateY: [0, 360] }}
            transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
            style={{
              width: '90px', height: '90px',
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              borderRadius: '22px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 24px',
              boxShadow: '0 8px 32px rgba(59, 130, 246, 0.4)',
              transformStyle: 'preserve-3d'
            }}
          >
            <span style={{ color: 'white', fontSize: '40px' }}>📄</span>
          </motion.div>
          <h1 style={{
            fontSize: '32px', fontWeight: 'bold', color: 'var(--text-primary)',
            marginBottom: '12px', letterSpacing: '-0.5px'
          }}>
            Credit Decisioning Engine
          </h1>
          <p style={{ fontSize: '16px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Upload financial documents for AI-powered credit analysis
          </p>
        </motion.div>

        {/* Drag & Drop Upload Zone */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4 }}
          style={{ marginBottom: '28px' }}
        >
          <label style={{
            display: 'block', fontSize: '15px', fontWeight: '600',
            color: 'var(--text-primary)', marginBottom: '12px'
          }}>
            📁 Select Documents (PDF, Excel, CSV, Word, Images)
          </label>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-input').click()}
            style={{
              width: '100%', padding: '40px 20px',
              border: `2px dashed ${dragOver ? '#3b82f6' : 'var(--border-color)'}`,
              borderRadius: '16px', textAlign: 'center',
              background: dragOver ? 'rgba(59, 130, 246, 0.05)' : 'rgba(255, 255, 255, 0.03)',
              cursor: 'pointer',
              transition: 'all 0.3s ease'
            }}
          >
            <div style={{ fontSize: '40px', marginBottom: '12px' }}>
              {dragOver ? '📥' : '☁️'}
            </div>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)', margin: '0 0 4px 0' }}>
              <span style={{ color: '#3b82f6', fontWeight: '600' }}>Click to upload</span> or drag and drop
            </p>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, opacity: 0.7 }}>
              PDF, XLSX, CSV, DOCX, JPG, PNG
            </p>
          </div>
          <input
            id="file-input"
            type="file"
            multiple
            accept=".pdf,.xlsx,.xls,.csv,.docx,.doc,.jpg,.jpeg,.png"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          {files.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              style={{
                marginTop: '12px', padding: '12px 16px',
                background: 'rgba(59, 130, 246, 0.1)',
                borderRadius: '12px', border: '1px solid rgba(59, 130, 246, 0.2)'
              }}
            >
              <p style={{ fontSize: '14px', color: '#3b82f6', fontWeight: '600', margin: 0 }}>
                📎 {files.length} file{files.length > 1 ? 's' : ''} selected
              </p>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                {files.map(f => f.name).join(', ')}
              </p>
            </motion.div>
          )}
        </motion.div>

        {/* Upload Progress */}
        {uploading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ marginBottom: '24px' }}
          >
            <div style={{
              width: '100%', height: '8px',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              borderRadius: '4px', overflow: 'hidden'
            }}>
              <motion.div
                animate={{ width: `${uploadProgress}%` }}
                transition={{ duration: 0.3 }}
                style={{
                  height: '100%',
                  background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)',
                  borderRadius: '4px'
                }}
              />
            </div>
            <p style={{
              textAlign: 'center', fontSize: '14px',
              color: 'var(--text-secondary)', marginTop: '8px'
            }}>
              Analyzing... {uploadProgress}%
            </p>
          </motion.div>
        )}

        {/* Message */}
        {message && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              padding: '14px 18px',
              backgroundColor: message.includes('success') || message.includes('loaded')
                ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: message.includes('success') || message.includes('loaded')
                ? '#10b981' : '#ef4444',
              borderRadius: '12px', fontSize: '14px', fontWeight: '500',
              marginBottom: '20px',
              border: `1px solid ${message.includes('success') || message.includes('loaded')
                ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
            }}
          >
            {message}
          </motion.div>
        )}

        {/* Action Buttons */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.6 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
        >
          <motion.button
            onClick={testBackendData}
            disabled={uploading}
            whileHover={{ scale: 1.03, translateZ: 10 }}
            whileTap={{ scale: 0.97 }}
            style={{
              background: 'linear-gradient(135deg, #8b5cf6, #7c3aed)',
              color: 'white', border: 'none',
              padding: '16px 30px', borderRadius: '14px',
              fontSize: '16px', fontWeight: '600', cursor: 'pointer',
              boxShadow: '0 8px 24px rgba(139, 92, 246, 0.35)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px'
            }}
          >
            <span style={{ fontSize: '20px' }}>🧪</span>
            Test with Sample Data
          </motion.button>

          <motion.button
            onClick={handleFileUpload}
            disabled={uploading || files.length === 0}
            whileHover={!uploading && files.length > 0 ? { scale: 1.03, translateZ: 10 } : {}}
            whileTap={!uploading && files.length > 0 ? { scale: 0.97 } : {}}
            style={{
              background: uploading ? 'rgba(255,255,255,0.1)' :
                files.length === 0 ? 'rgba(255,255,255,0.05)' :
                  'linear-gradient(135deg, #3b82f6, #2563eb)',
              color: 'white', border: 'none',
              padding: '16px 30px', borderRadius: '14px',
              fontSize: '16px', fontWeight: '600',
              cursor: uploading || files.length === 0 ? 'not-allowed' : 'pointer',
              opacity: uploading || files.length === 0 ? 0.5 : 1,
              boxShadow: files.length > 0 && !uploading ? '0 8px 24px rgba(59, 130, 246, 0.35)' : 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
              transition: 'opacity 0.3s ease'
            }}
          >
            {uploading ? (
              <>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  style={{
                    width: '20px', height: '20px',
                    border: '3px solid rgba(255, 255, 255, 0.3)',
                    borderTop: '3px solid white',
                    borderRadius: '50%'
                  }}
                />
                Processing...
              </>
            ) : (
              <>
                <span style={{ fontSize: '20px' }}>📤</span>
                Upload & Analyze
              </>
            )}
          </motion.button>
        </motion.div>
      </TiltCard>
    </motion.div>
  );
};

export default CompleteUploadPageFixed;
