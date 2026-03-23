import numpy as np
import pandas as pd
from typing import Dict, List, Any
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

class RiskEngine:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.risk_weights = {
            'financial_metrics': 0.35,
            'consistency_analysis': 0.25,
            'research_findings': 0.20,
            'qualitative_factors': 0.20
        }
        self.model_path = "models/risk_model.pkl"
        self.scaler_path = "models/scaler.pkl"
        
    def calculate_risk_score(self, financial_data: Dict, consistency_analysis: Dict, 
                            research_data: Dict, officer_input: Dict = None) -> Dict[str, Any]:
        """Calculate comprehensive risk score"""
        
        risk_result = {
            'risk_score': 0,
            'risk_category': '',
            'component_scores': {},
            'risk_factors': [],
            'recommendations': [],
            'confidence_level': 'Medium'
        }
        
        try:
            # Calculate component scores
            financial_score = self._calculate_financial_risk(financial_data)
            consistency_score = self._calculate_consistency_risk(consistency_analysis)
            research_score = self._calculate_research_risk(research_data)
            qualitative_score = self._calculate_qualitative_risk(officer_input)
            
            risk_result['component_scores'] = {
                'financial': financial_score,
                'consistency': consistency_score,
                'research': research_score,
                'qualitative': qualitative_score
            }
            
            # Calculate weighted overall risk score
            overall_score = (
                financial_score * self.risk_weights['financial_metrics'] +
                consistency_score * self.risk_weights['consistency_analysis'] +
                research_score * self.risk_weights['research_findings'] +
                qualitative_score * self.risk_weights['qualitative_factors']
            )
            
            risk_result['risk_score'] = round(overall_score, 1)
            
            # Determine risk category
            risk_result['risk_category'] = self._categorize_risk(overall_score)
            
            # Identify key risk factors
            risk_result['risk_factors'] = self._identify_risk_factors(
                financial_data, consistency_analysis, research_data, officer_input
            )
            
            # Generate recommendations
            risk_result['recommendations'] = self._generate_recommendations(risk_result)
            
            # Calculate confidence level
            risk_result['confidence_level'] = self._calculate_confidence_level(
                financial_data, consistency_analysis, research_data, officer_input
            )
            
        except Exception as e:
            risk_result['risk_score'] = 50  # Default to medium risk
            risk_result['risk_category'] = 'Medium'
            risk_result['risk_factors'].append(f"Risk calculation error: {str(e)}")
        
        return risk_result
    
    def _calculate_financial_risk(self, financial_data: Dict) -> float:
        """Calculate financial risk component score with improved ratio analysis"""
        
        score = 50  # Base neutral score
        risk_factors = []
        
        # 1. Revenue Scale & Growth
        revenue = financial_data.get('revenue', 0)
        if revenue <= 0:
            score += 30
            risk_factors.append("No verifiable revenue")
        elif revenue < 5000000:  # < 50 Lakhs
            score += 15
            risk_factors.append("Very small revenue base")
        elif revenue > 500000000:  # > 50 Crores
            score -= 15
        
        # 2. Leverage: Total Debt to Revenue
        existing_loans = financial_data.get('existing_loans', 0)
        if revenue > 0:
            debt_to_revenue = existing_loans / revenue
            if debt_to_revenue > 3.0:
                score += 25
                risk_factors.append("Critical leverage (Debt > 3x Revenue)")
            elif debt_to_revenue > 1.5:
                score += 15
                risk_factors.append("High leverage profile")
            elif debt_to_revenue < 0.5:
                score -= 10
        
        # 3. Liquidity: Current Ratio (Current Assets / Current Liabilities)
        # Using a fallback if specific CA/CL aren't parsed
        ca = financial_data.get('current_assets', financial_data.get('assets', 0) * 0.6)
        cl = financial_data.get('current_liabilities', financial_data.get('liabilities', 0) * 0.4)
        
        if cl > 0:
            current_ratio = ca / cl
            if current_ratio < 1.0:
                score += 20
                risk_factors.append("Liquidity stress: Current Ratio < 1.0")
            elif current_ratio < 1.2:
                score += 10
                risk_factors.append("Tight liquidity position")
            elif current_ratio > 1.8:
                score -= 10
        
        # 4. Solvency: Debt to Equity
        equity = financial_data.get('equity', (financial_data.get('assets', 0) - financial_data.get('liabilities', 0)))
        if equity > 0:
            debt_to_equity = existing_loans / equity
            if debt_to_equity > 2.5:
                score += 20
                risk_factors.append("High Debt-to-Equity ratio")
            elif debt_to_equity < 1.0:
                score -= 5
        elif equity < 0:
            score += 30
            risk_factors.append("Negative Net Worth / Insolvency risk")

        # 5. Profitability & Debt Service (DSCR approximation)
        profit = financial_data.get('profit', 0)
        interest_exp = existing_loans * 0.1  # Estimate 10% interest if not provided
        
        if revenue > 0:
            profit_margin = profit / revenue
            if profit_margin < 0.02:
                score += 15
                risk_factors.append("Thin or negative profit margins")
            elif profit_margin > 0.15:
                score -= 10
                
        # Debt Service Coverage Ratio (DSCR) approximation
        # (Net Profit + Depreciation + Interest) / (Interest + Principal Repayment)
        if interest_exp > 0:
            dscr_approx = (profit + interest_exp) / interest_exp
            if dscr_approx < 1.2:
                score += 20
                risk_factors.append("Low Interest Coverage / DSCR")
            elif dscr_approx > 3.0:
                score -= 10
        
        return min(max(score, 0), 100)
    
    def _calculate_consistency_risk(self, consistency_analysis: Dict) -> float:
        """Calculate consistency risk component score"""
        
        score = 50  # Base score
        
        if not consistency_analysis:
            return 60  # Medium risk if no consistency data
        
        # Consistency score from GST/Bank analysis
        consistency_score = consistency_analysis.get('consistency_score', 50)
        
        # Convert consistency score to risk score (inverse relationship)
        risk_from_consistency = 100 - consistency_score
        
        # Weight this component
        score = score * 0.4 + risk_from_consistency * 0.6
        
        # Additional penalties for specific anomalies
        anomalies = consistency_analysis.get('anomalies', [])
        
        if 'Revenue Inflation Risk' in anomalies:
            score += 25
        if 'Circular Trading Pattern' in anomalies:
            score += 30
        if 'Cash Flow Anomaly' in anomalies:
            score += 20
        
        return min(max(score, 0), 100)
    
    def _calculate_research_risk(self, research_data: Dict) -> float:
        """Calculate research-based risk component score"""
        
        score = 50  # Base score
        
        if not research_data:
            return 50  # Neutral risk if no research data
        
        # Litigation cases
        litigation_cases = research_data.get('litigation_cases', 0)
        if litigation_cases > 5:
            score += 30
        elif litigation_cases > 2:
            score += 15
        elif litigation_cases > 0:
            score += 5
        
        # News sentiment
        sentiment = research_data.get('news_sentiment', 'Neutral')
        if sentiment == 'Negative':
            score += 20
        elif sentiment == 'Positive':
            score -= 10
        
        # Promoter risk
        promoter_risk = research_data.get('promoter_risk', 'Low')
        if promoter_risk == 'High':
            score += 25
        elif promoter_risk == 'Medium':
            score += 10
        elif promoter_risk == 'Low':
            score -= 5
        
        # Sector outlook
        sector_outlook = research_data.get('sector_outlook', 'Neutral')
        if sector_outlook == 'Negative':
            score += 15
        elif sector_outlook == 'Positive':
            score -= 5
        
        # Adjust based on confidence in research
        confidence_score = research_data.get('confidence_score', 0)
        if confidence_score < 30:
            score += 10  # Add risk for low confidence research
        
        return min(max(score, 0), 100)
    
    def _calculate_qualitative_risk(self, officer_input: Dict) -> float:
        """Calculate qualitative risk based on credit officer input"""
        
        score = 50  # Base score
        
        if not officer_input:
            return 50  # Neutral risk if no officer input
        
        # Factory utilization
        utilization = officer_input.get('factory_utilization', 50)
        if utilization < 30:
            score += 20
        elif utilization < 50:
            score += 10
        elif utilization > 80:
            score -= 10
        
        # Management quality
        management = officer_input.get('management_quality', 'moderate').lower()
        if management == 'poor':
            score += 25
        elif management == 'moderate':
            score += 5
        elif management == 'good':
            score -= 10
        elif management == 'excellent':
            score -= 20
        
        # Inventory turnover
        inventory = officer_input.get('inventory_turnover', 'normal').lower()
        if inventory == 'low':
            score += 15
        elif inventory == 'high':
            score -= 5
        
        # Additional qualitative factors
        if officer_input.get('customer_concentration', 'low').lower() == 'high':
            score += 10
        
        if officer_input.get('industry_experience', 0) < 2:
            score += 10
        elif officer_input.get('industry_experience', 0) > 10:
            score -= 5
        
        return min(max(score, 0), 100)
    
    def _categorize_risk(self, score: float) -> str:
        """Categorize risk score into risk levels"""
        
        if score >= 80:
            return 'Very High'
        elif score >= 65:
            return 'High'
        elif score >= 45:
            return 'Medium'
        elif score >= 25:
            return 'Low'
        else:
            return 'Very Low'
    
    def _identify_risk_factors(self, financial_data: Dict, consistency_analysis: Dict, 
                              research_data: Dict, officer_input: Dict) -> List[str]:
        """Identify key risk factors"""
        
        risk_factors = []
        
        # Financial risk factors
        revenue = financial_data.get('revenue', 0)
        existing_loans = financial_data.get('existing_loans', 0)
        
        if revenue > 0 and existing_loans / revenue > 1.5:
            risk_factors.append("High debt burden")
        
        if financial_data.get('litigation', 0) > revenue * 0.05:
            risk_factors.append("Significant litigation exposure")
        
        if financial_data.get('profit', 0) < 0:
            risk_factors.append("Negative profitability")
        
        # Consistency risk factors
        if consistency_analysis and consistency_analysis.get('anomalies'):
            for anomaly in consistency_analysis['anomalies']:
                risk_factors.append(f"Data inconsistency: {anomaly}")
        
        # Research risk factors
        if research_data:
            if research_data.get('litigation_cases', 0) > 2:
                risk_factors.append("Multiple litigation cases found")
            
            if research_data.get('news_sentiment') == 'Negative':
                risk_factors.append("Negative news sentiment")
            
            if research_data.get('promoter_risk') == 'High':
                risk_factors.append("High promoter risk")
        
        # Qualitative risk factors
        if officer_input:
            if officer_input.get('factory_utilization', 50) < 40:
                risk_factors.append("Low factory utilization")
            
            if officer_input.get('management_quality', '').lower() == 'poor':
                risk_factors.append("Poor management quality")
        
        return risk_factors[:10]  # Limit to top 10 risk factors
    
    def _generate_recommendations(self, risk_result: Dict) -> List[str]:
        """Generate recommendations based on risk assessment"""
        
        recommendations = []
        risk_score = risk_result['risk_score']
        risk_category = risk_result['risk_category']
        
        if risk_score >= 65:
            recommendations.append("Recommend loan rejection due to high risk profile")
            recommendations.append("Consider alternative financing options")
        elif risk_score >= 45:
            recommendations.append("Conditional approval recommended with enhanced monitoring")
            recommendations.append("Implement stricter covenants and reporting requirements")
            recommendations.append("Consider lower loan amount and higher interest rate")
        else:
            recommendations.append("Loan approval recommended with standard terms")
        
        # Component-specific recommendations
        component_scores = risk_result.get('component_scores', {})
        
        if component_scores.get('financial', 0) > 70:
            recommendations.append("Require detailed financial statements and cash flow projections")
        
        if component_scores.get('consistency', 0) > 70:
            recommendations.append("Conduct detailed audit of financial data consistency")
        
        if component_scores.get('research', 0) > 70:
            recommendations.append("Enhanced due diligence on background and market position")
        
        if component_scores.get('qualitative', 0) > 70:
            recommendations.append("Site visit and management interview recommended")
        
        return recommendations
    
    def _calculate_confidence_level(self, financial_data: Dict, consistency_analysis: Dict, 
                                  research_data: Dict, officer_input: Dict) -> str:
        """Calculate confidence level in risk assessment"""
        
        data_completeness = 0
        
        # Check data availability
        if financial_data and financial_data.get('revenue', 0) > 0:
            data_completeness += 25
        
        if consistency_analysis and consistency_analysis.get('consistency_score', 0) > 0:
            data_completeness += 25
        
        if research_data and research_data.get('confidence_score', 0) > 30:
            data_completeness += 25
        
        if officer_input:
            data_completeness += 25
        
        if data_completeness >= 75:
            return 'High'
        elif data_completeness >= 50:
            return 'Medium'
        else:
            return 'Low'
    
    def train_model(self, training_data: pd.DataFrame):
        """Train the risk scoring model (placeholder for ML model training)"""
        
        # This is a placeholder for actual ML model training
        # In production, you would train on historical loan data
        
        features = [
            'debt_to_revenue', 'profit_margin', 'debt_to_assets',
            'consistency_score', 'litigation_count', 'sentiment_score',
            'factory_utilization', 'management_quality_score'
        ]
        
        X = training_data[features]
        y = training_data['default_flag']  # Target variable
        
        # Train Random Forest model
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X, y)
        
        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
