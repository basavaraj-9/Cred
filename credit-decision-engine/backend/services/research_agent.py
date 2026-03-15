import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any
import re
import json
from textblob import TextBlob
import time
from urllib.parse import quote_plus

class ResearchAgent:
    def __init__(self):
        self.news_sources = [
            'https://www.google.com/search?q=',
            'https://news.google.com/search?q=',
        ]
        self.litigation_keywords = [
            'case', 'lawsuit', 'legal', 'court', 'judgment', 'petition',
            'dispute', 'litigation', 'controversy', 'scam', 'fraud',
            'investigation', 'probe', 'seizure', 'attachment', 'bankruptcy'
        ]
        self.positive_keywords = [
            'growth', 'expansion', 'profit', 'success', 'award', 'recognition',
            'partnership', 'collaboration', 'innovation', 'achievement'
        ]
        self.negative_keywords = [
            'loss', 'decline', 'fraud', 'scandal', 'bankruptcy', 'closure',
            'layoff', 'termination', 'violation', 'penalty', 'fine'
        ]
    
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
            'confidence_score': 0
        }
        
        try:
            # Research company news
            company_news = await self._search_news(company_name)
            research_result['news_articles'].extend(company_news)
            
            # Research promoter if provided
            if promoter_name:
                promoter_news = await self._search_news(promoter_name)
                research_result['news_articles'].extend(promoter_news)
            
            # Research sector if provided
            if sector:
                sector_news = await self._search_news(f"{sector} sector outlook")
                research_result['sector_news'] = sector_news
            
            # Analyze litigation risk
            litigation_analysis = self._analyze_litigation_risk(research_result['news_articles'])
            research_result['litigation_cases'] = litigation_analysis['case_count']
            research_result['risk_factors'].extend(litigation_analysis['risk_factors'])
            
            # Analyze sentiment
            sentiment_analysis = self._analyze_sentiment(research_result['news_articles'])
            research_result['news_sentiment'] = sentiment_analysis['overall_sentiment']
            research_result['positive_indicators'] = sentiment_analysis['positive_indicators']
            research_result['risk_factors'].extend(sentiment_analysis['negative_indicators'])
            
            # Analyze promoter risk
            if promoter_name:
                promoter_risk = self._analyze_promoter_risk(promoter_name, research_result['news_articles'])
                research_result['promoter_risk'] = promoter_risk
            
            # Analyze sector outlook
            if sector:
                sector_outlook = self._analyze_sector_outlook(sector, research_result.get('sector_news', []))
                research_result['sector_outlook'] = sector_outlook
            
            # Generate research summary
            research_result['research_summary'] = self._generate_summary(research_result)
            
            # Calculate confidence score
            research_result['confidence_score'] = self._calculate_confidence_score(research_result)
            
        except Exception as e:
            research_result['research_summary'] = f"Research incomplete due to error: {str(e)}"
            research_result['confidence_score'] = 0
        
        return research_result
    
    async def _search_news(self, query: str) -> List[Dict[str, Any]]:
        """Search for news articles related to the query"""
        articles = []
        
        try:
            # Use Google search (this is a simplified version)
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=nws"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract news articles (simplified extraction)
                for item in soup.find_all('div', class_='g')[:10]:  # Limit to 10 articles
                    try:
                        title_elem = item.find('h3')
                        snippet_elem = item.find('span', {'data-ved': True})
                        
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            
                            articles.append({
                                'title': title,
                                'snippet': snippet,
                                'source': 'Google News',
                                'query': query,
                                'url': ''
                            })
                    except:
                        continue
            
            # Add delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"News search failed for query '{query}': {str(e)}")
        
        return articles
    
    def _analyze_litigation_risk(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze litigation risk from news articles"""
        
        litigation_indicators = {
            'case_count': 0,
            'risk_factors': [],
            'severity_score': 0
        }
        
        for article in articles:
            text = f"{article.get('title', '')} {article.get('snippet', '')}".lower()
            
            # Check for litigation keywords
            litigation_matches = []
            for keyword in self.litigation_keywords:
                if keyword in text:
                    litigation_matches.append(keyword)
            
            if litigation_matches:
                litigation_indicators['case_count'] += 1
                
                # Determine severity based on keywords
                high_severity_keywords = ['fraud', 'scam', 'bankruptcy', 'seizure', 'attachment']
                medium_severity_keywords = ['case', 'lawsuit', 'legal', 'court', 'dispute']
                
                if any(keyword in text for keyword in high_severity_keywords):
                    litigation_indicators['severity_score'] += 3
                    litigation_indicators['risk_factors'].append(f"High severity litigation: {article.get('title', '')}")
                elif any(keyword in text for keyword in medium_severity_keywords):
                    litigation_indicators['severity_score'] += 1
                    litigation_indicators['risk_factors'].append(f"Legal proceedings: {article.get('title', '')}")
        
        return litigation_indicators
    
    def _analyze_sentiment(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sentiment of news articles"""
        
        sentiment_analysis = {
            'overall_sentiment': 'Neutral',
            'positive_indicators': [],
            'negative_indicators': [],
            'sentiment_score': 0
        }
        
        total_sentiment = 0
        article_count = 0
        
        for article in articles:
            text = f"{article.get('title', '')} {article.get('snippet', '')}"
            
            # Use TextBlob for sentiment analysis
            blob = TextBlob(text)
            sentiment = blob.sentiment.polarity
            total_sentiment += sentiment
            article_count += 1
            
            # Check for specific positive/negative keywords
            text_lower = text.lower()
            
            for keyword in self.positive_keywords:
                if keyword in text_lower:
                    sentiment_analysis['positive_indicators'].append(f"Positive indicator: {keyword}")
            
            for keyword in self.negative_keywords:
                if keyword in text_lower:
                    sentiment_analysis['negative_indicators'].append(f"Negative indicator: {keyword}")
        
        if article_count > 0:
            avg_sentiment = total_sentiment / article_count
            sentiment_analysis['sentiment_score'] = avg_sentiment
            
            if avg_sentiment > 0.1:
                sentiment_analysis['overall_sentiment'] = 'Positive'
            elif avg_sentiment < -0.1:
                sentiment_analysis['overall_sentiment'] = 'Negative'
            else:
                sentiment_analysis['overall_sentiment'] = 'Neutral'
        
        return sentiment_analysis
    
    def _analyze_promoter_risk(self, promoter_name: str, articles: List[Dict[str, Any]]) -> str:
        """Analyze promoter-specific risk"""
        
        promoter_articles = [a for a in articles if promoter_name.lower() in a.get('title', '').lower() or 
                           promoter_name.lower() in a.get('snippet', '').lower()]
        
        if not promoter_articles:
            return 'Low'
        
        # Count negative indicators for promoter
        negative_count = 0
        for article in promoter_articles:
            text = f"{article.get('title', '')} {article.get('snippet', '')}".lower()
            
            high_risk_keywords = ['fraud', 'scam', 'arrest', 'jailed', 'money laundering']
            medium_risk_keywords = ['dispute', 'case', 'investigation', 'probe']
            
            if any(keyword in text for keyword in high_risk_keywords):
                negative_count += 3
            elif any(keyword in text for keyword in medium_risk_keywords):
                negative_count += 1
        
        if negative_count >= 5:
            return 'High'
        elif negative_count >= 2:
            return 'Medium'
        else:
            return 'Low'
    
    def _analyze_sector_outlook(self, sector: str, sector_articles: List[Dict[str, Any]]) -> str:
        """Analyze sector outlook"""
        
        if not sector_articles:
            return 'Neutral'
        
        positive_outlook_keywords = ['growth', 'expansion', 'boom', 'recovery', 'bullish']
        negative_outlook_keywords = ['decline', 'slowdown', 'recession', 'bearish', 'crisis']
        
        positive_count = 0
        negative_count = 0
        
        for article in sector_articles:
            text = f"{article.get('title', '')} {article.get('snippet', '')}".lower()
            
            for keyword in positive_outlook_keywords:
                if keyword in text:
                    positive_count += 1
                    break
            
            for keyword in negative_outlook_keywords:
                if keyword in text:
                    negative_count += 1
                    break
        
        if positive_count > negative_count:
            return 'Positive'
        elif negative_count > positive_count:
            return 'Negative'
        else:
            return 'Neutral'
    
    def _generate_summary(self, research_result: Dict[str, Any]) -> str:
        """Generate a summary of research findings"""
        
        summary_parts = []
        
        # Litigation summary
        if research_result['litigation_cases'] > 0:
            summary_parts.append(f"Found {research_result['litigation_cases']} litigation-related articles")
        
        # Sentiment summary
        if research_result['news_sentiment'] != 'Neutral':
            summary_parts.append(f"Overall news sentiment is {research_result['news_sentiment'].lower()}")
        
        # Promoter risk summary
        if research_result['promoter_risk'] != 'Low':
            summary_parts.append(f"Promoter risk assessed as {research_result['promoter_risk'].lower()}")
        
        # Sector outlook summary
        if research_result['sector_outlook'] != 'Neutral':
            summary_parts.append(f"Sector outlook is {research_result['sector_outlook'].lower()}")
        
        # Risk factors summary
        if research_result['risk_factors']:
            summary_parts.append(f"Identified {len(research_result['risk_factors'])} risk factors")
        
        if not summary_parts:
            return "No significant findings from public research"
        
        return ". ".join(summary_parts) + "."
    
    def _calculate_confidence_score(self, research_result: Dict[str, Any]) -> int:
        """Calculate confidence score for research findings"""
        
        score = 0
        
        # Base score for having any articles
        if research_result['news_articles']:
            score += 20
        
        # Additional points for article count
        score += min(len(research_result['news_articles']) * 2, 30)
        
        # Points for comprehensive analysis
        if research_result['litigation_cases'] > 0:
            score += 10
        
        if research_result['promoter_name'] and research_result['promoter_risk'] != 'Low':
            score += 10
        
        if research_result['sector'] and research_result['sector_outlook'] != 'Neutral':
            score += 10
        
        # Points for sentiment analysis
        if research_result['news_sentiment'] != 'Neutral':
            score += 10
        
        # Points for risk factors identified
        score += min(len(research_result['risk_factors']) * 5, 10)
        
        return min(score, 100)
