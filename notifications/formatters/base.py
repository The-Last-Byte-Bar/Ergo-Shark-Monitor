# notifications/formatters/base.py
from abc import ABC, abstractmethod
from typing import Dict, List
from models import Transaction

class MessageFormatter(ABC):
    """Base class for message formatters"""
    @abstractmethod
    def format_transaction(self, transaction: Transaction, wallet_name: str) -> str:
        """Format a transaction into a message"""
        pass

    @abstractmethod
    def format_balance_report(self, balances: Dict) -> str:
        """Format a balance report into a message"""
        pass