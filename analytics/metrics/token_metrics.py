# analytics/metrics/token_metrics.py
from typing import Dict, Any, List
from .base import BaseMetric
from models import Transaction

class TokenMetrics(BaseMetric):
    """Calculate token-related metrics"""
    
    @property
    def metric_name(self) -> str:
        return "token_analysis"
    
    def calculate(self, transactions: List[Dict], current_balance: Dict) -> Dict[str, Any]:
        metrics = {
            'movements': {},
            'total_tokens': 0,
            'unique_tokens': set()
        }
        
        for tx in transactions:
            self._process_token_transaction(tx, metrics)
            
        metrics['unique_tokens'] = len(metrics['unique_tokens'])
        return metrics
    
    def _process_token_transaction(self, tx: Dict, metrics: Dict):
        for token in tx.get('tokens', []):
            if not isinstance(token, dict):
                continue
            
            token_id = token.get('id')
            if not token_id:
                continue
                
            metrics['unique_tokens'].add(token_id)
            if token_id not in metrics['movements']:
                metrics['movements'][token_id] = {
                    'name': token.get('name'),
                    'total_in': 0,
                    'total_out': 0
                }
            
            amount = token.get('amount', 0)
            metrics['movements'][token_id][
                'total_in' if tx.get('type') == 'in' else 'total_out'
            ] += amount