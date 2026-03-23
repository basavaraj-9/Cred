from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LoanRecommendation:
    """Comprehensive loan recommendation"""
    decision: str  # Approved, Rejected, Conditional Approval
    loan_amount: float
    interest_rate: float
    tenure_months: int
    emi_amount: float
    processing_fee: float
    collateral_required: bool
    guarantee_required: bool
    conditions: List[str]
    risk_mitigation_measures: List[str]
    alternative_options: List[Dict[str, Any]]
    pricing_breakdown: Dict[str, Any]
    repayment_schedule: List[Dict[str, Any]]
    decision_rationale: Dict[str, Any]  # New: Why this decision was made
    factor_weights: Dict[str, float]    # New: Contribution of each factor
    risk_details: Dict[str, Any]       # New: Granular risk metrics
    recommended_at: datetime

class RecommendationEngine:
    """Enhanced recommendation engine for lending decisions"""
    
    def __init__(self):
        # Risk thresholds for decision making
        self.risk_thresholds = {
            'approve': 75,
            'conditional': 55,
            'reject': 55
        }
        
        # Base interest rate bands (in percentage)
        self.base_interest_rates = {
            'Very Low': 8.5,
            'Low': 9.5,
            'Medium': 11.0,
            'High': 12.5,
            'Very High': 14.0
        }
        
        # Loan multipliers based on risk category
        self.loan_multipliers = {
            'Very Low': 5.0,   # 5x annual revenue
            'Low': 4.0,       # 4x annual revenue
            'Medium': 3.0,    # 3x annual revenue
            'High': 2.0,      # 2x annual revenue
            'Very High': 1.5  # 1.5x annual revenue
        }
        
        # Industry risk adjustments
        self.industry_adjustments = {
            'technology': -0.5,
            'manufacturing': 0.0,
            'healthcare': -0.3,
            'finance': 0.2,
            'retail': 0.8,
            'construction': 1.0,
            'agriculture': 1.5,
            'real_estate': 1.2,
            'telecom': 0.3,
            'automobile': 0.5
        }
        
        # Processing fee structure
        self.processing_fees = {
            'Approved': 0.5,      # 0.5% of loan amount
            'Conditional': 1.0,    # 1.0% of loan amount
            'Rejected': 0.0       # No processing fee
        }
    
    def generate_comprehensive_recommendation(self, risk_score: float, risk_category: str,
                                           financial_data: Dict, research_data: Dict,
                                           consistency_data: Dict, qualitative_inputs: Dict) -> LoanRecommendation:
        """Generate comprehensive lending recommendation"""
        
        logger.info(f"Generating recommendation for risk score: {risk_score}, category: {risk_category}")
        
        # Determine primary decision
        decision = self._determine_decision(risk_score, risk_category)
        
        # Calculate loan parameters
        loan_amount = self._calculate_optimal_loan_amount(risk_category, financial_data, research_data)
        interest_rate = self._calculate_risk_adjusted_rate(risk_category, financial_data, research_data)
        tenure = self._determine_optimal_tenure(loan_amount, financial_data, risk_category)
        
        # Calculate EMI
        emi_amount = self._calculate_emi(loan_amount, interest_rate, tenure)
        
        # Calculate processing fee
        processing_fee = loan_amount * (self.processing_fees.get(decision, 0.0) / 100)
        
        # Determine collateral and guarantee requirements
        collateral_required, guarantee_required = self._assess_security_requirements(
            decision, risk_category, loan_amount, financial_data
        )
        
        # Generate conditions and risk mitigation measures
        conditions = self._generate_loan_conditions(decision, risk_category, financial_data, research_data)
        risk_mitigation = self._generate_risk_mitigation_measures(risk_category, research_data, consistency_data)
        
        # Generate alternative options
        alternative_options = self._generate_alternative_options(loan_amount, risk_category, financial_data)
        
        # Create pricing breakdown
        pricing_breakdown = self._create_pricing_breakdown(interest_rate, financial_data, research_data)
        
        # Generate repayment schedule
        repayment_schedule = self._generate_repayment_schedule(loan_amount, interest_rate, tenure)
        
        # New: Generate Explainability Data
        factor_weights = self._calculate_factor_weights(risk_score, financial_data, research_data)
        decision_rationale = self._generate_decision_rationale(decision, factor_weights, risk_score)
        risk_details = {
            "score": risk_score,
            "category": risk_category,
            "thresholds": self.risk_thresholds
        }
        
        return LoanRecommendation(
            decision=decision,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            tenure_months=tenure,
            emi_amount=emi_amount,
            processing_fee=processing_fee,
            collateral_required=collateral_required,
            guarantee_required=guarantee_required,
            conditions=conditions,
            risk_mitigation_measures=risk_mitigation,
            alternative_options=alternative_options,
            pricing_breakdown=pricing_breakdown,
            repayment_schedule=repayment_schedule,
            decision_rationale=decision_rationale,
            factor_weights=factor_weights,
            risk_details=risk_details,
            recommended_at=datetime.now()
        )

    def _calculate_factor_weights(self, risk_score: float, financial_data: Dict, 
                                research_data: Dict) -> Dict[str, float]:
        """Calculate the contribution weight of each factor to the final score"""
        # This is a simplified simulation of XAI (e.g. SHAP values)
        weights = {
            "financial_stability": 40.0,
            "market_conditions": 25.0,
            "industry_risk": 20.0,
            "historical_performance": 15.0
        }
        
        # Adjust weights slightly based on data
        if financial_data.get('debt_to_equity', 1.0) > 2.0:
            weights["financial_stability"] += 10
            weights["market_conditions"] -= 10
            
        return weights

    def _generate_decision_rationale(self, decision: str, weights: Dict[str, float], 
                                   risk_score: float) -> Dict[str, Any]:
        """Generate a human-readable explanation for the decision"""
        top_factor: str = max(weights.keys(), key=lambda k: weights[k])
        
        observations: List[str] = [
            f"Financial stability is the dominant factor with {weights['financial_stability']}% weight.",
            "Risk scoring methodology accounts for industry-wide volatility trends."
        ]
        
        if decision == 'Rejected':
            observations.append("Risk threshold exceeded due to high leverage or market instability.")
        elif decision == 'Approved':
            observations.append("Strong cash flow alignment with requested loan parameters.")
            
        rationale: Dict[str, Any] = {
            "summary": f"Decision was primarily driven by {top_factor.replace('_', ' ')}.",
            "primary_factor": top_factor,
            "confidence_level": "High" if risk_score < 40 or risk_score > 80 else "Medium",
            "key_observations": observations
        }
        
        return rationale
    
    def _determine_decision(self, risk_score: float, risk_category: str) -> str:
        """Determine lending decision based on risk score and category.
        
        NOTE: risk_score is HIGH = BAD (50 = medium risk, 80+ = very high risk).
        Lower score means safer borrower.
        """
        if risk_score < self.risk_thresholds['conditional']:   # < 55 → Approved
            return 'Approved'
        elif risk_score < self.risk_thresholds['approve']:     # < 75 → Conditional
            return 'Conditional Approval'
        else:                                                  # >= 75 → Rejected
            return 'Rejected'
    
    def _calculate_optimal_loan_amount(self, risk_category: str, financial_data: Dict, 
                                     research_data: Dict) -> float:
        """Calculate optimal loan amount based on risk and financial capacity"""
        
        # Get annual revenue
        annual_revenue = financial_data.get('revenue', 0)
        if annual_revenue <= 0:
            return 0
        
        # 1. Base Cap: Revenue Multiplier (more conservative for high risk)
        # multipliers scaled down to be more realistic (e.g. 0.2x to 0.5x revenue)
        multiplier_map = {
            'Very Low': 0.5,
            'Low': 0.4,
            'Medium': 0.3,
            'High': 0.2,
            'Very High': 0.1
        }
        multiplier = multiplier_map.get(risk_category, 0.2)
        base_loan_amount = annual_revenue * multiplier
        
        # 2. Cash Flow Constraint (DSCR based)
        # Assuming monthly profit is roughly available for debt service
        monthly_profit = financial_data.get('profit', 0) / 12
        if monthly_profit > 0:
            # Monthly EMI should not exceed 50% of monthly profit for safety
            max_emi_capacity = monthly_profit * 0.5
            # Simplified: approx loan = max_emi * (expected life of loan in months)
            # A 36 month loan at 12% has a factor of ~30x monthly payment
            cash_flow_cap = max_emi_capacity * 30
            base_loan_amount = min(base_loan_amount, cash_flow_cap)
        
        # 3. Existing Debt Burden Adjustment
        existing_loans = financial_data.get('existing_loans', 0)
        # Hard cap: Total Debt (old + new) should not exceed 0.6x Revenue for most SMEs
        hard_total_debt_cap = annual_revenue * 0.6
        max_additional_headroom = hard_total_debt_cap - existing_loans
        
        final_loan_amount = min(base_loan_amount, max_additional_headroom)
        
        return max(0, round(final_loan_amount, 0))
    
    def _calculate_risk_adjusted_rate(self, risk_category: str, financial_data: Dict, 
                                   research_data: Dict) -> float:
        """Calculate risk-adjusted interest rate"""
        
        # Base rate from risk category
        base_rate = self.base_interest_rates.get(risk_category, 12.0)
        
        # Industry adjustment
        industry = research_data.get('industry', '').lower()
        industry_adj = self.industry_adjustments.get(industry, 0.0)
        
        # Company size adjustment
        annual_revenue = financial_data.get('revenue', 0)
        if annual_revenue > 100000000:  # > 100 crore
            size_adj = -0.5
        elif annual_revenue > 50000000:  # > 50 crore
            size_adj = -0.3
        else:
            size_adj = 0.0
        
        # Calculate final rate
        final_rate = base_rate + industry_adj + size_adj
        
        # Ensure rate is within reasonable bounds
        final_rate = max(6.0, min(24.0, final_rate))
        
        return round(final_rate, 2)
    
    def _determine_optimal_tenure(self, loan_amount: float, financial_data: Dict, 
                                risk_category: str) -> int:
        """Determine optimal loan tenure"""
        
        if loan_amount == 0:
            return 0
        
        # Base tenure based on loan amount
        if loan_amount < 10000000:  # < 1 crore
            base_tenure = 36  # 3 years
        elif loan_amount < 50000000:  # < 5 crore
            base_tenure = 48  # 4 years
        else:
            base_tenure = 60  # 5 years
        
        # Adjust for risk category
        if risk_category in ['High', 'Very High']:
            base_tenure = min(base_tenure, 36)  # Shorter tenure for high risk
        
        return base_tenure
    
    def _calculate_emi(self, loan_amount: float, interest_rate: float, tenure_months: int) -> float:
        """Calculate Equated Monthly Installment"""
        
        if loan_amount == 0 or tenure_months == 0:
            return 0
        
        monthly_rate = interest_rate / 12 / 100
        
        # EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
        emi: float = loan_amount * monthly_rate * (1 + monthly_rate) ** tenure_months / \
              ((1 + monthly_rate) ** tenure_months - 1)
        
        return round(emi, 2)
    
    def _assess_security_requirements(self, decision: str, risk_category: str, 
                                    loan_amount: float, financial_data: Dict) -> Tuple[bool, bool]:
        """Assess collateral and guarantee requirements"""
        
        collateral_required = False
        guarantee_required = False
        
        if decision == 'Rejected':
            return False, False
        
        # Collateral requirements
        if risk_category in ['High', 'Very High']:
            collateral_required = True
        elif loan_amount > 50000000:  # > 5 crore
            collateral_required = True
        
        # Guarantee requirements
        if risk_category in ['High', 'Very High']:
            guarantee_required = True
        elif decision == 'Conditional Approval':
            guarantee_required = True
        elif loan_amount > 10000000:  # > 1 crore
            guarantee_required = True
        
        return collateral_required, guarantee_required
    
    def _generate_loan_conditions(self, decision: str, risk_category: str, 
                                 financial_data: Dict, research_data: Dict) -> List[str]:
        """Generate loan conditions based on decision and risk profile"""
        
        conditions = []
        
        # Common conditions
        conditions.append("Regular submission of financial statements")
        conditions.append("Maintenance of current ratio > 1.0")
        conditions.append("No additional borrowing without lender consent")
        
        if decision == 'Conditional Approval':
            conditions.extend([
                "Submit audited financial statements for last 3 years",
                "Provide business plan with cash flow projections",
                "Maintain minimum cash balance equivalent to 3 months EMI"
            ])
        
        # Risk category specific conditions
        if risk_category in ['High', 'Very High']:
            conditions.extend([
                "Monthly cash flow monitoring required",
                "Personal guarantee of promoters required"
            ])
        
        return conditions
    
    def _generate_risk_mitigation_measures(self, risk_category: str, research_data: Dict,
                                         consistency_data: Dict) -> List[str]:
        """Generate risk mitigation measures"""
        
        mitigation_measures = []
        
        # Litigation risk mitigation
        litigation_count = research_data.get('litigation_cases', 0)
        if litigation_count > 0:
            mitigation_measures.extend([
                "Escrow account for litigation payments",
                "Regular updates on case status"
            ])
        
        # Data consistency mitigation
        consistency_score = consistency_data.get('consistency_score', 100)
        if consistency_score < 80:
            mitigation_measures.extend([
                "Third-party audit of financial data",
                "Enhanced monitoring of GST and bank data"
            ])
        
        # General risk mitigation
        if risk_category in ['High', 'Very High']:
            mitigation_measures.extend([
                "Covenants monitoring system",
                "Early warning indicators tracking"
            ])
        
        return mitigation_measures
    
    def _generate_alternative_options(self, requested_amount: float, risk_category: str,
                                     financial_data: Dict) -> List[Dict[str, Any]]:
        """Generate alternative financing options"""
        
        alternatives = []
        
        # Lower amount option
        lower_amount = requested_amount * 0.7
        lower_rate = self._calculate_risk_adjusted_rate(risk_category, financial_data, {}) - 0.5
        
        alternatives.append({
            'type': 'Reduced Amount',
            'amount': lower_amount,
            'interest_rate': max(lower_rate, 6.0),
            'description': f"Lower loan amount with reduced interest rate",
            'advantages': ['Lower EMI burden', 'Higher approval probability'],
            'disadvantages': ['May not meet full financing needs']
        })
        
        # Working capital facility option
        if financial_data.get('working_capital', 0) > 0:
            wc_amount = financial_data['working_capital'] * 0.5
            wc_rate = self._calculate_risk_adjusted_rate('Medium', financial_data, {})
            
            alternatives.append({
                'type': 'Working Capital Facility',
                'amount': wc_amount,
                'interest_rate': wc_rate,
                'description': "Revolving working capital facility",
                'advantages': ['Flexible usage', 'Interest on utilized amount only'],
                'disadvantages': ['Variable interest rate', 'Requires regular monitoring']
            })
        
        return alternatives
    
    def _create_pricing_breakdown(self, interest_rate: float, financial_data: Dict,
                                research_data: Dict) -> Dict[str, Any]:
        """Create detailed pricing breakdown"""
        
        # Base rate components
        base_rate = 8.0  # RBI repo rate + margin
        
        # Risk premium
        risk_premium = interest_rate - base_rate
        
        # Industry adjustment
        industry = research_data.get('industry', '').lower()
        industry_adj = self.industry_adjustments.get(industry, 0.0)
        
        return {
            'base_rate': base_rate,
            'risk_premium': risk_premium,
            'industry_adjustment': industry_adj,
            'final_rate': interest_rate,
            'effective_rate': interest_rate + 0.5,  # Including processing fee effect
            'total_cost_percentage': interest_rate + 1.0  # Including all fees
        }
    
    def _generate_repayment_schedule(self, loan_amount: float, interest_rate: float,
                                   tenure_months: int) -> List[Dict[str, Any]]:
        """Generate detailed repayment schedule"""
        
        if loan_amount == 0 or tenure_months == 0:
            return []
        
        schedule = []
        monthly_rate = interest_rate / 12 / 100
        emi = self._calculate_emi(loan_amount, interest_rate, tenure_months)
        
        remaining_principal = loan_amount
        
        for month in range(1, tenure_months + 1):
            interest_payment = remaining_principal * monthly_rate
            principal_payment = emi - interest_payment
            remaining_principal -= principal_payment
            
            schedule.append({
                'month': month,
                'emi_amount': round(emi, 2),
                'principal_component': round(principal_payment, 2),
                'interest_component': round(interest_payment, 2),
                'remaining_principal': round(max(0, remaining_principal), 2)
            })
        
        return schedule
    
    def generate_recommendation(self, risk_score: float, risk_category: str, 
                              financial_data: Dict, component_scores: Dict) -> Dict[str, Any]:
        """Legacy method for backward compatibility"""
        
        # Create mock data for missing parameters
        research_data = {
            'industry': financial_data.get('industry', 'Manufacturing'),
            'litigation_cases': 0,
            'esg_score': 70
        }
        
        consistency_data = {
            'consistency_score': 85.0
        }
        
        qualitative_inputs = {}
        
        # Generate comprehensive recommendation
        recommendation = self.generate_comprehensive_recommendation(
            risk_score, risk_category, financial_data, research_data, 
            consistency_data, qualitative_inputs
        )
        
        # Convert to legacy format
        return {
            'decision': recommendation.decision,
            'loan_limit': recommendation.loan_amount,
            'interest_rate': recommendation.interest_rate,
            'tenure_months': recommendation.tenure_months,
            'emi_amount': recommendation.emi_amount,
            'conditions': recommendation.conditions,
            'explanations': recommendation.risk_mitigation_measures,
            'risk_adjusted_pricing': recommendation.pricing_breakdown,
            'alternative_suggestions': recommendation.alternative_options,
            'collateral_required': recommendation.collateral_required,
            'guarantee_required': recommendation.guarantee_required,
            'processing_fee': recommendation.processing_fee
        }

