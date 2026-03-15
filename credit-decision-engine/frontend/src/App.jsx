import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import ProfessionalLoading from './components/ProfessionalLoading';
import CompleteUploadPage from './CompleteUploadPage';
import ModernDashboard from './ModernDashboard';
import ModernResearchInsights from './ModernResearchInsights';
import CompleteCAMPreview from './CompleteCAMPreview';
import './App.css';

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <div className="app-container">
          <Routes>
            <Route path="/" element={<CompleteUploadPage />} />
            <Route path="/dashboard" element={<ModernDashboard />} />
            <Route path="/research" element={<ModernResearchInsights />} />
            <Route path="/cam-preview" element={<CompleteCAMPreview />} />
          </Routes>
        </div>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
