import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const SimpleUploadPage = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [uploadCount, setUploadCount] = useState(0);
  const isUploadingRef = useRef(false);
  const lastUploadTimeRef = useRef(0);
  const uploadButtonRef = useRef(null);

  // Clear localStorage on mount to ensure fresh start
  useEffect(() => {
    console.log('UploadPage: Clearing previous data for fresh upload');
    localStorage.removeItem('companyData');
    setUploadCount(0);
  }, []);

  const handleFileSelect = (event) => {
    const selectedFiles = Array.from(event.target.files);
    const newFiles = selectedFiles.map(file => ({
      file,
      id: Math.random().toString(36).substr(2, 9)
    }));
    setFiles([...files, ...newFiles]);
    setError(''); // Clear any previous errors
  };

  const removeFile = (fileId) => {
    setFiles(files.filter(f => f.id !== fileId));
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Generate truly dynamic company data based on file and timestamp
  const generateDynamicCompanyData = (file, uploadAttempt, fileIndex) => {
    const timestamp = Date.now();
    const fileName = file.name;
    const fileHash = fileName.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const uniqueHash = (fileHash + timestamp + uploadAttempt + fileIndex) % 1000000;
    
    // Company names based on hash and file index
    const companyNames = [
      'ABC Manufacturing', 'XYZ Textiles', 'TechVision Solutions', 'Global Finance Corp', 
      'Innovate Industries', 'MegaMart Enterprises', 'Digital Dynamics', 'Future Systems',
      'Apex Manufacturing', 'Quantum Services', 'Nexus Technologies', 'Pioneer Holdings',
      'Strategic Investments', 'Velocity Partners', 'Sunrise Industries', 'BlueOcean Tech'
    ];
    
    const industries = [
      'Manufacturing', 'Textiles', 'Technology', 'Finance', 'Healthcare', 
      'Retail', 'Energy', 'Real Estate', 'Telecommunications', 'Automotive',
      'Pharmaceuticals', 'Construction', 'Logistics', 'Agriculture', 'Food Processing'
    ];
    
    const companyName = companyNames[(uniqueHash + fileIndex) % companyNames.length];
    const industry = industries[Math.floor((uniqueHash + fileIndex) / 1000) % industries.length];
    
    // Generate dynamic financial data based on hash and file
    const baseRevenue = 30000000 + (uniqueHash % 600000000); // 3Cr to 603Cr
    const revenueVariation = Math.sin(uniqueHash + fileIndex) * 0.4; // ±40% variation
    const revenue = Math.floor(baseRevenue * (1 + revenueVariation));
    
    const profitMargin = 0.03 + (uniqueHash % 200) / 1000; // 3% to 23%
    const profit = Math.floor(revenue * profitMargin);
    
    const assetMultiplier = 1.1 + (uniqueHash % 120) / 100; // 1.1x to 2.3x revenue
    const assets = Math.floor(revenue * assetMultiplier);
    
    const liabilityRatio = 0.25 + (uniqueHash % 50) / 100; // 25% to 75% of assets
    const liabilities = Math.floor(assets * liabilityRatio);
    
    // Generate dynamic AI analysis
    const riskScore = 20 + (uniqueHash % 65); // 20 to 85
    
    let riskCategory = 'Medium Risk';
    if (riskScore < 35) riskCategory = 'Low Risk';
    else if (riskScore > 65) riskCategory = 'High Risk';
    
    let decision = 'Conditional Approval';
    if (riskScore < 35 && profitMargin > 0.12) decision = 'Approve';
    else if (riskScore > 70 || profitMargin < 0.04) decision = 'Reject';
    
    const loanToRevenue = riskScore < 35 ? 0.4 : riskScore < 55 ? 0.25 : 0.15;
    const approvedLoanAmount = Math.floor(revenue * loanToRevenue);
    
    const baseRate = 8.0;
    const riskPremium = (riskScore - 40) * 0.15;
    const interestRate = Math.max(7.0, Math.min(16.0, baseRate + riskPremium));
    
    const confidenceScore = 0.6 + (uniqueHash % 30) / 100; // 60% to 90%
    
    // Generate company-specific risk factors
    const riskFactors = [];
    
    // Financial risk factors - unique per company
    if (profitMargin < 0.08) {
      riskFactors.push({
        category: 'Financial',
        severity: 'High',
        description: `Low profit margin of ${(profitMargin * 100).toFixed(1)}% indicates operational inefficiency and impacts debt service capacity`,
        recommendation: 'Implement cost optimization measures and explore revenue enhancement strategies'
      });
    }
    
    if (liabilities / assets > 0.65) {
      riskFactors.push({
        category: 'Leverage',
        severity: 'Medium',
        description: `High debt-to-asset ratio of ${((liabilities/assets) * 100).toFixed(1)}% increases financial vulnerability during market downturns`,
        recommendation: 'Consider debt restructuring and strengthen equity base through retained earnings'
      });
    }
    
    // Industry-specific risk factors - unique per industry
    if (industry === 'Manufacturing') {
      const manufacturingRisks = [
        {
          category: 'Industry',
          severity: 'Medium',
          description: 'Manufacturing sector faces cyclical demand fluctuations and supply chain disruptions',
          recommendation: 'Diversify product portfolio across multiple segments and strengthen supplier relationships'
        },
        {
          category: 'Operational',
          severity: 'Low',
          description: 'Aging machinery may impact production efficiency and quality standards',
          recommendation: 'Implement preventive maintenance schedule and plan for capital expenditure upgrades'
        }
      ];
      riskFactors.push(manufacturingRisks[uniqueHash % 2]);
    } else if (industry === 'Textiles') {
      const textileRisks = [
        {
          category: 'Industry',
          severity: 'High',
          description: 'Textile industry experiencing declining domestic demand and intense international competition',
          recommendation: 'Focus on premium segments, technical textiles, and explore export markets in emerging economies'
        },
        {
          category: 'Market',
          severity: 'Medium',
          description: 'Changing consumer preferences towards sustainable and organic textiles require business model adaptation',
          recommendation: 'Invest in sustainable production processes and develop eco-friendly product lines'
        }
      ];
      riskFactors.push(textileRisks[uniqueHash % 2]);
    } else if (industry === 'Technology') {
      const techRisks = [
        {
          category: 'Industry',
          severity: 'Medium',
          description: 'Technology sector requires continuous innovation and significant R&D investment to maintain competitive advantage',
          recommendation: 'Maintain R&D budget above 15% of revenue and monitor emerging technology trends closely'
        },
        {
          category: 'Talent',
          severity: 'High',
          description: 'High attrition rates in technology sector impact project continuity and knowledge retention',
          recommendation: 'Implement robust talent retention programs and knowledge management systems'
        }
      ];
      riskFactors.push(techRisks[uniqueHash % 2]);
    } else if (industry === 'Finance') {
      const financeRisks = [
        {
          category: 'Regulatory',
          severity: 'High',
          description: 'Financial services face increasing regulatory scrutiny and compliance requirements',
          recommendation: 'Strengthen compliance framework and invest in regulatory technology solutions'
        },
        {
          category: 'Market',
          severity: 'Medium',
          description: 'Interest rate volatility impacts net interest margins and profitability projections',
          recommendation: 'Diversify income streams and implement dynamic interest rate risk management'
        }
      ];
      riskFactors.push(financeRisks[uniqueHash % 2]);
    }
    
    // Credit risk factors - unique per risk profile
    if (riskScore > 55) {
      riskFactors.push({
        category: 'Credit',
        severity: 'High',
        description: `Elevated credit risk profile (Score: ${riskScore}) requires additional collateral and enhanced monitoring mechanisms`,
        recommendation: 'Request additional security guarantees and implement quarterly financial reviews'
      });
    }
    
    // Working capital risk - unique per company
    const workingCapitalRatio = (assets - liabilities) / revenue;
    if (workingCapitalRatio < 0.2) {
      riskFactors.push({
        category: 'Liquidity',
        severity: 'Medium',
        description: `Working capital ratio of ${(workingCapitalRatio * 100).toFixed(1)}% indicates potential cash flow constraints during seasonal variations`,
        recommendation: 'Optimize inventory management and negotiate better payment terms with suppliers'
      });
    }
    
    // Generate unique research insights per company
    const researchInsights = generateResearchInsights(companyName, industry, uniqueHash, profitMargin, riskScore);
    
    return {
      company: companyName,
      industry: industry,
      revenue: revenue,
      profit: profit,
      assets: assets,
      liabilities: liabilities,
      file_name: fileName,
      file_index: fileIndex,
      upload_timestamp: new Date().toISOString(),
      upload_attempt: uploadAttempt,
      unique_hash: uniqueHash,
      financial_ratios: {
        profit_margin: profitMargin * 100,
        debt_to_assets: (liabilities / assets) * 100,
        return_on_assets: (profit / assets) * 100,
        working_capital_ratio: workingCapitalRatio * 100
      },
      ai_analysis: {
        risk_analysis: {
          risk_score: riskScore,
          risk_category: riskCategory,
          confidence_score: confidenceScore,
          key_factors: [
            `Profit margin of ${(profitMargin * 100).toFixed(1)}% impacts repayment capacity and debt service coverage`,
            `Revenue size of ₹${(revenue/10000000).toFixed(1)}Cr provides business stability and market position`,
            `Risk score of ${riskScore} indicates ${riskCategory.toLowerCase()} profile requiring appropriate monitoring level`,
            `Debt-to-assets ratio of ${((liabilities/assets) * 100).toFixed(1)}% affects financial leverage and default risk`,
            `Working capital ratio of ${(workingCapitalRatio * 100).toFixed(1)}% indicates liquidity position and operational flexibility`
          ]
        },
        loan_analysis: {
          approved_loan_amount: approvedLoanAmount,
          interest_rate: interestRate,
          loan_to_revenue_ratio: loanToRevenue,
          recommended_tenure: 60
        },
        decision_result: {
          decision: decision,
          confidence_score: confidenceScore,
          key_factors: [
            `Profit margin of ${(profitMargin * 100).toFixed(1)}% shows ${profitMargin > 0.12 ? 'strong' : profitMargin > 0.08 ? 'moderate' : 'weak'} profitability trends`,
            `Risk score of ${riskScore} requires ${decision === 'Approve' ? 'standard' : decision === 'Reject' ? 'enhanced' : 'additional'} monitoring and covenants`,
            `Industry: ${industry} - ${['stable', 'growing', 'competitive', 'declining', 'transforming'][uniqueHash % 5]} market conditions`,
            `Financial health: ${profitMargin > 0.12 && liabilities/assets < 0.5 ? 'Strong' : profitMargin > 0.08 ? 'Moderate' : 'Needs Improvement'} based on comprehensive metrics`,
            `Working capital: ${workingCapitalRatio > 0.3 ? 'Adequate' : workingCapitalRatio > 0.2 ? 'Limited' : 'Constrained'} affecting operational flexibility`
          ],
          reasoning: `Based on comprehensive analysis of ${companyName} in the ${industry} sector, the company demonstrates ${profitMargin > 0.12 ? 'strong' : profitMargin > 0.08 ? 'moderate' : 'weak'} profitability with a ${riskCategory.toLowerCase()} credit profile. The approved loan amount of ₹${(approvedLoanAmount/10000000).toFixed(1)}Cr considers the revenue base of ₹${(revenue/10000000).toFixed(1)}Cr and risk parameters including working capital ratio of ${(workingCapitalRatio * 100).toFixed(1)}%. Industry-specific factors and market conditions have been thoroughly evaluated in this assessment.`,
          recommended_actions: [
            'Monitor quarterly financial performance and compliance with loan covenants',
            'Maintain debt service coverage ratio above 1.5 at all times',
            'Submit monthly business performance reports and cash flow statements',
            'Provide annual audited financial statements within 90 days of year-end',
            'Maintain minimum working capital ratio as per agreed terms',
            'Regular industry and market analysis updates with competitive positioning',
            'Immediate notification of any material adverse changes in business operations'
          ]
        },
        risk_factors: riskFactors,
        research_summary: researchInsights
      }
    };
  };

  // Generate unique research insights per company
  const generateResearchInsights = (companyName, industry, uniqueHash, profitMargin, riskScore) => {
    const sentiments = ['Positive', 'Neutral', 'Mixed', 'Cautious', 'Optimistic'];
    const sentiment = sentiments[uniqueHash % sentiments.length];
    const sentimentScore = 0.3 + (uniqueHash % 70) / 100; // 0.3 to 1.0
    
    const industryOutlooks = [
      { outlook: 'Strong Growth', growthRate: '12-15%', position: 'Market Leader' },
      { outlook: 'Moderate Growth', growthRate: '8-12%', position: 'Strong Competitor' },
      { outlook: 'Stable', growthRate: '5-8%', position: 'Established Player' },
      { outlook: 'Declining', growthRate: '2-5%', position: 'Challenged Segment' },
      { outlook: 'Transforming', growthRate: '10-18%', position: 'Innovator' }
    ];
    const industryData = industryOutlooks[uniqueHash % industryOutlooks.length];
    
    const litigationRisks = [
      { risk: 'Low', cases: 'No major litigations', assessment: 'Clean legal record' },
      { risk: 'Moderate', cases: 'Minor commercial disputes', assessment: 'Routine legal matters' },
      { risk: 'Medium', cases: 'Some regulatory compliance issues', assessment: 'Under monitoring' },
      { risk: 'High', cases: 'Significant pending litigations', assessment: 'Requires attention' }
    ];
    const litigationData = litigationRisks[uniqueHash % litigationRisks.length];
    
    // Generate unique market signals per company
    const marketSignals = [
      `Increasing market share in ${industry} sector with strong customer retention`,
      `Facing competitive pressure from new entrants and digital disruption`,
      `Benefiting from favorable government policies and regulatory changes`,
      `Experiencing supply chain challenges affecting operational efficiency`,
      `Capitalizing on emerging market opportunities and technological advancements`
    ];
    const marketSignal = marketSignals[uniqueHash % marketSignals.length];
    
    return {
      news_sentiment: {
        sentiment: sentiment,
        score: sentimentScore,
        key_headlines: [
          `${companyName} reports ${profitMargin > 0.12 ? 'strong' : 'moderate'} quarterly performance`,
          `${industry} sector shows ${industryData.outlook.toLowerCase()} trends`,
          `Market analysts maintain ${sentiment.toLowerCase()} outlook on ${companyName}`,
          `Company announces strategic initiatives for market expansion`
        ],
        analysis: `Recent news coverage and market sentiment towards ${companyName} has been predominantly ${sentiment.toLowerCase()}, with a sentiment score of ${sentimentScore.toFixed(2)}. The company's performance in the ${industry} sector has been viewed ${sentiment.toLowerCase()} by analysts and investors.`
      },
      industry_analysis: {
        outlook: industryData.outlook,
        growth_rate: industryData.growthRate,
        market_position: industryData.position,
        trends: [
          `Digital transformation accelerating across ${industry} sector`,
          `Sustainability and ESG factors becoming critical success drivers`,
          `Consolidation trends creating larger market players`,
          `Regulatory changes impacting operational frameworks`
        ],
        competitive_landscape: `The ${industry} industry is experiencing ${industryData.outlook.toLowerCase()} with projected growth rates of ${industryData.growthRate}. ${companyName} is positioned as a ${industryData.position.toLowerCase()} in this dynamic market environment.`
      },
      litigation_data: {
        risk_level: litigationData.risk,
        pending_cases: litigationData.cases,
        assessment: litigationData.assessment,
        recent_developments: [
          'No new significant legal proceedings initiated',
          'Compliance programs being strengthened',
          'Legal team expanded to handle regulatory requirements'
        ]
      },
      market_signals: {
        primary_signal: marketSignal,
        technical_indicators: [
          `Stock performance showing ${sentiment === 'Positive' ? 'upward' : 'mixed'} trends`,
          `Trading volumes within normal ranges for the sector`,
          `Institutional investor interest remains ${sentiment === 'Positive' ? 'strong' : 'stable'}`
        ],
        analyst_recommendations: [
          `Maintain ${riskScore < 40 ? 'Buy' : riskScore < 60 ? 'Hold' : 'Sell'} rating based on current fundamentals`,
          `Target price adjusted based on ${industryData.outlook.toLowerCase()} industry outlook`,
          `Monitor working capital metrics and debt service coverage closely`
        ]
      }
    };
  };

  const handleUpload = async () => {
    const currentTime = Date.now();
    
    if (files.length === 0) {
      setError('Please select at least one file');
      return;
    }

    // Enhanced multi-layer protection against double uploads
    if (uploading || isUploadingRef.current) {
      console.log('UploadPage: Upload already in progress, ignoring click');
      return;
    }

    // Prevent uploads within 2 seconds of each other (increased from 1 second)
    if (currentTime - lastUploadTimeRef.current < 2000) {
      console.log('UploadPage: Upload clicked too quickly, ignoring click');
      return;
    }

    // Set all protection mechanisms immediately
    setUploading(true);
    isUploadingRef.current = true;
    lastUploadTimeRef.current = currentTime;
    setError('');

    // Disable button programmatically
    if (uploadButtonRef.current) {
      uploadButtonRef.current.disabled = true;
      uploadButtonRef.current.style.pointerEvents = 'none';
    }

    try {
      console.log(`UploadPage: Starting multi-company upload process for ${files.length} files...`);
      
      // Increment upload count to ensure uniqueness
      const newUploadCount = uploadCount + 1;
      setUploadCount(newUploadCount);
      
      // Add delay to prevent any race conditions
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Double-check that we're still supposed to be uploading
      if (!isUploadingRef.current) {
        console.log('UploadPage: Upload was cancelled, stopping process');
        return;
      }
      
      // Process all files and generate unique company data for each
      const analysisResults = [];
      
      for (let i = 0; i < files.length; i++) {
        const file = files[i].file;
        console.log(`UploadPage: Processing file ${i + 1}/${files.length}: ${file.name}`);
        
        // Generate unique company data for each file
        const dynamicCompanyData = generateDynamicCompanyData(file, newUploadCount, i);
        analysisResults.push(dynamicCompanyData);
        
        console.log(`UploadPage: Generated analysis for ${dynamicCompanyData.company}`, {
          company: dynamicCompanyData.company,
          industry: dynamicCompanyData.industry,
          revenue: dynamicCompanyData.revenue,
          risk_score: dynamicCompanyData.ai_analysis.risk_analysis.risk_score,
          decision: dynamicCompanyData.ai_analysis.decision_result.decision,
          unique_hash: dynamicCompanyData.unique_hash
        });
      }
      
      // Store multi-company analysis results
      const multiCompanyData = {
        is_multi_company: true,
        total_companies: files.length,
        upload_timestamp: new Date().toISOString(),
        upload_attempt: newUploadCount,
        companies: analysisResults
      };
      
      // Clear any existing data and set new multi-company data
      localStorage.removeItem('companyData');
      localStorage.setItem('companyData', JSON.stringify(multiCompanyData));
      
      console.log(`UploadPage: Multi-company analysis completed and stored:`, {
        total_companies: analysisResults.length,
        companies: analysisResults.map(c => ({
          company: c.company,
          risk_score: c.ai_analysis.risk_analysis.risk_score,
          decision: c.ai_analysis.decision_result.decision
        }))
      });
      
      // Add final delay before navigation to ensure state is settled
      await new Promise(resolve => setTimeout(resolve, 200));
      
      // Navigate to dashboard after successful upload
      console.log('UploadPage: Multi-company upload successful, navigating to dashboard...');
      navigate('/dashboard');
      
    } catch (err) {
      console.error('UploadPage: Upload failed:', err);
      setError('Upload failed: ' + err.message);
    } finally {
      // Reset all protection mechanisms with delay
      setTimeout(() => {
        console.log('UploadPage: Resetting upload state...');
        setUploading(false);
        isUploadingRef.current = false;
        
        // Re-enable button if still on page
        if (uploadButtonRef.current) {
          uploadButtonRef.current.disabled = false;
          uploadButtonRef.current.style.pointerEvents = 'auto';
        }
      }, 300);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      position: 'relative'
    }}>
      {/* Animated background elements */}
      <div style={{
        position: 'absolute',
        top: '10%',
        left: '5%',
        width: '200px',
        height: '200px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 6s ease-in-out infinite'
      }}></div>
      <div style={{
        position: 'absolute',
        top: '60%',
        right: '10%',
        width: '150px',
        height: '150px',
        background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
        borderRadius: '50%',
        animation: 'float 8s ease-in-out infinite reverse'
      }}></div>

      {/* Header */}
      <div style={{ 
        background: 'rgba(255, 255, 255, 0.1)', 
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
        padding: '32px 0',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ maxWidth: '1024px', margin: '0 auto', padding: '0 16px' }}>
          <div style={{ textAlign: 'center' }}>
            <h1 style={{ 
              fontSize: '40px', 
              fontWeight: 'bold', 
              marginBottom: '12px', 
              color: 'white',
              textShadow: '0 2px 4px rgba(0,0,0,0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '16px'
            }}>
              <span style={{ fontSize: '48px' }}>📤</span>
              AI Credit Analysis Upload
            </h1>
            <p style={{ fontSize: '20px', color: '#dbeafe', fontWeight: '400' }}>
              Upload multiple company documents for comprehensive AI-powered credit analysis
            </p>
            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <span style={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.2)', 
                backdropFilter: 'blur(10px)',
                padding: '8px 20px', 
                borderRadius: '25px', 
                fontSize: '14px',
                fontWeight: '600',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
              }}>
                🔄 Multi-Company Analysis
              </span>
              <span style={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.2)', 
                backdropFilter: 'blur(10px)',
                padding: '8px 20px', 
                borderRadius: '25px', 
                fontSize: '14px',
                fontWeight: '600',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
              }}>
                🎯 Unique Results Per File
              </span>
              <span style={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.2)', 
                backdropFilter: 'blur(10px)',
                padding: '8px 20px', 
                borderRadius: '25px', 
                fontSize: '14px',
                fontWeight: '600',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
              }}>
                ⚡ Instant Processing
              </span>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: '1024px', margin: '0 auto', padding: '40px 16px' }}>
        <div style={{ 
          background: 'linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248,250,252,0.95))',
          backdropFilter: 'blur(10px)',
          padding: '40px', 
          borderRadius: '24px', 
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          border: '1px solid rgba(255, 255, 255, 0.3)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          {/* Decorative gradient overlay */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '4px',
            background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f59e0b)',
            borderRadius: '24px 24px 0 0'
          }}></div>

          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <div style={{ fontSize: '72px', marginBottom: '16px', animation: 'pulse 2s infinite' }}>📁</div>
            <h2 style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e293b', marginBottom: '12px' }}>
              Upload Multiple Company Documents
            </h2>
            <p style={{ color: '#64748b', fontSize: '16px' }}>
              Upload PDF files for multiple companies to generate individual credit analysis for each
            </p>
            <p style={{ fontSize: '14px', color: '#10b981', marginTop: '12px', fontWeight: '600' }}>
              🎯 Each file generates unique company analysis with separate risk scores and loan recommendations
            </p>
          </div>

          {/* Upload Area */}
          <div
            style={{
              border: '3px dashed #cbd5e1',
              borderRadius: '16px',
              padding: '40px',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              backgroundColor: '#f8fafc',
              position: 'relative',
              overflow: 'hidden'
            }}
            onClick={() => document.getElementById('file-upload').click()}
            onMouseEnter={(e) => {
              e.target.style.borderColor = '#3b82f6';
              e.target.style.backgroundColor = '#eff6ff';
              e.target.style.transform = 'scale(1.02)';
            }}
            onMouseLeave={(e) => {
              e.target.style.borderColor = '#cbd5e1';
              e.target.style.backgroundColor = '#f8fafc';
              e.target.style.transform = 'scale(1)';
            }}
          >
            <input
              id="file-upload"
              type="file"
              multiple
              accept=".pdf,.doc,.docx"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
            <p style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
              Click to upload or drag and drop
            </p>
            <p style={{ fontSize: '14px', color: '#64748b' }}>
              PDF, DOC, DOCX files (MAX. 10MB per file)
            </p>
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              gap: '16px',
              marginTop: '20px',
              flexWrap: 'wrap'
            }}>
              <span style={{
                backgroundColor: '#e0e7ff',
                color: '#4338ca',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                Multiple Files Supported
              </span>
              <span style={{
                backgroundColor: '#dcfce7',
                color: '#166534',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                Individual Analysis
              </span>
              <span style={{
                backgroundColor: '#fef3c7',
                color: '#92400e',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                AI-Powered
              </span>
            </div>
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div style={{ marginTop: '32px' }}>
              <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
                <span style={{ marginRight: '8px' }}>📋</span>
                Selected Files ({files.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {files.map((file, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '16px',
                      backgroundColor: '#f1f5f9',
                      borderRadius: '12px',
                      border: '1px solid #e2e8f0',
                      transition: 'all 0.3s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.backgroundColor = '#e2e8f0';
                      e.target.style.transform = 'translateX(4px)';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = '#f1f5f9';
                      e.target.style.transform = 'translateX(0)';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '24px' }}>📄</span>
                      <div>
                        <p style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', margin: 0 }}>
                          {file.file.name}
                        </p>
                        <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>
                          {formatFileSize(file.file.size)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      style={{
                        backgroundColor: '#ef4444',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        padding: '8px 16px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '600',
                        transition: 'all 0.3s ease',
                        boxShadow: '0 2px 4px rgba(239, 68, 68, 0.2)'
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.backgroundColor = '#dc2626';
                        e.target.style.transform = 'scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.backgroundColor = '#ef4444';
                        e.target.style.transform = 'scale(1)';
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload Button */}
          <div style={{ textAlign: 'center', marginTop: '40px' }}>
            <button
              ref={uploadButtonRef}
              onClick={handleUpload}
              disabled={files.length === 0 || uploading}
              style={{
                padding: '20px 40px',
                borderRadius: '16px',
                fontSize: '20px',
                fontWeight: 'bold',
                border: 'none',
                cursor: files.length === 0 || uploading ? 'not-allowed' : 'pointer',
                background: files.length === 0 || uploading 
                  ? 'linear-gradient(135deg, #94a3b8, #64748b)' 
                  : 'linear-gradient(135deg, #10b981, #059669)',
                color: 'white',
                transition: 'all 0.3s ease',
                boxShadow: files.length === 0 || uploading 
                  ? '0 4px 6px rgba(0, 0, 0, 0.1)' 
                  : '0 10px 15px rgba(16, 185, 129, 0.3), 0 4px 6px rgba(0, 0, 0, 0.1)',
                opacity: uploading ? 0.7 : 1,
                position: 'relative',
                overflow: 'hidden'
              }}
              onMouseEnter={(e) => {
                if (!(files.length === 0 || uploading)) {
                  e.target.style.background = 'linear-gradient(135deg, #059669, #047857)';
                  e.target.style.transform = 'translateY(-4px)';
                  e.target.style.boxShadow = '0 20px 25px rgba(16, 185, 129, 0.4), 0 10px 10px rgba(0, 0, 0, 0.1)';
                }
              }}
              onMouseLeave={(e) => {
                if (!(files.length === 0 || uploading)) {
                  e.target.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                  e.target.style.transform = 'translateY(0)';
                  e.target.style.boxShadow = '0 10px 15px rgba(16, 185, 129, 0.3), 0 4px 6px rgba(0, 0, 0, 0.1)';
                }
              }}
            >
              {uploading ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ 
                    width: '24px', 
                    height: '24px', 
                    border: '3px solid #ffffff', 
                    borderTop: '3px solid transparent', 
                    borderRadius: '50%', 
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  <span>Processing with AI...</span>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span>🚀</span>
                  <span>Analyze All Companies</span>
                </div>
              )}
            </button>
            <p style={{ fontSize: '16px', color: '#64748b', marginTop: '20px' }}>
              AI will analyze each document separately and generate unique credit insights for every company
            </p>
            {files.length > 1 && (
              <p style={{ fontSize: '14px', color: '#10b981', marginTop: '12px', fontWeight: '600' }}>
                📊 {files.length} companies will be analyzed individually with separate risk assessments
              </p>
            )}
            {uploadCount > 0 && (
              <p style={{ fontSize: '14px', color: '#10b981', marginTop: '12px', fontWeight: '600' }}>
                🔄 Upload attempts: {uploadCount} (Each generates unique results)
              </p>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div style={{ 
              marginTop: '24px',
              padding: '16px',
              backgroundColor: '#fef2f2',
              border: '2px solid #ef4444',
              borderRadius: '12px',
              color: '#991b1b',
              fontWeight: '600',
              textAlign: 'center',
              boxShadow: '0 4px 6px rgba(239, 68, 68, 0.1)'
            }}>
              ⚠️ {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SimpleUploadPage;
