"""
Financial Consistency Analyzer Module
Detects financial inconsistencies across datasets and validates data integrity
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
import re
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

@dataclass
class ConsistencyAlert:
    """Alert for financial inconsistency"""
    alert_type: str
    description: str
    severity: RiskLevel
    confidence: float
    affected_data: List[str]
    recommendation: str
    detected_at: datetime

@dataclass
class FinancialMetrics:
    """Financial metrics for comparison"""
    gst_revenue: float = 0.0
    bank_deposits: float = 0.0
    reported_revenue: float = 0.0
    cash_flow: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    equity: float = 0.0
    working_capital: float = 0.0
    inventory_turnover: float = 0.0
    debtor_turnover: float = 0.0

class FinancialConsistencyAnalyzer:
    """Analyzes financial data consistency across multiple sources"""
    
    def __init__(self):
        self.consistency_rules = self._initialize_rules()
        self.thresholds = self._initialize_thresholds()
        
    def _initialize_rules(self) -> Dict[str, Dict]:
        """Initialize consistency checking rules"""
        return {
            'gst_vs_bank': {
                'name': 'GST Revenue vs Bank Deposits',
                'description': 'Compare GST reported revenue with bank deposits',
                'threshold': 0.3,  # 30% tolerance
                'severity_weights': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.3,
                    'critical': 0.5
                }
            },
            'revenue_growth': {
                'name': 'Revenue Growth Consistency',
                'description': 'Check for unrealistic revenue growth patterns',
                'threshold': 0.5,  # 50% year-over-year growth threshold
                'severity_weights': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.3,
                    'critical': 0.4
                }
            },
            'cash_flow_consistency': {
                'name': 'Cash Flow Consistency',
                'description': 'Validate cash flow against profit figures',
                'threshold': 0.2,  # 20% tolerance
                'severity_weights': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.3,
                    'critical': 0.4
                }
            },
            'working_capital': {
                'name': 'Working Capital Analysis',
                'description': 'Analyze working capital adequacy',
                'threshold': 0.15,  # 15% of revenue as minimum working capital
                'severity_weights': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.3,
                    'critical': 0.4
                }
            },
            'debt_equity_ratio': {
                'name': 'Debt-Equity Ratio',
                'description': 'Check debt-equity ratio consistency',
                'threshold': 2.0,  # Maximum 2:1 ratio
                'severity_weights': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.3,
                    'critical': 0.4
                }
            },
            'inventory_turnover': {
                'name': 'Inventory Turnover Analysis',
                'description': 'Analyze inventory turnover patterns',
                'threshold': 0.5,  # Minimum 0.5 times per year
                'severity_weights': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.3,
                    'critical': 0.4
                }
            }
        }
    
    def _initialize_thresholds(self) -> Dict[str, float]:
        """Initialize risk thresholds"""
        return {
            'gst_bank_mismatch_critical': 0.5,  # >50% difference
            'gst_bank_mismatch_high': 0.3,     # 30-50% difference
            'gst_bank_mismatch_medium': 0.2,   # 20-30% difference
            'revenue_growth_unrealistic': 1.0,  # >100% YoY growth
            'cash_flow_negative_critical': -0.5, # Cash flow < -50% of profit
            'working_capital_inadequate': 0.1,   # <10% of revenue
            'debt_equity_critical': 3.0,        # >3:1 ratio
            'inventory_turnover_low': 0.2       # <0.2 times per year
        }
    
    def analyze_consistency(self, gst_data: Dict, bank_data: Dict, 
                          financial_statements: Dict) -> Dict[str, Any]:
        """
        Main method to analyze financial consistency across datasets
        
        Args:
            gst_data: GST returns data
            bank_data: Bank statements data  
            financial_statements: Audited financial statements
            
        Returns:
            Comprehensive consistency analysis report
        """
        
        logger.info("Starting financial consistency analysis")
        
        # Extract metrics from all data sources
        gst_metrics = self._extract_gst_metrics(gst_data)
        bank_metrics = self._extract_bank_metrics(bank_data)
        stmt_metrics = self._extract_statement_metrics(financial_statements)
        
        # Combine all metrics
        combined_metrics = FinancialMetrics(
            gst_revenue=gst_metrics.get('total_turnover', 0),
            bank_deposits=bank_metrics.get('total_deposits', 0),
            reported_revenue=stmt_metrics.get('revenue', 0),
            cash_flow=stmt_metrics.get('cash_flow', 0),
            total_assets=stmt_metrics.get('total_assets', 0),
            total_liabilities=stmt_metrics.get('total_liabilities', 0),
            equity=stmt_metrics.get('equity', 0),
            working_capital=stmt_metrics.get('working_capital', 0),
            inventory_turnover=stmt_metrics.get('inventory_turnover', 0),
            debtor_turnover=stmt_metrics.get('debtor_turnover', 0)
        )
        
        # Run all consistency checks
        alerts = []
        
        # GST vs Bank Deposits check
        gst_bank_alert = self._check_gst_vs_bank_deposits(combined_metrics)
        if gst_bank_alert:
            alerts.append(gst_bank_alert)
        
        # Revenue growth consistency
        revenue_alert = self._check_revenue_growth_consistency(combined_metrics, financial_statements)
        if revenue_alert:
            alerts.append(revenue_alert)
        
        # Cash flow consistency
        cash_flow_alert = self._check_cash_flow_consistency(combined_metrics)
        if cash_flow_alert:
            alerts.append(cash_flow_alert)
        
        # Working capital analysis
        working_capital_alert = self._check_working_capital_adequacy(combined_metrics)
        if working_capital_alert:
            alerts.append(working_capital_alert)
        
        # Debt-equity ratio
        debt_equity_alert = self._check_debt_equity_ratio(combined_metrics)
        if debt_equity_alert:
            alerts.append(debt_equity_alert)
        
        # Inventory turnover analysis
        inventory_alert = self._check_inventory_turnover(combined_metrics)
        if inventory_alert:
            alerts.append(inventory_alert)
        
        # Circular trading detection
        circular_trading_alerts = self._detect_circular_trading(gst_data, bank_data)
        alerts.extend(circular_trading_alerts)
        
        # Revenue inflation detection
        inflation_alerts = self._detect_revenue_inflation(combined_metrics)
        alerts.extend(inflation_alerts)
        
        # Calculate overall consistency score
        consistency_score = self._calculate_consistency_score(alerts, combined_metrics)
        
        # Generate analysis report
        analysis_report = {
            'consistency_score': consistency_score,
            'overall_risk_level': self._determine_overall_risk(alerts),
            'total_alerts': len(alerts),
            'alerts_by_severity': self._categorize_alerts(alerts),
            'detailed_alerts': alerts,
            'financial_metrics': combined_metrics,
            'data_quality_score': self._calculate_data_quality(gst_data, bank_data, financial_statements),
            'recommendations': self._generate_recommendations(alerts),
            'analysis_timestamp': datetime.now().isoformat(),
            'summary': self._generate_analysis_summary(alerts, consistency_score)
        }
        
        logger.info(f"Consistency analysis completed. Score: {consistency_score:.2f}, Alerts: {len(alerts)}")
        
        return analysis_report
    
    def _extract_gst_metrics(self, gst_data: Dict) -> Dict[str, float]:
        """Extract key metrics from GST data"""
        metrics = {}
        
        try:
            # Extract turnover from GST returns
            if 'returns' in gst_data:
                total_turnover = 0
                for return_period in gst_data['returns']:
                    if 'turnover' in return_period:
                        total_turnover += float(return_period['turnover'])
                metrics['total_turnover'] = total_turnover
            
            # Extract tax liability patterns
            if 'tax_liabilities' in gst_data:
                metrics['total_tax_liability'] = sum([
                    float(liability.get('amount', 0)) 
                    for liability in gst_data['tax_liabilities']
                ])
            
            # Extract filing consistency
            if 'filing_history' in gst_data:
                filed_returns = len([r for r in gst_data['filing_history'] if r.get('filed', False)])
                total_returns = len(gst_data['filing_history'])
                metrics['filing_consistency'] = filed_returns / total_returns if total_returns > 0 else 0
            
        except Exception as e:
            logger.error(f"Error extracting GST metrics: {str(e)}")
        
        return metrics
    
    def _extract_bank_metrics(self, bank_data: Dict) -> Dict[str, float]:
        """Extract key metrics from bank statements"""
        metrics = {}
        
        try:
            # Total deposits
            if 'transactions' in bank_data:
                deposits = [
                    float(t.get('amount', 0)) 
                    for t in bank_data['transactions'] 
                    if t.get('type') == 'credit' and float(t.get('amount', 0)) > 0
                ]
                metrics['total_deposits'] = sum(deposits)
                metrics['deposit_count'] = len(deposits)
                
                # Average deposit size
                metrics['avg_deposit_size'] = np.mean(deposits) if deposits else 0
            
            # Cash flow patterns
            if 'monthly_summary' in bank_data:
                cash_flows = [
                    float(month.get('net_cash_flow', 0)) 
                    for month in bank_data['monthly_summary']
                ]
                metrics['avg_monthly_cash_flow'] = np.mean(cash_flows) if cash_flows else 0
                metrics['cash_flow_volatility'] = np.std(cash_flows) if cash_flows else 0
            
            # Large transactions analysis
            if 'transactions' in bank_data:
                large_transactions = [
                    t for t in bank_data['transactions'] 
                    if abs(float(t.get('amount', 0))) > 1000000  # > 1 lakh
                ]
                metrics['large_transaction_count'] = len(large_transactions)
                metrics['large_transaction_ratio'] = len(large_transactions) / len(bank_data['transactions'])
            
        except Exception as e:
            logger.error(f"Error extracting bank metrics: {str(e)}")
        
        return metrics
    
    def _extract_statement_metrics(self, financial_statements: Dict) -> Dict[str, float]:
        """Extract key metrics from financial statements"""
        metrics = {}
        
        try:
            # Balance sheet metrics
            if 'balance_sheet' in financial_statements:
                bs = financial_statements['balance_sheet']
                metrics['total_assets'] = float(bs.get('total_assets', 0))
                metrics['total_liabilities'] = float(bs.get('total_liabilities', 0))
                metrics['equity'] = float(bs.get('shareholders_equity', 0))
                
                # Working capital
                current_assets = float(bs.get('current_assets', 0))
                current_liabilities = float(bs.get('current_liabilities', 0))
                metrics['working_capital'] = current_assets - current_liabilities
            
            # Profit & Loss metrics
            if 'profit_loss' in financial_statements:
                pl = financial_statements['profit_loss']
                metrics['revenue'] = float(pl.get('total_revenue', 0))
                metrics['net_profit'] = float(pl.get('net_profit', 0))
                metrics['gross_profit'] = float(pl.get('gross_profit', 0))
            
            # Cash flow metrics
            if 'cash_flow' in financial_statements:
                cf = financial_statements['cash_flow']
                metrics['cash_flow'] = float(cf.get('net_cash_flow', 0))
                metrics['operating_cash_flow'] = float(cf.get('operating_cash_flow', 0))
            
            # Ratio calculations
            if metrics.get('revenue', 0) > 0:
                # Inventory turnover
                cogs = float(financial_statements.get('profit_loss', {}).get('cost_of_goods_sold', 0))
                inventory = float(financial_statements.get('balance_sheet', {}).get('inventory', 0))
                metrics['inventory_turnover'] = cogs / inventory if inventory > 0 else 0
                
                # Debtor turnover
                debtors = float(financial_statements.get('balance_sheet', {}).get('trade_receivables', 0))
                metrics['debtor_turnover'] = metrics['revenue'] / debtors if debtors > 0 else 0
            
        except Exception as e:
            logger.error(f"Error extracting statement metrics: {str(e)}")
        
        return metrics
    
    def _check_gst_vs_bank_deposits(self, metrics: FinancialMetrics) -> Optional[ConsistencyAlert]:
        """Check consistency between GST revenue and bank deposits"""
        
        if metrics.gst_revenue == 0 or metrics.bank_deposits == 0:
            return None
        
        # Calculate variance
        variance = abs(metrics.gst_revenue - metrics.bank_deposits) / metrics.gst_revenue
        
        if variance > self.thresholds['gst_bank_mismatch_critical']:
            severity = RiskLevel.CRITICAL
            description = f"Critical mismatch: GST revenue (₹{metrics.gst_revenue:,.0f}) differs from bank deposits (₹{metrics.bank_deposits:,.0f}) by {variance:.1%}"
            recommendation = "Immediate investigation required. Possible revenue inflation or fund diversion detected."
        elif variance > self.thresholds['gst_bank_mismatch_high']:
            severity = RiskLevel.HIGH
            description = f"High variance: GST revenue (₹{metrics.gst_revenue:,.0f}) differs from bank deposits (₹{metrics.bank_deposits:,.0f}) by {variance:.1%}"
            recommendation = "Detailed reconciliation required. Verify revenue recognition practices."
        elif variance > self.thresholds['gst_bank_mismatch_medium']:
            severity = RiskLevel.MEDIUM
            description = f"Moderate variance: GST revenue (₹{metrics.gst_revenue:,.0f}) differs from bank deposits (₹{metrics.bank_deposits:,.0f}) by {variance:.1%}"
            recommendation = "Review payment terms and collection cycles."
        else:
            return None
        
        return ConsistencyAlert(
            alert_type="GST_Bank_Mismatch",
            description=description,
            severity=severity,
            confidence=min(variance * 2, 1.0),
            affected_data=["GST Returns", "Bank Statements"],
            recommendation=recommendation,
            detected_at=datetime.now()
        )
    
    def _check_revenue_growth_consistency(self, metrics: FinancialMetrics, 
                                        financial_statements: Dict) -> Optional[ConsistencyAlert]:
        """Check for unrealistic revenue growth patterns"""
        
        # Get historical revenue data
        historical_revenue = self._extract_historical_revenue(financial_statements)
        
        if len(historical_revenue) < 2:
            return None
        
        # Calculate year-over-year growth rates
        growth_rates = []
        for i in range(1, len(historical_revenue)):
            if historical_revenue[i-1] > 0:
                growth_rate = (historical_revenue[i] - historical_revenue[i-1]) / historical_revenue[i-1]
                growth_rates.append(growth_rate)
        
        if not growth_rates:
            return None
        
        avg_growth = np.mean(growth_rates)
        max_growth = max(growth_rates)
        
        # Check for unrealistic growth
        if max_growth > self.thresholds['revenue_growth_unrealistic']:
            severity = RiskLevel.HIGH
            description = f"Unrealistic revenue growth detected: Maximum YoY growth of {max_growth:.1%}"
            recommendation = "Verify revenue recognition and business model sustainability."
        elif avg_growth > 0.5:  # 50% average growth
            severity = RiskLevel.MEDIUM
            description = f"High revenue growth pattern: Average YoY growth of {avg_growth:.1%}"
            recommendation = "Validate growth drivers and market conditions."
        else:
            return None
        
        return ConsistencyAlert(
            alert_type="Revenue_Growth_Anomaly",
            description=description,
            severity=severity,
            confidence=min(max_growth, 1.0),
            affected_data=["Financial Statements"],
            recommendation=recommendation,
            detected_at=datetime.now()
        )
    
    def _check_cash_flow_consistency(self, metrics: FinancialMetrics) -> Optional[ConsistencyAlert]:
        """Check consistency between profit and cash flow"""
        
        if metrics.reported_revenue == 0:
            return None
        
        # Calculate cash flow to revenue ratio
        cash_flow_ratio = metrics.cash_flow / metrics.reported_revenue
        
        if cash_flow_ratio < self.thresholds['cash_flow_negative_critical']:
            severity = RiskLevel.CRITICAL
            description = f"Critical cash flow issue: Cash flow (₹{metrics.cash_flow:,.0f}) is {abs(cash_flow_ratio):.1%} of revenue"
            recommendation = "Immediate liquidity assessment required. Check working capital management."
        elif cash_flow_ratio < 0:
            severity = RiskLevel.HIGH
            description = f"Negative cash flow: Cash flow (₹{metrics.cash_flow:,.0f}) while revenue is positive"
            recommendation = "Review cash conversion cycle and collection efficiency."
        elif cash_flow_ratio < 0.1:  # Less than 10% of revenue
            severity = RiskLevel.MEDIUM
            description = f"Low cash flow conversion: Only {cash_flow_ratio:.1%} of revenue converted to cash"
            recommendation = "Optimize working capital and collection processes."
        else:
            return None
        
        return ConsistencyAlert(
            alert_type="Cash_Flow_Inconsistency",
            description=description,
            severity=severity,
            confidence=abs(cash_flow_ratio),
            affected_data=["Cash Flow Statement", "Profit & Loss"],
            recommendation=recommendation,
            detected_at=datetime.now()
        )
    
    def _check_working_capital_adequacy(self, metrics: FinancialMetrics) -> Optional[ConsistencyAlert]:
        """Check working capital adequacy"""
        
        if metrics.reported_revenue == 0:
            return None
        
        # Calculate working capital to revenue ratio
        wc_ratio = metrics.working_capital / metrics.reported_revenue
        
        if wc_ratio < self.thresholds['working_capital_inadequate']:
            severity = RiskLevel.HIGH
            description = f"Inadequate working capital: Only {wc_ratio:.1%} of annual revenue"
            recommendation = "Assess working capital requirements and financing needs."
        elif wc_ratio < 0.15:  # Less than 15% of revenue
            severity = RiskLevel.MEDIUM
            description = f"Tight working capital: {wc_ratio:.1%} of annual revenue"
            recommendation = "Monitor working capital trends and collection cycles."
        else:
            return None
        
        return ConsistencyAlert(
            alert_type="Working_Capital_Inadequate",
            description=description,
            severity=severity,
            confidence=1.0 - wc_ratio,
            affected_data=["Balance Sheet"],
            recommendation=recommendation,
            detected_at=datetime.now()
        )
    
    def _check_debt_equity_ratio(self, metrics: FinancialMetrics) -> Optional[ConsistencyAlert]:
        """Check debt-equity ratio"""
        
        if metrics.equity == 0:
            return None
        
        # Calculate debt-equity ratio
        debt_equity_ratio = metrics.total_liabilities / metrics.equity
        
        if debt_equity_ratio > self.thresholds['debt_equity_critical']:
            severity = RiskLevel.CRITICAL
            description = f"Critical leverage: Debt-equity ratio of {debt_equity_ratio:.1f}:1"
            recommendation = "Immediate deleveraging required. Restructure debt obligations."
        elif debt_equity_ratio > 2.0:  # Standard threshold
            severity = RiskLevel.HIGH
            description = f"High leverage: Debt-equity ratio of {debt_equity_ratio:.1f}:1"
            recommendation = "Review debt servicing capacity and financial risk."
        elif debt_equity_ratio > 1.5:
            severity = RiskLevel.MEDIUM
            description = f"Moderate leverage: Debt-equity ratio of {debt_equity_ratio:.1f}:1"
            recommendation = "Monitor debt levels and interest coverage ratio."
        else:
            return None
        
        return ConsistencyAlert(
            alert_type="High_Debt_Equity",
            description=description,
            severity=severity,
            confidence=min(debt_equity_ratio / 3.0, 1.0),
            affected_data=["Balance Sheet"],
            recommendation=recommendation,
            detected_at=datetime.now()
        )
    
    def _check_inventory_turnover(self, metrics: FinancialMetrics) -> Optional[ConsistencyAlert]:
        """Check inventory turnover patterns"""
        
        if metrics.inventory_turnover == 0:
            return None
        
        if metrics.inventory_turnover < self.thresholds['inventory_turnover_low']:
            severity = RiskLevel.HIGH
            description = f"Very low inventory turnover: {metrics.inventory_turnover:.1f} times per year"
            recommendation = "Investigate inventory obsolescence and sales performance."
        elif metrics.inventory_turnover < 1.0:  # Less than 1 time per year
            severity = RiskLevel.MEDIUM
            description = f"Low inventory turnover: {metrics.inventory_turnover:.1f} times per year"
            recommendation = "Review inventory management and sales strategy."
        else:
            return None
        
        return ConsistencyAlert(
            alert_type="Low_Inventory_Turnover",
            description=description,
            severity=severity,
            confidence=1.0 - min(metrics.inventory_turnover / 2.0, 1.0),
            affected_data=["Balance Sheet", "Profit & Loss"],
            recommendation=recommendation,
            detected_at=datetime.now()
        )
    
    def _detect_circular_trading(self, gst_data: Dict, bank_data: Dict) -> List[ConsistencyAlert]:
        """Detect potential circular trading patterns"""
        alerts = []
        
        try:
            # Analyze transaction patterns for circular trading indicators
            if 'transactions' in bank_data:
                transactions = bank_data['transactions']
                
                # Look for round amount transactions (potential circular trading)
                round_transactions = [
                    t for t in transactions 
                    if self._is_round_amount(float(t.get('amount', 0)))
                ]
                
                if len(round_transactions) > len(transactions) * 0.3:  # >30% round amounts
                    alerts.append(ConsistencyAlert(
                        alert_type="Circular_Trading_Suspected",
                        description=f"High proportion of round amount transactions: {len(round_transactions)}/{len(transactions)}",
                        severity=RiskLevel.HIGH,
                        confidence=0.7,
                        affected_data=["Bank Statements"],
                        recommendation="Investigate transaction counterparties and business rationale.",
                        detected_at=datetime.now()
                    ))
            
            # Check for same-day reciprocal transactions
            if 'transactions' in bank_data:
                reciprocal_alerts = self._check_reciprocal_transactions(bank_data['transactions'])
                alerts.extend(reciprocal_alerts)
                
        except Exception as e:
            logger.error(f"Error in circular trading detection: {str(e)}")
        
        return alerts
    
    def _detect_revenue_inflation(self, metrics: FinancialMetrics) -> List[ConsistencyAlert]:
        """Detect potential revenue inflation"""
        alerts = []
        
        try:
            # GST revenue significantly higher than bank deposits
            if metrics.gst_revenue > 0 and metrics.bank_deposits > 0:
                inflation_ratio = metrics.gst_revenue / metrics.bank_deposits
                
                if inflation_ratio > 1.5:  # GST revenue 50% higher than bank deposits
                    alerts.append(ConsistencyAlert(
                        alert_type="Revenue_Inflation_Suspected",
                        description=f"GST revenue exceeds bank deposits by {(inflation_ratio - 1) * 100:.1f}%",
                        severity=RiskLevel.HIGH,
                        confidence=min((inflation_ratio - 1) / 2, 1.0),
                        affected_data=["GST Returns", "Bank Statements"],
                        recommendation="Verify revenue recognition and investigate potential invoice manipulation.",
                        detected_at=datetime.now()
                    ))
            
            # Check for inconsistent profit margins
            if metrics.reported_revenue > 0 and metrics.net_profit > 0:
                profit_margin = metrics.net_profit / metrics.reported_revenue
                
                if profit_margin > 0.3:  # >30% profit margin (unusually high)
                    alerts.append(ConsistencyAlert(
                        alert_type="Unrealistic_Profit_Margin",
                        description=f"Unusually high profit margin: {profit_margin:.1%}",
                        severity=RiskLevel.MEDIUM,
                        confidence=min(profit_margin / 0.5, 1.0),
                        affected_data=["Profit & Loss"],
                        recommendation="Validate cost structure and pricing strategy.",
                        detected_at=datetime.now()
                    ))
                    
        except Exception as e:
            logger.error(f"Error in revenue inflation detection: {str(e)}")
        
        return alerts
    
    def _is_round_amount(self, amount: float) -> bool:
        """Check if amount is a round number (potential circular trading indicator)"""
        if amount <= 0:
            return False
        
        # Check for amounts ending in 000 or 00000
        amount_str = f"{amount:.0f}"
        return amount_str.endswith('000') or amount_str.endswith('00000')
    
    def _check_reciprocal_transactions(self, transactions: List[Dict]) -> List[ConsistencyAlert]:
        """Check for same-day reciprocal transactions"""
        alerts = []
        
        try:
            # Group transactions by date and amount
            daily_transactions = {}
            for transaction in transactions:
                date = transaction.get('date', '')
                amount = float(transaction.get('amount', 0))
                
                if date not in daily_transactions:
                    daily_transactions[date] = []
                daily_transactions[date].append({
                    'amount': amount,
                    'type': transaction.get('type', ''),
                    'counterparty': transaction.get('counterparty', '')
                })
            
            # Look for reciprocal patterns
            for date, day_txns in daily_transactions.items():
                credit_amounts = [t['amount'] for t in day_txns if t['type'] == 'credit']
                debit_amounts = [t['amount'] for t in day_txns if t['type'] == 'debit']
                
                # Check for matching amounts on same day
                for credit in credit_amounts:
                    for debit in debit_amounts:
                        if abs(credit - debit) < 100:  # Within Rs. 100
                            alerts.append(ConsistencyAlert(
                                alert_type="Reciprocal_Transaction_Detected",
                                description=f"Same-day reciprocal transaction of ₹{credit:,.0f} on {date}",
                                severity=RiskLevel.MEDIUM,
                                confidence=0.6,
                                affected_data=["Bank Statements"],
                                recommendation="Verify business purpose of reciprocal transactions.",
                                detected_at=datetime.now()
                            ))
                            break
                            
        except Exception as e:
            logger.error(f"Error checking reciprocal transactions: {str(e)}")
        
        return alerts
    
    def _extract_historical_revenue(self, financial_statements: Dict) -> List[float]:
        """Extract historical revenue data"""
        revenues = []
        
        try:
            if 'historical_data' in financial_statements:
                for period in financial_statements['historical_data']:
                    if 'revenue' in period:
                        revenues.append(float(period['revenue']))
            elif 'profit_loss' in financial_statements:
                # Current period only
                revenues.append(float(financial_statements['profit_loss'].get('total_revenue', 0)))
                
        except Exception as e:
            logger.error(f"Error extracting historical revenue: {str(e)}")
        
        return revenues
    
    def _calculate_consistency_score(self, alerts: List[ConsistencyAlert], 
                                   metrics: FinancialMetrics) -> float:
        """Calculate overall consistency score (0-100)"""
        
        if not alerts:
            return 100.0
        
        # Base score of 100, deduct points for each alert
        score = 100.0
        
        for alert in alerts:
            if alert.severity == RiskLevel.CRITICAL:
                score -= 25 * alert.confidence
            elif alert.severity == RiskLevel.HIGH:
                score -= 15 * alert.confidence
            elif alert.severity == RiskLevel.MEDIUM:
                score -= 10 * alert.confidence
            else:  # LOW
                score -= 5 * alert.confidence
        
        return max(0, score)
    
    def _determine_overall_risk(self, alerts: List[ConsistencyAlert]) -> RiskLevel:
        """Determine overall risk level based on alerts"""
        
        if not alerts:
            return RiskLevel.LOW
        
        # Check for critical alerts
        critical_alerts = [a for a in alerts if a.severity == RiskLevel.CRITICAL]
        if critical_alerts:
            return RiskLevel.CRITICAL
        
        # Check for high severity alerts
        high_alerts = [a for a in alerts if a.severity == RiskLevel.HIGH]
        if len(high_alerts) >= 2:
            return RiskLevel.CRITICAL
        elif high_alerts:
            return RiskLevel.HIGH
        
        # Check for multiple medium alerts
        medium_alerts = [a for a in alerts if a.severity == RiskLevel.MEDIUM]
        if len(medium_alerts) >= 3:
            return RiskLevel.HIGH
        elif medium_alerts:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _categorize_alerts(self, alerts: List[ConsistencyAlert]) -> Dict[str, int]:
        """Categorize alerts by severity"""
        categories = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for alert in alerts:
            categories[alert.severity.value.lower()] += 1
        
        return categories
    
    def _calculate_data_quality(self, gst_data: Dict, bank_data: Dict, 
                              financial_statements: Dict) -> float:
        """Calculate data quality score based on completeness and consistency"""
        
        quality_score = 0.0
        total_checks = 0
        
        # Check GST data completeness
        if gst_data:
            total_checks += 1
            if 'returns' in gst_data and gst_data['returns']:
                quality_score += 1.0
            if 'filing_history' in gst_data:
                quality_score += 0.8
        
        # Check bank data completeness
        if bank_data:
            total_checks += 1
            if 'transactions' in bank_data and bank_data['transactions']:
                quality_score += 1.0
            if 'monthly_summary' in bank_data:
                quality_score += 0.8
        
        # Check financial statements completeness
        if financial_statements:
            total_checks += 1
            required_statements = ['balance_sheet', 'profit_loss', 'cash_flow']
            present_statements = sum(1 for stmt in required_statements if stmt in financial_statements)
            quality_score += present_statements / len(required_statements)
        
        return (quality_score / total_checks * 100) if total_checks > 0 else 0.0
    
    def _generate_recommendations(self, alerts: List[ConsistencyAlert]) -> List[str]:
        """Generate actionable recommendations based on alerts"""
        recommendations = []
        
        # Consolidate similar recommendations
        seen_recommendations = set()
        
        for alert in alerts:
            if alert.recommendation not in seen_recommendations:
                recommendations.append(alert.recommendation)
                seen_recommendations.add(alert.recommendation)
        
        # Add general recommendations
        if alerts:
            recommendations.append("Conduct detailed reconciliation of all financial data sources.")
            recommendations.append("Consider engaging external auditors for verification.")
        
        return recommendations
    
    def _generate_analysis_summary(self, alerts: List[ConsistencyAlert], 
                                 consistency_score: float) -> str:
        """Generate a concise analysis summary"""
        
        if not alerts:
            return "Financial data shows strong consistency across all sources with no significant anomalies detected."
        
        alert_summary = []
        severity_counts = self._categorize_alerts(alerts)
        
        if severity_counts['critical'] > 0:
            alert_summary.append(f"{severity_counts['critical']} critical issues")
        if severity_counts['high'] > 0:
            alert_summary.append(f"{severity_counts['high']} high-risk issues")
        if severity_counts['medium'] > 0:
            alert_summary.append(f"{severity_counts['medium']} medium-risk issues")
        if severity_counts['low'] > 0:
            alert_summary.append(f"{severity_counts['low']} low-risk issues")
        
        summary = f"Financial consistency analysis reveals {', '.join(alert_summary)}. "
        summary += f"Overall consistency score is {consistency_score:.1f}/100. "
        
        if consistency_score < 50:
            summary += "Immediate investigation and remediation required."
        elif consistency_score < 75:
            summary += "Review and corrective actions recommended."
        else:
            summary += "Minor issues that should be monitored."
        
        return summary

# Usage example
if __name__ == "__main__":
    # Mock data for testing
    gst_data = {
        'returns': [
            {'turnover': '10000000'},
            {'turnover': '12000000'}
        ],
        'filing_history': [
            {'filed': True, 'period': '2023-01'},
            {'filed': True, 'period': '2023-02'}
        ]
    }
    
    bank_data = {
        'transactions': [
            {'amount': '5000000', 'type': 'credit', 'date': '2023-01-15'},
            {'amount': '7000000', 'type': 'credit', 'date': '2023-02-15'}
        ],
        'monthly_summary': [
            {'net_cash_flow': '2000000'},
            {'net_cash_flow': '3000000'}
        ]
    }
    
    financial_statements = {
        'balance_sheet': {
            'total_assets': '50000000',
            'total_liabilities': '20000000',
            'shareholders_equity': '30000000',
            'current_assets': '25000000',
            'current_liabilities': '10000000'
        },
        'profit_loss': {
            'total_revenue': '15000000',
            'net_profit': '2000000',
            'cost_of_goods_sold': '10000000'
        },
        'cash_flow': {
            'net_cash_flow': '2500000',
            'operating_cash_flow': '3000000'
        }
    }
    
    analyzer = FinancialConsistencyAnalyzer()
    result = analyzer.analyze_consistency(gst_data, bank_data, financial_statements)
    
    print("Financial Consistency Analysis Results:")
    print(f"Consistency Score: {result['consistency_score']:.1f}/100")
    print(f"Overall Risk Level: {result['overall_risk_level'].value}")
    print(f"Total Alerts: {result['total_alerts']}")
    print(f"Summary: {result['summary']}")
