"""
Dynamic Loan Affordability and Interest Rate Calculator
Calculates maximum loan amounts and risk-adjusted interest rates
"""

from typing import Dict, Any, Tuple, List
from dataclasses import dataclass

@dataclass
class LoanTerms:
    """Data class for loan terms and conditions"""
    max_loan_amount: float
    approved_loan_amount: float
    interest_rate: float
    tenure_months: int
    risk_adjustment_factor: float
    affordability_ratio: float
    monthly_emi: float
    debt_service_ratio: float

class LoanCalculator:
    """Advanced loan calculation engine with risk-based pricing"""
    
    def __init__(self):
        # Interest rate brackets based on risk score
        self.interest_brackets = [
            {'min_score': 75, 'max_score': 100, 'rate': 9.0, 'category': 'Low Risk'},
            {'min_score': 60, 'max_score': 74, 'rate': 10.5, 'category': 'Medium-Low Risk'},
            {'min_score': 45, 'max_score': 59, 'rate': 12.0, 'category': 'Medium-High Risk'},
            {'min_score': 0, 'max_score': 44, 'rate': 14.0, 'category': 'High Risk'}
        ]
        
        # Risk adjustment factors for loan amount
        self.risk_adjustments = [
            {'min_score': 0, 'max_score': 49, 'factor': 0.5, 'category': 'High Risk'},
            {'min_score': 50, 'max_score': 70, 'factor': 0.75, 'category': 'Medium Risk'},
            {'min_score': 71, 'max_score': 100, 'factor': 1.0, 'category': 'Low Risk'}
        ]
    
    def calculate_loan_affordability(self, company_data: Dict[str, Any], risk_score: int) -> Dict[str, Any]:
        """
        Calculate comprehensive loan affordability based on financial metrics and risk
        
        Args:
            company_data: Company financial data
            risk_score: Calculated risk score (0-100)
            
        Returns:
            Complete loan analysis with amounts, rates, and terms
        """
        # Extract financial metrics
        revenue = company_data.get('revenue', 0)
        profit = company_data.get('profit', 0)
        assets = company_data.get('assets', 0)
        liabilities = company_data.get('liabilities', 0)
        existing_loans = company_data.get('existing_loans', 0)
        
        # Calculate base loan affordability
        base_affordability = self._calculate_base_affordability(revenue, profit, assets, liabilities)
        
        # Apply risk-based adjustments
        risk_factor = self._get_risk_adjustment_factor(risk_score)
        approved_amount = base_affordability * risk_factor
        
        # Calculate interest rate based on risk
        interest_rate = self._calculate_interest_rate(risk_score)
        
        # Calculate loan terms
        loan_terms = self._calculate_loan_terms(approved_amount, interest_rate, profit, existing_loans)
        
        # Generate affordability explanation
        explanation = self._generate_affordability_explanation(
            base_affordability, approved_amount, risk_factor, risk_score, company_data
        )
        
        return {
            'max_loan_amount': base_affordability,
            'approved_loan_amount': approved_amount,
            'interest_rate': interest_rate,
            'tenure_months': loan_terms.tenure_months,
            'monthly_emi': loan_terms.monthly_emi,
            'debt_service_ratio': loan_terms.debt_service_ratio,
            'risk_adjustment_factor': risk_factor,
            'affordability_analysis': {
                'base_calculation': self._explain_base_calculation(revenue, profit, assets),
                'risk_adjustment': f"Risk Score {risk_score}: {risk_factor * 100:.0f}% of maximum",
                'final_amount': approved_amount
            },
            'explanation': explanation,
            'loan_terms': {
                'principal': approved_amount,
                'interest_rate': interest_rate,
                'tenure_months': loan_terms.tenure_months,
                'monthly_emi': loan_terms.monthly_emi,
                'total_interest': loan_terms.monthly_emi * loan_terms.tenure_months - approved_amount,
                'total_payment': loan_terms.monthly_emi * loan_terms.tenure_months
            }
        }
    
    def _calculate_base_affordability(self, revenue: float, profit: float, assets: float, liabilities: float) -> float:
        """
        Calculate maximum loan amount based on fundamental financial metrics
        
        Formula: Average of (Profit × 4) and (Net Assets × 0.3)
        """
        # Method 1: Profit-based (4x annual profit)
        profit_based = profit * 4 if profit > 0 else 0
        
        # Method 2: Asset-based (30% of net assets)
        net_assets = max(assets - liabilities, 0)
        asset_based = net_assets * 0.3
        
        # Method 3: Revenue-based (10% of annual revenue)
        revenue_based = revenue * 0.1
        
        # Take the most conservative approach (minimum of the three)
        base_affordability = min(profit_based, asset_based, revenue_based)
        
        # Ensure minimum loan amount for viable businesses
        if profit > 0 and base_affordability < 10000000:  # ₹1 Crore minimum
            base_affordability = 10000000
        
        return base_affordability
    
    def _get_risk_adjustment_factor(self, risk_score: int) -> float:
        """Get risk adjustment factor based on risk score"""
        for bracket in self.risk_adjustments:
            if bracket['min_score'] <= risk_score <= bracket['max_score']:
                return bracket['factor']
        return 0.5  # Default to most conservative
    
    def _calculate_interest_rate(self, risk_score: int) -> float:
        """Calculate interest rate based on risk score"""
        for bracket in self.interest_brackets:
            if bracket['min_score'] <= risk_score <= bracket['max_score']:
                return bracket['rate']
        return 14.0  # Default to highest rate
    
    def _calculate_loan_terms(self, loan_amount: float, interest_rate: float, 
                            annual_profit: float, existing_loans: float) -> LoanTerms:
        """Calculate detailed loan terms"""
        # Standard tenure based on loan amount
        if loan_amount <= 100000000:  # ≤ ₹1 Crore
            tenure = 36  # 3 years
        elif loan_amount <= 500000000:  # ≤ ₹5 Crore
            tenure = 60  # 5 years
        else:
            tenure = 84  # 7 years
        
        # Calculate monthly EMI
        monthly_rate = interest_rate / 12 / 100
        emi = loan_amount * monthly_rate * (1 + monthly_rate) ** tenure / ((1 + monthly_rate) ** tenure - 1)
        
        # Calculate debt service ratio
        monthly_profit = annual_profit / 12
        monthly_existing_emi = existing_loans * 0.01  # Assume 1% monthly on existing loans
        debt_service_ratio = (emi + monthly_existing_emi) / max(monthly_profit, 1)
        
        return LoanTerms(
            max_loan_amount=loan_amount,
            approved_loan_amount=loan_amount,
            interest_rate=interest_rate,
            tenure_months=tenure,
            risk_adjustment_factor=1.0,
            affordability_ratio=loan_amount / max(annual_profit, 1),
            monthly_emi=emi,
            debt_service_ratio=debt_service_ratio
        )
    
    def _explain_base_calculation(self, revenue: float, profit: float, assets: float) -> str:
        """Generate explanation for base affordability calculation"""
        profit_based = profit * 4 if profit > 0 else 0
        net_assets = max(assets - 0, 0)  # liabilities would be subtracted here
        asset_based = net_assets * 0.3
        revenue_based = revenue * 0.1
        
        explanation = f"Base loan calculation:\n"
        explanation += f"• Profit-based: ₹{profit_based/10000000:.1f} Cr (4x annual profit)\n"
        explanation += f"• Asset-based: ₹{asset_based/10000000:.1f} Cr (30% of net assets)\n"
        explanation += f"• Revenue-based: ₹{revenue_based/10000000:.1f} Cr (10% of revenue)\n"
        explanation += f"• Maximum approved: ₹{min(profit_based, asset_based, revenue_based)/10000000:.1f} Cr (most conservative)"
        
        return explanation
    
    def _generate_affordability_explanation(self, base_amount: float, approved_amount: float, 
                                         risk_factor: float, risk_score: int, 
                                         company_data: Dict[str, Any]) -> str:
        """Generate detailed explanation of loan affordability decision"""
        company_name = company_data.get('company', 'Company')
        revenue = company_data.get('revenue', 0)
        profit = company_data.get('profit', 0)
        
        explanation = f"Loan Affordability Analysis for {company_name}:\n\n"
        explanation += f"Financial Profile:\n"
        explanation += f"• Annual Revenue: ₹{revenue/10000000:.1f} Cr\n"
        explanation += f"• Annual Profit: ₹{profit/10000000:.1f} Cr\n"
        explanation += f"• Maximum Eligible: ₹{base_amount/10000000:.1f} Cr\n\n"
        
        explanation += f"Risk Assessment:\n"
        explanation += f"• Risk Score: {risk_score}/100\n"
        explanation += f"• Risk Category: {self._get_risk_category(risk_score)}\n"
        explanation += f"• Risk Adjustment: {risk_factor * 100:.0f}% of maximum\n\n"
        
        explanation += f"Final Approval:\n"
        explanation += f"• Approved Loan Amount: ₹{approved_amount/10000000:.1f} Cr\n"
        
        if risk_factor < 1.0:
            explanation += f"• Note: Amount reduced due to risk factors\n"
        
        return explanation
    
    def _get_risk_category(self, risk_score: int) -> str:
        """Get risk category based on score"""
        if risk_score >= 71:
            return "Low Risk"
        elif risk_score >= 50:
            return "Medium Risk"
        else:
            return "High Risk"
    
    def generate_loan_conditions(self, loan_amount: float, risk_score: int, 
                              company_data: Dict[str, Any]) -> List[str]:
        """Generate specific loan conditions based on risk profile"""
        conditions = []
        
        # Standard conditions
        conditions.extend([
            "Quarterly financial statement submission",
            "Monthly cash flow reporting",
            "No additional borrowing without lender consent"
        ])
        
        # Risk-based conditions
        if risk_score < 50:
            conditions.extend([
                "Weekly bank statement submission",
                "Personal guarantee from directors",
                "Collateral security required",
                "Restriction on dividend payments"
            ])
        elif risk_score < 70:
            conditions.extend([
                "Maintain current debt service coverage ratio",
                "Quarterly business performance review",
            ])
        
        # Company-specific conditions
        if company_data.get('litigation', 0) > 0:
            conditions.append("Regular updates on litigation status")
        
        return conditions
