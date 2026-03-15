"""
Dynamic Risk Analysis Engine for AI Credit Decisioning System
Calculates risk scores based on comprehensive financial metrics and analysis
"""

import math
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class RiskMetrics:
    """Data class for risk calculation metrics"""
    revenue: float
    assets: float
    liabilities: float
    profit: float
    existing_loans: float
    litigation: float
    gst_revenue: float
    
    def calculate_derived_metrics(self) -> Dict[str, float]:
        """Calculate derived financial ratios"""
        return {
            'debt_to_equity': self.liabilities / max(self.assets - self.liabilities, 1),
            'profit_margin': (self.profit / max(self.revenue, 1)) * 100,
            'revenue_growth': 0,  # Would need historical data
            'working_capital_ratio': (self.assets - self.liabilities) / max(self.revenue, 1) * 100,
            'cash_flow_stability': self.profit / max(self.existing_loans, 1),
            'gst_consistency': self.gst_revenue / max(self.revenue, 1),
            'litigation_ratio': self.litigation / max(self.revenue, 1) * 100
        }

class RiskAnalyzer:
    """Advanced risk analysis engine with dynamic scoring"""
    
    def __init__(self):
        self.risk_factors = {
            'high_debt_ratio': {'threshold': 2.0, 'impact': -15, 'description': 'High debt-to-equity ratio'},
            'low_profit_margin': {'threshold': 5.0, 'impact': -10, 'description': 'Low profit margin'},
            'good_profit_margin': {'threshold': 15.0, 'impact': 10, 'description': 'Strong profit margin'},
            'negative_working_capital': {'threshold': 10.0, 'impact': -10, 'description': 'Low working capital'},
            'high_litigation': {'threshold': 5.0, 'impact': -15, 'description': 'High litigation exposure'},
            'good_cash_flow': {'threshold': 0.5, 'impact': 10, 'description': 'Strong cash flow'},
            'poor_gst_consistency': {'threshold': 0.8, 'impact': -10, 'description': 'GST revenue inconsistency'},
            'high_existing_debt': {'threshold': 0.5, 'impact': -10, 'description': 'High existing loan burden'}
        }
    
    def calculate_risk_score(self, company_data: Dict[str, Any], research_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive risk score based on financial metrics and research
        
        Args:
            company_data: Financial data from uploaded documents
            research_data: AI research findings from web search
            
        Returns:
            Complete risk analysis with score, category, and factors
        """
        # Create risk metrics object
        risk_metrics = RiskMetrics(
            revenue=company_data.get('revenue', 0),
            assets=company_data.get('assets', 0),
            liabilities=company_data.get('liabilities', 0),
            profit=company_data.get('profit', 0),
            existing_loans=company_data.get('existing_loans', 0),
            litigation=company_data.get('litigation', 0),
            gst_revenue=company_data.get('gst_revenue', 0)
        )
        
        # Calculate derived metrics
        derived_metrics = risk_metrics.calculate_derived_metrics()
        
        # Start with base score
        base_score = 50
        score_adjustments = []
        identified_risks = []
        
        # Financial metric analysis
        for factor_name, factor_config in self.risk_factors.items():
            metric_value = derived_metrics.get(self._get_metric_name(factor_name), 0)
            
            if self._evaluate_condition(factor_name, metric_value, factor_config):
                adjustment = factor_config['impact']
                base_score += adjustment
                
                score_adjustments.append({
                    'factor': factor_config['description'],
                    'value': metric_value,
                    'impact': adjustment,
                    'type': 'increase' if adjustment > 0 else 'decrease'
                })
                
                if adjustment < 0:
                    identified_risks.append(factor_config['description'])
        
        # Research-based risk adjustments
        if research_data:
            research_impact = self._analyze_research_risks(research_data)
            base_score += research_impact['score_adjustment']
            identified_risks.extend(research_impact['additional_risks'])
        
        # Ensure score is within bounds
        final_score = max(0, min(100, base_score))
        
        # Determine risk category
        if final_score <= 40:
            risk_category = "High Risk"
            decision = "Reject"
        elif final_score <= 70:
            risk_category = "Medium Risk"
            decision = "Conditional Approval"
        else:
            risk_category = "Low Risk"
            decision = "Approve"
        
        return {
            'risk_score': final_score,
            'risk_category': risk_category,
            'decision': decision,
            'base_score': 50,
            'final_score': final_score,
            'score_adjustments': score_adjustments,
            'identified_risks': identified_risks,
            'financial_metrics': derived_metrics,
            'confidence_level': self._calculate_confidence(derived_metrics, research_data)
        }
    
    def _get_metric_name(self, factor_name: str) -> str:
        """Map factor names to metric names"""
        mapping = {
            'high_debt_ratio': 'debt_to_equity',
            'low_profit_margin': 'profit_margin',
            'good_profit_margin': 'profit_margin',
            'negative_working_capital': 'working_capital_ratio',
            'high_litigation': 'litigation_ratio',
            'good_cash_flow': 'cash_flow_stability',
            'poor_gst_consistency': 'gst_consistency',
            'high_existing_debt': 'existing_loans'
        }
        return mapping.get(factor_name, '')
    
    def _evaluate_condition(self, factor_name: str, value: float, config: Dict) -> bool:
        """Evaluate if risk factor condition is met"""
        threshold = config['threshold']
        
        if factor_name in ['high_debt_ratio', 'high_litigation', 'high_existing_debt']:
            return value > threshold
        elif factor_name == 'low_profit_margin':
            return value < threshold
        elif factor_name == 'good_profit_margin':
            return value > threshold
        elif factor_name == 'negative_working_capital':
            return value < threshold
        elif factor_name == 'good_cash_flow':
            return value > threshold
        elif factor_name == 'poor_gst_consistency':
            return value < threshold
        
        return False
    
    def _analyze_research_risks(self, research_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze research findings for additional risk factors"""
        score_adjustment = 0
        additional_risks = []
        
        # Analyze news sentiment
        if 'news_sentiment' in research_data:
            sentiment = research_data['news_sentiment'].get('score', 0)
            if sentiment < -0.3:  # Negative sentiment
                score_adjustment -= 10
                additional_risks.append("Negative news sentiment detected")
            elif sentiment > 0.3:  # Positive sentiment
                score_adjustment += 5
        
        # Analyze litigation
        if 'litigation_data' in research_data:
            total_cases = research_data['litigation_data'].get('total_cases', 0)
            if total_cases > 5:
                score_adjustment -= 15
                additional_risks.append("Multiple active litigation cases")
            elif total_cases > 2:
                score_adjustment -= 5
                additional_risks.append("Pending litigation matters")
        
        # Analyze industry outlook
        if 'sector_outlook' in research_data:
            outlook = research_data['sector_outlook'].get('outlook', '').lower()
            if outlook == 'negative':
                score_adjustment -= 10
                additional_risks.append("Negative industry outlook")
            elif outlook == 'positive':
                score_adjustment += 5
        
        return {
            'score_adjustment': score_adjustment,
            'additional_risks': additional_risks
        }
    
    def _calculate_confidence(self, metrics: Dict[str, float], research_data: Dict[str, Any] = None) -> str:
        """Calculate confidence level of the risk assessment"""
        confidence_score = 0
        
        # Data completeness
        if metrics.get('debt_to_equity', 0) > 0:
            confidence_score += 20
        if metrics.get('profit_margin', 0) > 0:
            confidence_score += 20
        if metrics.get('working_capital_ratio', 0) > 0:
            confidence_score += 20
        
        # Research data availability
        if research_data:
            if 'news_sentiment' in research_data:
                confidence_score += 15
            if 'litigation_data' in research_data:
                confidence_score += 15
            if 'sector_outlook' in research_data:
                confidence_score += 10
        
        if confidence_score >= 80:
            return "High"
        elif confidence_score >= 60:
            return "Medium"
        else:
            return "Low"
