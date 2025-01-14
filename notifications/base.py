from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from dataclasses import dataclass
from models import Transaction

class NotificationHandler(ABC):
    """Base class for all notification handlers"""
    @abstractmethod
    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        """Handle a transaction notification"""
        pass

    @abstractmethod
    async def init_session(self):
        """Initialize any required sessions"""
        pass

    @abstractmethod
    async def close_session(self):
        """Cleanup any sessions"""
        pass
