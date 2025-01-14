from typing import Dict, Optional, List, Any
from .base import BaseMetric
from models import WalletBalance, TokenBalance
import logging

class BalanceMetrics(BaseMetric):
    """Track and analyze wallet balances"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    def metric_name(self) -> str:
        return "balance_analysis"
    
    def calculate(self, transactions: List[Dict], current_balance: Dict) -> Dict[str, Any]:
        """Calculate balance metrics with proper null handling"""
        try:
            # Ensure current_balance has required fields
            if not isinstance(current_balance, dict):
                current_balance = {}
                
            # Initialize balance metrics
            metrics = {
                'current_balance': {
                    'erg_balance': current_balance.get('erg_balance', 0.0),
                    'tokens': current_balance.get('tokens', {})
                },
                'balance_history': []
            }
            
            # Process transactions if available
            if transactions:
                history = self._calculate_balance_history(transactions, current_balance)
                if history:
                    metrics['balance_history'] = history
                    
            return metrics
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error calculating balance metrics: {str(e)}")
            return {
                'current_balance': {'erg_balance': 0.0, 'tokens': {}},
                'balance_history': []
            }
    
    @staticmethod
    async def get_current_balance(explorer_client, address: str, node_client=None) -> Optional[WalletBalance]:
        """Get current balance for an address using node API"""
        if not node_client:
            raise ValueError("Node client is required for balance retrieval")
            
        try:
            node_balance = await node_client.get_balance(address)
            if not node_balance:
                raise ValueError("No balance data received from node")
                
            balance = WalletBalance()
            
            # Handle confirmed balance
            confirmed = node_balance.get('confirmed', {})
            balance.erg_balance = confirmed.get('nanoErgs', 0) / 1e9
            
            # Handle confirmed tokens
            for token in confirmed.get('tokens', []):
                token_id = token.get('tokenId')
                if token_id:
                    balance.tokens[token_id] = TokenBalance(
                        token_id=token_id,
                        amount=token.get('amount', 0),
                        name=token.get('name'),
                        decimals=token.get('decimals')
                    )
            
            # Add unconfirmed balance if any
            unconfirmed = node_balance.get('unconfirmed', {})
            if unconfirmed:
                balance.erg_balance += unconfirmed.get('nanoErgs', 0) / 1e9
                for token in unconfirmed.get('tokens', []):
                    token_id = token.get('tokenId')
                    if token_id:
                        if token_id in balance.tokens:
                            balance.tokens[token_id].amount += token.get('amount', 0)
                        else:
                            balance.tokens[token_id] = TokenBalance(
                                token_id=token_id,
                                amount=token.get('amount', 0),
                                name=token.get('name'),
                                decimals=token.get('decimals')
                            )
            
            logging.info(f"Node API balance data: {balance.erg_balance:.8f} ERG")
            return balance
            
        except Exception as e:
            logging.error(f"Error getting balance from node: {str(e)}")
            raise ValueError(f"Error getting balance from node: {str(e)}")
            
    def _calculate_balance_history(self, transactions: List[Dict], current_balance: Dict) -> Dict:
        """Calculate historical balance changes"""
        history = []
        running_balance = WalletBalance()
        
        # Start with current balance
        running_balance.erg_balance = current_balance.get('erg_balance', 0)
        running_balance.tokens = {
            token_id: TokenBalance(**token_data)
            for token_id, token_data in current_balance.get('tokens', {}).items()
        }
        
        # Calculate historical balances
        for tx in sorted(transactions, key=lambda x: x.get('timestamp', 0)):
            balance_snapshot = {
                'timestamp': tx.get('timestamp'),
                'erg_balance': running_balance.erg_balance,
                'tokens': {
                    token_id: token.to_dict()
                    for token_id, token in running_balance.tokens.items()
                }
            }
            history.append(balance_snapshot)
            
            # Update running balance based on transaction
            if tx.get('type') == 'in':
                running_balance.erg_balance -= tx.get('value', 0)
            else:
                running_balance.erg_balance += tx.get('value', 0)
                
            for token in tx.get('tokens', []):
                token_id = token.get('token_id')
                if token_id:
                    if token_id not in running_balance.tokens:
                        running_balance.tokens[token_id] = TokenBalance(
                            token_id=token_id,
                            amount=0,
                            name=token.get('name')
                        )
                    if tx.get('type') == 'in':
                        running_balance.tokens[token_id].amount -= token.get('amount', 0)
                    else:
                        running_balance.tokens[token_id].amount += token.get('amount', 0)
        
        return history