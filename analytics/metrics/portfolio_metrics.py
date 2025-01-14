# analytics/metrics/portfolio_metrics.py
from typing import Dict, Any, List
from .base import BaseMetric
from models import Transaction

class PortfolioMetrics(BaseMetric):
    """Calculate portfolio-related metrics"""
    
    @property
    def metric_name(self) -> str:
        return "portfolio_analysis"
    
    def calculate(self, transactions: List[Dict], current_balance: Dict) -> Dict[str, Any]:
        metrics = {
            'portfolio_value': {
                'total_value': 0.0,
                'erg_value': 0.0,
                'token_value': 0.0,
                'token_breakdown': {}
            },
            'historic_values': {},
            'performance': {
                'daily_change': 0.0,
                'weekly_change': 0.0,
                'monthly_change': 0.0
            }
        }
        
        # Calculate current portfolio value
        if current_balance:
            metrics['portfolio_value']['erg_value'] = current_balance.get('erg_balance', 0) 
            
            for token_id, token_data in current_balance.get('tokens', {}).items():
                token_value = token_data.get('usd_value', 0)
                metrics['portfolio_value']['token_value'] += token_value
                metrics['portfolio_value']['token_breakdown'][token_id] = {
                    'value': token_value,
                    'amount': token_data.get('amount', 0),
                    'name': token_data.get('name')
                }
            
            metrics['portfolio_value']['total_value'] = (
                metrics['portfolio_value']['erg_value'] + 
                metrics['portfolio_value']['token_value']
            )
        
        return metrics