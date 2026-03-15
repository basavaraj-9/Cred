import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import joblib
import os
from datetime import datetime

class CreditRiskModelTrainer:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_columns = [
            'debt_to_revenue',
            'profit_margin', 
            'debt_to_assets',
            'consistency_score',
            'litigation_count',
            'sentiment_score',
            'factory_utilization',
            'management_quality_score'
        ]
        
    def generate_sample_data(self, n_samples=1000):
        """Generate synthetic training data for demonstration"""
        
        np.random.seed(42)
        
        data = {
            'company_id': range(1, n_samples + 1),
            'debt_to_revenue': np.random.uniform(0, 3, n_samples),
            'profit_margin': np.random.uniform(-0.2, 0.3, n_samples),
            'debt_to_assets': np.random.uniform(0, 1.5, n_samples),
            'consistency_score': np.random.uniform(0, 100, n_samples),
            'litigation_count': np.random.randint(0, 10, n_samples),
            'sentiment_score': np.random.uniform(-1, 1, n_samples),
            'factory_utilization': np.random.uniform(20, 95, n_samples),
            'management_quality_score': np.random.uniform(1, 5, n_samples)
        }
        
        df = pd.DataFrame(data)
        
        # Generate target variable (default_flag) based on risk factors
        # Higher risk factors lead to higher probability of default
        risk_score = (
            df['debt_to_revenue'] * 0.25 +
            (df['profit_margin'] < 0) * 0.2 +
            df['debt_to_assets'] * 0.2 +
            (100 - df['consistency_score']) * 0.01 +
            df['litigation_count'] * 0.05 +
            (df['sentiment_score'] < -0.2) * 0.15 +
            (100 - df['factory_utilization']) * 0.005 +
            (5 - df['management_quality_score']) * 0.1
        )
        
        # Convert to binary default flag with some randomness
        default_probability = 1 / (1 + np.exp(-risk_score + 0.5))
        df['default_flag'] = (np.random.random(n_samples) < default_probability).astype(int)
        
        return df
    
    def preprocess_data(self, df):
        """Preprocess the data for training"""
        
        # Handle missing values
        df = df.fillna(df.mean())
        
        # Create derived features
        df['high_debt_ratio'] = (df['debt_to_revenue'] > 1.5).astype(int)
        df['negative_profit'] = (df['profit_margin'] < 0).astype(int)
        df['low_consistency'] = (df['consistency_score'] < 50).astype(int)
        df['has_litigation'] = (df['litigation_count'] > 0).astype(int)
        df['negative_sentiment'] = (df['sentiment_score'] < -0.1).astype(int)
        df['low_utilization'] = (df['factory_utilization'] < 50).astype(int)
        df['poor_management'] = (df['management_quality_score'] < 3).astype(int)
        
        # Update feature columns
        self.feature_columns.extend([
            'high_debt_ratio', 'negative_profit', 'low_consistency',
            'has_litigation', 'negative_sentiment', 'low_utilization', 'poor_management'
        ])
        
        return df
    
    def train_models(self, df):
        """Train multiple models and select the best one"""
        
        # Prepare features and target
        X = df[self.feature_columns]
        y = df['default_flag']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train multiple models
        models = {
            'random_forest': RandomForestClassifier(
                n_estimators=100, 
                max_depth=10, 
                random_state=42
            ),
            'gradient_boosting': GradientBoostingClassifier(
                n_estimators=100, 
                learning_rate=0.1, 
                max_depth=6, 
                random_state=42
            ),
            'logistic_regression': LogisticRegression(
                random_state=42, 
                max_iter=1000
            )
        }
        
        best_model = None
        best_score = 0
        best_model_name = ""
        
        for name, model in models.items():
            if name == 'logistic_regression':
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                score = accuracy_score(y_test, y_pred)
            else:
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                score = accuracy_score(y_test, y_pred)
            
            print(f"{name} - Accuracy: {score:.4f}")
            
            if score > best_score:
                best_score = score
                best_model = model
                best_model_name = name
        
        print(f"\nBest model: {best_model_name} with accuracy: {best_score:.4f}")
        
        # Store the best model and scaler
        self.models['best_model'] = best_model
        self.models['model_name'] = best_model_name
        self.scalers['standard_scaler'] = scaler
        
        # Feature importance for tree-based models
        if hasattr(best_model, 'feature_importances_'):
            feature_importance = pd.DataFrame({
                'feature': self.feature_columns,
                'importance': best_model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            print("\nFeature Importance:")
            print(feature_importance.head(10))
        
        return best_model, scaler, best_score
    
    def evaluate_model(self, model, X_test, y_test, use_scaler=False):
        """Evaluate the trained model"""
        
        if use_scaler:
            X_test_scaled = self.scalers['standard_scaler'].transform(X_test)
            y_pred = model.predict(X_test_scaled)
        else:
            y_pred = model.predict(X_test)
        
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred)
        
        print(f"\nModel Evaluation:")
        print(f"Accuracy: {accuracy:.4f}")
        print(f"\nClassification Report:")
        print(report)
        print(f"\nConfusion Matrix:")
        print(cm)
        
        return accuracy, report, cm
    
    def save_models(self, save_dir="ml_models/saved_models"):
        """Save the trained models and scalers"""
        
        os.makedirs(save_dir, exist_ok=True)
        
        # Save the best model
        joblib.dump(
            self.models['best_model'], 
            os.path.join(save_dir, 'credit_risk_model.pkl')
        )
        
        # Save the scaler
        if 'standard_scaler' in self.scalers:
            joblib.dump(
                self.scalers['standard_scaler'], 
                os.path.join(save_dir, 'feature_scaler.pkl')
            )
        
        # Save feature columns
        joblib.dump(
            self.feature_columns, 
            os.path.join(save_dir, 'feature_columns.pkl')
        )
        
        # Save model metadata
        metadata = {
            'model_name': self.models['model_name'],
            'feature_columns': self.feature_columns,
            'training_date': datetime.now().isoformat(),
            'model_type': 'classification'
        }
        
        joblib.dump(
            metadata, 
            os.path.join(save_dir, 'model_metadata.pkl')
        )
        
        print(f"Models saved to {save_dir}")
    
    def load_models(self, save_dir="ml_models/saved_models"):
        """Load the trained models and scalers"""
        
        try:
            # Load the model
            self.models['best_model'] = joblib.load(
                os.path.join(save_dir, 'credit_risk_model.pkl')
            )
            
            # Load the scaler
            self.scalers['standard_scaler'] = joblib.load(
                os.path.join(save_dir, 'feature_scaler.pkl')
            )
            
            # Load feature columns
            self.feature_columns = joblib.load(
                os.path.join(save_dir, 'feature_columns.pkl')
            )
            
            # Load metadata
            metadata = joblib.load(
                os.path.join(save_dir, 'model_metadata.pkl')
            )
            self.models['model_name'] = metadata['model_name']
            
            print(f"Models loaded from {save_dir}")
            print(f"Model type: {metadata['model_name']}")
            
            return True
        except Exception as e:
            print(f"Error loading models: {str(e)}")
            return False
    
    def predict_risk(self, data):
        """Make predictions on new data"""
        
        if 'best_model' not in self.models:
            raise ValueError("Model not trained. Please train the model first.")
        
        # Ensure data has all required features
        for col in self.feature_columns:
            if col not in data.columns:
                data[col] = 0
        
        X = data[self.feature_columns]
        
        # Apply scaling if needed
        if self.models['model_name'] == 'logistic_regression':
            X_scaled = self.scalers['standard_scaler'].transform(X)
            predictions = self.models['best_model'].predict_proba(X_scaled)[:, 1]
        else:
            predictions = self.models['best_model'].predict_proba(X)[:, 1]
        
        return predictions


def main():
    """Main training function"""
    
    print("Starting Credit Risk Model Training...")
    
    # Initialize trainer
    trainer = CreditRiskModelTrainer()
    
    # Generate sample data
    print("Generating sample training data...")
    df = trainer.generate_sample_data(n_samples=1000)
    
    # Preprocess data
    print("Preprocessing data...")
    df = trainer.preprocess_data(df)
    
    # Train models
    print("Training models...")
    best_model, scaler, accuracy = trainer.train_models(df)
    
    # Evaluate on test set
    X_train, X_test, y_train, y_test = train_test_split(
        df[trainer.feature_columns], 
        df['default_flag'], 
        test_size=0.2, 
        random_state=42, 
        stratify=df['default_flag']
    )
    
    use_scaler = trainer.models['model_name'] == 'logistic_regression'
    trainer.evaluate_model(best_model, X_test, y_test, use_scaler)
    
    # Save models
    trainer.save_models()
    
    print("\nTraining completed successfully!")
    print(f"Best model accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()
