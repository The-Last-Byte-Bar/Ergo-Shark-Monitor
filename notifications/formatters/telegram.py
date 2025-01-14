# notifications/formatters/telegram.py
from datetime import datetime
from typing import Dict, List
from .base import MessageFormatter
from models import Transaction


class TelegramFormatter(MessageFormatter):
    """Format messages for Telegram with markdown"""
    
    def format_transaction(self, transaction: Transaction, wallet_name: str) -> str:
        """Format a transaction into a message"""
        message = [
            f"🔄 *{self._escape_markdown(wallet_name)} Transaction*",
            f"Type: {self._get_direction(transaction)}",
            f"Status: {self._get_status_emoji(transaction)} {transaction.status}",
            f"Amount: `{transaction.value:+.8f}` ERG"
        ]
        
        if transaction.block:
            message.append(f"Block: `{transaction.block}`")
        
        if transaction.fee > 0:
            message.append(f"Fee: `{transaction.fee:.8f}` ERG")
            
        if transaction.tokens:
            message.append("\n*Tokens:*")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = self._escape_markdown(token.name or f"[{token.token_id[:12]}...]")
                prefix = "+" if token.amount > 0 else ""
                message.append(f"`{prefix}{token.amount}` {token_name}")
                
        message.append(f"\n[View Transaction](https://explorer.ergoplatform.com/en/transactions/{transaction.tx_id})")
        
        return "\n".join(message)

    def format_balance_report(self, balances: Dict) -> str:
        """Format a balance report into a message"""
        message = [
            "📊 *Daily Balance Report*",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        ]
        
        for address, info in sorted(balances.items(), key=lambda x: x[1].nickname):
            message.extend([
                f"*{self._escape_markdown(info.nickname)}*",
                f"ERG: `{info.balance.erg_balance:.8f}`"
            ])
            
            if info.balance.tokens:
                for token in sorted(info.balance.tokens.values(), key=lambda x: x.amount, reverse=True):
                    token_name = self._escape_markdown(token.name or f"[{token.token_id[:12]}...]")
                    message.append(f"`{token.amount:>12}` {token_name}")
            message.append("")
            
        return "\n".join(message)
        
    def _get_direction(self, transaction: Transaction) -> str:
        """Get transaction direction text"""
        return "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
        
    def _get_status_emoji(self, transaction: Transaction) -> str:
        """Get status emoji for transaction"""
        return "⏳" if transaction.status == "Pending" else "✅"

    def _escape_markdown(self, text: str) -> str:
        """Escape Telegram markdown special characters"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = str(text).replace(char, '\\' + char)
        return text