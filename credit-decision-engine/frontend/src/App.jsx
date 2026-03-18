import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import ProfessionalLoading from './components/ProfessionalLoading';
import CompleteUploadPageFixed from './CompleteUploadPageFixed';
import ModernDashboard from './ModernDashboard';
import ModernResearchInsights from './ModernResearchInsights';
import CompleteCAMPreview from './CompleteCAMPreview';
import WorkingDynamicDashboard from './components/WorkingDynamicDashboard';
import { ThemeProvider } from './components/ThemeProvider';
import ThemeSwitcher from './components/ThemeSwitcher';
import './App.css';

function App() {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <Router>
          <div className="app-container" style={{ position: 'relative', minHeight: '100vh' }}>
            <div style={{ 
              position: 'fixed', 
              bottom: '32px', 
              right: '32px', 
              zIndex: 1100,
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <ThemeSwitcher />
            </div>
            <Routes>
            <Route path="/" element={<CompleteUploadPageFixed />} />
            <Route path="/dashboard" element={<ModernDashboard />} />
            <Route path="/dynamic-dashboard" element={<WorkingDynamicDashboard />} />
            <Route path="/research" element={<ModernResearchInsights />} />
            <Route path="/cam-preview" element={<CompleteCAMPreview />} />
            </Routes>
          </div>
        </Router>
      </ErrorBoundary>
    </ThemeProvider>
  );
}

export default App;
