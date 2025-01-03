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
        tx_direction = "Received" if transaction.tx_type == "In" else "Sent" if transaction.tx_type == "Out" else "Mixed"
        counterparty = transaction.to_address if transaction.tx_type == "Out" else transaction.from_address
        
        # Get wallet nickname from the address info if available
        wallet_name = next((info.nickname for info in monitor.watched_addresses.values() if info.address == address), address[:8])
        
        message = [
            f"=== {wallet_name} Transaction ===",
            f"Type: {tx_direction}",
            f"Block: {transaction.block}",
            f"Amount: {abs(transaction.value):.8f} ERG",
            f"Fee: {transaction.fee:.8f} ERG",
            f"{'To' if transaction.tx_type == 'Out' else 'From'}: {counterparty[:12] if counterparty else 'Unknown'}",
            f"Block: {transaction.block}",
            f"Status: {'Pending' if transaction.block is None or transaction.block == 0 else 'Confirmed'}",
            f"Tx ID: {transaction.tx_id}"
        ]
        
        if transaction.tokens:
            message.append("Tokens:")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = token.name or f"[{token.token_id[:12]}...]"
                prefix = "-" if (transaction.tx_type == "Out" and token.amount < 0) or \
                                (transaction.tx_type in ["In", "Mixed"] and token.amount < 0) else "+"
                message.append(f"  {prefix}{abs(token.amount)} {token_name}")
        
        self.logger.info("\n".join(message) + "\n")