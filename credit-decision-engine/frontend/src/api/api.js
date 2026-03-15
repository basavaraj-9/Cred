import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // Increased timeout to 60 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Separate instance for file uploads (no default Content-Type)
const uploadApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

// Request interceptor for regular API calls
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Upload documents - using direct fetch approach
export const uploadDocuments = async (fileArray) => {
  console.log('API uploadDocuments called with:', fileArray.length, 'files');
  console.log('fileArray type:', typeof fileArray);
  console.log('fileArray constructor:', fileArray.constructor.name);
  
  // First test basic connectivity
  try {
    console.log('Testing basic connectivity to backend...');
    const healthResponse = await fetch('http://localhost:8000/health');
    const healthData = await healthResponse.json();
    console.log('Backend health check:', healthData);
  } catch (healthError) {
    console.error('Backend health check failed:', healthError);
    throw new Error('Cannot connect to backend. Please ensure the backend is running on http://localhost:8000');
  }
  
  if (!fileArray || fileArray.length === 0) {
    throw new Error('No files provided to uploadDocuments');
  }
  
  const formData = new FormData();
  fileArray.forEach((file, index) => {
    console.log(`Processing file ${index}:`, {
      name: file.name,
      type: file.type,
      size: file.size,
      isFile: file instanceof File,
      constructor: file.constructor.name
    });
    
    if (!file || !(file instanceof File)) {
      console.error(`Invalid file at index ${index}:`, file);
      throw new Error(`Invalid file at index ${index}: not a File object`);
    }
    
    formData.append('files', file);
  });

  // Log FormData contents for debugging
  console.log('FormData entries:');
  let entryCount = 0;
  for (let [key, value] of formData.entries()) {
    entryCount++;
    console.log(`Entry ${entryCount}:`, key, value instanceof File ? `File: ${value.name} (${value.size} bytes)` : value);
  }
  
  if (entryCount === 0) {
    throw new Error('FormData is empty - no files were added');
  }

  try {
    console.log('Making direct fetch POST request to /upload-documents');
    console.log('FormData size:', formData);
    
    const response = await fetch('http://localhost:8000/api/upload-documents', {
      method: 'POST',
      body: formData,
      mode: 'cors',
      credentials: 'same-origin'
    });
    
    console.log('Fetch response status:', response.status, response.statusText);
    console.log('Fetch response headers:', response.headers);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Response error text:', errorText);
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
    }
    
    const data = await response.json();
    console.log('Fetch response received:', data);
    return data;
    
  } catch (error) {
    console.error('Direct fetch upload error:', error);
    console.error('Error type:', typeof error);
    console.error('Error message:', error.message);
    console.error('Error stack:', error.stack);
    throw error;
  }
};

// Analyze company
export const analyzeCompany = async (documents) => {
  const response = await api.post('/analyze-company', { documents });
  return response.data;
};

// Consistency analysis
export const analyzeConsistency = async (gstData, bankData) => {
  const response = await api.post('/consistency-analysis', { gst_data: gstData, bank_data: bankData });
  return response.data;
};

// Calculate risk score
export const calculateRiskScore = async (financialData, gstData, bankData, researchData, officerInput) => {
  const response = await api.post('/risk-score', {
    financial_data: financialData,
    gst_data: gstData,
    bank_data: bankData,
    research_data: researchData,
    officer_input: officerInput
  });
  return response.data;
};

// Generate recommendation
export const generateRecommendation = async (riskAnalysis, financialData) => {
  const response = await api.post('/recommendation', {
    risk_analysis: riskAnalysis,
    financial_data: financialData
  });
  return response.data;
};

// Research insights
export const getResearchInsights = async (companyName, promoterName, sector) => {
  const response = await api.post('/research-insights', {
    company_name: companyName,
    promoter_name: promoterName,
    sector: sector
  });
  return response.data;
};

// Generate CAM
export const generateCAM = async (companyData, financialData, riskAnalysis, researchData, recommendation) => {
  const response = await api.post('/generate-cam', {
    company_data: companyData,
    financial_data: financialData,
    risk_analysis: riskAnalysis,
    research_data: researchData,
    recommendation: recommendation
  });
  return response.data;
};

// Download CAM
export const downloadCAM = async (filename, fileType = 'word') => {
  const response = await api.get(`/download-cam/${filename}?file_type=${fileType}`, {
    responseType: 'blob'
  });
  
  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${filename}.${fileType === 'pdf' ? 'pdf' : 'docx'}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// Get sector outlook
export const getSectorOutlook = async (sector) => {
  const response = await api.get(`/sector-outlook/${sector}`);
  return response.data;
};

// Get news sentiment
export const getNewsSentiment = async (companyName) => {
  const response = await api.get(`/news-sentiment/${companyName}`);
  return response.data;
};

// Check litigation
export const checkLitigation = async (companyName) => {
  const response = await api.get(`/litigation-check/${companyName}`);
  return response.data;
};

// Get risk factors
export const getRiskFactors = async () => {
  const response = await api.get('/risk-factors');
  return response.data;
};

// Get CAM list
export const getCAMList = async () => {
  const response = await api.get('/cam-list');
  return response.data;
};

// Get CAM preview
export const getCAMPreview = async (filename) => {
  const response = await api.get(`/cam-preview/${filename}`);
  return response.data;
};

// Get risk score (simplified version for dashboard)
export const getRiskScore = async () => {
  const response = await api.get('/risk-score');
  return response.data;
};

// Get recommendation (simplified version for dashboard)
export const getRecommendation = async () => {
  const response = await api.get('/recommendation');
  return response.data;
};

// Get consistency analysis (simplified version for dashboard)
export const getConsistencyAnalysis = async () => {
  const response = await api.get('/consistency-analysis');
  return response.data;
};

// List CAM files
export const listCAMFiles = async () => {
  const response = await api.get('/cam-list');
  return response.data;
};

export default api;
