# notifications.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Protocol
import logging
from models import Transaction

class TransactionHandler(Protocol):
    async def handle_transaction(self, address: str, transaction: Transaction) -> None:
        pass

class LogHandler(TransactionHandler):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def handle_transaction(self, address: str, transaction: Transaction, monitor: ErgoTransactionMonitor) -> None:
        tx_direction = "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
        
        # Get wallet nickname from the address info if available
        wallet_name = next((info.nickname for info in monitor.watched_addresses.values() if info.address == address), address[:8])
        
        message = [
            f"=== {wallet_name} Transaction ===",
            f"Type: {tx_direction}",
            f"Block: {transaction.block}",
            # Show value with sign to indicate direction
            f"Amount: {transaction.value:+.8f} ERG",
            f"Fee: {transaction.fee:.8f} ERG"
        ]
        
        if transaction.from_address:
            message.append(f"From: {transaction.from_address}")
        if transaction.to_address:
            message.append(f"To: {transaction.to_address}")
            
        message.extend([
            f"Status: {transaction.status}",
            f"Tx ID: {transaction.tx_id}"
        ])
        
        if transaction.tokens:
            message.append("Tokens:")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = token.name or f"[{token.token_id[:12]}...]"
                message.append(f"  {token.amount:+} {token_name}")
        
        self.logger.info("\n".join(message) + "\n")