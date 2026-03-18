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

app = FastAPI(
    title="AI Credit Decisioning Engine",
    description="Production-grade credit decisioning system with AI-powered risk assessment",
    version="1.0.0"
)

# Initialize services
doc_parser = DocumentParser()
bank_analyzer = GSTBankAnalyzer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def simple_upload(files: List[UploadFile] = File(...)):
    """Simple upload endpoint that returns dynamic mock data"""
    try:
        import hashlib
        import time
        
        # Generate dynamic data based on timestamp
        timestamp = str(int(time.time()))
        hash_seed = int(hashlib.md5(timestamp.encode()).hexdigest()[:8], 16)
        
        # Get actual filename from uploaded file
        actual_filename = files[0].filename if files else "document.pdf"
        
        # Extract company name from filename (remove extension and clean up)
        company_name = actual_filename
        if '.' in company_name:
            company_name = company_name.rsplit('.', 1)[0]  # Remove extension
        company_name = company_name.replace('_', ' ').replace('-', ' ')  # Replace separators with spaces
        company_name = company_name.title()  # Capitalize words
        
        # If filename is too generic, use a meaningful name
        if len(company_name) < 3 or company_name.lower() in ['document', 'file', 'pdf']:
            company_name = f"Company {hash_seed % 1000}"
        
        # Dynamic financial calculations
        base_revenue = 50000000 + (hash_seed % 10000000)  # 5Cr to 15Cr
        monthly_revenue = base_revenue / 12
        monthly_profit = monthly_revenue * (0.08 + (hash_seed % 100) / 1000)  # 8-18% profit margin
        total_liabilities = base_revenue * (0.3 + (hash_seed % 100) / 1000)  # 30-40% of revenue
        equity = base_revenue * (0.6 + (hash_seed % 100) / 1000)  # 60-70% of revenue
        
        # Dynamic loan calculations
        risk_score = 60 + (hash_seed % 30)  # 60-90 risk score
        loan_multiplier = 0.2 + (risk_score / 500)  # Higher risk = higher loan multiplier
        approved_loan_amount = int(base_revenue * loan_multiplier)
        interest_rate = 10 + (100 - risk_score) / 20  # Lower risk = lower interest
        
        def fmt_m(val):
            """Format a rupee value as 'X.XM' string."""
            return f"{val / 1000000:.1f}M"

        # Create dynamic company data
        mock_company_data = {
            "company": company_name,
            "industry": ["Technology", "Manufacturing", "Healthcare", "Retail", "Finance"][hash_seed % 5],
            # raw rupees — frontend divides by 10_000_000 to get Crores
            "revenue": base_revenue,
            "file_name": actual_filename,
            "is_multi_company": False,
            "ai_analysis": {
                "risk_analysis": {
                    "risk_score": risk_score,
                    "risk_category": "LOW" if risk_score >= 80 else "MEDIUM" if risk_score >= 65 else "HIGH"
                },
                "decision_result": {
                    "decision": "APPROVED" if risk_score >= 75 else "CONDITIONALLY_APPROVED" if risk_score >= 60 else "REJECTED",
                    "confidence_score": round(0.7 + (risk_score / 300), 2)
                },
                "loan_analysis": {
                    "approved_loan_amount": approved_loan_amount,
                    "interest_rate": round(interest_rate, 1),
                    "recommended_tenure": 36 + (hash_seed % 48)
                },
                "risk_factors": [
                    {
                        "factor": "Market Volatility",
                        "description": f"Industry risk level: {risk_score / 10:.1f}/10",
                        "severity": "low" if risk_score >= 80 else "medium" if risk_score >= 65 else "high"
                    },
                    {
                        "factor": "Debt Service Coverage",
                        "description": f"DSCR ratio: {monthly_profit / (approved_loan_amount / 60):.2f}",
                        "severity": "low" if monthly_profit > approved_loan_amount / 50 else "medium"
                    },
                    {
                        "factor": "Liquidity Position",
                        "description": f"Current ratio: {(equity / total_liabilities):.2f}",
                        "severity": "low" if equity > total_liabilities else "medium"
                    }
                ]
            },
            # financial_metrics with formatted strings expected by ModernDashboard
            "financial_metrics": {
                "annual_revenue": base_revenue,
                "monthly_revenue": fmt_m(monthly_revenue),
                "monthly_profit": fmt_m(monthly_profit),
                "total_assets": fmt_m(base_revenue * 1.3),
                "total_liabilities": fmt_m(total_liabilities),
                "equity": fmt_m(equity),
                "cash_flow": fmt_m(monthly_profit * 0.8),
                "debt_to_equity_ratio": round(total_liabilities / equity, 2),
                "current_ratio": round(equity / total_liabilities * 1.2, 2),
                "profit_margin": f"{(monthly_profit / monthly_revenue) * 100:.1f}%",
            },
            # loan_affordability block expected by Max Loan Amount card
            "loan_affordability": {
                "max_loan_amount": fmt_m(approved_loan_amount),
                "interest_rate": f"{round(interest_rate, 1)}%",
                "loan_term_months": 36 + (hash_seed % 48),
                "affordability_score": min(95, int(risk_score * 1.1)),
            },
            # liabilities_breakdown block expected by Liabilities Breakdown card
            "liabilities_breakdown": {
                "accounts_payable": fmt_m(total_liabilities * 0.25),
                "short_term_debt": fmt_m(total_liabilities * 0.20),
                "accrued_expenses": fmt_m(total_liabilities * 0.15),
                "long_term_bank_loans": fmt_m(total_liabilities * 0.30),
                "bonds_payable": fmt_m(total_liabilities * 0.05),
                "other_current_liabilities": fmt_m(total_liabilities * 0.05),
            },
            # Phase 2: Advanced Document Intelligence
            "bank_analysis": {
                "transactions": [
                    {"date": "2024-03-01", "description": "VENDOR_PAYMENT_ABC", "amount": 450000, "type": "debit"},
                    {"date": "2024-03-05", "description": "REVENUE_CLIENT_X", "amount": 1200000, "type": "credit"},
                    {"date": "2024-03-10", "description": "SALARY_BATCH_01", "amount": 800000, "type": "debit"},
                    {"date": "2024-03-15", "description": "LOAN_EMI_BANK_Y", "amount": 200000, "type": "debit"},
                    {"date": "2024-03-20", "description": "REVENUE_CLIENT_Y", "amount": 950000, "type": "credit"},
                ],
                "counterparty_risk": {
                    "risk_level": "Low",
                    "description": "Diversified counterparties; no significant related-party concentration.",
                    "top_counterparties": [("CLIENT_X", 1200000), ("CLIENT_Y", 950000)]
                },
                "debt_service_ratio": {
                    "value": 0.25,
                    "status": "Healthy",
                    "monthly_debt_obligations": 200000,
                    "monthly_average_inflow": 1100000
                }
            },
            "upload_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        return {
            "status": "success",
            "message": "Successfully uploaded files",
            "data": mock_company_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/test-data")
async def get_test_data():
    """Test endpoint to return sample data without file upload"""
    import hashlib
    import time
    
    timestamp = str(int(time.time()))
    hash_seed = int(hashlib.md5(timestamp.encode()).hexdigest()[:8], 16)
    
    # Same calculations as main upload
    base_revenue = 50000000 + (hash_seed % 10000000)
    monthly_revenue = base_revenue / 12
    monthly_profit = monthly_revenue * (0.08 + (hash_seed % 100) / 1000)
    total_liabilities = base_revenue * (0.3 + (hash_seed % 100) / 1000)
    equity = base_revenue * (0.6 + (hash_seed % 100) / 1000)
    risk_score = 60 + (hash_seed % 30)
    loan_multiplier = 0.2 + (risk_score / 500)
    approved_loan_amount = int(base_revenue * loan_multiplier)
    interest_rate = 10 + (100 - risk_score) / 20
    
    def fmt_m(val):
        return f"{val / 1000000:.1f}M"

    test_data = {
        "company": "Test Company",
        "industry": "Technology",
        "revenue": base_revenue,
        "file_name": "test_document.pdf",
        "is_multi_company": False,
        "ai_analysis": {
            "risk_analysis": {
                "risk_score": risk_score,
                "risk_category": "LOW" if risk_score >= 80 else "MEDIUM" if risk_score >= 65 else "HIGH"
            },
            "decision_result": {
                "decision": "APPROVED" if risk_score >= 75 else "CONDITIONALLY_APPROVED" if risk_score >= 60 else "REJECTED",
                "confidence_score": round(0.7 + (risk_score / 300), 2)
            },
            "loan_analysis": {
                "approved_loan_amount": approved_loan_amount,
                "interest_rate": round(interest_rate, 1),
                "recommended_tenure": 36 + (hash_seed % 48)
            },
            "risk_factors": [
                {
                    "factor": "Market Volatility",
                    "description": f"Industry risk level: {risk_score / 10:.1f}/10",
                    "severity": "low" if risk_score >= 80 else "medium" if risk_score >= 65 else "high"
                }
            ]
        },
        "financial_metrics": {
            "annual_revenue": base_revenue,
            "monthly_revenue": fmt_m(monthly_revenue),
            "monthly_profit": fmt_m(monthly_profit),
            "total_assets": fmt_m(base_revenue * 1.3),
            "total_liabilities": fmt_m(total_liabilities),
            "equity": fmt_m(equity),
            "cash_flow": fmt_m(monthly_profit * 0.8),
            "debt_to_equity_ratio": round(total_liabilities / equity, 2),
            "current_ratio": round(equity / total_liabilities * 1.2, 2),
            "profit_margin": f"{(monthly_profit / monthly_revenue) * 100:.1f}%",
        },
        "loan_affordability": {
            "max_loan_amount": fmt_m(approved_loan_amount),
            "interest_rate": f"{round(interest_rate, 1)}%",
            "loan_term_months": 36 + (hash_seed % 48),
            "affordability_score": min(95, int(risk_score * 1.1)),
        },
        "liabilities_breakdown": {
            "accounts_payable": fmt_m(total_liabilities * 0.25),
            "short_term_debt": fmt_m(total_liabilities * 0.20),
            "accrued_expenses": fmt_m(total_liabilities * 0.15),
            "long_term_bank_loans": fmt_m(total_liabilities * 0.30),
            "bonds_payable": fmt_m(total_liabilities * 0.05),
            "other_current_liabilities": fmt_m(total_liabilities * 0.05),
        },
        # Phase 2: Advanced Document Intelligence
        "bank_analysis": {
            "transactions": [
                {"date": "2024-03-01", "description": "SALARY_PAYOUT", "amount": 150000, "type": "debit"},
                {"date": "2024-03-02", "description": "INCOMING_WIRE_X", "amount": 500000, "type": "credit"},
                {"date": "2024-03-05", "description": "GST_PAYMENT", "amount": 75000, "type": "debit"},
                {"date": "2024-03-10", "description": "EMI_TRANSFER", "amount": 120000, "type": "debit"},
            ],
            "counterparty_risk": {
                "risk_level": "Medium",
                "description": "35% concentration detected with single counterparty (WIRE_X).",
                "top_counterparties": [("WIRE_X", 500000)]
            },
            "debt_service_ratio": {
                "value": 0.35,
                "status": "Warning",
                "monthly_debt_obligations": 120000,
                "monthly_average_inflow": 450000
            }
        },
        "upload_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    return {
        "status": "success",
        "message": "Test data generated",
        "data": test_data
    }

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
