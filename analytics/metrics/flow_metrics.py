# analytics/metrics/flow_metrics.py
from datetime import datetime
from typing import Dict, Any, List
from .base import BaseMetric
from models import Transaction

class FlowMetrics(BaseMetric):
    """Calculate transaction flow metrics"""
    
    @property
    def metric_name(self) -> str:
        return "flow_analysis"
    
    def calculate(self, transactions: List[Dict], current_balance: Dict) -> Dict[str, Any]:
        metrics = {
            'inflow': 0.0,
            'outflow': 0.0,
            'net_flow': 0.0,
            'daily_flows': {},
            'monthly_flows': {}
        }
        
        for tx in transactions:
            # Get transaction value in nanoERG
            value = tx.get('value', 0)
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    value = 0
            
            # Convert from nanoERG to ERG
            value = value / 1e9
            
            # Process inputs
            inputs_value = sum(
                float(box.get('value', 0)) / 1e9
                for box in tx.get('inputs', [])
                if box.get('address') == current_balance.get('address')
            )
            
            # Process outputs
            outputs_value = sum(
                float(box.get('value', 0)) / 1e9
                for box in tx.get('outputs', [])
                if box.get('address') == current_balance.get('address')
            )
            
            # Calculate net flow
            if outputs_value > inputs_value:
                metrics['inflow'] += (outputs_value - inputs_value)
            elif inputs_value > outputs_value:
                metrics['outflow'] += (inputs_value - outputs_value)
            
            # Update daily flows
            tx_date = datetime.fromtimestamp(tx.get('timestamp', 0) / 1000).strftime('%Y-%m-%d')
            if tx_date not in metrics['daily_flows']:
                metrics['daily_flows'][tx_date] = {'in': 0.0, 'out': 0.0}
            
            if outputs_value > inputs_value:
                metrics['daily_flows'][tx_date]['in'] += (outputs_value - inputs_value)
            elif inputs_value > outputs_value:
                metrics['daily_flows'][tx_date]['out'] += (inputs_value - outputs_value)
            
            # Update monthly flows
            tx_month = tx_date[:7]
            if tx_month not in metrics['monthly_flows']:
                metrics['monthly_flows'][tx_month] = {'in': 0.0, 'out': 0.0}
            
            if outputs_value > inputs_value:
                metrics['monthly_flows'][tx_month]['in'] += (outputs_value - inputs_value)
            elif inputs_value > outputs_value:
                metrics['monthly_flows'][tx_month]['out'] += (inputs_value - outputs_value)
            
        metrics['net_flow'] = metrics['inflow'] - metrics['outflow']
        return metrics
        
    def _format_value(self, value: float) -> float:
        """Format ERG value with proper decimal precision"""
        return round(value, 8)