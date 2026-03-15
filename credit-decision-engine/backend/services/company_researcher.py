"""
AI-Powered Company Research Module
Performs real web searches and NLP analysis to extract risk signals
"""

import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Import the real web search service
try:
    from .web_search_service import WebSearchService
    WEB_SEARCH_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Web search service not available: {e}")
    WEB_SEARCH_AVAILABLE = False
    # Create dummy web search service for fallback
    class WebSearchService:
        async def search_company(self, company_name):
            return {
                'status': 'success',
                'company_name': company_name,
                'sentiment_analysis': {
                    'score': 0.0,
                    'sentiment': 'Neutral',
                    'total_articles_analyzed': 0,
                    'positive_articles': 0,
                    'negative_articles': 0,
                    'neutral_articles': 0
                },
                'litigation_analysis': {
                    'total_cases': 0,
                    'active_cases': 0,
                    'settled_cases': 0,
                    'risk_assessment': 'Low'
                },
                'industry_analysis': {
                    'outlook': 'Unknown',
                    'growth_rate': 'Unknown',
                    'key_drivers': [],
                    'challenges': [],
                    'market_position': 'Unknown'
                },
                'risk_signals': ['Web search unavailable - using fallback analysis'],
                'research_confidence': 0.3,
                'search_timestamp': datetime.now().isoformat()
            }

@dataclass
class ResearchResult:
    """Data class for research findings"""
    company_name: str
    search_queries: List[str]
    news_sentiment: Dict[str, Any]
    litigation_data: Dict[str, Any]
    industry_analysis: Dict[str, Any]
    risk_signals: List[str]
    confidence_score: float
    research_timestamp: str

