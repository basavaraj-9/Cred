from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from services.gst_bank_analyzer import GSTBankAnalyzer
from services.risk_engine import RiskEngine
from services.recommendation_engine import RecommendationEngine

router = APIRouter()

class CreditOfficerInput(BaseModel):
    factory_utilization: Optional[float] = 50
    management_quality: Optional[str] = "moderate"
    inventory_turnover: Optional[str] = "normal"
    customer_concentration: Optional[str] = "low"
    industry_experience: Optional[float] = 5

class RiskAnalysisRequest(BaseModel):
    financial_data: Dict[str, Any]
    gst_data: Dict[str, Any]
    bank_data: Dict[str, Any]
    research_data: Optional[Dict[str, Any]] = {}
    officer_input: Optional[CreditOfficerInput] = None

@router.post("/consistency-analysis")
async def analyze_consistency(gst_data: Dict[str, Any], bank_data: Dict[str, Any]):
    """Analyze consistency between GST and bank data"""
    
    try:
        analyzer = GSTBankAnalyzer()
        consistency_result = analyzer.analyze_consistency(gst_data, bank_data)
        
        return {
            "status": "success",
            "consistency_analysis": consistency_result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consistency analysis failed: {str(e)}")

@router.post("/risk-score")
async def calculate_risk_score(request: RiskAnalysisRequest):
    """Calculate comprehensive risk score"""
    
    try:
        # Initialize engines
        risk_engine = RiskEngine()
        
        # Perform consistency analysis if GST and bank data provided
        consistency_analysis = {}
        if request.gst_data and request.bank_data:
            analyzer = GSTBankAnalyzer()
            consistency_analysis = analyzer.analyze_consistency(request.gst_data, request.bank_data)
        
        # Calculate risk score
        risk_result = risk_engine.calculate_risk_score(
            financial_data=request.financial_data,
            consistency_analysis=consistency_analysis,
            research_data=request.research_data or {},
            officer_input=request.officer_input.dict() if request.officer_input else None
        )
        
        return {
            "status": "success",
            "risk_analysis": risk_result,
            "consistency_analysis": consistency_analysis
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk scoring failed: {str(e)}")

@router.post("/recommendation")
async def generate_recommendation(risk_analysis: Dict[str, Any], financial_data: Dict[str, Any]):
    """Generate final lending recommendation"""
    
    try:
        recommendation_engine = RecommendationEngine()
        
        recommendation = recommendation_engine.generate_recommendation(
            risk_score=risk_analysis.get('risk_score', 0),
            risk_category=risk_analysis.get('risk_category', 'Medium'),
            financial_data=financial_data,
            component_scores=risk_analysis.get('component_scores', {})
        )
        
        return {
            "status": "success",
            "recommendation": recommendation
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")

@router.post("/credit-officer-input")
async def submit_officer_input(officer_input: CreditOfficerInput):
    """Submit credit officer qualitative input"""
    
    try:
        # Validate input
        if officer_input.factory_utilization < 0 or officer_input.factory_utilization > 100:
            raise HTTPException(status_code=400, detail="Factory utilization must be between 0 and 100")
        
        if officer_input.management_quality not in ["poor", "moderate", "good", "excellent"]:
            raise HTTPException(status_code=400, detail="Management quality must be one of: poor, moderate, good, excellent")
        
        if officer_input.inventory_turnover not in ["low", "normal", "high"]:
            raise HTTPException(status_code=400, detail="Inventory turnover must be one of: low, normal, high")
        
        return {
            "status": "success",
            "message": "Credit officer input recorded successfully",
            "officer_input": officer_input.dict()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process officer input: {str(e)}")

@router.get("/risk-factors")
async def get_risk_factors():
    """Get list of common risk factors"""
    
    risk_factors = {
        "financial": [
            "High debt-to-revenue ratio",
            "Negative profitability",
            "Low revenue base",
            "High litigation exposure",
            "Poor asset quality"
        ],
        "consistency": [
            "Revenue inflation detected",
            "Circular trading patterns",
            "Cash flow anomalies",
            "GST-bank statement mismatch",
            "Unusual transaction patterns"
        ],
        "research": [
            "Negative news sentiment",
            "Multiple litigation cases",
            "High promoter risk",
            "Negative sector outlook",
            "Regulatory compliance issues"
        ],
        "qualitative": [
            "Low factory utilization",
            "Poor management quality",
            "High customer concentration",
            "Low industry experience",
            "Weak internal controls"
        ]
    }
    
    return {
        "status": "success",
        "risk_factors": risk_factors
    }
