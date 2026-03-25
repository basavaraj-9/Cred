from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
from typing import List, Optional, Dict, Any
import os

from routes.upload import router as upload_router
from routes.risk import router as risk_router
from routes.research import router as research_router
from routes.cam import router as cam_router
from services.document_parser import DocumentParser
from services.gst_bank_analyzer import GSTBankAnalyzer
from services.risk_engine import RiskEngine
from services.recommendation_engine import RecommendationEngine
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Credit Decisioning Engine",
    description="Production-grade credit decisioning system with AI-powered risk assessment",
    version="1.0.0"
)

# Initialize services
doc_parser = DocumentParser()
bank_analyzer = GSTBankAnalyzer()
risk_engine = RiskEngine()
recommendation_engine = RecommendationEngine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/upload")
async def simple_upload(files: List[UploadFile] = File(...)):
    """Real upload endpoint that parses documents and runs the analytical engines"""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
            
        file = files[0]
        content = await file.read()
        
        # 1. Parse Document
        extracted_data = await doc_parser.parse_document(
            content, 
            file.content_type, 
            file.filename
        )
        
        # 2. Run Risk Analysis
        # Explicitly cast to float to ensure math safety
        financial_data = {
            'revenue': float(extracted_data.get('revenue', 0)),
            'profit': float(extracted_data.get('profit', 0)),
            'assets': float(extracted_data.get('assets', 0)),
            'liabilities': float(extracted_data.get('liabilities', 0)),
            'existing_loans': float(extracted_data.get('existing_loans', 0)),
            'industry': extracted_data.get('industry', 'Manufacturing')
        }
        
        risk_result = risk_engine.calculate_risk_score(
            financial_data=financial_data,
            consistency_analysis={}, 
            research_data={'industry': financial_data['industry']}
        )
        
        # 3. Generate Recommendation
        rec_result = recommendation_engine.generate_recommendation(
            risk_score=risk_result['risk_score'],
            risk_category=risk_result['risk_category'],
            financial_data=financial_data,
            component_scores=risk_result['component_scores']
        )
        
        # 4. Map to UI format
        def fmt_m(val):
            return f"{val / 1000000:.1f}M"

        response_data = {
            "company": extracted_data.get('company') or "Extracted Entity",
            "industry": financial_data['industry'],
            "revenue": financial_data['revenue'],
            "file_name": file.filename,
            "is_multi_company": False,
            "ai_analysis": {
                "risk_analysis": {
                    "risk_score": risk_result['risk_score'],
                    "risk_category": risk_result['risk_category'].upper()
                },
                "decision_result": {
                    "decision": rec_result['decision'].upper().replace(' ', '_'),
                    "confidence_score": 0.85 if risk_result['confidence_level'] == 'High' else 0.7
                },
                "loan_analysis": {
                    "approved_loan_amount": rec_result['loan_limit'],
                    "interest_rate": rec_result['interest_rate'],
                    "recommended_tenure": rec_result['tenure_months']
                },
                "risk_factors": [
                    {"factor": f, "description": "System identified risk", "severity": "medium"}
                    for f in risk_result['risk_factors'][:3]
                ]
            },
            "financial_metrics": {
                "annual_revenue": financial_data['revenue'],
                "monthly_revenue": fmt_m(financial_data['revenue'] / 12),
                "monthly_profit": fmt_m(financial_data['profit'] / 12),
                "total_assets": fmt_m(financial_data['assets']),
                "total_liabilities": fmt_m(financial_data['liabilities']),
                "equity": fmt_m(financial_data['assets'] - financial_data['liabilities']),
                "cash_flow": fmt_m(financial_data['profit'] / 12 * 0.8),
                "debt_to_equity_ratio": round(financial_data['existing_loans'] / max(1.0, (financial_data['assets'] - financial_data['liabilities'])), 2),
                "current_ratio": 1.5,
                "profit_margin": f"{(financial_data['profit'] / max(1.0, financial_data['revenue'])) * 100:.1f}%",
            },
            "loan_affordability": {
                "max_loan_amount": fmt_m(rec_result['loan_limit']),
                "interest_rate": f"{rec_result['interest_rate']}%",
                "loan_term_months": rec_result['tenure_months'],
                "affordability_score": int(100 - risk_result['risk_score']),
            },
            "liabilities_breakdown": {
                "accounts_payable": fmt_m(financial_data['liabilities'] * 0.3),
                "long_term_bank_loans": fmt_m(financial_data['existing_loans']),
                "other_current_liabilities": fmt_m(financial_data['liabilities'] * 0.1),
            },
            "upload_timestamp": datetime.now().isoformat()
        }
        
        return {"status": "success", "message": "Successfully analyzed document", "data": response_data}
    except Exception as e:
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/test-data")
async def get_test_data():
    """Deterministic test data endpoint using real analytical engines on a static profile"""
    try:
        # 1. Static Profile: High-Growth Healthy Tech SME
        financial_data = {
            'revenue': 120000000,      # 12 Cr
            'profit': 18000000,        # 1.8 Cr (15% margin)
            'assets': 85000000,        # 8.5 Cr
            'liabilities': 30000000,   # 3.0 Cr
            'existing_loans': 15000000, # 1.5 Cr
            'industry': 'Technology'
        }
        
        # 2. Run Engines
        risk_result = risk_engine.calculate_risk_score(
            financial_data=financial_data,
            consistency_analysis={'consistency_score': 95.0, 'anomalies': []},
            research_data={'industry': 'Technology', 'news_sentiment': 'Positive'}
        )
        
        rec_result = recommendation_engine.generate_recommendation(
            risk_score=risk_result['risk_score'],
            risk_category=risk_result['risk_category'],
            financial_data=financial_data,
            component_scores=risk_result['component_scores']
        )
        
        def fmt_m(val):
            return f"{val / 1000000:.1f}M"

        # 3. Map to UI format
        test_data = {
            "company": "Crystal Tech Solutions Ltd",
            "industry": "Technology",
            "revenue": financial_data['revenue'],
            "file_name": "annual_report_2024.pdf",
            "is_multi_company": False,
            "ai_analysis": {
                "risk_analysis": {
                    "risk_score": risk_result['risk_score'],
                    "risk_category": risk_result['risk_category'].upper()
                },
                "decision_result": {
                    "decision": rec_result['decision'].upper().replace(' ', '_'),
                    "confidence_score": 0.92
                },
                "loan_analysis": {
                    "approved_loan_amount": rec_result['loan_limit'],
                    "interest_rate": rec_result['interest_rate'],
                    "recommended_tenure": rec_result['tenure_months']
                },
                "risk_factors": [
                    {"factor": f, "description": "Analysis insight", "severity": "low"}
                    for f in risk_result['risk_factors'][:3]
                ]
            },
            "financial_metrics": {
                "annual_revenue": financial_data['revenue'],
                "monthly_revenue": fmt_m(financial_data['revenue'] / 12),
                "monthly_profit": fmt_m(financial_data['profit'] / 12),
                "total_assets": fmt_m(financial_data['assets']),
                "total_liabilities": fmt_m(financial_data['liabilities']),
                "equity": fmt_m(financial_data['assets'] - financial_data['liabilities']),
                "cash_flow": fmt_m(financial_data['profit'] / 12 * 0.85),
                "debt_to_equity_ratio": 0.27,
                "current_ratio": 2.1,
                "profit_margin": "15.0%",
            },
            "loan_affordability": {
                "max_loan_amount": fmt_m(rec_result['loan_limit']),
                "interest_rate": f"{rec_result['interest_rate']}%",
                "loan_term_months": rec_result['tenure_months'],
                "affordability_score": 88,
            },
            "liabilities_breakdown": {
                "accounts_payable": "4.5M",
                "short_term_debt": "2.0M",
                "long_term_bank_loans": "15.0M",
            },
            "bank_analysis": {
                "transactions": [
                    {"date": "2024-03-01", "description": "CLIENT_PAYMENT_A", "amount": 2500000, "type": "credit"},
                    {"date": "2024-03-05", "description": "AWS_INFRA_FEES", "amount": 400000, "type": "debit"},
                    {"date": "2024-03-10", "description": "SALARY_OUT_MARCH", "amount": 1200000, "type": "debit"},
                    {"date": "2024-03-15", "description": "OFFICE_RENT", "amount": 350000, "type": "debit"},
                    {"date": "2024-03-20", "description": "CLIENT_PAYMENT_B", "amount": 1800000, "type": "credit"},
                ],
                "counterparty_risk": {
                    "risk_level": "Low", 
                    "description": "Healthy diversification across multiple blue-chip clients. No single counterparty dependency found.",
                    "top_counterparties": [
                        ["Global Exports", 4500000],
                        ["Apex Solutions", 3200000],
                        ["Nexus IT", 2800000]
                    ]
                },
                "debt_service_ratio": {
                    "value": 0.12, 
                    "status": "Healthy",
                    "monthly_average_inflow": 4300000,
                    "monthly_debt_obligations": 516000
                }
            },
            "upload_timestamp": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "message": "Deterministic test data generated",
            "data": test_data
        }
    except Exception as e:
        logger.error(f"Test data generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(risk_router, prefix="/api", tags=["risk"])
app.include_router(research_router, prefix="/api", tags=["research"])
app.include_router(cam_router, prefix="/api", tags=["cam"])

@app.get("/")
async def root():
    return {"message": "AI Credit Decisioning Engine API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
