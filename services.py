# services.py
from __future__ import annotations
from typing import Dict, List, Set, Tuple, Optional, DefaultDict
from collections import defaultdict
import logging
from datetime import datetime
from models import Token, Transaction, TokenBalance, WalletBalance

class TokenInfoCache:
    """Cache for token information to avoid repeated API calls"""
    _cache: Dict[str, Dict] = {}
    _logger = logging.getLogger("TokenInfoCache")

    @classmethod
    async def get_token_info(cls, explorer_client: ExplorerClient, token_id: str) -> Dict:
        """Get token information with caching"""
        if token_id not in cls._cache:
            try:
                url = f"{explorer_client.explorer_url}/tokens/{token_id}"
                token_info = await explorer_client._make_request(url)
                if token_info:
                    cls._cache[token_id] = token_info
                else:
                    cls._cache[token_id] = {"decimals": 0}  # Default if not found
            except Exception as e:
                cls._logger.error(f"Error fetching token info for {token_id}: {str(e)}")
                cls._cache[token_id] = {"decimals": 0}  # Default on error
        
        return cls._cache[token_id]

    @classmethod
    async def get_token_decimals(cls, explorer_client: ExplorerClient, token_id: str) -> int:
        """Get token decimals with caching"""
        token_info = await cls.get_token_info(explorer_client, token_id)
        return token_info.get("decimals", 0)

class TransactionAnalyzer:
    @staticmethod
    def determine_transaction_type(tx: Dict, address: str) -> str:
        """
        Determine if this is an incoming, outgoing, or mixed transaction
        by analyzing inputs and outputs.
        """
        our_input_boxes = [box for box in tx.get('inputs', []) if box.get('address') == address]
        our_output_boxes = [box for box in tx.get('outputs', []) if box.get('address') == address]
        
        if our_input_boxes and our_output_boxes:
            return "Mixed"
        elif our_input_boxes:
            return "Out"
        elif our_output_boxes:
            return "In"
        return "Unknown"

    @staticmethod
    async def extract_transaction_details(tx: Dict, address: str, explorer_client: ExplorerClient) -> Transaction:
        """Extract detailed transaction information including value transfers and token movements."""
        inputs = tx.get('inputs', [])
        outputs = tx.get('outputs', [])
        
        # Track which boxes belong to our address
        our_input_boxes = [box for box in inputs if box.get('address') == address]
        our_output_boxes = [box for box in outputs if box.get('address') == address]
        
        # Determine transaction type
        tx_type = TransactionAnalyzer.determine_transaction_type(tx, address)
        
        # Calculate value changes with proper signs
        input_value = sum(box.get('value', 0) / 1e9 for box in our_input_boxes)
        output_value = sum(box.get('value', 0) / 1e9 for box in our_output_boxes)
        
        # Calculate net value change with proper sign
        if tx_type == "Out":
            value = -(input_value - output_value)
        elif tx_type == "In":
            value = output_value
        else:  # Mixed
            value = output_value - input_value
        
        # Calculate miner fee
        fee = sum(
            out.get('value', 0) / 1e9 
            for out in outputs 
            if out.get('address') == "Ergo Platform (Miner Fee)"
        )
        
        # Find counterparties
        from_addresses = set()
        to_addresses = set()
        
        if tx_type in ["Out", "Mixed"]:
            for out in outputs:
                out_address = out.get('address')
                if (out_address and 
                    out_address != address and 
                    out_address != "Ergo Platform (Miner Fee)"):
                    to_addresses.add(out_address)
        
        if tx_type in ["In", "Mixed"]:
            for inp in inputs:
                inp_address = inp.get('address')
                if inp_address and inp_address != address:
                    from_addresses.add(inp_address)
        
        # Format addresses
        from_address = ', '.join(addr[:10] + '...' + addr[-4:] for addr in from_addresses) if from_addresses else None
        to_address = ', '.join(addr[:10] + '...' + addr[-4:] for addr in to_addresses) if to_addresses else None
        
        # Track token movements with decimals
        token_changes: DefaultDict[str, Dict] = defaultdict(
            lambda: {"amount": 0, "name": None, "decimals": None}
        )
        
        # Process input tokens (negative for our inputs)
        for box in our_input_boxes:
            for asset in box.get('assets', []):
                token_id = asset.get('tokenId')
                amount = asset.get('amount', 0)
                token_changes[token_id]["amount"] -= amount
                if not token_changes[token_id]["name"]:
                    token_changes[token_id]["name"] = asset.get('name')
        
        # Process output tokens (positive for our outputs)
        for box in our_output_boxes:
            for asset in box.get('assets', []):
                token_id = asset.get('tokenId')
                amount = asset.get('amount', 0)
                token_changes[token_id]["amount"] += amount
                if not token_changes[token_id]["name"]:
                    token_changes[token_id]["name"] = asset.get('name')
        
        # Fetch decimals for all tokens and create Token objects
        tokens = []
        for token_id, info in token_changes.items():
            if info["amount"] != 0:
                decimals = await TokenInfoCache.get_token_decimals(explorer_client, token_id)
                tokens.append(Token(
                    token_id=token_id,
                    amount=info["amount"],
                    name=info["name"],
                    decimals=decimals
                ))
        
        # Determine transaction status
        is_mempool = tx.get('mempool', False)
        status = "Pending" if is_mempool else "Confirmed"
        
        return Transaction(
            tx_type=tx_type,
            value=value,
            fee=fee,
            from_address=from_address,
            to_address=to_address,
            tokens=tokens,
            tx_id=tx.get('id'),
            block=None if is_mempool else (tx.get('inclusionHeight') or tx.get('height')),
            timestamp=datetime.fromtimestamp(tx.get('timestamp', 0) / 1000),
            status=status
        )

class BalanceTracker:
    @staticmethod
    async def get_current_balance(explorer_client: ExplorerClient, address: str) -> WalletBalance:
        """Get current balance for an address from unspent boxes"""
        try:
            url = f"{explorer_client.explorer_url}/boxes/unspent/byAddress/{address}"
            unspent_boxes = await explorer_client._make_request(url)
            
            if not isinstance(unspent_boxes, list):
                unspent_boxes = unspent_boxes.get('items', []) if unspent_boxes else []
            
            total_erg = 0.0
            token_balances: Dict[str, TokenBalance] = {}
            
            # Calculate balances from each box
            for box in unspent_boxes:
                total_erg += box.get('value', 0) / 1e9
                
                # Process tokens with decimals
                for asset in box.get('assets', []):
                    token_id = asset.get('tokenId')
                    if token_id:
                        amount = asset.get('amount', 0)
                        name = asset.get('name')
                        
                        if token_id in token_balances:
                            token_balances[token_id].amount += amount
                            if name and not token_balances[token_id].name:
                                token_balances[token_id].name = name
                        else:
                            # Fetch token decimals when first encountering a token
                            decimals = await TokenInfoCache.get_token_decimals(explorer_client, token_id)
                            token_balances[token_id] = TokenBalance(
                                token_id=token_id,
                                amount=amount,
                                name=name,
                                decimals=decimals
                            )
            
            return WalletBalance(
                erg_balance=total_erg,
                tokens=token_balances
            )
            
        except Exception as e:
            logging.error(f"Error getting balance for {address}: {str(e)}")
            return WalletBalance()