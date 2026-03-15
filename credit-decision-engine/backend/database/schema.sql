-- Credit Decision Engine Database Schema

-- Companies table
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    business_nature VARCHAR(255),
    years_in_operation INTEGER,
    sector VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial data table
CREATE TABLE financial_data (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    revenue DECIMAL(20,2),
    existing_loans DECIMAL(20,2),
    liabilities DECIMAL(20,2),
    litigation DECIMAL(20,2),
    gst_revenue DECIMAL(20,2),
    assets DECIMAL(20,2),
    profit DECIMAL(20,2),
    document_type VARCHAR(100),
    filename VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk analysis table
CREATE TABLE risk_analysis (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    risk_score DECIMAL(5,2),
    risk_category VARCHAR(50),
    component_scores TEXT, -- JSON string
    risk_factors TEXT, -- JSON string
    confidence_level VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Research data table
CREATE TABLE research_data (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    promoter_risk VARCHAR(20),
    sector_outlook VARCHAR(20),
    litigation_cases INTEGER,
    news_sentiment VARCHAR(20),
    news_articles TEXT, -- JSON string
    confidence_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recommendations table
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    decision VARCHAR(50),
    loan_limit DECIMAL(20,2),
    interest_rate DECIMAL(5,2),
    tenure_months INTEGER,
    conditions TEXT, -- JSON string
    explanations TEXT, -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CAM documents table
CREATE TABLE cam_documents (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    filename VARCHAR(255),
    word_path VARCHAR(500),
    pdf_path VARCHAR(500),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Credit officer input table
CREATE TABLE credit_officer_input (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    factory_utilization DECIMAL(5,2),
    management_quality VARCHAR(20),
    inventory_turnover VARCHAR(20),
    customer_concentration VARCHAR(20),
    industry_experience DECIMAL(5,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs table
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    user_id VARCHAR(100),
    action VARCHAR(100),
    details TEXT, -- JSON string
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX idx_companies_name ON companies(name);
CREATE INDEX idx_financial_data_company_id ON financial_data(company_id);
CREATE INDEX idx_risk_analysis_company_id ON risk_analysis(company_id);
CREATE INDEX idx_research_data_company_id ON research_data(company_id);
CREATE INDEX idx_recommendations_company_id ON recommendations(company_id);
CREATE INDEX idx_cam_documents_company_id ON cam_documents(company_id);
CREATE INDEX idx_credit_officer_input_company_id ON credit_officer_input(company_id);
CREATE INDEX idx_audit_logs_company_id ON audit_logs(company_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER update_companies_updated_at 
    BEFORE UPDATE ON companies 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
