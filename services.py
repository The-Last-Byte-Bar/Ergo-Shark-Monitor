# services.py
from __future__ import annotations
from typing import Dict, List, Set, Tuple
import logging
from datetime import datetime
from models import Token, Transaction, TokenBalance, WalletBalance
from clients import ExplorerClient

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
    def extract_transaction_details(tx: Dict, address: str) -> Transaction:
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
            # For outgoing, value should be negative (we're spending)
            value = -(input_value - output_value)
        elif tx_type == "In":
            # For incoming, value should be positive (we're receiving)
            value = output_value
        else:  # Mixed
            # For mixed, calculate net change (positive if receiving more than sending)
            value = output_value - input_value
        
        # Calculate miner fee
        fee = sum(
            out.get('value', 0) / 1e9 
            for out in outputs 
            if out.get('address') == "Ergo Platform (Miner Fee)"
        )
        
        # Find counterparties (could be multiple in mixed transactions)
        from_addresses = set()
        to_addresses = set()
        
        if tx_type in ["Out", "Mixed"]:
            # Add non-change output addresses
            for out in outputs:
                out_address = out.get('address')
                if (out_address and 
                    out_address != address and 
                    out_address != "Ergo Platform (Miner Fee)"):
                    to_addresses.add(out_address)
        
        if tx_type in ["In", "Mixed"]:
            # Add input addresses
            for inp in inputs:
                inp_address = inp.get('address')
                if inp_address and inp_address != address:
                    from_addresses.add(inp_address)
        
        # Format the addresses
        from_address = ', '.join(addr[:10] + '...' + addr[-4:] for addr in from_addresses) if from_addresses else ''
        to_address = ', '.join(addr[:10] + '...' + addr[-4:] for addr in to_addresses) if to_addresses else ''
        
        # Track token movements with proper signs
        token_changes = {}
        
        # Process input tokens (negative for our inputs)
        for box in our_input_boxes:
            for asset in box.get('assets', []):
                token_id = asset.get('tokenId')
                amount = asset.get('amount', 0)
                token_changes[token_id] = token_changes.get(token_id, 0) - amount
        
        # Process output tokens (positive for our outputs)
        for box in our_output_boxes:
            for asset in box.get('assets', []):
                token_id = asset.get('tokenId')
                amount = asset.get('amount', 0)
                token_changes[token_id] = token_changes.get(token_id, 0) + amount
        
        # Create Token objects for non-zero changes
        tokens = []
        for token_id, amount in token_changes.items():
            if amount != 0:
                # Find token name from any box containing this token
                token_name = None
                for box in outputs + inputs:
                    for asset in box.get('assets', []):
                        if asset.get('tokenId') == token_id:
                            token_name = asset.get('name')
                            break
                    if token_name:
                        break
                
                tokens.append(Token(
                    token_id=token_id,
                    amount=amount,
                    name=token_name
                ))
        
        # Determine transaction status
        is_mempool = tx.get('mempool', False)
        status = "Pending" if is_mempool else "Confirmed"
        
        return Transaction(
            tx_type=tx_type,
            value=value,  # Now properly signed
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
            # Get unspent boxes
            url = f"{explorer_client.explorer_url}/boxes/unspent/byAddress/{address}"
            unspent_boxes = await explorer_client._make_request(url)
            
            if not isinstance(unspent_boxes, list):
                unspent_boxes = unspent_boxes.get('items', []) if unspent_boxes else []
            
            total_erg = 0.0
            token_balances: Dict[str, TokenBalance] = {}
            
            # Calculate balances from each box
            for box in unspent_boxes:
                # Add ERG value
                total_erg += box.get('value', 0) / 1e9
                
                # Process tokens in the box
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
                            token_balances[token_id] = TokenBalance(
                                token_id=token_id,
                                amount=amount,
                                name=name
                            )
            
            return WalletBalance(
                erg_balance=total_erg,
                tokens=token_balances
            )
            
        except Exception as e:
            logging.error(f"Error getting balance for {address}: {str(e)}")
            return WalletBalance()