# Usage example
if __name__ == "__main__":
    # Initialize recommendation engine
    engine = RecommendationEngine()
    
    # Mock data for testing
    risk_score = 72
    risk_category = 'Medium'
    
    financial_data = {
        'revenue': 50000000,  # 5 crore
        'monthly_cash_flow': 2000000,  # 2 lakh
        'working_capital': 15000000,  # 1.5 crore
        'existing_loans': 10000000,  # 1 crore
        'industry': 'Manufacturing'
    }
    
    research_data = {
        'industry': 'Manufacturing',
        'litigation_cases': 1,
        'esg_score': 75
    }
    
    consistency_data = {
        'consistency_score': 85.0
    }
    
    qualitative_inputs = {
        'management_quality': 0.7,
        'factory_utilization': 0.8
    }
    
    # Generate recommendation
    recommendation = engine.generate_comprehensive_recommendation(
        risk_score, risk_category, financial_data, research_data, consistency_data, qualitative_inputs
    )
    
    print("Loan Recommendation Results:")
    print(f"Decision: {recommendation.decision}")
    print(f"Loan Amount: ₹{recommendation.loan_amount:,.0f}")
    print(f"Interest Rate: {recommendation.interest_rate}%")
    print(f"Tenure: {recommendation.tenure_months} months")
    print(f"EMI: ₹{recommendation.emi_amount:,.0f}")
    print(f"Conditions: {len(recommendation.conditions)}")
    print(f"Risk Mitigation Measures: {len(recommendation.risk_mitigation_measures)}")
    print(f"Alternative Options: {len(recommendation.alternative_options)}")
