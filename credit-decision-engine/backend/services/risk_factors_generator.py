"""
Company-Specific Risk Factors Generator
Combines financial analysis, research findings, and industry context to generate unique risk factors
"""

from typing import Dict, List, Any
from dataclasses import dataclass
import re

@dataclass
class RiskFactor:
    """Data class for individual risk factors"""
    category: str
    description: str
    severity: str  # Low, Medium, High, Critical
    impact: str
    source: str  # Financial, Research, Industry, Regulatory
    recommendation: str

class RiskFactorsGenerator:
    """Generates company-specific risk factors based on comprehensive analysis"""
    
    def __init__(self):
        self.financial_risk_patterns = {
            'high_debt_ratio': {
                'threshold': 2.0,
                'description': 'High debt-to-equity ratio indicates excessive leverage',
                'severity': 'High',
                'impact': 'Increases default risk and reduces financial flexibility',
                'recommendation': 'Monitor debt service coverage and consider debt restructuring'
            },
            'low_profit_margin': {
                'threshold': 5.0,
                'description': 'Low profit margin suggests operational inefficiency',
                'severity': 'Medium',
                'impact': 'Reduced ability to absorb shocks and generate cash flow',
                'recommendation': 'Review cost structure and pricing strategy'
            },
            'negative_working_capital': {
                'threshold': 10.0,
                'description': 'Low working capital indicates liquidity constraints',
                'severity': 'High',
                'impact': 'Potential cash flow problems and difficulty meeting obligations',
                'recommendation': 'Improve working capital management and secure additional liquidity'
            },
            'high_litigation': {
                'threshold': 5.0,
                'description': 'Significant litigation exposure',
                'severity': 'Medium',
                'impact': 'Potential financial losses and reputational damage',
                'recommendation': 'Strengthen legal compliance and consider insurance coverage'
            },
            'poor_cash_flow': {
                'threshold': 0.3,
                'description': 'Weak cash flow relative to debt obligations',
                'severity': 'High',
                'impact': 'Difficulty servicing debt and funding operations',
                'recommendation': 'Implement strict cash flow monitoring and cost controls'
            }
        }
        
        self.industry_risk_mapping = {
            'manufacturing': [
                'Supply chain dependency',
                'Raw material price volatility',
                'Technology obsolescence risk',
                'Environmental compliance costs'
            ],
            'technology': [
                'Rapid technological changes',
                'Cybersecurity threats',
                'Talent retention challenges',
                'Intellectual property risks'
            ],
            'retail': [
                'Changing consumer preferences',
                'E-commerce competition',
                'Inventory management risks',
                'Seasonal demand fluctuations'
            ],
            'financial_services': [
                'Regulatory compliance burden',
                'Market volatility exposure',
                'Credit risk concentration',
                'Technology disruption'
            ],
            'healthcare': [
                'Regulatory approval risks',
                'Medical malpractice exposure',
                'Reimbursement policy changes',
                'R&D investment uncertainty'
            ]
        }
    
    def generate_risk_factors(self, company_data: Dict[str, Any], 
                            risk_analysis: Dict[str, Any], 
                            research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate comprehensive, company-specific risk factors
        
        Args:
            company_data: Financial data from uploaded documents
            risk_analysis: Risk score and analysis results
            research_data: AI research findings
            
        Returns:
            List of detailed risk factors with severity and recommendations
        """
        risk_factors = []
        
        # Generate financial risk factors
        financial_factors = self._generate_financial_risk_factors(company_data, risk_analysis)
        risk_factors.extend(financial_factors)
        
        # Generate research-based risk factors
        research_factors = self._generate_research_risk_factors(research_data)
        risk_factors.extend(research_factors)
        
        # Generate industry-specific risk factors
        industry_factors = self._generate_industry_risk_factors(company_data, research_data)
        risk_factors.extend(industry_factors)
        
        # Generate operational risk factors
        operational_factors = self._generate_operational_risk_factors(company_data, risk_analysis)
        risk_factors.extend(operational_factors)
        
        # Generate regulatory and compliance risk factors
        regulatory_factors = self._generate_regulatory_risk_factors(research_data)
        risk_factors.extend(regulatory_factors)
        
        # Sort by severity and limit to top factors
        risk_factors.sort(key=lambda x: self._severity_score(x['severity']), reverse=True)
        
        return risk_factors[:8]  # Return top 8 risk factors
    
    def _generate_financial_risk_factors(self, company_data: Dict[str, Any], 
                                       risk_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate risk factors based on financial metrics"""
        factors = []
        
        financial_metrics = risk_analysis.get('financial_metrics', {})
        
        for pattern_name, pattern_config in self.financial_risk_patterns.items():
            metric_name = self._get_metric_name(pattern_name)
            metric_value = financial_metrics.get(metric_name, 0)
            
            if self._evaluate_financial_condition(pattern_name, metric_value, pattern_config):
                factor = {
                    'category': 'Financial Risk',
                    'description': pattern_config['description'],
                    'severity': pattern_config['severity'],
                    'impact': pattern_config['impact'],
                    'source': 'Financial Analysis',
                    'recommendation': pattern_config['recommendation'],
                    'metric_value': metric_value,
                    'threshold': pattern_config['threshold']
                }
                factors.append(factor)
        
        # Add revenue concentration risk
        revenue = company_data.get('revenue', 0)
        if revenue > 0:
            # Check if company is overly dependent on few clients (mock analysis)
            factors.append({
                'category': 'Financial Risk',
                'description': 'Revenue concentration risk - potential dependency on key clients',
                'severity': 'Medium',
                'impact': 'Loss of major clients could significantly impact revenue',
                'source': 'Financial Analysis',
                'recommendation': 'Diversify client base and strengthen customer relationships'
            })
        
        return factors
    
    def _generate_research_risk_factors(self, research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate risk factors based on research findings"""
        factors = []
        
        research_summary = research_data.get('research_summary', {})
        
        # News sentiment risk factors
        news_sentiment = research_summary.get('news_sentiment', {})
        sentiment_score = news_sentiment.get('score', 0)
        
        if sentiment_score < -0.2:
            factors.append({
                'category': 'Reputational Risk',
                'description': 'Negative news sentiment indicates potential reputational issues',
                'severity': 'Medium',
                'impact': 'May affect business relationships and customer confidence',
                'source': 'News Analysis',
                'recommendation': 'Implement proactive PR strategy and address underlying issues'
            })
        
        # Litigation risk factors
        litigation_data = research_summary.get('litigation_data', {})
        total_cases = litigation_data.get('total_cases', 0)
        
        if total_cases > 2:
            factors.append({
                'category': 'Legal Risk',
                'description': f'Multiple legal matters ({total_cases} cases) require attention',
                'severity': 'High' if total_cases > 5 else 'Medium',
                'impact': 'Potential financial losses and management distraction',
                'source': 'Legal Research',
                'recommendation': 'Strengthen legal compliance and consider settlement strategies'
            })
        
        # Research risk signals
        risk_signals = research_summary.get('risk_signals', [])
        for signal in risk_signals[:3]:  # Top 3 risk signals
            if signal != 'No significant risk signals found':
                factors.append({
                    'category': 'Business Risk',
                    'description': signal,
                    'severity': 'Medium',
                    'impact': 'May affect business performance and growth prospects',
                    'source': 'AI Research',
                    'recommendation': 'Monitor closely and develop mitigation strategies'
                })
        
        return factors
    
    def _generate_industry_risk_factors(self, company_data: Dict[str, Any], 
                                      research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate industry-specific risk factors"""
        factors = []
        
        company_name = company_data.get('company', '').lower()
        
        # Determine industry based on company name (mock logic)
        industry = self._determine_industry(company_name)
        
        if industry in self.industry_risk_mapping:
            industry_risks = self.industry_risk_mapping[industry]
            
            for risk_desc in industry_risks[:2]:  # Top 2 industry risks
                factors.append({
                    'category': 'Industry Risk',
                    'description': risk_desc,
                    'severity': 'Medium',
                    'impact': 'Industry-specific challenges may affect performance',
                    'source': 'Industry Analysis',
                    'recommendation': 'Develop industry-specific risk mitigation strategies'
                })
        
        # Industry outlook risk
        industry_analysis = research_data.get('research_summary', {}).get('industry_analysis', {})
        outlook = industry_analysis.get('outlook', '').lower()
        
        if outlook in ['challenging', 'negative']:
            factors.append({
                'category': 'Industry Risk',
                'description': f'Challenging industry outlook ({outlook})',
                'severity': 'High',
                'impact': 'Industry downturn may affect company performance',
                'source': 'Industry Analysis',
                'recommendation': 'Focus on cost efficiency and market differentiation'
            })
        
        return factors
    
    def _generate_operational_risk_factors(self, company_data: Dict[str, Any], 
                                         risk_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate operational risk factors"""
        factors = []
        
        # Size-related operational risks
        revenue = company_data.get('revenue', 0)
        
        if revenue < 500000000:  # Less than ₹50 Cr
            factors.append({
                'category': 'Operational Risk',
                'description': 'Limited scale may affect competitive positioning',
                'severity': 'Medium',
                'impact': 'May face challenges in competing with larger players',
                'source': 'Operational Analysis',
                'recommendation': 'Focus on niche markets and operational efficiency'
            })
        
        # Working capital management risk
        assets = company_data.get('assets', 0)
        liabilities = company_data.get('liabilities', 0)
        
        if assets > 0 and (liabilities / assets) > 0.7:
            factors.append({
                'category': 'Operational Risk',
                'description': 'High asset utilization indicates potential operational strain',
                'severity': 'Medium',
                'impact': 'May limit flexibility and growth capacity',
                'source': 'Operational Analysis',
                'recommendation': 'Optimize asset utilization and consider capacity expansion'
            })
        
        return factors
    
    def _generate_regulatory_risk_factors(self, research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate regulatory and compliance risk factors"""
        factors = []
        
        # Add general regulatory compliance risk
        factors.append({
            'category': 'Regulatory Risk',
            'description': 'Regulatory compliance requirements increasing across sectors',
            'severity': 'Medium',
            'impact': 'Compliance costs and potential penalties for non-compliance',
            'source': 'Regulatory Analysis',
            'recommendation': 'Strengthen compliance framework and stay updated on regulations'
        })
        
        # Environmental, Social, Governance (ESG) risks
        factors.append({
            'category': 'ESG Risk',
            'description': 'Growing ESG compliance requirements and stakeholder expectations',
            'severity': 'Low',
            'impact': 'May affect access to capital and market reputation',
            'source': 'ESG Analysis',
            'recommendation': 'Develop comprehensive ESG strategy and reporting framework'
        })
        
        return factors
    
    def _get_metric_name(self, pattern_name: str) -> str:
        """Map pattern names to metric names"""
        mapping = {
            'high_debt_ratio': 'debt_to_equity',
            'low_profit_margin': 'profit_margin',
            'negative_working_capital': 'working_capital_ratio',
            'high_litigation': 'litigation_ratio',
            'poor_cash_flow': 'cash_flow_stability'
        }
        return mapping.get(pattern_name, '')
    
    def _evaluate_financial_condition(self, pattern_name: str, value: float, 
                                    config: Dict) -> bool:
        """Evaluate if financial risk condition is met"""
        threshold = config['threshold']
        
        if pattern_name in ['high_debt_ratio', 'high_litigation']:
            return value > threshold
        elif pattern_name == 'low_profit_margin':
            return value < threshold
        elif pattern_name == 'negative_working_capital':
            return value < threshold
        elif pattern_name == 'poor_cash_flow':
            return value < threshold
        
        return False
    
    def _determine_industry(self, company_name: str) -> str:
        """Determine industry based on company name (mock logic)"""
        if any(keyword in company_name for keyword in ['tech', 'software', 'digital']):
            return 'technology'
        elif any(keyword in company_name for keyword in ['manufacturing', 'industrial', 'engineering']):
            return 'manufacturing'
        elif any(keyword in company_name for keyword in ['retail', 'store', 'shop']):
            return 'retail'
        elif any(keyword in company_name for keyword in ['finance', 'bank', 'investment']):
            return 'financial_services'
        elif any(keyword in company_name for keyword in ['health', 'medical', 'pharma']):
            return 'healthcare'
        else:
            return 'manufacturing'  # Default
    
    def _severity_score(self, severity: str) -> int:
        """Convert severity to numeric score for sorting"""
        severity_mapping = {
            'Critical': 4,
            'High': 3,
            'Medium': 2,
            'Low': 1
        }
        return severity_mapping.get(severity, 0)
    
    def generate_risk_mitigation_plan(self, risk_factors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive risk mitigation plan"""
        # Group risk factors by category
        categorized_risks = {}
        for factor in risk_factors:
            category = factor['category']
            if category not in categorized_risks:
                categorized_risks[category] = []
            categorized_risks[category].append(factor)
        
        # Generate mitigation strategies for each category
        mitigation_plan = {}
        for category, factors in categorized_risks.items():
            high_severity_factors = [f for f in factors if f['severity'] in ['High', 'Critical']]
            
            mitigation_plan[category] = {
                'risk_count': len(factors),
                'high_priority_risks': len(high_severity_factors),
                'key_recommendations': [f['recommendation'] for f in high_severity_factors[:3]],
                'monitoring_required': high_severity_factors > 0,
                'review_frequency': 'Monthly' if high_severity_factors > 0 else 'Quarterly'
            }
        
        return {
            'total_risks': len(risk_factors),
            'high_priority_risks': len([f for f in risk_factors if f['severity'] in ['High', 'Critical']]),
            'categorized_plan': mitigation_plan,
            'overall_risk_level': self._assess_overall_risk_level(risk_factors)
        }
    
    def _assess_overall_risk_level(self, risk_factors: List[Dict[str, Any]]) -> str:
        """Assess overall risk level based on all risk factors"""
        critical_count = len([f for f in risk_factors if f['severity'] == 'Critical'])
        high_count = len([f for f in risk_factors if f['severity'] == 'High'])
        
        if critical_count > 0 or high_count > 3:
            return 'High'
        elif high_count > 0:
            return 'Medium'
        else:
            return 'Low'
