# services.py
from __future__ import annotations
from typing import Dict, List, Set
import logging
from datetime import datetime
from models import Token, Transaction

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
        """
        Extract detailed transaction information including value transfers,
        token movements, and fees.
        """
        inputs = tx.get('inputs', [])
        outputs = tx.get('outputs', [])
        
        # Track which boxes belong to our address
        our_input_boxes = [box for box in inputs if box.get('address') == address]
        our_output_boxes = [box for box in outputs if box.get('address') == address]
        
        # Determine transaction type
        tx_type = TransactionAnalyzer.determine_transaction_type(tx, address)
        
        # Calculate actual value transfer (excluding change boxes)
        if tx_type == "Out":
            # For outgoing, sum all outputs to other addresses (excluding miner fee)
            value = -sum(
                out.get('value', 0) / 1e9 
                for out in outputs 
                if out.get('address') != address and out.get('address') != "Ergo Platform (Miner Fee)"
            )
        elif tx_type == "In":
            # For incoming, sum all outputs to our address
            value = sum(
                out.get('value', 0) / 1e9 
                for out in outputs 
                if out.get('address') == address
            )
        else:  # Mixed
            # For mixed, calculate net value change
            total_in = sum(box.get('value', 0) / 1e9 for box in our_input_boxes)
            total_out = sum(box.get('value', 0) / 1e9 for box in our_output_boxes)
            value = total_out - total_in

        # Calculate miner fee from the designated fee box
        miner_fee_boxes = [
            out for out in outputs 
            if out.get('address') == "Ergo Platform (Miner Fee)"
        ]
        fee = sum(box.get('value', 0) / 1e9 for box in miner_fee_boxes)
        
        # Find the main counterparty (excluding change addresses and miner fee)
        counterparty = None
        if tx_type == "Out":
            non_change_outputs = [
                out for out in outputs 
                if out.get('address') != address and 
                out.get('address') != "Ergo Platform (Miner Fee)"
            ]
            if non_change_outputs:
                counterparty = non_change_outputs[0].get('address')
        elif tx_type == "In":
            non_self_inputs = [inp for inp in inputs if inp.get('address') != address]
            if non_self_inputs:
                counterparty = non_self_inputs[0].get('address')
        
        # Extract token movements
        tokens = []
        if tx_type == "Out":
            # Track tokens sent to other addresses (excluding change boxes)
            for output in outputs:
                if output.get('address') != address and output.get('address') != "Ergo Platform (Miner Fee)":
                    for asset in output.get('assets', []):
                        tokens.append(Token(
                            token_id=asset.get('tokenId'),
                            amount=-asset.get('amount'),  # Negative for outgoing
                            name=asset.get('name')
                        ))
        elif tx_type == "In":
            # Track tokens received in our output boxes
            for output in our_output_boxes:
                for asset in output.get('assets', []):
                    tokens.append(Token(
                        token_id=asset.get('tokenId'),
                        amount=asset.get('amount'),
                        name=asset.get('name')
                    ))
        else:  # Mixed
            # Calculate net token changes
            input_tokens = {}
            output_tokens = {}
            
            # Track input tokens
            for box in our_input_boxes:
                for asset in box.get('assets', []):
                    token_id = asset.get('tokenId')
                    input_tokens[token_id] = input_tokens.get(token_id, 0) + asset.get('amount', 0)
            
            # Track output tokens
            for box in our_output_boxes:
                for asset in box.get('assets', []):
                    token_id = asset.get('tokenId')
                    output_tokens[token_id] = output_tokens.get(token_id, 0) + asset.get('amount', 0)
            
            # Calculate net token changes
            all_token_ids = set(list(input_tokens.keys()) + list(output_tokens.keys()))
            for token_id in all_token_ids:
                net_amount = output_tokens.get(token_id, 0) - input_tokens.get(token_id, 0)
                if net_amount != 0:
                    # Find token name from any box containing this token
                    token_name = None
                    for out in outputs:
                        for asset in out.get('assets', []):
                            if asset.get('tokenId') == token_id:
                                token_name = asset.get('name')
                                break
                        if token_name:
                            break
                    
                    tokens.append(Token(
                        token_id=token_id,
                        amount=net_amount,
                        name=token_name
                    ))
        
        # Format addresses for display
        from_address = inputs[0].get('address', '') if inputs else ''
        if from_address:
            from_address = f"{from_address[:10]}...{from_address[-4:]}"
        
        to_address = counterparty or ''
        if to_address:
            to_address = f"{to_address[:10]}...{to_address[-4:]}"

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