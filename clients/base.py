from abc import ABC, abstractmethod
from typing import Optional
import aiohttp
import logging

class BaseClient(ABC):
    """Base client for API interactions"""
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def init_session(self):
        """Initialize aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    @abstractmethod
    async def get_data(self, *args, **kwargs):
        """Generic data retrieval method"""
        pass