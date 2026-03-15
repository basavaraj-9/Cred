#!/usr/bin/env python3
"""
Test script to run the Research Agent independently
"""

import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.research_agent import ResearchAgent

async def test_research_agent():
    """Test the Research Agent with sample data"""
    print("🔍 Starting Research Agent Test...")
    print("=" * 50)
    
    # Initialize the research agent
    agent = ResearchAgent()
    
    # Test data
    test_company = "ABC Manufacturing Ltd"
    test_promoter = "John Doe"
    test_sector = "Manufacturing"
    
    print(f"📊 Analyzing Company: {test_company}")
    print(f"👤 Promoter: {test_promoter}")
    print(f"🏭 Sector: {test_sector}")
    print()
    
    try:
        # Run research analysis
        print("🔍 Performing comprehensive research analysis...")
        result = await agent.research_company(test_company, test_promoter, test_sector)
        
        print("\n" + "=" * 50)
        print("📋 RESEARCH RESULTS")
        print("=" * 50)
        
        # Display results
        print(f"\n🏢 Company: {result.get('company', 'N/A')}")
        print(f"👤 Promoter Risk: {result.get('promoter_risk', 'N/A')}")
        print(f"📈 Sector Outlook: {result.get('sector_outlook', 'N/A')}")
        print(f"⚖️  Litigation Cases: {result.get('litigation_cases', 'N/A')}")
        print(f"📰 News Sentiment: {result.get('news_sentiment', 'N/A')}")
        print(f"🔍 Confidence Score: {result.get('confidence_score', 'N/A')}%")
        
        print(f"\n📝 Research Summary:")
        print("-" * 30)
        summary = result.get('research_summary', 'No summary available')
        print(summary)
        
        print(f"\n📊 Component Scores:")
        print("-" * 30)
        component_scores = result.get('component_scores', {})
        for component, score in component_scores.items():
            print(f"{component.replace('_', ' ').title()}: {score}")
        
        print(f"\n⚠️  Risk Factors:")
        print("-" * 30)
        risk_factors = result.get('risk_factors', [])
        if risk_factors:
            for i, factor in enumerate(risk_factors, 1):
                print(f"{i}. {factor}")
        else:
            print("No significant risk factors identified")
        
        print(f"\n🌐 News Analysis:")
        print("-" * 30)
        news_analysis = result.get('news_analysis', {})
        print(f"Total Articles: {news_analysis.get('total_articles', 0)}")
        print(f"Positive: {news_analysis.get('positive_articles', 0)}")
        print(f"Negative: {news_analysis.get('negative_articles', 0)}")
        print(f"Neutral: {news_analysis.get('neutral_articles', 0)}")
        
        print(f"\n⚖️  Litigation Details:")
        print("-" * 30)
        litigation = result.get('litigation_details', {})
        print(f"Total Cases: {litigation.get('total_cases', 0)}")
        print(f"Active Cases: {litigation.get('active_cases', 0)}")
        print(f"Settled Cases: {litigation.get('settled_cases', 0)}")
        
        print("\n" + "=" * 50)
        print("✅ Research Agent Test Completed Successfully!")
        print("=" * 50)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during research analysis: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_research_agent())
