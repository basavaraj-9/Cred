from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from services.research_agent import ResearchAgent

router = APIRouter()

class ResearchRequest(BaseModel):
    company_name: str
    promoter_name: Optional[str] = ""
    sector: Optional[str] = ""

@router.post("/research-insights")
async def get_research_insights(request: ResearchRequest):
    """Perform comprehensive research on company and sector"""
    
    try:
        research_agent = ResearchAgent()
        
        # Perform research
        research_result = await research_agent.research_company(
            company_name=request.company_name,
            promoter_name=request.promoter_name or "",
            sector=request.sector or ""
        )
        
        return {
            "status": "success",
            "research_data": research_result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")

@router.get("/research-status/{task_id}")
async def get_research_status(task_id: str):
    """Get research status (placeholder for async processing)"""
    
    return {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "Research completed successfully"
    }

@router.get("/sector-outlook/{sector}")
async def get_sector_outlook(sector: str):
    """Get sector outlook information"""
    
    # Mock sector outlook data
    sector_outlooks = {
        "manufacturing": {
            "outlook": "Positive",
            "growth_rate": "8-12%",
            "key_drivers": ["Make in India initiative", "Export demand", "Technology adoption"],
            "challenges": ["Supply chain disruptions", "Raw material costs", "Competition"]
        },
        "textiles": {
            "outlook": "Neutral",
            "growth_rate": "5-8%",
            "key_drivers": ["Domestic demand", "Government schemes", "Technical textiles"],
            "challenges": ["International competition", "Environmental regulations", "Cotton price volatility"]
        },
        "it_services": {
            "outlook": "Positive",
            "growth_rate": "12-15%",
            "key_drivers": ["Digital transformation", "Cloud adoption", "AI/ML integration"],
            "challenges": ["Talent shortage", "Global slowdown", "Currency fluctuations"]
        },
        "retail": {
            "outlook": "Positive",
            "growth_rate": "10-15%",
            "key_drivers": ["Consumer spending", "E-commerce growth", "Organized retail expansion"],
            "challenges": ["Competition", "Supply chain", "Changing consumer preferences"]
        },
        "construction": {
            "outlook": "Negative",
            "growth_rate": "2-4%",
            "key_drivers": ["Infrastructure projects", "Urbanization", "Housing demand"],
            "challenges": ["Regulatory delays", "Funding constraints", "Material costs"]
        }
    }
    
    outlook = sector_outlooks.get(sector.lower(), {
        "outlook": "Neutral",
        "growth_rate": "6-8%",
        "key_drivers": ["Economic growth", "Market demand", "Innovation"],
        "challenges": ["Competition", "Regulatory environment", "Market volatility"]
    })
    
    return {
        "status": "success",
        "sector": sector,
        "outlook": outlook
    }

@router.get("/news-sentiment/{company_name}")
async def get_news_sentiment(company_name: str):
    """Get news sentiment for a specific company"""
    
    # Mock sentiment analysis
    sentiments = {
        "positive": {
            "score": 0.7,
            "sentiment": "Positive",
            "headlines": [
                "Company reports strong quarterly results",
                "New product launch receives market approval",
                "Strategic partnership announced"
            ]
        },
        "neutral": {
            "score": 0.1,
            "sentiment": "Neutral",
            "headlines": [
                "Company maintains market position",
                "Board meeting scheduled for next month",
                "Annual report filed on time"
            ]
        },
        "negative": {
            "score": -0.6,
            "sentiment": "Negative",
            "headlines": [
                "Company faces regulatory scrutiny",
                "Profit margins under pressure",
                "Key executive resigns"
            ]
        }
    }
    
    # For demo, return neutral sentiment
    sentiment_data = sentiments["neutral"]
    
    return {
        "status": "success",
        "company": company_name,
        "sentiment_analysis": sentiment_data
    }

@router.get("/litigation-check/{company_name}")
async def check_litigation(company_name: str):
    """Check litigation history for a company"""
    
    # Mock litigation data
    litigation_data = {
        "total_cases": 2,
        "active_cases": 1,
        "settled_cases": 1,
        "cases": [
            {
                "case_number": "CS/2023/0456",
                "type": "Commercial Dispute",
                "status": "Active",
                "amount": "₹50,00,000",
                "description": "Dispute with supplier over contract terms"
            },
            {
                "case_number": "CS/2022/0123",
                "type": "Labor Matter",
                "status": "Settled",
                "amount": "₹5,00,000",
                "description": "Employee compensation dispute - settled out of court"
            }
        ],
        "risk_assessment": "Medium"
    }
    
    return {
        "status": "success",
        "company": company_name,
        "litigation_data": litigation_data
    }
