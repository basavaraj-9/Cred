import pandas as pd
import numpy as np
import joblib
import os
from typing import Dict, List, Any, Tuple
from datetime import datetime

class CreditScoringPipeline:
    def __init__(self, model_dir="ml_models/saved_models"):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.model_metadata = {}
        self.load_models()
    
    def load_models(self):
        """Load the trained model and preprocessing artifacts"""
        
        try:
            # Load the model
            model_path = os.path.join(self.model_dir, 'credit_risk_model.pkl')
            if not os.path.exists(model_path):
                print("Model not found. Please train the model first.")
                return False
            
            self.model = joblib.load(model_path)
            
            # Load the scaler
            scaler_path = os.path.join(self.model_dir, 'feature_scaler.pkl')
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
            
            # Load feature columns
            feature_path = os.path.join(self.model_dir, 'feature_columns.pkl')
            if os.path.exists(feature_path):
                self.feature_columns = joblib.load(feature_path)
            
            # Load metadata
            metadata_path = os.path.join(self.model_dir, 'model_metadata.pkl')
            if os.path.exists(metadata_path):
                self.model_metadata = joblib.load(metadata_path)
            
            print(f"Model loaded successfully: {self.model_metadata.get('model_name', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"Error loading model: {str(e)}")
            return False
    
    def preprocess_input(self, financial_data: Dict, risk_analysis: Dict, 
                        research_data: Dict, officer_input: Dict = None) -> pd.DataFrame:
        """Preprocess input data for scoring"""
        
        # Base features from financial data
        revenue = financial_data.get('revenue', 0)
        existing_loans = financial_data.get('existing_loans', 0)
        assets = financial_data.get('assets', 0)
        liabilities = financial_data.get('liabilities', 0)
        profit = financial_data.get('profit', 0)
        
        # Calculate ratios
        debt_to_revenue = existing_loans / revenue if revenue > 0 else 0
        profit_margin = profit / revenue if revenue > 0 else 0
        debt_to_assets = liabilities / assets if assets > 0 else 0
        
        # Extract other features
        consistency_score = risk_analysis.get('consistency_score', 50)
        litigation_count = research_data.get('litigation_cases', 0)
        
        # Convert sentiment to numeric score
        sentiment_map = {'Positive': 0.5, 'Neutral': 0.0, 'Negative': -0.5}
        news_sentiment = research_data.get('news_sentiment', 'Neutral')
        sentiment_score = sentiment_map.get(news_sentiment, 0.0)
        
        # Officer input features
        factory_utilization = officer_input.get('factory_utilization', 50) if officer_input else 50
        
        management_map = {'poor': 1, 'moderate': 2.5, 'good': 3.5, 'excellent': 4.5}
        management_quality = officer_input.get('management_quality', 'moderate') if officer_input else 'moderate'
        management_quality_score = management_map.get(management_quality.lower(), 2.5)
        
        # Create feature dictionary
        features = {
            'debt_to_revenue': debt_to_revenue,
            'profit_margin': profit_margin,
            'debt_to_assets': debt_to_assets,
            'consistency_score': consistency_score,
            'litigation_count': litigation_count,
            'sentiment_score': sentiment_score,
            'factory_utilization': factory_utilization,
            'management_quality_score': management_quality_score
        }
        
        # Create derived features
        features['high_debt_ratio'] = int(debt_to_revenue > 1.5)
        features['negative_profit'] = int(profit_margin < 0)
        features['low_consistency'] = int(consistency_score < 50)
        features['has_litigation'] = int(litigation_count > 0)
        features['negative_sentiment'] = int(sentiment_score < -0.1)
        features['low_utilization'] = int(factory_utilization < 50)
        features['poor_management'] = int(management_quality_score < 3)
        
        # Convert to DataFrame
        df = pd.DataFrame([features])
        
        # Ensure all required columns are present
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = 0
        
        # Reorder columns to match training data
        df = df[self.feature_columns]
        
        return df
    
    def predict_default_probability(self, financial_data: Dict, risk_analysis: Dict,
                                  research_data: Dict, officer_input: Dict = None) -> Dict[str, Any]:
        """Predict default probability for a loan application"""
        
        if self.model is None:
            return {'error': 'Model not loaded'}
        
        try:
            # Preprocess input
            features_df = self.preprocess_input(
                financial_data, risk_analysis, research_data, officer_input
            )
            
            # Make prediction
            if self.model_metadata.get('model_name') == 'logistic_regression' and self.scaler:
                features_scaled = self.scaler.transform(features_df)
                default_prob = self.model.predict_proba(features_scaled)[0][1]
            else:
                default_prob = self.model.predict_proba(features_df)[0][1]
            
            # Convert to risk score (0-100, higher = more risky)
            risk_score = default_prob * 100
            
            # Categorize risk
            if risk_score >= 75:
                risk_category = 'Very High'
            elif risk_score >= 60:
                risk_category = 'High'
            elif risk_score >= 40:
                risk_category = 'Medium'
            elif risk_score >= 25:
                risk_category = 'Low'
            else:
                risk_category = 'Very Low'
            
            return {
                'default_probability': round(default_prob, 4),
                'risk_score': round(risk_score, 1),
                'risk_category': risk_category,
                'model_confidence': 'High' if 0.1 < default_prob < 0.9 else 'Medium',
                'prediction_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {'error': f'Prediction failed: {str(e)}'}
    
    def batch_predict(self, applications: List[Dict]) -> List[Dict[str, Any]]:
        """Make predictions for multiple applications"""
        
        results = []
        
        for app in applications:
            financial_data = app.get('financial_data', {})
            risk_analysis = app.get('risk_analysis', {})
            research_data = app.get('research_data', {})
            officer_input = app.get('officer_input', {})
            
            prediction = self.predict_default_probability(
                financial_data, risk_analysis, research_data, officer_input
            )
            
            results.append({
                'application_id': app.get('application_id', 'Unknown'),
                'company_name': app.get('company_name', 'Unknown'),
                **prediction
            })
        
        return results
    
    def explain_prediction(self, financial_data: Dict, risk_analysis: Dict,
                          research_data: Dict, officer_input: Dict = None) -> Dict[str, Any]:
        """Explain the prediction by showing feature contributions"""
        
        if self.model is None:
            return {'error': 'Model not loaded'}
        
        try:
            # Preprocess input
            features_df = self.preprocess_input(
                financial_data, risk_analysis, research_data, officer_input
            )
            
            # Get feature importance if available
            feature_importance = {}
            if hasattr(self.model, 'feature_importances_'):
                importance_scores = self.model.feature_importances_
                for i, feature in enumerate(self.feature_columns):
                    if i < len(importance_scores):
                        feature_importance[feature] = importance_scores[i]
            
            # Get feature values for this application
            feature_values = features_df.iloc[0].to_dict()
            
            # Create explanation
            explanations = []
            
            # High impact features
            high_impact_features = sorted(
                feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            for feature, importance in high_impact_features:
                value = feature_values.get(feature, 0)
                
                if feature == 'debt_to_revenue' and value > 1.5:
                    explanations.append(f"High debt-to-revenue ratio ({value:.2f}x) increases risk")
                elif feature == 'profit_margin' and value < 0:
                    explanations.append(f"Negative profit margin ({value:.2%}) increases risk")
                elif feature == 'debt_to_assets' and value > 0.8:
                    explanations.append(f"High debt-to-assets ratio ({value:.2f}x) increases risk")
                elif feature == 'consistency_score' and value < 50:
                    explanations.append(f"Low data consistency score ({value:.1f}) increases risk")
                elif feature == 'litigation_count' and value > 0:
                    explanations.append(f"Multiple litigation cases ({int(value)}) increase risk")
                elif feature == 'sentiment_score' and value < -0.1:
                    explanations.append(f"Negative news sentiment ({value:.2f}) increases risk")
                elif feature == 'factory_utilization' and value < 50:
                    explanations.append(f"Low factory utilization ({value:.1f}%) increases risk")
                elif feature == 'management_quality_score' and value < 3:
                    explanations.append(f"Poor management quality score ({value:.1f}) increases risk")
            
            # Positive factors
            positive_factors = []
            if feature_values.get('profit_margin', 0) > 0.1:
                positive_factors.append(f"Strong profit margin ({feature_values['profit_margin']:.2%})")
            if feature_values.get('consistency_score', 0) > 70:
                positive_factors.append(f"High data consistency ({feature_values['consistency_score']:.1f})")
            if feature_values.get('debt_to_revenue', 0) < 0.5:
                positive_factors.append(f"Low debt burden ({feature_values['debt_to_revenue']:.2f}x)")
            
            return {
                'risk_factors': explanations,
                'positive_factors': positive_factors,
                'feature_importance': feature_importance,
                'feature_values': feature_values
            }
            
        except Exception as e:
            return {'error': f'Explanation failed: {str(e)}'}
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        
        return {
            'model_name': self.model_metadata.get('model_name', 'Unknown'),
            'feature_count': len(self.feature_columns),
            'feature_columns': self.feature_columns,
            'training_date': self.model_metadata.get('training_date', 'Unknown'),
            'model_type': self.model_metadata.get('model_type', 'Unknown'),
            'is_loaded': self.model is not None
        }


# Example usage and testing
def test_pipeline():
    """Test the scoring pipeline with sample data"""
    
    print("Testing Credit Scoring Pipeline...")
    
    # Initialize pipeline
    pipeline = CreditScoringPipeline()
    
    if not pipeline.model:
        print("Model not available. Please train the model first.")
        return
    
    # Sample application data
    sample_application = {
        'financial_data': {
            'revenue': 50000000,  # 5 crore
            'existing_loans': 30000000,  # 3 crore
            'assets': 80000000,  # 8 crore
            'liabilities': 40000000,  # 4 crore
            'profit': 2500000  # 25 lakh
        },
        'risk_analysis': {
            'consistency_score': 65
        },
        'research_data': {
            'litigation_cases': 1,
            'news_sentiment': 'Neutral'
        },
        'officer_input': {
            'factory_utilization': 65,
            'management_quality': 'Good'
        }
    }
    
    # Make prediction
    prediction = pipeline.predict_default_probability(
        sample_application['financial_data'],
        sample_application['risk_analysis'],
        sample_application['research_data'],
        sample_application['officer_input']
    )
    
    print("Prediction Result:")
    print(prediction)
    
    # Get explanation
    explanation = pipeline.explain_prediction(
        sample_application['financial_data'],
        sample_application['risk_analysis'],
        sample_application['research_data'],
        sample_application['officer_input']
    )
    
    print("\nExplanation:")
    print(f"Risk Factors: {explanation.get('risk_factors', [])}")
    print(f"Positive Factors: {explanation.get('positive_factors', [])}")
    
    # Get model info
    model_info = pipeline.get_model_info()
    print(f"\nModel Info: {model_info}")


if __name__ == "__main__":
    test_pipeline()
