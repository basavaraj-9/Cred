"""
Risk Scoring Engine with Explainable AI
Implements ML-based risk scoring with SHAP explanations and feature importance
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
import json
import pickle
from pathlib import Path

# ML Libraries
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
    import shap
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.warning("ML libraries not available. Install: pip install scikit-learn shap")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RiskFeatures:
    """Features used for risk scoring"""
    # Financial metrics
    revenue_growth: float = 0.0
    profit_margin: float = 0.0
    debt_to_equity: float = 0.0
    current_ratio: float = 0.0
    cash_flow_ratio: float = 0.0
    inventory_turnover: float = 0.0
    debtor_turnover: float = 0.0
    
    # Industry and market factors
    industry_risk_score: float = 0.5
    market_position_score: float = 0.5
    sector_outlook_score: float = 0.5
    
    # Research and qualitative factors
    litigation_count: int = 0
    litigation_amount: float = 0.0
    news_sentiment_score: float = 0.5
    promoter_risk_score: float = 0.5
    esg_score: float = 0.5
    
    # Consistency and data quality
    consistency_score: float = 100.0
    data_quality_score: float = 100.0
    
    # Credit officer inputs
    management_quality_score: float = 0.5
    factory_utilization: float = 0.5
    inventory_management_score: float = 0.5
    
    # Historical performance
    years_in_business: int = 0
    default_history: int = 0
    credit_history_score: float = 0.5

@dataclass
class RiskScore:
    """Comprehensive risk scoring result"""
    overall_score: float  # 0-100
    risk_category: str     # Low, Medium, High, Critical
    default_probability: float  # 0-1
    confidence: float      # 0-1
    feature_importance: Dict[str, float]
    shap_explanations: Dict[str, Any]
    risk_factors: List[str]
    positive_factors: List[str]
    recommendations: List[str]
    model_version: str
    scored_at: datetime

class RiskScoringEngine:
    """ML-powered risk scoring engine with explainable AI"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_encoder = LabelEncoder()
        self.explainer = None
        self.model_path = model_path
        self.is_trained = False
        
        # Feature definitions and weights
        self.feature_weights = {
            'financial_metrics': 0.35,
            'industry_factors': 0.15,
            'research_factors': 0.20,
            'consistency_factors': 0.15,
            'qualitative_factors': 0.15
        }
        
        # Risk thresholds
        self.risk_thresholds = {
            'low': 75,
            'medium': 50,
            'high': 25,
            'critical': 0
        }
        
        # Initialize model if available
        if model_path and Path(model_path).exists():
            self.load_model()
    
    def prepare_features(self, financial_data: Dict, research_data: Dict, 
                       consistency_data: Dict, qualitative_inputs: Dict) -> RiskFeatures:
        """Prepare features from various data sources"""
        
        features = RiskFeatures()
        
        # Financial metrics
        if financial_data:
            features.revenue_growth = self._calculate_revenue_growth(financial_data)
            features.profit_margin = self._calculate_profit_margin(financial_data)
            features.debt_to_equity = self._calculate_debt_equity(financial_data)
            features.current_ratio = self._calculate_current_ratio(financial_data)
            features.cash_flow_ratio = self._calculate_cash_flow_ratio(financial_data)
            features.inventory_turnover = self._calculate_inventory_turnover(financial_data)
            features.debtor_turnover = self._calculate_debtor_turnover(financial_data)
        
        # Industry and market factors
        if research_data:
            features.industry_risk_score = research_data.get('industry_analysis', {}).get('risk_score', 0.5)
            features.market_position_score = research_data.get('market_position', {}).get('score', 0.5)
            features.sector_outlook_score = self._convert_outlook_to_score(
                research_data.get('sector_outlook', 'Neutral')
            )
        
        # Research and qualitative factors
        if research_data:
            features.litigation_count = research_data.get('litigation_cases', 0)
            features.litigation_amount = sum([
                case.get('amount', 0) for case in research_data.get('litigation_details', [])
            ])
            features.news_sentiment_score = self._convert_sentiment_to_score(
                research_data.get('news_sentiment', 'Neutral')
            )
            features.promoter_risk_score = self._convert_risk_to_score(
                research_data.get('promoter_risk', 'Medium')
            )
            features.esg_score = research_data.get('esg_score', 0.5) / 100.0
        
        # Consistency and data quality
        if consistency_data:
            features.consistency_score = consistency_data.get('consistency_score', 100.0)
            features.data_quality_score = consistency_data.get('data_quality_score', 100.0)
        
        # Credit officer inputs
        if qualitative_inputs:
            features.management_quality_score = qualitative_inputs.get('management_quality', 0.5)
            features.factory_utilization = qualitative_inputs.get('factory_utilization', 0.5)
            features.inventory_management_score = qualitative_inputs.get('inventory_management', 0.5)
        
        # Historical performance (mock data for now)
        features.years_in_business = 5  # Default value
        features.default_history = 0
        features.credit_history_score = 0.8  # Good credit history
        
        return features
    
    def calculate_risk_score(self, features: RiskFeatures) -> RiskScore:
        """Calculate comprehensive risk score using ML model"""
        
        try:
            if not ML_AVAILABLE:
                return self._fallback_risk_scoring(features)
            
            # Convert features to numpy array
            feature_array = self._features_to_array(features)
            
            # Scale features
            if not self.is_trained:
                # For first-time scoring, use rule-based approach
                return self._rule_based_scoring(features)
            
            scaled_features = self.scaler.transform([feature_array])
            
            # Predict risk score
            if self.model:
                risk_probability = self.model.predict_proba(scaled_features)[0][1]  # Probability of default
                risk_score = (1 - risk_probability) * 100  # Convert to 0-100 scale
                
                # Generate explanations
                shap_values = self._generate_shap_explanations(scaled_features, feature_array)
                feature_importance = self._get_feature_importance()
                
                # Determine risk category
                risk_category = self._determine_risk_category(risk_score)
                
                # Generate insights
                risk_factors, positive_factors = self._analyze_risk_factors(features, shap_values)
                recommendations = self._generate_recommendations(risk_category, risk_factors)
                
                return RiskScore(
                    overall_score=risk_score,
                    risk_category=risk_category,
                    default_probability=risk_probability,
                    confidence=0.85,  # Model confidence
                    feature_importance=feature_importance,
                    shap_explanations=shap_values,
                    risk_factors=risk_factors,
                    positive_factors=positive_factors,
                    recommendations=recommendations,
                    model_version="v1.0",
                    scored_at=datetime.now()
                )
            else:
                return self._rule_based_scoring(features)
                
        except Exception as e:
            logger.error(f"Error in risk scoring: {str(e)}")
            return self._fallback_risk_scoring(features)
    
    def _features_to_array(self, features: RiskFeatures) -> np.ndarray:
        """Convert RiskFeatures to numpy array"""
        feature_dict = asdict(features)
        
        # Define feature order (must match training order)
        feature_order = [
            'revenue_growth', 'profit_margin', 'debt_to_equity', 'current_ratio',
            'cash_flow_ratio', 'inventory_turnover', 'debtor_turnover',
            'industry_risk_score', 'market_position_score', 'sector_outlook_score',
            'litigation_count', 'litigation_amount', 'news_sentiment_score',
            'promoter_risk_score', 'esg_score', 'consistency_score',
            'data_quality_score', 'management_quality_score', 'factory_utilization',
            'inventory_management_score', 'years_in_business', 'default_history',
            'credit_history_score'
        ]
        
        return np.array([feature_dict.get(feature, 0) for feature in feature_order])
    
    def _rule_based_scoring(self, features: RiskFeatures) -> RiskScore:
        """Rule-based scoring when ML model is not available"""
        
        # Financial metrics score (0-100)
        financial_score = self._calculate_financial_score(features)
        
        # Industry and market score (0-100)
        industry_score = self._calculate_industry_score(features)
        
        # Research and qualitative score (0-100)
        research_score = self._calculate_research_score(features)
        
        # Consistency score (0-100)
        consistency_score = features.consistency_score
        
        # Qualitative inputs score (0-100)
        qualitative_score = self._calculate_qualitative_score(features)
        
        # Weighted combination
        overall_score = (
            financial_score * self.feature_weights['financial_metrics'] +
            industry_score * self.feature_weights['industry_factors'] +
            research_score * self.feature_weights['research_factors'] +
            consistency_score * self.feature_weights['consistency_factors'] +
            qualitative_score * self.feature_weights['qualitative_factors']
        )
        
        # Determine risk category
        risk_category = self._determine_risk_category(overall_score)
        
        # Calculate default probability (inverse of score)
        default_probability = (100 - overall_score) / 100.0
        
        # Generate insights
        risk_factors, positive_factors = self._analyze_rule_based_factors(features)
        recommendations = self._generate_recommendations(risk_category, risk_factors)
        
        return RiskScore(
            overall_score=overall_score,
            risk_category=risk_category,
            default_probability=default_probability,
            confidence=0.75,  # Rule-based confidence
            feature_importance=self._get_rule_based_importance(),
            shap_explanations={},
            risk_factors=risk_factors,
            positive_factors=positive_factors,
            recommendations=recommendations,
            model_version="rule-based",
            scored_at=datetime.now()
        )
    
    def _fallback_risk_scoring(self, features: RiskFeatures) -> RiskScore:
        """Fallback scoring method"""
        
        # Simple scoring based on key metrics
        score = 50.0  # Base score
        
        # Adjust based on key factors
        if features.profit_margin > 0.1:
            score += 10
        elif features.profit_margin < 0:
            score -= 20
        
        if features.debt_to_equity < 1:
            score += 10
        elif features.debt_to_equity > 2:
            score -= 15
        
        if features.litigation_count > 0:
            score -= features.litigation_count * 5
        
        if features.consistency_score > 80:
            score += 10
        elif features.consistency_score < 60:
            score -= 15
        
        score = max(0, min(100, score))
        
        return RiskScore(
            overall_score=score,
            risk_category=self._determine_risk_category(score),
            default_probability=(100 - score) / 100.0,
            confidence=0.5,
            feature_importance={},
            shap_explanations={},
            risk_factors=["Limited data available for detailed analysis"],
            positive_factors=["Basic financial metrics considered"],
            recommendations=["Complete data collection for accurate risk assessment"],
            model_version="fallback",
            scored_at=datetime.now()
        )
    
    def _calculate_financial_score(self, features: RiskFeatures) -> float:
        """Calculate financial metrics score"""
        score = 50.0  # Base score
        
        # Revenue growth
        if features.revenue_growth > 0.2:
            score += 15
        elif features.revenue_growth > 0.1:
            score += 10
        elif features.revenue_growth < 0:
            score -= 15
        
        # Profit margin
        if features.profit_margin > 0.15:
            score += 15
        elif features.profit_margin > 0.1:
            score += 10
        elif features.profit_margin < 0.05:
            score -= 10
        elif features.profit_margin < 0:
            score -= 20
        
        # Debt to equity
        if features.debt_to_equity < 0.5:
            score += 10
        elif features.debt_to_equity > 2:
            score -= 15
        elif features.debt_to_equity > 3:
            score -= 25
        
        # Current ratio
        if features.current_ratio > 2:
            score += 10
        elif features.current_ratio < 1:
            score -= 15
        
        # Cash flow ratio
        if features.cash_flow_ratio > 0.2:
            score += 10
        elif features.cash_flow_ratio < 0:
            score -= 20
        
        return max(0, min(100, score))
    
    def _calculate_industry_score(self, features: RiskFeatures) -> float:
        """Calculate industry and market score"""
        score = 50.0
        
        # Industry risk
        if features.industry_risk_score < 0.3:
            score += 20
        elif features.industry_risk_score > 0.7:
            score -= 20
        
        # Market position
        if features.market_position_score > 0.7:
            score += 15
        elif features.market_position_score < 0.3:
            score -= 15
        
        # Sector outlook
        if features.sector_outlook_score > 0.7:
            score += 15
        elif features.sector_outlook_score < 0.3:
            score -= 15
        
        return max(0, min(100, score))
    
    def _calculate_research_score(self, features: RiskFeatures) -> float:
        """Calculate research and qualitative score"""
        score = 50.0
        
        # Litigation
        if features.litigation_count == 0:
            score += 20
        elif features.litigation_count > 3:
            score -= 25
        elif features.litigation_count > 1:
            score -= 10
        
        # Litigation amount
        if features.litigation_amount > 10000000:  # > 1 crore
            score -= 15
        elif features.litigation_amount > 5000000:  # > 50 lakh
            score -= 10
        
        # News sentiment
        if features.news_sentiment_score > 0.7:
            score += 15
        elif features.news_sentiment_score < 0.3:
            score -= 15
        
        # Promoter risk
        if features.promoter_risk_score < 0.3:
            score += 15
        elif features.promoter_risk_score > 0.7:
            score -= 15
        
        # ESG score
        if features.esg_score > 0.7:
            score += 10
        elif features.esg_score < 0.3:
            score -= 10
        
        return max(0, min(100, score))
    
    def _calculate_qualitative_score(self, features: RiskFeatures) -> float:
        """Calculate qualitative inputs score"""
        score = 50.0
        
        # Management quality
        if features.management_quality_score > 0.7:
            score += 20
        elif features.management_quality_score < 0.3:
            score -= 20
        
        # Factory utilization
        if features.factory_utilization > 0.8:
            score += 15
        elif features.factory_utilization < 0.5:
            score -= 15
        
        # Inventory management
        if features.inventory_management_score > 0.7:
            score += 15
        elif features.inventory_management_score < 0.3:
            score -= 15
        
        return max(0, min(100, score))
    
    def _determine_risk_category(self, score: float) -> str:
        """Determine risk category based on score"""
        if score >= self.risk_thresholds['low']:
            return 'Low'
        elif score >= self.risk_thresholds['medium']:
            return 'Medium'
        elif score >= self.risk_thresholds['high']:
            return 'High'
        else:
            return 'Critical'
    
    def _generate_shap_explanations(self, scaled_features: np.ndarray, 
                                  original_features: np.ndarray) -> Dict[str, Any]:
        """Generate SHAP explanations for model predictions"""
        
        if not self.explainer:
            return {}
        
        try:
            # Calculate SHAP values
            shap_values = self.explainer.shap_values(scaled_features)
            
            # Get feature names
            feature_names = [
                'Revenue Growth', 'Profit Margin', 'Debt/Equity', 'Current Ratio',
                'Cash Flow Ratio', 'Inventory Turnover', 'Debtor Turnover',
                'Industry Risk', 'Market Position', 'Sector Outlook',
                'Litigation Count', 'Litigation Amount', 'News Sentiment',
                'Promoter Risk', 'ESG Score', 'Consistency Score',
                'Data Quality', 'Management Quality', 'Factory Utilization',
                'Inventory Management', 'Years in Business', 'Default History',
                'Credit History'
            ]
            
            # Create explanation dictionary
            explanations = {
                'shap_values': shap_values[0].tolist() if isinstance(shap_values, list) else shap_values.tolist(),
                'feature_names': feature_names,
                'base_value': float(self.explainer.expected_value),
                'feature_contributions': {}
            }
            
            # Calculate feature contributions
            for i, name in enumerate(feature_names):
                explanations['feature_contributions'][name] = float(shap_values[0][i])
            
            return explanations
            
        except Exception as e:
            logger.error(f"Error generating SHAP explanations: {str(e)}")
            return {}
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from trained model"""
        
        if not self.model:
            return {}
        
        try:
            if hasattr(self.model, 'feature_importances_'):
                feature_names = [
                    'revenue_growth', 'profit_margin', 'debt_to_equity', 'current_ratio',
                    'cash_flow_ratio', 'inventory_turnover', 'debtor_turnover',
                    'industry_risk_score', 'market_position_score', 'sector_outlook_score',
                    'litigation_count', 'litigation_amount', 'news_sentiment_score',
                    'promoter_risk_score', 'esg_score', 'consistency_score',
                    'data_quality_score', 'management_quality_score', 'factory_utilization',
                    'inventory_management_score', 'years_in_business', 'default_history',
                    'credit_history_score'
                ]
                
                importance_dict = {}
                for name, importance in zip(feature_names, self.model.feature_importances_):
                    importance_dict[name] = float(importance)
                
                return importance_dict
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error getting feature importance: {str(e)}")
            return {}
    
    def _get_rule_based_importance(self) -> Dict[str, float]:
        """Get rule-based feature importance"""
        return {
            'profit_margin': 0.15,
            'debt_to_equity': 0.12,
            'revenue_growth': 0.10,
            'current_ratio': 0.08,
            'cash_flow_ratio': 0.08,
            'litigation_count': 0.10,
            'news_sentiment_score': 0.08,
            'promoter_risk_score': 0.08,
            'consistency_score': 0.10,
            'management_quality_score': 0.11
        }
    
    def _analyze_risk_factors(self, features: RiskFeatures, 
                            shap_explanations: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Analyze risk factors and positive factors"""
        
        risk_factors = []
        positive_factors = []
        
        # Analyze financial metrics
        if features.profit_margin < 0.05:
            risk_factors.append("Low profit margin indicates poor profitability")
        elif features.profit_margin > 0.15:
            positive_factors.append("Strong profit margin demonstrates good profitability")
        
        if features.debt_to_equity > 2:
            risk_factors.append("High debt-to-equity ratio indicates financial leverage risk")
        elif features.debt_to_equity < 0.5:
            positive_factors.append("Conservative debt structure with low leverage")
        
        if features.current_ratio < 1:
            risk_factors.append("Current ratio below 1 indicates liquidity concerns")
        elif features.current_ratio > 2:
            positive_factors.append("Strong current ratio indicates good liquidity")
        
        # Analyze research factors
        if features.litigation_count > 2:
            risk_factors.append(f"Multiple litigation cases ({features.litigation_count}) indicate legal risks")
        elif features.litigation_count == 0:
            positive_factors.append("No litigation history indicates good legal compliance")
        
        if features.news_sentiment_score < 0.3:
            risk_factors.append("Negative news sentiment suggests reputation concerns")
        elif features.news_sentiment_score > 0.7:
            positive_factors.append("Positive news sentiment indicates good market perception")
        
        # Analyze consistency
        if features.consistency_score < 70:
            risk_factors.append("Low data consistency score indicates potential data quality issues")
        elif features.consistency_score > 90:
            positive_factors.append("High data consistency score indicates reliable financial data")
        
        # Add SHAP-based insights if available
        if shap_explanations and 'feature_contributions' in shap_explanations:
            contributions = shap_explanations['feature_contributions']
            
            # Find most negative and positive contributions
            sorted_contributions = sorted(contributions.items(), key=lambda x: x[1])
            
            # Top 3 negative factors
            for feature, contribution in sorted_contributions[:3]:
                if contribution < -0.1:
                    risk_factors.append(f"High negative impact from {feature.replace('_', ' ').title()}")
            
            # Top 3 positive factors
            for feature, contribution in sorted_contributions[-3:]:
                if contribution > 0.1:
                    positive_factors.append(f"Strong positive contribution from {feature.replace('_', ' ').title()}")
        
        return risk_factors, positive_factors
    
    def _analyze_rule_based_factors(self, features: RiskFeatures) -> Tuple[List[str], List[str]]:
        """Analyze factors for rule-based scoring"""
        return self._analyze_risk_factors(features, {})
    
    def _generate_recommendations(self, risk_category: str, risk_factors: List[str]) -> List[str]:
        """Generate recommendations based on risk category and factors"""
        
        recommendations = []
        
        if risk_category == 'Critical':
            recommendations.extend([
                "Reject loan application - critical risk level",
                "Recommend complete financial restructuring before reconsideration",
                "Require external audit and due diligence"
            ])
        elif risk_category == 'High':
            recommendations.extend([
                "Consider loan approval with stringent conditions",
                "Require additional collateral and guarantees",
                "Implement enhanced monitoring and reporting requirements"
            ])
        elif risk_category == 'Medium':
            recommendations.extend([
                "Approve loan with standard conditions",
                "Regular monitoring of financial performance",
                "Consider periodic review of credit terms"
            ])
        else:  # Low
            recommendations.extend([
                "Approve loan with favorable terms",
                "Standard monitoring procedures applicable",
                "Consider for relationship banking benefits"
            ])
        
        # Add specific recommendations based on risk factors
        factor_recommendations = {
            'profit margin': "Focus on improving operational efficiency and cost management",
            'debt': "Implement debt reduction strategy and improve capital structure",
            'liquidity': "Optimize working capital management and improve cash flow",
            'litigation': "Resolve legal disputes and improve compliance framework",
            'consistency': "Strengthen internal controls and financial reporting systems"
        }
        
        for factor in risk_factors[:3]:  # Top 3 risk factors
            for key, recommendation in factor_recommendations.items():
                if key in factor.lower():
                    recommendations.append(recommendation)
                    break
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    # Helper methods for data conversion
    def _calculate_revenue_growth(self, financial_data: Dict) -> float:
        """Calculate revenue growth rate"""
        # Mock implementation
        return 0.15  # 15% growth
    
    def _calculate_profit_margin(self, financial_data: Dict) -> float:
        """Calculate profit margin"""
        # Mock implementation
        return 0.12  # 12% margin
    
    def _calculate_debt_to_equity(self, financial_data: Dict) -> float:
        """Calculate debt-to-equity ratio"""
        # Mock implementation
        return 1.2
    
    def _calculate_current_ratio(self, financial_data: Dict) -> float:
        """Calculate current ratio"""
        # Mock implementation
        return 1.5
    
    def _calculate_cash_flow_ratio(self, financial_data: Dict) -> float:
        """Calculate cash flow ratio"""
        # Mock implementation
        return 0.25
    
    def _calculate_inventory_turnover(self, financial_data: Dict) -> float:
        """Calculate inventory turnover"""
        # Mock implementation
        return 4.0
    
    def _calculate_debtor_turnover(self, financial_data: Dict) -> float:
        """Calculate debtor turnover"""
        # Mock implementation
        return 6.0
    
    def _convert_outlook_to_score(self, outlook: str) -> float:
        """Convert sector outlook to score"""
        outlook_scores = {
            'Positive': 0.8,
            'Neutral': 0.5,
            'Negative': 0.2
        }
        return outlook_scores.get(outlook, 0.5)
    
    def _convert_sentiment_to_score(self, sentiment: str) -> float:
        """Convert news sentiment to score"""
        sentiment_scores = {
            'Positive': 0.8,
            'Neutral': 0.5,
            'Negative': 0.2
        }
        return sentiment_scores.get(sentiment, 0.5)
    
    def _convert_risk_to_score(self, risk: str) -> float:
        """Convert risk level to score"""
        risk_scores = {
            'Low': 0.2,
            'Medium': 0.5,
            'High': 0.8
        }
        return risk_scores.get(risk, 0.5)
    
    def train_model(self, training_data: pd.DataFrame, target_column: str = 'default_flag') -> bool:
        """Train the ML risk scoring model"""
        
        if not ML_AVAILABLE:
            logger.warning("ML libraries not available. Cannot train model.")
            return False
        
        try:
            # Prepare features and target
            feature_columns = [col for col in training_data.columns if col != target_column]
            X = training_data[feature_columns]
            y = training_data[target_column]
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=3,
                random_state=42
            )
            
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            y_pred = self.model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            # Create SHAP explainer
            self.explainer = shap.TreeExplainer(self.model)
            
            # Cross-validation
            cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
            
            logger.info(f"Model trained successfully. Accuracy: {accuracy:.3f}, CV Score: {cv_scores.mean():.3f}")
            
            self.is_trained = True
            
            # Save model if path provided
            if self.model_path:
                self.save_model()
            
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return False
    
    def save_model(self) -> bool:
        """Save trained model to disk"""
        
        if not self.model or not self.model_path:
            return False
        
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_encoder': self.feature_encoder,
                'explainer': self.explainer,
                'feature_weights': self.feature_weights,
                'risk_thresholds': self.risk_thresholds
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Model saved to {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            return False
    
    def load_model(self) -> bool:
        """Load trained model from disk"""
        
        if not self.model_path or not Path(self.model_path).exists():
            return False
        
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_encoder = model_data['feature_encoder']
            self.explainer = model_data['explainer']
            self.feature_weights = model_data['feature_weights']
            self.risk_thresholds = model_data['risk_thresholds']
            
            self.is_trained = True
            logger.info(f"Model loaded from {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

# Usage example
if __name__ == "__main__":
    # Initialize risk scoring engine
    engine = RiskScoringEngine()
    
    # Mock data for testing
    financial_data = {
        'revenue': 10000000,
        'net_profit': 1200000,
        'total_assets': 20000000,
        'total_liabilities': 8000000
    }
    
    research_data = {
        'litigation_cases': 1,
        'news_sentiment': 'Positive',
        'promoter_risk': 'Low',
        'esg_score': 75,
        'sector_outlook': 'Positive'
    }
    
    consistency_data = {
        'consistency_score': 85.0,
        'data_quality_score': 90.0
    }
    
    qualitative_inputs = {
        'management_quality': 0.8,
        'factory_utilization': 0.75,
        'inventory_management': 0.7
    }
    
    # Prepare features
    features = engine.prepare_features(financial_data, research_data, consistency_data, qualitative_inputs)
    
    # Calculate risk score
    risk_score = engine.calculate_risk_score(features)
    
    print("Risk Scoring Results:")
    print(f"Overall Score: {risk_score.overall_score:.1f}/100")
    print(f"Risk Category: {risk_score.risk_category}")
    print(f"Default Probability: {risk_score.default_probability:.2%}")
    print(f"Confidence: {risk_score.confidence:.2%}")
    print(f"Risk Factors: {len(risk_score.risk_factors)}")
    print(f"Positive Factors: {len(risk_score.positive_factors)}")
    print(f"Recommendations: {len(risk_score.recommendations)}")
