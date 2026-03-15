from typing import Dict, List, Any
import math

class RecommendationEngine:
    def __init__(self):
        self.risk_thresholds = {
            'approve': 75,
            'conditional': 60,
            'reject': 60
        }
        self.interest_rate_bands = {
            'Very Low': 8.5,
            'Low': 9.5,
            'Medium': 11.0,
            'High': 12.5,
            'Very High': 14.0
        }
        self.loan_multiplier = {
            'Very Low': 5.0,
            'Low': 4.0,
            'Medium': 3.0,
            'High': 2.0,
            'Very High': 1.5
        }
    
    def generate_recommendation(self, risk_score: float, risk_category: str, 
                              financial_data: Dict, component_scores: Dict) -> Dict[str, Any]:
        """Generate final lending recommendation"""
        
        recommendation = {
            'decision': '',
            'loan_limit': 0,
            'interest_rate': 0.0,
            'tenure_months': 0,
            'conditions': [],
            'explanations': [],
            'risk_adjusted_pricing': {},
            'alternative_suggestions': []
        }
        
        # Determine decision
        recommendation['decision'] = self._determine_decision(risk_score)
        
        # Calculate loan limit
        recommendation['loan_limit'] = self._calculate_loan_limit(
            risk_category, financial_data, component_scores
        )
        
        # Calculate interest rate
        recommendation['interest_rate'] = self._calculate_interest_rate(
            risk_category, risk_score, component_scores
        )
        
        # Determine tenure
        recommendation['tenure_months'] = self._determine_tenure(risk_category, financial_data)
        
        # Generate conditions
        recommendation['conditions'] = self._generate_conditions(
            recommendation['decision'], risk_category, component_scores
        )
        
        # Generate explanations
        recommendation['explanations'] = self._generate_explanations(
            risk_score, risk_category, component_scores
        )
        
        # Risk-adjusted pricing details
        recommendation['risk_adjusted_pricing'] = self._calculate_risk_adjusted_pricing(
            risk_score, risk_category
        )
        
        # Alternative suggestions
        recommendation['alternative_suggestions'] = self._suggest_alternatives(
            recommendation['decision'], risk_category
        )
        
        return recommendation
    
    def _determine_decision(self, risk_score: float) -> str:
        """Determine lending decision based on risk score"""
        
        if risk_score >= self.risk_thresholds['approve']:
            return 'Approve'
        elif risk_score >= self.risk_thresholds['conditional']:
            return 'Conditional Approval'
        else:
            return 'Reject'
    
    def _calculate_loan_limit(self, risk_category: str, financial_data: Dict, 
                            component_scores: Dict) -> int:
        """Calculate recommended loan limit"""
        
        # Base calculation on revenue
        revenue = financial_data.get('revenue', 0)
        existing_loans = financial_data.get('existing_loans', 0)
        
        if revenue == 0:
            return 0
        
        # Base loan amount as percentage of revenue
        base_multiplier = self.loan_multiplier.get(risk_category, 2.0)
        base_loan_amount = revenue * base_multiplier / 12  # Monthly equivalent
        
        # Adjust for existing debt burden
        if revenue > 0:
            debt_to_revenue = existing_loans / revenue
            if debt_to_revenue > 1.5:
                base_loan_amount *= 0.3  # Reduce by 70%
            elif debt_to_revenue > 1.0:
                base_loan_amount *= 0.5  # Reduce by 50%
            elif debt_to_revenue > 0.5:
                base_loan_amount *= 0.7  # Reduce by 30%
        
        # Adjust for component scores
        financial_score = component_scores.get('financial', 50)
        if financial_score > 70:
            base_loan_amount *= 0.6  # Reduce for high financial risk
        elif financial_score < 30:
            base_loan_amount *= 1.2  # Increase for low financial risk
        
        consistency_score = component_scores.get('consistency', 50)
        if consistency_score > 70:
            base_loan_amount *= 0.7  # Reduce for consistency issues
        
        # Apply minimum and maximum limits
        min_loan = 100000  # 1 lakh minimum
        max_loan = revenue * 0.5  # Maximum 50% of annual revenue
        
        final_loan = int(max(min_loan, min(base_loan_amount, max_loan)))
        
        # Round to nearest lakh
        return round(final_loan / 100000) * 100000
    
    def _calculate_interest_rate(self, risk_category: str, risk_score: float, 
                              component_scores: Dict) -> float:
        """Calculate interest rate based on risk"""
        
        base_rate = self.interest_rate_bands.get(risk_category, 11.0)
        
        # Fine-tune based on exact risk score
        risk_adjustment = (risk_score - 50) * 0.05  # 0.05% per point above/below 50
        adjusted_rate = base_rate + risk_adjustment
        
        # Adjust for specific risk factors
        financial_score = component_scores.get('financial', 50)
        if financial_score > 80:
            adjusted_rate += 1.0  # Add 1% for very high financial risk
        elif financial_score > 70:
            adjusted_rate += 0.5  # Add 0.5% for high financial risk
        
        consistency_score = component_scores.get('consistency', 50)
        if consistency_score > 70:
            adjusted_rate += 0.5  # Add 0.5% for consistency issues
        
        research_score = component_scores.get('research', 50)
        if research_score > 70:
            adjusted_rate += 0.3  # Add 0.3% for research red flags
        
        # Apply rate caps
        min_rate = 7.0
        max_rate = 18.0
        
        return round(max(min_rate, min(adjusted_rate, max_rate)), 1)
    
    def _determine_tenure(self, risk_category: str, financial_data: Dict) -> int:
        """Determine recommended loan tenure"""
        
        # Base tenure by risk category
        base_tenure = {
            'Very Low': 60,  # 5 years
            'Low': 48,       # 4 years
            'Medium': 36,    # 3 years
            'High': 24,      # 2 years
            'Very High': 12  # 1 year
        }
        
        tenure = base_tenure.get(risk_category, 36)
        
        # Adjust for business type
        revenue = financial_data.get('revenue', 0)
        if revenue > 100000000:  # Large businesses
            tenure = min(tenure + 12, 60)  # Add up to 1 year
        elif revenue < 10000000:  # Small businesses
            tenure = min(tenure, 24)  # Cap at 2 years
        
        return tenure
    
    def _generate_conditions(self, decision: str, risk_category: str, 
                           component_scores: Dict) -> List[str]:
        """Generate loan conditions"""
        
        conditions = []
        
        if decision == 'Conditional Approval':
            conditions.append("Quarterly financial statement submission")
            conditions.append("Monthly cash flow reporting")
            conditions.append("No additional borrowing without lender consent")
            conditions.append("Maintain current debt-to-equity ratio")
        
        if risk_category in ['High', 'Very High']:
            conditions.append("Personal guarantee from promoters")
            conditions.append("Regular site visits by lender")
            conditions.append("Enhanced monitoring and covenants")
        
        # Component-specific conditions
        if component_scores.get('financial', 0) > 70:
            conditions.append("Maintain minimum current ratio of 1.2")
            conditions.append("Restrict dividend payments until debt reduction")
        
        if component_scores.get('consistency', 0) > 70:
            conditions.append("Third-party audit of financial statements")
            conditions.append("Bank statement verification for 6 months")
        
        if component_scores.get('research', 0) > 70:
            conditions.append("Submit latest litigation status report")
            conditions.append("Provide details of any new legal proceedings")
        
        # General conditions for all approvals
        if decision != 'Reject':
            conditions.append("Insurance for assets pledged as collateral")
            conditions.append("Life insurance for key promoters")
        
        return conditions
    
    def _generate_explanations(self, risk_score: float, risk_category: str, 
                             component_scores: Dict) -> List[str]:
        """Generate explanations for the decision"""
        
        explanations = []
        
        # Risk score explanation
        if risk_score >= 75:
            explanations.append("High risk score indicates elevated credit risk")
        elif risk_score >= 60:
            explanations.append("Moderate risk score requires careful monitoring")
        else:
            explanations.append("Acceptable risk profile for lending")
        
        # Component-based explanations
        if component_scores.get('financial', 0) > 70:
            explanations.append("Financial metrics indicate elevated risk")
        elif component_scores.get('financial', 0) < 30:
            explanations.append("Strong financial fundamentals support lending")
        
        if component_scores.get('consistency', 0) > 70:
            explanations.append("Data inconsistencies raise concerns")
        
        if component_scores.get('research', 0) > 70:
            explanations.append("External research findings indicate elevated risk")
        
        if component_scores.get('qualitative', 0) > 70:
            explanations.append("Qualitative assessment suggests higher risk")
        
        # Risk category specific explanations
        if risk_category == 'Very High':
            explanations.append("Very high risk profile - recommend rejection")
        elif risk_category == 'High':
            explanations.append("High risk profile - strict conditions recommended")
        elif risk_category == 'Medium':
            explanations.append("Medium risk profile - standard terms applicable")
        else:
            explanations.append("Low risk profile - favorable terms recommended")
        
        return explanations[:6]  # Limit to top 6 explanations
    
    def _calculate_risk_adjusted_pricing(self, risk_score: float, risk_category: str) -> Dict[str, Any]:
        """Calculate risk-adjusted pricing details"""
        
        base_rate = self.interest_rate_bands.get(risk_category, 11.0)
        
        pricing = {
            'base_rate': base_rate,
            'risk_premium': round(base_rate - 8.5, 1),  # Premium over base rate
            'processing_fee': 2.0 if risk_category in ['High', 'Very High'] else 1.0,
            'prepayment_penalty': 3.0 if risk_category in ['High', 'Very High'] else 2.0,
            'collateral_requirement': self._get_collateral_requirement(risk_category)
        }
        
        return pricing
    
    def _get_collateral_requirement(self, risk_category: str) -> str:
        """Determine collateral requirement based on risk"""
        
        requirements = {
            'Very Low': 'No collateral required for loans up to 50 lakhs',
            'Low': 'Collateral required for loans above 1 crore',
            'Medium': 'Collateral required for loans above 50 lakhs',
            'High': '100% collateral coverage required',
            'Very High': '150% collateral coverage with personal guarantees'
        }
        
        return requirements.get(risk_category, 'Collateral as per policy')
    
    def _suggest_alternatives(self, decision: str, risk_category: str) -> List[str]:
        """Suggest alternative financing options"""
        
        alternatives = []
        
        if decision == 'Reject':
            alternatives.extend([
                "Consider working capital finance instead of term loan",
                "Explore invoice discounting or factoring",
                "Consider government-backed loan schemes",
                "Recommend equity infusion or venture capital",
                "Suggest asset-based lending"
            ])
        elif decision == 'Conditional Approval':
            alternatives.extend([
                "Consider smaller loan amount with easier conditions",
                "Explore line of credit instead of term loan",
                "Consider staggered disbursement based on milestones"
            ])
        else:  # Approve
            alternatives.extend([
                "Consider higher loan amount based on strong profile",
                "Explore longer tenure options",
                "Consider refinancing existing high-cost debt"
            ])
        
        return alternatives[:4]  # Limit to top 4 suggestions
