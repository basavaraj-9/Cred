from typing import Dict, List, Any
import pandas as pd
import numpy as np

class GSTBankAnalyzer:
    def __init__(self):
        self.anomaly_thresholds = {
            'revenue_mismatch_tolerance': 0.3,  # 30% tolerance
            'circular_trading_threshold': 2.0,  # 2x multiplier
            'cash_flow_anomaly_threshold': 0.5  # 50% deviation
        }
    
    def analyze_consistency(self, gst_data: Dict, bank_data: Dict) -> Dict[str, Any]:
        """Analyze consistency between GST returns and bank statements"""
        
        analysis_result = {
            'anomalies': [],
            'risk_flags': [],
            'consistency_score': 0,
            'detailed_analysis': {}
        }
        
        # Extract key metrics
        gst_revenue = gst_data.get('gst_revenue', 0)
        bank_deposits = self._extract_total_deposits(bank_data)
        bank_withdrawals = self._extract_total_withdrawals(bank_data)
        
        # Revenue consistency check
        revenue_analysis = self._analyze_revenue_consistency(gst_revenue, bank_deposits)
        analysis_result['detailed_analysis']['revenue'] = revenue_analysis
        
        if revenue_analysis['is_anomaly']:
            analysis_result['anomalies'].append(revenue_analysis['anomaly_type'])
            analysis_result['risk_flags'].append(revenue_analysis['risk_flag'])
        
        # Circular trading detection
        circular_analysis = self._detect_circular_trading(gst_data, bank_data)
        analysis_result['detailed_analysis']['circular_trading'] = circular_analysis
        
        if circular_analysis['is_suspicious']:
            analysis_result['anomalies'].append('Circular Trading Pattern')
            analysis_result['risk_flags'].append('High circular trading activity detected')
        
        # Cash flow analysis
        cash_flow_analysis = self._analyze_cash_flow(bank_data)
        analysis_result['detailed_analysis']['cash_flow'] = cash_flow_analysis
        
        if cash_flow_analysis['is_anomaly']:
            analysis_result['anomalies'].append('Cash Flow Anomaly')
            analysis_result['risk_flags'].append(cash_flow_analysis['anomaly_description'])
        
        # Calculate overall consistency score
        analysis_result['consistency_score'] = self._calculate_consistency_score(
            revenue_analysis, circular_analysis, cash_flow_analysis
        )
        
        # New: Counterparty Risk & DSR
        analysis_result['counterparty_risk'] = self._analyze_counterparty_risk(bank_data)
        analysis_result['debt_service_ratio'] = self._calculate_dsr(bank_data, gst_data)
        
        return analysis_result

    def _analyze_counterparty_risk(self, bank_data: Dict) -> Dict[str, Any]:
        """Identify potential related-party transactions and concentration risk"""
        if not isinstance(bank_data, dict) or 'transactions' not in bank_data:
            return {'risk_level': 'Low', 'details': 'No transaction data available'}
            
        transactions = bank_data['transactions']
        counterparties = {}
        
        for t in transactions:
            desc = t.get('description', '').upper()
            amount = t.get('amount', 0)
            
            # Simplified entity extraction from description
            # In production, this would use a NER model or entity database
            entity = desc.split('/')[0].split('-')[0].strip()
            if len(entity) > 3:
                if entity not in counterparties:
                    counterparties[entity] = {'total_volume': 0, 'count': 0}
                counterparties[entity]['total_volume'] += amount
                counterparties[entity]['count'] += 1
        
        # Identify concentration (e.g., more than 40% volume with one party)
        total_vol = sum(c['total_volume'] for c in counterparties.values())
        high_concentration_parties = []
        if total_vol > 0:
            for entity, stats in counterparties.items():
                if stats['total_volume'] / total_vol > 0.4:
                    high_concentration_parties.append(entity)
                    
        return {
            'risk_level': 'High' if high_concentration_parties else 'Low',
            'top_counterparties': sorted(counterparties.items(), key=lambda x: x[1]['total_volume'], reverse=True)[:5],
            'high_concentration_parties': high_concentration_parties,
            'description': f"High concentration detected with: {', '.join(high_concentration_parties)}" if high_concentration_parties else "Diversified counterparties"
        }

    def _calculate_dsr(self, bank_data: Dict, gst_data: Dict) -> Dict[str, Any]:
        """Calculate Debt Service Ratio (DSR) and Debt-to-Income"""
        # Estimates based on bank flows
        total_inflow = self._extract_total_deposits(bank_data)
        total_outflow = self._extract_total_withdrawals(bank_data)
        
        # Estimated monthly debt obligation (would usually come from bureau data)
        # Here we look for keywords in withdrawals like 'EMI', 'LOAN', 'INTEREST'
        debt_obligations = 0
        if isinstance(bank_data, dict) and 'transactions' in bank_data:
            debt_obligations = sum(t['amount'] for t in bank_data['transactions'] 
                                 if any(k in t.get('description', '').upper() for k in ['EMI', 'LOAN', 'INTEREST', 'FINANCE']))
        
        # Monthly average inflow
        monthly_inflow = total_inflow / 6  # Assuming 6 months of data
        dsr = (debt_obligations / monthly_inflow) if monthly_inflow > 0 else 0
        
        return {
            'value': round(dsr, 2),
            'status': 'Healthy' if dsr < 0.4 else 'Warning' if dsr < 0.6 else 'Critical',
            'monthly_debt_obligations': debt_obligations,
            'monthly_average_inflow': round(monthly_inflow, 2)
        }
    
    def _extract_total_deposits(self, bank_data: Dict) -> float:
        """Extract total deposits from bank statement data"""
        try:
            if isinstance(bank_data, dict) and 'transactions' in bank_data:
                deposits = [t['amount'] for t in bank_data['transactions'] 
                           if t.get('type') == 'credit' and t.get('amount', 0) > 0]
                return sum(deposits)
            elif isinstance(bank_data, dict) and 'total_deposits' in bank_data:
                return bank_data['total_deposits']
            else:
                return bank_data.get('revenue', 0) * 0.9  # Estimate
        except:
            return 0.0
    
    def _extract_total_withdrawals(self, bank_data: Dict) -> float:
        """Extract total withdrawals from bank statement data"""
        try:
            if isinstance(bank_data, dict) and 'transactions' in bank_data:
                withdrawals = [t['amount'] for t in bank_data['transactions'] 
                             if t.get('type') == 'debit' and t.get('amount', 0) > 0]
                return sum(withdrawals)
            elif isinstance(bank_data, dict) and 'total_withdrawals' in bank_data:
                return bank_data['total_withdrawals']
            else:
                return 0.0
        except:
            return 0.0
    
    def _analyze_revenue_consistency(self, gst_revenue: float, bank_deposits: float) -> Dict[str, Any]:
        """Analyze consistency between GST revenue and bank deposits"""
        
        if gst_revenue == 0 or bank_deposits == 0:
            return {
                'is_anomaly': True,
                'anomaly_type': 'Missing Data',
                'risk_flag': 'Insufficient financial data',
                'gst_revenue': gst_revenue,
                'bank_deposits': bank_deposits,
                'variance_percentage': 0
            }
        
        variance = abs(gst_revenue - bank_deposits) / max(gst_revenue, bank_deposits)
        variance_percentage = variance * 100
        
        # Check for revenue inflation (GST > Bank deposits)
        if gst_revenue > bank_deposits * (1 + self.anomaly_thresholds['revenue_mismatch_tolerance']):
            return {
                'is_anomaly': True,
                'anomaly_type': 'Revenue Inflation Risk',
                'risk_flag': f'GST revenue exceeds bank deposits by {variance_percentage:.1f}%',
                'gst_revenue': gst_revenue,
                'bank_deposits': bank_deposits,
                'variance_percentage': variance_percentage
            }
        
        # Check for revenue underreporting (Bank deposits > GST)
        elif bank_deposits > gst_revenue * (1 + self.anomaly_thresholds['revenue_mismatch_tolerance']):
            return {
                'is_anomaly': True,
                'anomaly_type': 'Revenue Underreporting Risk',
                'risk_flag': f'Bank deposits exceed GST revenue by {variance_percentage:.1f}%',
                'gst_revenue': gst_revenue,
                'bank_deposits': bank_deposits,
                'variance_percentage': variance_percentage
            }
        
        return {
            'is_anomaly': False,
            'anomaly_type': None,
            'risk_flag': None,
            'gst_revenue': gst_revenue,
            'bank_deposits': bank_deposits,
            'variance_percentage': variance_percentage
        }
    
    def _detect_circular_trading(self, gst_data: Dict, bank_data: Dict) -> Dict[str, Any]:
        """Detect circular trading patterns"""
        
        # Indicators of circular trading
        indicators = {
            'high_frequency_transactions': False,
            'round_amounts': False,
            'same_day_in_out': False,
            'multiple_small_deposits': False
        }
        
        suspicious_score = 0
        
        if isinstance(bank_data, dict) and 'transactions' in bank_data:
            transactions = bank_data['transactions']
            
            # Check for high frequency transactions
            if len(transactions) > 100:  # Threshold for high frequency
                indicators['high_frequency_transactions'] = True
                suspicious_score += 1
            
            # Check for round amounts (indicative of circular trading)
            round_amount_count = sum(1 for t in transactions 
                                   if t.get('amount', 0) % 10000 == 0 and t.get('amount', 0) > 0)
            if round_amount_count > len(transactions) * 0.3:  # 30% round amounts
                indicators['round_amounts'] = True
                suspicious_score += 1
            
            # Check for same day in-out patterns
            dates = {}
            for t in transactions:
                date = t.get('date', '')
                if date not in dates:
                    dates[date] = {'credits': 0, 'debits': 0}
                
                if t.get('type') == 'credit':
                    dates[date]['credits'] += 1
                else:
                    dates[date]['debits'] += 1
            
            same_day_patterns = sum(1 for d in dates.values() 
                                  if d['credits'] > 0 and d['debits'] > 0)
            if same_day_patterns > len(dates) * 0.5:  # 50% of days have both credits and debits
                indicators['same_day_in_out'] = True
                suspicious_score += 1
            
            # Check for multiple small deposits just below reporting thresholds
            small_deposits = [t for t in transactions 
                            if t.get('type') == 'credit' and 40000 < t.get('amount', 0) < 50000]
            if len(small_deposits) > 10:
                indicators['multiple_small_deposits'] = True
                suspicious_score += 1
        
        is_suspicious = suspicious_score >= 2
        
        return {
            'is_suspicious': is_suspicious,
            'suspicious_score': suspicious_score,
            'indicators': indicators,
            'risk_level': 'High' if suspicious_score >= 3 else 'Medium' if suspicious_score >= 2 else 'Low'
        }
    
    def _analyze_cash_flow(self, bank_data: Dict) -> Dict[str, Any]:
        """Analyze cash flow patterns for anomalies"""
        
        if not isinstance(bank_data, dict) or 'transactions' not in bank_data:
            return {
                'is_anomaly': True,
                'anomaly_type': 'Insufficient Data',
                'anomaly_description': 'Unable to analyze cash flow - insufficient transaction data'
            }
        
        transactions = bank_data['transactions']
        
        # Calculate cash flow metrics
        monthly_cash_flows = {}
        
        for transaction in transactions:
            date = transaction.get('date', '')
            amount = transaction.get('amount', 0)
            trans_type = transaction.get('type', 'credit')
            
            # Extract month (simplified)
            month = date[:7] if len(date) >= 7 else date
            
            if month not in monthly_cash_flows:
                monthly_cash_flows[month] = {'inflow': 0, 'outflow': 0}
            
            if trans_type == 'credit':
                monthly_cash_flows[month]['inflow'] += amount
            else:
                monthly_cash_flows[month]['outflow'] += amount
        
        # Analyze cash flow consistency
        if len(monthly_cash_flows) < 2:
            return {
                'is_anomaly': True,
                'anomaly_type': 'Insufficient History',
                'anomaly_description': 'Need at least 2 months of cash flow data'
            }
        
        # Calculate coefficient of variation for cash flows
        inflows = [cf['inflow'] for cf in monthly_cash_flows.values()]
        outflows = [cf['outflow'] for cf in monthly_cash_flows.values()]
        
        inflow_cv = np.std(inflows) / np.mean(inflows) if np.mean(inflows) > 0 else 0
        outflow_cv = np.std(outflows) / np.mean(outflows) if np.mean(outflows) > 0 else 0
        
        # Check for anomalies
        anomalies = []
        
        if inflow_cv > self.anomaly_thresholds['cash_flow_anomaly_threshold']:
            anomalies.append('Highly variable cash inflows')
        
        if outflow_cv > self.anomaly_thresholds['cash_flow_anomaly_threshold']:
            anomalies.append('Highly variable cash outflows')
        
        # Check for negative cash flow months
        negative_months = sum(1 for cf in monthly_cash_flows.values() 
                            if cf['inflow'] < cf['outflow'])
        
        if negative_months > len(monthly_cash_flows) * 0.5:
            anomalies.append('Consistent negative cash flow')
        
        return {
            'is_anomaly': len(anomalies) > 0,
            'anomaly_type': 'Cash Flow Anomaly' if anomalies else None,
            'anomaly_description': '; '.join(anomalies) if anomalies else None,
            'monthly_analysis': monthly_cash_flows,
            'inflow_volatility': inflow_cv,
            'outflow_volatility': outflow_cv,
            'negative_cash_flow_months': negative_months
        }
    
    def _calculate_consistency_score(self, revenue_analysis: Dict, circular_analysis: Dict, cash_flow_analysis: Dict) -> int:
        """Calculate overall consistency score (0-100)"""
        
        score = 100
        
        # Deduct points for revenue inconsistency
        if revenue_analysis['is_anomaly']:
            score -= 30
        
        # Deduct points for circular trading
        if circular_analysis['is_suspicious']:
            score -= circular_analysis['suspicious_score'] * 15
        
        # Deduct points for cash flow anomalies
        if cash_flow_analysis['is_anomaly']:
            score -= 20
        
        return max(0, score)
