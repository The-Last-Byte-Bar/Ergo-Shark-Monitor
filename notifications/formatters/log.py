# notifications/formatters/log.py
from datetime import datetime
from typing import Dict, List
from .base import MessageFormatter
from models import Transaction

class LogFormatter(MessageFormatter):
    """Format messages for logging"""
    
    def format_transaction(self, transaction: Transaction, wallet_name: str) -> str:
        message = [
            f"=== {wallet_name} Transaction ===",
            f"Type: {self._get_direction(transaction)}",
            f"Amount: {transaction.value:+.8f} ERG"
        ]
        
        if transaction.fee > 0:
            message.append(f"Fee: {transaction.fee:.8f} ERG")
            
        if transaction.tokens:
            message.append("Tokens:")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = token.name or f"[{token.token_id[:12]}...]"
                message.append(f"  {token.amount:+} {token_name}")
                
        return "\n".join(message)

    def format_balance_report(self, balances: Dict) -> str:
        message = ["=== Balance Report ==="]
        
        for address, info in sorted(balances.items(), key=lambda x: x[1].nickname):
            message.extend([
                f"Wallet: {info.nickname}",
                f"ERG Balance: {info.balance.erg_balance:.8f}"
            ])
            
            if info.balance.tokens:
                message.append("Tokens:")
                for token in sorted(info.balance.tokens.values(), key=lambda x: x.amount, reverse=True):
                    token_name = token.name or f"[{token.token_id[:12]}...]"
                    message.append(f"  {token.amount} {token_name}")
            message.append("")
            
        return "\n".join(message)

    def _get_direction(self, transaction: Transaction) -> str:
        return "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
