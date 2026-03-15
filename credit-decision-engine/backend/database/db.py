from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/credit_decision_db")

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Models
class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    business_nature = Column(String)
    years_in_operation = Column(Integer)
    sector = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FinancialData(Base):
    __tablename__ = "financial_data"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    revenue = Column(Float)
    existing_loans = Column(Float)
    liabilities = Column(Float)
    litigation = Column(Float)
    gst_revenue = Column(Float)
    assets = Column(Float)
    profit = Column(Float)
    document_type = Column(String)
    filename = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class RiskAnalysis(Base):
    __tablename__ = "risk_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    risk_score = Column(Float)
    risk_category = Column(String)
    component_scores = Column(Text)  # JSON string
    risk_factors = Column(Text)  # JSON string
    confidence_level = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ResearchData(Base):
    __tablename__ = "research_data"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    promoter_risk = Column(String)
    sector_outlook = Column(String)
    litigation_cases = Column(Integer)
    news_sentiment = Column(String)
    news_articles = Column(Text)  # JSON string
    confidence_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    decision = Column(String)
    loan_limit = Column(Float)
    interest_rate = Column(Float)
    tenure_months = Column(Integer)
    conditions = Column(Text)  # JSON string
    explanations = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class CAMDocument(Base):
    __tablename__ = "cam_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    filename = Column(String)
    word_path = Column(String)
    pdf_path = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)
    
class CreditOfficerInput(Base):
    __tablename__ = "credit_officer_input"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    factory_utilization = Column(Float)
    management_quality = Column(String)
    inventory_turnover = Column(String)
    customer_concentration = Column(String)
    industry_experience = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, index=True)
    user_id = Column(String)
    action = Column(String)
    details = Column(Text)  # JSON string
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)
