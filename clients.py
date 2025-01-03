# clients.py
from __future__ import annotations
import aiohttp
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from models import Token, Transaction, AddressInfo

class BaseClient(ABC):
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    @abstractmethod
    async def get_data(self, *args, **kwargs):
        pass

class ExplorerClient(BaseClient):
    def __init__(self, explorer_url: str):
        super().__init__()
        self.explorer_url = explorer_url.rstrip('/')

    async def get_data(self, *args, **kwargs):
        """Implementation of abstract method from BaseClient"""
        if 'address' in kwargs:
            return await self.get_address_transactions(kwargs['address'])
        return []

    async def get_address_transactions(self, address: str, offset: int = 0) -> List[Dict]:
        await self.init_session()
        try:
            transactions = []
            
            # Get confirmed transactions
            transactions_url = f"{self.explorer_url}/addresses/{address}/transactions"
            params = {
                'offset': offset,
                'limit': 50,
                'sortDirection': 'desc'
            }
            
            async with self.session.get(transactions_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict) and 'items' in data:
                        transactions.extend(data['items'])
            
            # Get mempool transactions
            mempool_url = f"{self.explorer_url}/mempool/transactions/byAddress/{address}"
            async with self.session.get(mempool_url) as response:
                if response.status == 200:
                    mempool_data = await response.json()
                    
                    if isinstance(mempool_data, dict) and 'items' in mempool_data:
                        if mempool_data.get('total', 0) > 0:
                            for tx in mempool_data['items']:
                                if isinstance(tx, dict):
                                    # Format mempool transaction to match confirmed transaction structure
                                    tx['mempool'] = True
                                    tx['inclusionHeight'] = None
                                    tx['height'] = None
                                    tx['timestamp'] = int(datetime.now().timestamp() * 1000)
                                    transactions.append(tx)
                    elif isinstance(mempool_data, list):
                        for tx in mempool_data:
                            if isinstance(tx, dict):
                                tx['mempool'] = True
                                tx['inclusionHeight'] = None
                                tx['height'] = None
                                tx['timestamp'] = int(datetime.now().timestamp() * 1000)
                                transactions.append(tx)
            
            return transactions
        except Exception as e:
            self.logger.error(f"Error getting transactions: {str(e)}")
            return []

    def _format_mempool_transaction(self, tx: Dict) -> Dict:
        """Helper method to format mempool transaction to match confirmed transaction structure"""
        return {
            'id': tx.get('id'),
            'inputs': tx.get('inputs', []),
            'outputs': tx.get('outputs', []),
            'mempool': True,
            'inclusionHeight': None,
            'height': None,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }