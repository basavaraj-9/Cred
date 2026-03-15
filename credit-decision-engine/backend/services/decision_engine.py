"""
AI Credit Decision Engine with Explanations
Makes intelligent lending decisions with detailed reasoning and explanations
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DecisionResult:
    """Data class for credit decision results"""
    decision: str  # Approve, Conditional Approval, Reject
    confidence_score: float
    reasoning: str
    key_factors: List[str]
    conditions: List[str]
    recommended_actions: List[str]
    next_review_date: str

class DecisionEngine:
    """Advanced credit decision engine with explainable AI"""
    
    def __init__(self):
        self.decision_thresholds = {
            'approve_min': 71,
            'conditional_min': 50,
            'reject_max': 49
        }
        
        self.decision_factors = {
            'positive': [
                'Strong revenue growth',
                'Healthy profit margins',
                'Low debt burden',
                'Positive cash flow',
                'Good industry outlook',
                'Clean legal record',
                'Strong asset base',
                'Positive news sentiment'
            ],
            'negative': [
                'High debt-to-equity ratio',
                'Negative profit margins',
                'Poor cash flow',
                'Industry challenges',
                'Legal issues',
                'Negative news sentiment',
                'Weak working capital',
                'High litigation exposure'
            ]
        }
    
    def make_credit_decision(self, company_data: Dict[str, Any], 
                           risk_analysis: Dict[str, Any],
                           loan_analysis: Dict[str, Any],
                           research_data: Dict[str, Any],
                           risk_factors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make comprehensive credit decision with detailed explanations
        
        Args:
            company_data: Company financial data
            risk_analysis: Risk score and analysis
            loan_analysis: Loan affordability and terms
            research_data: AI research findings
            risk_factors: Generated risk factors
            
        Returns:
            Complete decision with reasoning and recommendations
        """
        # Extract key metrics
        risk_score = risk_analysis.get('risk_score', 50)
        risk_category = risk_analysis.get('risk_category', 'Medium Risk')
        
        # Make primary decision based on risk score
        decision, confidence = self._make_base_decision(risk_score)
        
        # Generate detailed reasoning
        reasoning = self._generate_reasoning(
            company_data, risk_analysis, loan_analysis, research_data, risk_factors, decision
        )
        
        # Identify key factors influencing decision
        key_factors = self._identify_key_factors(
            risk_analysis, loan_analysis, research_data, risk_factors, decision
        )
        
        # Generate conditions and recommendations
        conditions = self._generate_conditions(decision, risk_score, risk_factors)
        recommended_actions = self._generate_recommended_actions(
            decision, risk_factors, company_data
        )
        
        # Set next review date
        next_review = self._calculate_next_review_date(decision, risk_score)
        
        decision_result = DecisionResult(
            decision=decision,
            confidence_score=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            conditions=conditions,
            recommended_actions=recommended_actions,
            next_review_date=next_review
        )
        
        return self._format_decision_output(decision_result, company_data, risk_analysis, loan_analysis)
    
    def _make_base_decision(self, risk_score: int) -> Tuple[str, float]:
        """Make base decision based on risk score"""
        if risk_score >= self.decision_thresholds['approve_min']:
            return "Approve", min(0.95, 0.5 + (risk_score - 70) * 0.015)
        elif risk_score >= self.decision_thresholds['conditional_min']:
            return "Conditional Approval", min(0.85, 0.4 + (risk_score - 50) * 0.015)
        else:
            return "Reject", max(0.6, 0.9 - (50 - risk_score) * 0.01)
    
    def _generate_reasoning(self, company_data: Dict[str, Any], risk_analysis: Dict[str, Any],
                          loan_analysis: Dict[str, Any], research_data: Dict[str, Any],
                          risk_factors: List[Dict[str, Any]], decision: str) -> str:
        """Generate detailed reasoning for the decision"""
        company_name = company_data.get('company', 'Company')
        risk_score = risk_analysis.get('risk_score', 50)
        revenue = company_data.get('revenue', 0)
        profit = company_data.get('profit', 0)
        
        reasoning = f"Credit Decision Analysis for {company_name}:\n\n"
        
        # Financial performance summary
        reasoning += f"Financial Performance:\n"
        reasoning += f"• Annual Revenue: ₹{revenue/10000000:.1f} Cr\n"
        reasoning += f"• Annual Profit: ₹{profit/10000000:.1f} Cr\n"
        reasoning += f"• Risk Score: {risk_score}/100 ({risk_analysis.get('risk_category', 'Medium Risk')})\n\n"
        
        # Decision-specific reasoning
        if decision == "Approve":
            reasoning += f"Approval Rationale:\n"
            reasoning += f"• Strong financial profile with risk score of {risk_score}\n"
            reasoning += f"• Healthy profit margins indicate operational efficiency\n"
            reasoning += f"• Manageable debt levels and positive cash flow\n"
            reasoning += f"• Favorable industry outlook and market position\n"
            
        elif decision == "Conditional Approval":
            reasoning += f"Conditional Approval Rationale:\n"
            reasoning += f"• Moderate risk profile (score: {risk_score}) requires monitoring\n"
            
            # Identify specific concerns
            high_risk_factors = [f for f in risk_factors if f['severity'] in ['High', 'Critical']]
            if high_risk_factors:
                reasoning += f"• Key concerns: {', '.join([f['description'] for f in high_risk_factors[:2]])}\n"
            
            reasoning += f"• Overall business model viable with proper risk mitigation\n"
            reasoning += f"• Conditions imposed to address identified risks\n"
            
        else:  # Reject
            reasoning += f"Rejection Rationale:\n"
            reasoning += f"• High risk profile (score: {risk_score}) exceeds acceptable thresholds\n"
            
            # Identify critical issues
            critical_factors = [f for f in risk_factors if f['severity'] == 'Critical']
            if critical_factors:
                reasoning += f"• Critical issues: {', '.join([f['description'] for f in critical_factors])}\n"
            
            reasoning += f"• Financial metrics indicate potential default risk\n"
            reasoning += f"• Recommend addressing core issues before reapplying\n"
        
        # Loan affordability context
        approved_amount = loan_analysis.get('approved_loan_amount', 0)
        reasoning += f"\nLoan Assessment:\n"
        reasoning += f"• Approved Amount: ₹{approved_amount/10000000:.1f} Cr\n"
        reasoning += f"• Interest Rate: {loan_analysis.get('interest_rate', 0)}%\n"
        reasoning += f"• Debt Service Ratio: {loan_analysis.get('debt_service_ratio', 0):.1f}x\n"
        
        return reasoning
    
    def _identify_key_factors(self, risk_analysis: Dict[str, Any], loan_analysis: Dict[str, Any],
                            research_data: Dict[str, Any], risk_factors: List[Dict[str, Any]],
                            decision: str) -> List[str]:
        """Identify key factors influencing the decision"""
        key_factors = []
        
        # Risk score impact
        risk_score = risk_analysis.get('risk_score', 50)
        if risk_score >= 75:
            key_factors.append("Excellent risk profile with strong financial metrics")
        elif risk_score >= 60:
            key_factors.append("Good risk profile with manageable risks")
        elif risk_score >= 40:
            key_factors.append("Moderate risk profile requiring monitoring")
        else:
            key_factors.append("High risk profile with significant concerns")
        
        # Top risk factors
        high_severity_factors = [f for f in risk_factors if f['severity'] in ['High', 'Critical']]
        for factor in high_severity_factors[:2]:
            key_factors.append(f"{factor['category']}: {factor['description']}")
        
        # Positive factors
        if risk_score > 50:
            revenue = loan_analysis.get('affordability_analysis', {}).get('base_calculation', '')
            if revenue:
                key_factors.append("Strong revenue and profit generation capacity")
        
        # Research insights
        research_summary = research_data.get('research_summary', {})
        news_sentiment = research_summary.get('news_sentiment', {}).get('sentiment', 'Neutral')
        if news_sentiment == 'Positive':
            key_factors.append("Positive market sentiment and news coverage")
        elif news_sentiment == 'Negative':
            key_factors.append("Negative market sentiment requires attention")
        
        # Industry context
        industry_outlook = research_summary.get('industry_analysis', {}).get('outlook', 'Stable')
        if industry_outlook == 'Positive':
            key_factors.append("Favorable industry outlook and growth prospects")
        elif industry_outlook == 'Challenging':
            key_factors.append("Challenging industry conditions affect risk assessment")
        
        return key_factors[:6]  # Return top 6 factors
    
    def _generate_conditions(self, decision: str, risk_score: int, 
                           risk_factors: List[Dict[str, Any]]) -> List[str]:
        """Generate conditions based on decision and risk profile"""
        conditions = []
        
        if decision == "Approve":
            # Standard conditions for approved cases
            conditions.extend([
                "Quarterly financial statement submission",
                "Annual business review meeting",
                "Maintain current debt service coverage ratio > 1.5",
                "No additional borrowing without lender consent"
            ])
            
            # Additional conditions based on risk factors
            if risk_score < 80:
                conditions.append("Semi-annual performance monitoring")
            
        elif decision == "Conditional Approval":
            # Stricter conditions for conditional approval
            conditions.extend([
                "Monthly financial statement submission",
                "Quarterly business performance review",
                "Maintain debt service coverage ratio > 2.0",
                "Restrict dividend payments during loan tenure",
                "Provide personal guarantees from directors",
                "Collateral security for loan amount"
            ])
            
            # Risk-specific conditions
            for factor in risk_factors:
                if factor['severity'] == 'High' and 'Financial Risk' in factor['category']:
                    conditions.append("Weekly cash flow reporting")
                    break
            
            if any('Legal Risk' in f['category'] for f in risk_factors):
                conditions.append("Regular updates on legal proceedings")
        
        else:  # Reject
            # Recommendations for rejected cases (not conditions, but guidance)
            conditions.extend([
                "Improve financial metrics and profitability",
                "Reduce debt levels and improve cash flow",
                "Address legal and regulatory compliance issues",
                "Consider reapplication after 6-12 months"
            ])
        
        return conditions
    
    def _generate_recommended_actions(self, decision: str, risk_factors: List[Dict[str, Any]],
                                    company_data: Dict[str, Any]) -> List[str]:
        """Generate recommended actions for the company"""
        actions = []
        
        # Financial management actions
        high_financial_risks = [f for f in risk_factors if f['category'] == 'Financial Risk' and f['severity'] in ['High', 'Critical']]
        if high_financial_risks:
            actions.extend([
                "Implement comprehensive financial monitoring system",
                "Develop cost optimization and efficiency improvement plan",
                "Strengthen working capital management practices"
            ])
        
        # Operational actions
        if any(f['category'] == 'Operational Risk' for f in risk_factors):
            actions.extend([
                "Review and optimize operational processes",
                "Implement risk management framework",
                "Develop business continuity plan"
            ])
        
        # Legal and compliance actions
        if any(f['category'] in ['Legal Risk', 'Regulatory Risk'] for f in risk_factors):
            actions.extend([
                "Strengthen legal compliance program",
                "Regular regulatory compliance audits",
                "Develop crisis management protocols"
            ])
        
        # Growth and strategy actions
        if decision in ['Approve', 'Conditional Approval']:
            actions.extend([
                "Focus on core business strengths and market position",
                "Explore strategic partnerships for growth",
                "Invest in technology and process improvements"
            ])
        
        # Decision-specific actions
        if decision == "Reject":
            actions.extend([
                "Conduct comprehensive business review",
                "Seek professional financial advisory services",
                "Consider restructuring debt and operations"
            ])
        
        return actions[:6]  # Return top 6 actions
    
    def _calculate_next_review_date(self, decision: str, risk_score: int) -> str:
        """Calculate next review date based on decision and risk"""
        from datetime import datetime, timedelta
        
        if decision == "Approve":
            if risk_score >= 80:
                days = 180  # 6 months
            else:
                days = 90   # 3 months
        elif decision == "Conditional Approval":
            days = 60      # 2 months
        else:  # Reject
            days = 180     # 6 months for reapplication
        
        next_review = datetime.now() + timedelta(days=days)
        return next_review.strftime("%Y-%m-%d")
    
    def _format_decision_output(self, decision_result: DecisionResult, 
                              company_data: Dict[str, Any],
                              risk_analysis: Dict[str, Any],
                              loan_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format decision output for API response"""
        return {
            'status': 'success',
            'decision': decision_result.decision,
            'confidence_score': decision_result.confidence_score,
            'reasoning': decision_result.reasoning,
            'key_factors': decision_result.key_factors,
            'conditions': decision_result.conditions,
            'recommended_actions': decision_result.recommended_actions,
            'next_review_date': decision_result.next_review_date,
            'decision_summary': {
                'company': company_data.get('company', 'Company'),
                'risk_score': risk_analysis.get('risk_score', 50),
                'risk_category': risk_analysis.get('risk_category', 'Medium Risk'),
                'approved_amount': loan_analysis.get('approved_loan_amount', 0),
                'interest_rate': loan_analysis.get('interest_rate', 0),
                'decision_timestamp': datetime.now().isoformat()
            },
            'decision_metrics': {
                'decision_confidence': decision_result.confidence_score,
                'risk_tolerance_level': self._get_risk_tolerance_level(decision_result.decision),
                'monitoring_intensity': self._get_monitoring_intensity(decision_result.decision, risk_analysis.get('risk_score', 50))
            }
        }
    
    def _get_risk_tolerance_level(self, decision: str) -> str:
        """Get risk tolerance level based on decision"""
        tolerance_mapping = {
            'Approve': 'Low Risk Tolerance',
            'Conditional Approval': 'Medium Risk Tolerance',
            'Reject': 'High Risk Aversion'
        }
        return tolerance_mapping.get(decision, 'Medium Risk Tolerance')
    
    def _get_monitoring_intensity(self, decision: str, risk_score: int) -> str:
        """Get monitoring intensity based on decision and risk score"""
        if decision == "Approve":
            return "Standard Monitoring" if risk_score >= 80 else "Enhanced Monitoring"
        elif decision == "Conditional Approval":
            return "Intensive Monitoring"
        else:
            return "Not Applicable"
    
    def generate_decision_summary(self, decision_result: Dict[str, Any]) -> str:
        """Generate concise decision summary for reports"""
        decision = decision_result.get('decision', 'Unknown')
        confidence = decision_result.get('confidence_score', 0)
        company = decision_result.get('decision_summary', {}).get('company', 'Company')
        amount = decision_result.get('decision_summary', {}).get('approved_amount', 0)
        
        summary = f"{decision}: {company}\n"
        summary += f"Confidence: {confidence:.1%} | "
        
        if decision in ['Approve', 'Conditional Approval']:
            summary += f"Loan: ₹{amount/10000000:.1f} Cr"
        else:
            summary += "Application not approved"
        
        return summary
