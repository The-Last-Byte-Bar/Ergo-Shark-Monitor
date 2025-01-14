# notifications/handlers/base.py
from abc import ABC, abstractmethod
from typing import Optional
from models import Transaction

class NotificationHandler(ABC):
    """Base class for notification handlers"""
    
    @abstractmethod
    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        """Handle a new transaction notification"""
        pass
        
    @abstractmethod
    async def init_session(self):
        """Initialize any required sessions/connections"""
        pass
        
    @abstractmethod
    async def close_session(self):
        """Close any open sessions/connections"""
        pass