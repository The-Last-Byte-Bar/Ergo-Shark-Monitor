# notifications/handlers/log_handler.py
import logging
from typing import Optional
from core import NotificationHandler
from ..formatters import LogFormatter
from models import Transaction

class LogHandler(NotificationHandler):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.formatter = LogFormatter()

    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        wallet_name = next(
            (info.nickname for info in monitor.watched_addresses.values() if info.address == address),
            address[:8]
        )
        message = self.formatter.format_transaction(transaction, wallet_name)
        self.logger.info(message)

    async def init_session(self):
        pass  # No session needed for logging

    async def close_session(self):
        pass  # No cleanup needed