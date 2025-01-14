# analytics/metrics/flow_metrics.py
from datetime import datetime
from typing import Dict, Any, List, Union
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
            try:
                # Process inputs with safe conversion
                inputs_value = sum(
                    self._safe_convert_to_erg(box.get('value', 0))
                    for box in tx.get('inputs', [])
                    if box.get('address') == current_balance.get('address')
                )
                
                # Process outputs with safe conversion
                outputs_value = sum(
                    self._safe_convert_to_erg(box.get('value', 0))
                    for box in tx.get('outputs', [])
                    if box.get('address') == current_balance.get('address')
                )
                
                # Calculate net flow
                if outputs_value > inputs_value:
                    inflow = outputs_value - inputs_value
                    metrics['inflow'] += inflow
                    self._update_time_flows(tx, inflow, 0, metrics)
                elif inputs_value > outputs_value:
                    outflow = inputs_value - outputs_value
                    metrics['outflow'] += outflow
                    self._update_time_flows(tx, 0, outflow, metrics)
                
            except Exception as e:
                logging.error(f"Error processing transaction in flow metrics: {str(e)}")
                continue
            
        metrics['net_flow'] = metrics['inflow'] - metrics['outflow']
        return metrics

    def _safe_convert_to_erg(self, value: Any) -> float:
        """Safely convert any value to ERG amount"""
        try:
            # Handle string values
            if isinstance(value, str):
                value = float(value)
            # Handle integer or float values
            elif isinstance(value, (int, float)):
                value = float(value)
            else:
                return 0.0
            
            # Convert from nanoERG to ERG
            return value / 1e9
        except (ValueError, TypeError):
            return 0.0
            
    def _update_time_flows(self, tx: Dict, inflow: float, outflow: float, metrics: Dict):
        """Update daily and monthly flow metrics"""
        try:
            timestamp = tx.get('timestamp', 0)
            if isinstance(timestamp, str):
                timestamp = int(timestamp)
            
            tx_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
            tx_month = tx_date[:7]
            
            # Update daily flows
            if tx_date not in metrics['daily_flows']:
                metrics['daily_flows'][tx_date] = {'in': 0.0, 'out': 0.0}
            metrics['daily_flows'][tx_date]['in'] += inflow
            metrics['daily_flows'][tx_date]['out'] += outflow
            
            # Update monthly flows
            if tx_month not in metrics['monthly_flows']:
                metrics['monthly_flows'][tx_month] = {'in': 0.0, 'out': 0.0}
            metrics['monthly_flows'][tx_month]['in'] += inflow
            metrics['monthly_flows'][tx_month]['out'] += outflow
            
        except Exception as e:
            logging.error(f"Error updating time flows: {str(e)}")
            return