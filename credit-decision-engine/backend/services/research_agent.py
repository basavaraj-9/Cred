import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
import re
import json
from textblob import TextBlob
import time
from urllib.parse import quote_plus
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    title: str
    content: str
    source: str
    date: str
    sentiment: float
    url: str
    relevance_score: float

@dataclass
class LitigationCase:
    case_number: str
    court: str
    parties: List[str]
    case_type: str
    status: str
    amount: float
    date_filed: str
    description: str

@dataclass
class PromoterProfile:
    name: str
    experience_years: int
    previous_companies: List[str]
    education: str
    reputation_score: float
    red_flags: List[str]
    achievements: List[str]

class ResearchAgent:
    """Enhanced Research Agent for comprehensive company and promoter analysis"""
    
    def __init__(self):
        self.news_sources = [
            'https://www.google.com/search?q=',
            'https://news.google.com/search?q=',
            'https://www.bing.com/news/search?q=',
        ]
        
        # Enhanced keyword lists
        self.litigation_keywords = [
            'case', 'lawsuit', 'legal', 'court', 'judgment', 'petition',
            'dispute', 'litigation', 'controversy', 'scam', 'fraud',
            'investigation', 'probe', 'seizure', 'attachment', 'bankruptcy',
            'insolvency', 'cheque bounce', 'dishonour', 'NPA', 'default',
            'regulatory action', 'sebi', 'rbi', 'income tax', 'gst',
            'customs', 'excise', 'environmental violation', 'labor dispute'
        ]
        
        self.positive_keywords = [
            'growth', 'expansion', 'profit', 'success', 'award', 'recognition',
            'partnership', 'collaboration', 'innovation', 'achievement',
            'market leader', 'award winning', 'certified', 'compliant',
            'sustainable', 'esg', 'social responsibility', 'dividend',
            'bonus issue', 'stock split', 'merger', 'acquisition', 'ipo'
        ]
        
        self.negative_keywords = [
            'loss', 'decline', 'fraud', 'scandal', 'bankruptcy', 'closure',
            'layoff', 'termination', 'violation', 'penalty', 'fine',
            'default', 'delisted', 'suspended', 'probe', 'investigation',
            'controversy', 'scam', 'cheat', 'fake', 'bogus', 'shell company'
        ]
        
        # Industry risk profiles
        self.industry_risk_profiles = {
            'technology': {'base_risk': 'Medium', 'factors': ['rapid change', 'competition']},
            'manufacturing': {'base_risk': 'Medium', 'factors': ['cyclicality', 'capital intensity']},
            'healthcare': {'base_risk': 'Low', 'factors': ['regulatory', 'stable demand']},
            'finance': {'base_risk': 'High', 'factors': ['regulation', 'market risk']},
            'retail': {'base_risk': 'Medium', 'factors': ['competition', 'consumer trends']},
            'construction': {'base_risk': 'High', 'factors': ['cyclicality', 'payment delays']},
            'agriculture': {'base_risk': 'High', 'factors': ['weather', 'price volatility']},
            'real estate': {'base_risk': 'High', 'factors': ['market cycles', 'regulation']},
            'telecom': {'base_risk': 'Medium', 'factors': ['competition', 'technology risk']},
            'automobile': {'base_risk': 'Medium', 'factors': ['cyclicality', 'competition']}
        }
    
    async def research_company(self, company_name: str, promoter_name: str = "", sector: str = "") -> Dict[str, Any]:
        """Perform comprehensive research on company, promoter, and sector"""
        
        research_result = {
            'company_name': company_name,
            'promoter_name': promoter_name,
            'sector': sector,
            'promoter_risk': 'Low',
            'sector_outlook': 'Neutral',
            'litigation_cases': 0,
            'news_sentiment': 'Neutral',
            'news_articles': [],
            'risk_factors': [],
            'positive_indicators': [],
            'research_summary': '',
            'confidence_score': 0,
            'promoter_profile': None,
            'litigation_details': [],
            'industry_analysis': {},
            'regulatory_compliance': {},
            'market_position': {},
            'financial_health_indicators': [],
            'esg_score': 0,
            'credit_history': {}
        }
        
        try:
            # Research company news and sentiment
            logger.info(f"Researching company: {company_name}")
            company_news = await self._search_news(company_name)
            research_result['news_articles'] = company_news
            
            # Calculate overall sentiment
            if company_news:
                avg_sentiment = sum(article.sentiment for article in company_news) / len(company_news)
                research_result['news_sentiment'] = self._classify_sentiment(avg_sentiment)
            
            # Research litigation history
            litigation_data = await self._search_litigation(company_name, promoter_name)
            research_result['litigation_cases'] = len(litigation_data)
            research_result['litigation_details'] = litigation_data
            
            # Research promoter profile
            if promoter_name:
                promoter_profile = await self._research_promoter(promoter_name)
                research_result['promoter_profile'] = promoter_profile
                research_result['promoter_risk'] = self._assess_promoter_risk(promoter_profile)
            
            # Industry analysis
            if sector:
                industry_analysis = self._analyze_industry(sector)
                research_result['industry_analysis'] = industry_analysis
                research_result['sector_outlook'] = industry_analysis.get('outlook', 'Neutral')
            
            # Identify risk factors and positive indicators
            research_result['risk_factors'] = self._identify_risk_factors(company_news, litigation_data)
            research_result['positive_indicators'] = self._identify_positive_indicators(company_news)
            
            # ESG assessment
            esg_data = await self._assess_esg(company_name)
            research_result['esg_score'] = esg_data.get('overall_score', 0)
            
            # Market position analysis
            market_data = await self._analyze_market_position(company_name, sector)
            research_result['market_position'] = market_data
            
            # Generate research summary
            research_result['research_summary'] = self._generate_research_summary(research_result)
            
            # Calculate confidence score
            research_result['confidence_score'] = self._calculate_confidence_score(research_result)
            
            logger.info(f"Research completed for {company_name}. Confidence: {research_result['confidence_score']}")
            
        except Exception as e:
            logger.error(f"Research error for {company_name}: {str(e)}")
            research_result['error'] = str(e)
        
        return research_result
    
    async def _search_news(self, company_name: str) -> List[NewsArticle]:
        """Search for news articles about the company"""
        articles = []
        
        try:
            # Search query construction
            query = f"{company_name} business news financial"
            encoded_query = quote_plus(query)
            
            # Simulate news search (in production, use real APIs)
            # This is a mock implementation
            mock_articles = [
                NewsArticle(
                    title=f"{company_name} reports strong quarterly results",
                    content=f"{company_name} announced better than expected quarterly performance with revenue growth of 15% year-on-year.",
                    source="Financial Times",
                    date="2024-01-15",
                    sentiment=0.6,
                    url=f"https://example.com/{company_name}-q1-results",
                    relevance_score=0.9
                ),
                NewsArticle(
                    title=f"{company_name} expands operations to new markets",
                    content=f"The company announced expansion plans into emerging markets, showing confidence in future growth prospects.",
                    source="Business Standard",
                    date="2024-01-10",
                    sentiment=0.4,
                    url=f"https://example.com/{company_name}-expansion",
                    relevance_score=0.8
                )
            ]
            
            articles = mock_articles
            
        except Exception as e:
            logger.error(f"News search error: {str(e)}")
        
        return articles
    
    async def _search_litigation(self, company_name: str, promoter_name: str) -> List[LitigationCase]:
        """Search for litigation cases involving company or promoter"""
        cases = []
        
        try:
            # Mock litigation data (in production, use court databases)
            mock_cases = [
                LitigationCase(
                    case_number="CS/2023/1234",
                    court="Delhi High Court",
                    parties=[company_name, "ABC Suppliers"],
                    case_type="Commercial Dispute",
                    status="Pending",
                    amount=5000000,
                    date_filed="2023-06-15",
                    description="Dispute over payment terms and delivery obligations"
                )
            ]
            
            # Filter cases based on relevance
            if company_name.lower() in [party.lower() for case in mock_cases for party in case.parties]:
                cases = mock_cases
            
        except Exception as e:
            logger.error(f"Litigation search error: {str(e)}")
        
        return cases
    
    async def _research_promoter(self, promoter_name: str) -> PromoterProfile:
        """Research promoter background and reputation"""
        
        # Mock promoter profile (in production, use professional databases)
        profile = PromoterProfile(
            name=promoter_name,
            experience_years=15,
            previous_companies=["ABC Corp", "XYZ Ltd"],
            education="MBA from IIM Ahmedabad",
            reputation_score=0.7,
            red_flags=[],
            achievements=["Industry Award 2022", "Successfully led IPO"]
        )
        
        return profile
    
    def _analyze_industry(self, sector: str) -> Dict[str, Any]:
        """Analyze industry-specific risks and outlook"""
        
        sector_lower = sector.lower()
        industry_data = self.industry_risk_profiles.get(sector_lower, {
            'base_risk': 'Medium',
            'factors': ['general business risks']
        })
        
        analysis = {
            'sector': sector,
            'base_risk': industry_data['base_risk'],
            'risk_factors': industry_data['factors'],
            'outlook': 'Neutral',
            'trends': [],
            'regulatory_environment': 'Moderate',
            'competition_level': 'Medium'
        }
        
        # Adjust outlook based on current trends (mock data)
        if sector_lower in ['technology', 'healthcare']:
            analysis['outlook'] = 'Positive'
        elif sector_lower in ['real estate', 'construction']:
            analysis['outlook'] = 'Negative'
        
        return analysis
    
    def _identify_risk_factors(self, news_articles: List[NewsArticle], litigation_cases: List[LitigationCase]) -> List[str]:
        """Identify risk factors from news and litigation data"""
        risk_factors = []
        
        # Check litigation risks
        if litigation_cases:
            risk_factors.append(f"Active litigation cases: {len(litigation_cases)}")
            total_litigation_amount = sum(case.amount for case in litigation_cases)
            if total_litigation_amount > 10000000:  # > 1 crore
                risk_factors.append(f"High litigation exposure: ₹{total_litigation_amount:,.0f}")
        
        # Check news sentiment risks
        negative_articles = [article for article in news_articles if article.sentiment < -0.2]
        if negative_articles:
            risk_factors.append(f"Negative news coverage: {len(negative_articles)} articles")
        
        # Check for risk keywords in news
        all_news_text = " ".join([article.content for article in news_articles])
        for keyword in self.negative_keywords:
            if keyword.lower() in all_news_text.lower():
                risk_factors.append(f"Risk indicator found: {keyword}")
        
        return risk_factors
    
    def _identify_positive_indicators(self, news_articles: List[NewsArticle]) -> List[str]:
        """Identify positive indicators from news data"""
        positive_indicators = []
        
        # Check positive news sentiment
        positive_articles = [article for article in news_articles if article.sentiment > 0.2]
        if positive_articles:
            positive_indicators.append(f"Positive news coverage: {len(positive_articles)} articles")
        
        # Check for positive keywords
        all_news_text = " ".join([article.content for article in news_articles])
        for keyword in self.positive_keywords:
            if keyword.lower() in all_news_text.lower():
                positive_indicators.append(f"Positive indicator: {keyword}")
        
        return positive_indicators
    
    async def _assess_esg(self, company_name: str) -> Dict[str, Any]:
        """Assess Environmental, Social, and Governance factors"""
        
        # Mock ESG assessment (in production, use ESG rating agencies)
        esg_data = {
            'environmental_score': 0.7,
            'social_score': 0.8,
            'governance_score': 0.6,
            'overall_score': 0.7,
            'certifications': ['ISO 14001', 'ISO 45001'],
            'sustainability_initiatives': ['Carbon neutrality program', 'Community development']
        }
        
        return esg_data
    
    async def _analyze_market_position(self, company_name: str, sector: str) -> Dict[str, Any]:
        """Analyze company's market position"""
        
        # Mock market analysis (in production, use market research data)
        market_data = {
            'market_share': 0.05,  # 5%
            'competitor_count': 15,
            'market_growth_rate': 0.12,  # 12%
            'competitive_position': 'Mid-tier',
            'barriers_to_entry': 'Medium',
            'customer_concentration': 'Low'
        }
        
        return market_data
    
    def _classify_sentiment(self, sentiment_score: float) -> str:
        """Classify sentiment score into categories"""
        if sentiment_score > 0.2:
            return 'Positive'
        elif sentiment_score < -0.2:
            return 'Negative'
        else:
            return 'Neutral'
    
    def _assess_promoter_risk(self, promoter_profile: PromoterProfile) -> str:
        """Assess promoter risk based on profile"""
        risk_score = promoter_profile.reputation_score
        
        if promoter_profile.red_flags:
            risk_score -= 0.2
        
        if risk_score > 0.7:
            return 'Low'
        elif risk_score > 0.4:
            return 'Medium'
        else:
            return 'High'
    
    def _generate_research_summary(self, research_result: Dict[str, Any]) -> str:
        """Generate comprehensive research summary"""
        
        summary_parts = []
        
        # Company overview
        summary_parts.append(f"Research conducted for {research_result['company_name']}")
        
        # Sentiment analysis
        summary_parts.append(f"News sentiment: {research_result['news_sentiment']}")
        
        # Litigation summary
        if research_result['litigation_cases'] > 0:
            summary_parts.append(f"Found {research_result['litigation_cases']} active litigation cases")
        
        # Promoter assessment
        if research_result['promoter_profile']:
            summary_parts.append(f"Promoter risk: {research_result['promoter_risk']}")
        
        # Industry outlook
        summary_parts.append(f"Sector outlook: {research_result['sector_outlook']}")
        
        # Risk factors
        if research_result['risk_factors']:
            summary_parts.append(f"Key risks: {', '.join(research_result['risk_factors'][:3])}")
        
        # Positive indicators
        if research_result['positive_indicators']:
            summary_parts.append(f"Positive factors: {', '.join(research_result['positive_indicators'][:3])}")
        
        return ". ".join(summary_parts) + "."
    
    def _calculate_confidence_score(self, research_result: Dict[str, Any]) -> float:
        """Calculate overall confidence score for research results"""
        
        score = 0.5  # Base score
        
        # News coverage contribution
        if research_result['news_articles']:
            score += 0.2
        
        # Litigation data contribution
        if research_result['litigation_cases'] > 0:
            score += 0.1
        
        # Promoter data contribution
        if research_result['promoter_profile']:
            score += 0.1
        
        # Industry analysis contribution
        if research_result['industry_analysis']:
            score += 0.1
        
        return min(score, 1.0)

# Usage example
if __name__ == "__main__":
    import asyncio
    
    async def test_research():
        agent = ResearchAgent()
        result = await agent.research_company(
            company_name="Tech Innovations Pvt Ltd",
            promoter_name="John Doe",
            sector="Technology"
        )
        print(json.dumps(result, indent=2, default=str))
    
    asyncio.run(test_research())
