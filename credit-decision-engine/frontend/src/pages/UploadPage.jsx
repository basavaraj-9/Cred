import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle, AlertTriangle, ArrowRight, Sparkles } from 'lucide-react';
import { uploadDocuments, analyzeCompany } from '../api/api';
import AnimatedCard from '../components/AnimatedCard';
import GradientButton from '../components/GradientButton';
import LoadingSpinner from '../components/LoadingSpinner';

const UploadPage = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const onDrop = useCallback(acceptedFiles => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      id: Math.random().toString(36).substr(2, 9),
      preview: URL.createObjectURL(file)
    }));
    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv'],
      'image/*': ['.jpg', '.jpeg', '.png', '.tiff']
    }
  });

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please upload at least one document');
      return;
    }

    setUploading(true);
    setError('');

    try {
      const formData = new FormData();
      files.forEach(item => {
        formData.append('files', item.file);
      });

      const response = await uploadDocuments(formData);
      
      if (response.status === 'success') {
        setSuccess(true);
        
        // Auto analyze after successful upload
        setTimeout(async () => {
          setAnalyzing(true);
          try {
            const analysisResponse = await analyzeCompany();
            if (analysisResponse.status === 'success') {
              localStorage.setItem('companyData', JSON.stringify(analysisResponse.company_analysis));
              setTimeout(() => {
                navigate('/dashboard');
              }, 1500);
            }
          } catch (err) {
            setError('Analysis failed: ' + err.message);
          } finally {
            setAnalyzing(false);
          }
        }, 2000);
      }
    } catch (err) {
      setError('Upload failed: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (id) => {
    setFiles(prev => prev.filter(file => file.id !== id));
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="text-center"
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-8"
          >
            <div className="w-24 h-24 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-12 h-12 text-green-600" />
            </div>
          </motion.div>
          
          <motion.h1
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-3xl font-bold text-gray-900 mb-4"
          >
            Upload Successful!
          </motion.h1>
          
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="text-lg text-gray-600 mb-8"
          >
            Analyzing your documents...
          </motion.p>
          
          <LoadingSpinner size="lg" text="Processing financial data" />
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center space-x-3 mb-4">
            <Sparkles className="w-8 h-8 text-blue-600" />
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              AI Credit Decisioning Engine
            </h1>
          </div>
          <p className="text-lg text-gray-600">
            Upload your financial documents for intelligent credit analysis
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Upload Area */}
          <AnimatedCard delay={0.1} className="p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
                <Upload className="w-6 h-6 mr-2 text-blue-600" />
                Upload Documents
              </h2>
              <p className="text-gray-600">
                Upload financial statements, GST returns, bank statements, and legal documents
              </p>
            </div>

            <div
              {...getRootProps()}
              className={`upload-area border-3 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-300 ${
                isDragActive 
                  ? 'border-blue-500 bg-blue-50 scale-102' 
                  : 'border-gray-300 hover:border-blue-400 bg-gray-50 hover:bg-blue-50'
              }`}
            >
              <input {...getInputProps()} />
              <motion.div
                animate={isDragActive ? { scale: 1.1 } : { scale: 1 }}
                className="flex flex-col items-center"
              >
                <Upload className={`w-16 h-16 mb-4 ${isDragActive ? 'text-blue-600' : 'text-gray-400'}`} />
                <p className="text-lg font-medium text-gray-900 mb-2">
                  {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
                </p>
                <p className="text-sm text-gray-500 mb-4">or</p>
                <GradientButton variant="primary" size="sm">
                  Browse Files
                </GradientButton>
              </motion.div>
            </div>

            <div className="mt-6 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>Supported formats:</strong> PDF, Excel, CSV, Images (JPG, PNG, TIFF)
              </p>
            </div>
          </AnimatedCard>

          {/* File List */}
          <AnimatedCard delay={0.2} className="p-8">
            <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center">
              <FileText className="w-5 h-5 mr-2 text-blue-600" />
              Uploaded Files ({files.length})
            </h3>

            {files.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-8 h-8 text-gray-400" />
                </div>
                <p className="text-gray-500">No files uploaded yet</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {files.map((fileObj, index) => (
                  <motion.div
                    key={fileObj.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200 hover:border-blue-300 transition-colors"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <FileText className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{fileObj.file.name}</p>
                        <p className="text-sm text-gray-500">{formatFileSize(fileObj.file.size)}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(fileObj.id)}
                      className="text-red-500 hover:text-red-700 transition-colors"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </motion.div>
                ))}
              </div>
            )}
          </AnimatedCard>
        </div>

        {/* Parsed Data Preview */}
        {parsedData && (
          <div className="bg-white rounded-lg shadow-md p-8">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Analysis Preview
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <p className="text-sm text-blue-600 font-medium">Company</p>
                <p className="text-lg font-bold text-blue-900">{parsedData.company || 'N/A'}</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <p className="text-sm text-green-600 font-medium">Revenue</p>
                <p className="text-lg font-bold text-green-900">
                  ₹{(parsedData.revenue / 10000000).toFixed(2)} Cr
                </p>
              </div>
              <div className="bg-yellow-50 p-4 rounded-lg">
                <p className="text-sm text-yellow-600 font-medium">Existing Loans</p>
                <p className="text-lg font-bold text-yellow-900">
                  ₹{(parsedData.existing_loans / 10000000).toFixed(2)} Cr
                </p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <p className="text-sm text-purple-600 font-medium">Documents</p>
                <p className="text-lg font-bold text-purple-900">
                  {parsedData.documents_summary?.length || 0}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-8 bg-blue-50 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-3">
            Supported Documents
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800">
            <div>
              <p className="font-medium">Financial Documents:</p>
              <ul className="mt-1 space-y-1">
                <li>• Annual Reports (PDF)</li>
                <li>• Financial Statements (PDF/Excel)</li>
                <li>• GST Returns (Excel/CSV)</li>
              </ul>
            </div>
            <div>
              <p className="font-medium">Bank & Legal Documents:</p>
              <ul className="mt-1 space-y-1">
                <li>• Bank Statements (PDF/Excel)</li>
                <li>• Legal Notices (PDF)</li>
                <li>• Sanction Letters (PDF)</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