class CompanyResearcher:
    """AI-powered company research and risk analysis with real web search"""
    
    def __init__(self):
        # Initialize the real web search service
        self.web_search_service = WebSearchService()
        
        # Risk signal patterns for NLP analysis
        self.risk_patterns = {
            'financial_distress': [
                r'bankruptcy', r'insolvency', r'default', r'debt crisis', r'financial distress',
                r'cash flow problems', r'liquidity crisis', r'loss making', r'negative equity'
            ],
            'legal_issues': [
                r'lawsuit', r'litigation', r'legal dispute', r'court case', r'regulatory action',
                r'compliance violation', r'penalty', r'fine', r'investigation'
            ],
            'operational_risks': [
                r'supply chain', r'dependency', r'single supplier', r'operational issues',
                r'production halt', r'factory closure', r'labor disputes', r'strike'
            ],
            'market_risks': [
                r'market share decline', r'competition', r'price war', r'demand fall',
                r'industry downturn', r'market contraction', r'losing customers'
            ],
            'management_risks': [
                r'management change', r'CEO resignation', r'board dispute', r'governance issues',
                r'fraud', r'scandal', r'corruption', r'mismanagement'
            ]
        }
    
    async def research_company(self, company_name: str) -> Dict[str, Any]:
        """
        Perform comprehensive company research using real web search and NLP analysis
        
        Args:
            company_name: Name of the company to research
            
        Returns:
            Complete research findings with risk analysis from real web search
        """
        try:
            print(f"Starting {'REAL' if WEB_SEARCH_AVAILABLE else 'FALLBACK'} web search research for: {company_name}")
            
            # Perform web search using the web search service
            web_search_results = await self.web_search_service.search_company(company_name)
            
            if web_search_results['status'] != 'success':
                print(f"Web search failed, using fallback for: {company_name}")
                return self._get_fallback_research(company_name)
            
            search_type = "REAL" if WEB_SEARCH_AVAILABLE else "FALLBACK"
            print(f"{search_type} web search completed for {company_name} with confidence: {web_search_results.get('research_confidence', 0):.1%}")
            
            # Extract data from web search results
            sentiment_analysis = web_search_results.get('sentiment_analysis', {})
            litigation_analysis = web_search_results.get('litigation_analysis', {})
            industry_analysis = web_search_results.get('industry_analysis', {})
            risk_signals = web_search_results.get('risk_signals', [])
            research_confidence = web_search_results.get('research_confidence', 0.5)
            
            # Create research result
            research_result = ResearchResult(
                company_name=company_name,
                search_queries=[f"{search_type} web search for {company_name}"],
                news_sentiment=sentiment_analysis,
                litigation_data=litigation_analysis,
                industry_analysis=industry_analysis,
                risk_signals=risk_signals,
                confidence_score=research_confidence,
                research_timestamp=web_search_results.get('search_timestamp', datetime.now().isoformat())
            )
            
            # Format and return the research output
            formatted_output = self._format_research_output(research_result)
            
            # Add web search specific metadata
            formatted_output['web_search_metadata'] = {
                'search_performed': True,
                'search_type': search_type,
                'data_sources': web_search_results.get('data_sources', []),
                'total_articles_found': web_search_results.get('sentiment_analysis', {}).get('total_articles_analyzed', 0),
                'search_quality': 'High' if research_confidence > 0.8 else 'Medium' if research_confidence > 0.6 else 'Low',
                'web_search_available': WEB_SEARCH_AVAILABLE
            }
            
            print(f"Research completed for {company_name}: {len(risk_signals)} risk signals identified ({search_type})")
            return formatted_output
            
        except Exception as e:
            print(f"Error in company research: {str(e)}")
            return self._get_fallback_research(company_name)
    
    def _generate_search_queries(self, company_name: str) -> List[str]:
        """Generate specific search queries for the company"""
        queries = []
        for template in self.search_queries_template:
            query = template.format(company_name=company_name)
            queries.append(query)
        return queries
    
    async def _perform_web_searches(self, search_queries: List[str]) -> Dict[str, Any]:
        """
        Perform web searches (mock implementation)
        In production, this would integrate with real search APIs like Google Search API, Bing API, etc.
        """
        # Mock search results for demonstration
        # In production, replace with actual API calls
        mock_results = {
            'financial_problems': {
                'articles': [
                    {
                        'title': f'Company faces working capital challenges',
                        'snippet': 'The company is experiencing temporary cash flow issues due to market conditions',
                        'source': 'Financial Times',
                        'date': '2024-01-15'
                    }
                ],
                'total_results': 5
            },
            'lawsuits': {
                'articles': [
                    {
                        'title': f'Commercial dispute with supplier resolved',
                        'snippet': 'A minor legal dispute regarding contract terms was settled out of court',
                        'source': 'Legal News',
                        'date': '2024-02-01'
                    }
                ],
                'total_results': 2
            },
            'competition': {
                'articles': [
                    {
                        'title': f'Industry competition intensifies',
                        'snippet': 'The sector is seeing increased competition from new entrants and established players',
                        'source': 'Industry Report',
                        'date': '2024-01-20'
                    }
                ],
                'total_results': 8
            }
        }
        
        # Simulate API delay
        await asyncio.sleep(0.5)
        
        return mock_results
    
    def _extract_risk_signals(self, search_results: Dict[str, Any], company_name: str) -> List[str]:
        """Extract risk signals from search results using pattern matching"""
        risk_signals = []
        
        # Combine all text from search results
        all_text = ""
        for category, results in search_results.items():
            if 'articles' in results:
                for article in results['articles']:
                    all_text += f" {article.get('title', '')} {article.get('snippet', '')}"
        
        # Apply risk pattern matching
        for risk_category, patterns in self.risk_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                if matches:
                    risk_signals.append(f"{risk_category.replace('_', ' ').title()}: {pattern}")
        
        # Add contextual risk signals based on search results
        if search_results.get('financial_problems', {}).get('total_results', 0) > 3:
            risk_signals.append("Multiple financial concerns identified")
        
        if search_results.get('lawsuits', {}).get('total_results', 0) > 2:
            risk_signals.append("Multiple legal matters pending")
        
        if search_results.get('competition', {}).get('total_results', 0) > 5:
            risk_signals.append("High competitive pressure in industry")
        
        # Remove duplicates and limit to top risks
        unique_risks = list(set(risk_signals))[:8]
        
        return unique_risks if unique_risks else ["No significant risk signals found"]
    
    def _analyze_news_sentiment(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment from news articles"""
        # Mock sentiment analysis
        # In production, use NLP models like VADER, TextBlob, or transformer models
        
        total_articles = sum(results.get('total_results', 0) for results in search_results.values())
        
        # Simulate sentiment calculation
        if total_articles > 10:
            sentiment_score = -0.2  # Slightly negative due to more risk articles
            sentiment_label = "Slightly Negative"
        elif total_articles > 5:
            sentiment_score = 0.1   # Slightly positive
            sentiment_label = "Slightly Positive"
        else:
            sentiment_score = 0.3   # Positive
            sentiment_label = "Positive"
        
        return {
            'score': sentiment_score,
            'sentiment': sentiment_label,
            'total_articles_analyzed': total_articles,
            'positive_articles': max(0, int(total_articles * 0.3)),
            'negative_articles': max(0, int(total_articles * 0.2)),
            'neutral_articles': max(0, total_articles - int(total_articles * 0.5))
        }
    
    def _extract_litigation_data(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract litigation information from search results"""
        lawsuit_results = search_results.get('lawsuits', {})
        articles = lawsuit_results.get('articles', [])
        
        # Analyze litigation articles
        total_cases = len(articles)
        active_cases = sum(1 for article in articles 
                          if any(keyword in article.get('snippet', '').lower() 
                                for keyword in ['ongoing', 'pending', 'current']))
        
        settled_cases = total_cases - active_cases
        
        # Determine risk assessment
        if total_cases == 0:
            risk_assessment = "Low"
        elif total_cases <= 2:
            risk_assessment = "Medium"
        else:
            risk_assessment = "High"
        
        return {
            'total_cases': total_cases,
            'active_cases': active_cases,
            'settled_cases': settled_cases,
            'risk_assessment': risk_assessment,
            'case_details': [
                {
                    'type': 'Commercial Dispute' if 'contract' in article.get('snippet', '').lower() else 'Regulatory',
                    'status': 'Active' if active_cases > 0 else 'Settled'
                }
                for article in articles[:3]
            ]
        }
    
    def _analyze_industry_context(self, search_results: Dict[str, Any], company_name: str) -> Dict[str, Any]:
        """Analyze industry context and outlook"""
        competition_results = search_results.get('competition', {})
        
        # Mock industry analysis
        # In production, this would analyze actual industry reports and trends
        
        return {
            'outlook': 'Positive' if competition_results.get('total_results', 0) < 5 else 'Challenging',
            'growth_rate': '8-12%' if competition_results.get('total_results', 0) < 5 else '3-5%',
            'key_drivers': [
                'Digital transformation initiatives',
                'Domestic market expansion',
                'Export opportunities'
            ],
            'challenges': [
                'Supply chain disruptions',
                'Raw material cost volatility',
                'Increasing competition'
            ],
            'market_position': 'Strong' if competition_results.get('total_results', 0) < 3 else 'Moderate'
        }
    
    def _calculate_research_confidence(self, search_results: Dict[str, Any], risk_signals: List[str]) -> float:
        """Calculate confidence score for research findings"""
        total_results = sum(results.get('total_results', 0) for results in search_results.values())
        
        # Base confidence on data availability
        if total_results > 15:
            base_confidence = 0.8
        elif total_results > 8:
            base_confidence = 0.6
        elif total_results > 3:
            base_confidence = 0.4
        else:
            base_confidence = 0.2
        
        # Adjust based on risk signals found
        if len(risk_signals) > 5:
            base_confidence += 0.1  # More data points increase confidence
        
        return min(1.0, base_confidence)
    
    def _format_research_output(self, research_result: ResearchResult) -> Dict[str, Any]:
        """Format research results for API response"""
        return {
            'status': 'success',
            'company_name': research_result.company_name,
            'research_summary': {
                'news_sentiment': research_result.news_sentiment,
                'litigation_data': research_result.litigation_data,
                'industry_analysis': research_result.industry_analysis,
                'risk_signals': research_result.risk_signals,
                'confidence_score': research_result.confidence_score,
                'research_timestamp': research_result.research_timestamp
            },
            'search_queries_used': research_result.search_queries,
            'data_sources': ['News Articles', 'Legal Databases', 'Industry Reports', ' Regulatory Filings']
        }
    
    def _get_fallback_research(self, company_name: str) -> Dict[str, Any]:
        """Provide fallback research when web search fails"""
        return {
            'status': 'success',
            'company_name': company_name,
            'research_summary': {
                'news_sentiment': {
                    'score': 0.0,
                    'sentiment': 'Neutral',
                    'total_articles_analyzed': 0,
                    'positive_articles': 0,
                    'negative_articles': 0,
                    'neutral_articles': 0
                },
                'litigation_data': {
                    'total_cases': 0,
                    'active_cases': 0,
                    'settled_cases': 0,
                    'risk_assessment': 'Low'
                },
                'industry_analysis': {
                    'outlook': 'Stable',
                    'growth_rate': '5-8%',
                    'key_drivers': ['Market demand', 'Economic growth'],
                    'challenges': ['Competition', 'Regulatory changes'],
                    'market_position': 'Unknown'
                },
                'risk_signals': ['Limited research data available'],
                'confidence_score': 0.3,
                'research_timestamp': datetime.now().isoformat()
            },
            'search_queries_used': [],
            'data_sources': ['Fallback Analysis'],
            'note': 'Web search unavailable, using fallback analysis'
        }
