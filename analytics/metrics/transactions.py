from typing import Dict, Optional, List, Any
from datetime import datetime
from .base import BaseMetric
from models import Transaction, Token
import logging

class TransactionAnalyzer(BaseMetric):
    """Analyze and extract transaction details"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @property
    def metric_name(self) -> str:
        return "transaction_analysis"
    
    def calculate(self, transactions: List[Dict], current_balance: Dict) -> Dict[str, Any]:
        """Calculate transaction metrics"""
        address = current_balance.get('address', '')
        self.logger.info(f"Analyzing {len(transactions)} transactions for {address}")
        
        analyzed_txs = []
        for tx in transactions:
            try:
                analyzed_tx = self.extract_transaction_details(tx, address)
                if analyzed_tx:
                    analyzed_txs.append(analyzed_tx)
            except Exception as e:
                self.logger.error(f"Error analyzing transaction: {str(e)}", exc_info=True)
                
        self.logger.info(f"Successfully analyzed {len(analyzed_txs)} transactions")
        return {
            'analyzed_transactions': analyzed_txs,
            'address': address
        }

    @staticmethod
    def extract_transaction_details(tx_data: Dict, address: str) -> Optional[Transaction]:
        """Extract relevant transaction details with proper value conversion"""
        try:
            tx_id = tx_data.get('id')
            height = tx_data.get('inclusionHeight')
            timestamp = datetime.fromtimestamp(tx_data.get('timestamp', 0) / 1000)
            
            # Calculate value changes with proper nanoERG conversion
            value_in = sum(
                float(box.get('value', 0)) / 1e9 
                for box in tx_data.get('outputs', [])
                if box.get('address') == address
            )
            
            value_out = sum(
                float(box.get('value', 0)) / 1e9 
                for box in tx_data.get('inputs', [])
                if box.get('address') == address
            )
            
            # Determine transaction type and net value
            if value_in > 0 and value_out == 0:
                tx_type = "In"
                value = value_in
            elif value_out > 0 and value_in == 0:
                tx_type = "Out"
                value = -value_out
            else:
                tx_type = "Mixed"
                value = value_in - value_out
            
            return Transaction(
                tx_id=tx_id,
                tx_type=tx_type,
                value=value,
                timestamp=timestamp,
                block=height,
                status="Confirmed" if height else "Pending"
            )
            
        except Exception as e:
            raise ValueError(f"Error extracting transaction details: {str(e)}")
            
    def _extract_token_transfers(self, tx_data: Dict, address: str) -> List[Dict]:
        """Extract token transfers from transaction"""
        tokens = []
        processed_token_ids = set()
        
        try:
            # Process output tokens (incoming)
            for box in tx_data.get('outputs', []):
                if box.get('address') == address:
                    for asset in box.get('assets', []):
                        token_id = asset.get('tokenId')
                        if token_id and token_id not in processed_token_ids:
                            tokens.append({
                                'token_id': token_id,
                                'amount': asset.get('amount', 0),
                                'name': asset.get('name')
                            })
                            processed_token_ids.add(token_id)
            
            # Process input tokens (outgoing)
            for box in tx_data.get('inputs', []):
                if box.get('address') == address:
                    for asset in box.get('assets', []):
                        token_id = asset.get('tokenId')
                        if token_id and token_id not in processed_token_ids:
                            tokens.append({
                                'token_id': token_id,
                                'amount': -asset.get('amount', 0),
                                'name': asset.get('name')
                            })
                            processed_token_ids.add(token_id)
                            
            return tokens
            
        except Exception as e:
            self.logger.error(f"Error extracting token transfers: {str(e)}", exc_info=True)
            return []