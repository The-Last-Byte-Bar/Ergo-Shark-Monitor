# clients.py
from __future__ import annotations
import aiohttp
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from models import Token, Transaction, AddressInfo
import time
import asyncio

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
    def __init__(self, explorer_url: str, max_retries: int = 3, retry_delay: float = 5.0):
        super().__init__()
        self.explorer_url = explorer_url.rstrip('/')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
    
    async def get_data(self, *args, **kwargs):
        if 'address' in kwargs:
            return await self.get_address_transactions(kwargs['address'])
        return []
        
    async def _make_request(self, url: str, params: Dict = None) -> Dict:
        """Make a request with retry logic and rate limiting"""
        if not self.session:
            await self.init_session()
            
        for attempt in range(self.max_retries):
            try:
                # Implement rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_request_time
                if time_since_last_request < self.min_request_interval:
                    await asyncio.sleep(self.min_request_interval - time_since_last_request)

                # Make the request
                async with self.session.get(url, params=params) as response:
                    self.last_request_time = time.time()
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            # Ensure we never return None
                            return data if data is not None else {}
                        except Exception as e:
                            self.logger.error(f"Failed to parse JSON response: {str(e)}")
                            return {}
                    elif response.status == 429:  # Too Many Requests
                        retry_after = float(response.headers.get('Retry-After', self.retry_delay))
                        self.logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status >= 500:  # Server error
                        self.logger.warning(f"Server error {response.status}, attempt {attempt + 1}/{self.max_retries}")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        self.logger.error(f"Request failed with status {response.status}: {url}")
                        return {}

            except aiohttp.ClientConnectorError as e:
                if "Temporary failure in name resolution" in str(e):
                    self.logger.warning(f"DNS resolution failed, attempt {attempt + 1}/{self.max_retries}")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    self.logger.error(f"Connection error: {str(e)}")
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                self.logger.error(f"Request failed: {str(e)}")
                await asyncio.sleep(self.retry_delay)
                if attempt == self.max_retries - 1:
                    return {}  # Return empty dict on final attempt

        return {}  # Return empty dict if all retries failed

    async def get_address_transactions(self, address: str, offset: int = 0) -> List[Dict]:
        try:
            transactions = []
            
            # Get mempool transactions
            mempool_url = f"{self.explorer_url}/mempool/transactions/byAddress/{address}"
            mempool_data = await self._make_request(mempool_url)
            
            # Handle both list and dict response formats safely
            mempool_items = []
            if isinstance(mempool_data, dict):
                mempool_items = mempool_data.get('items', [])
            elif isinstance(mempool_data, list):
                mempool_items = mempool_data
            
            # Process and add mempool transactions
            for tx in mempool_items:
                if isinstance(tx, dict):
                    formatted_tx = self._format_mempool_transaction(tx)
                    transactions.append(formatted_tx)
            
            # Get confirmed transactions
            transactions_url = f"{self.explorer_url}/addresses/{address}/transactions"
            params = {
                'offset': offset,
                'limit': 50,  # Reasonable limit per request
                'sortDirection': 'desc'
            }
            
            confirmed_data = await self._make_request(transactions_url, params)
            if isinstance(confirmed_data, dict):
                transactions.extend(confirmed_data.get('items', []))
            
            return transactions

        except Exception as e:
            self.logger.error(f"Error getting transactions: {str(e)}")
            return []

    def _format_mempool_transaction(self, tx: Dict) -> Dict:
        """Format mempool transaction to match confirmed transaction structure"""
        if not isinstance(tx, dict):
            return {}
            
        formatted_tx = {
            'id': tx.get('id'),
            'inputs': tx.get('inputs', []),
            'outputs': tx.get('outputs', []),
            'size': tx.get('size', 0),
            'mempool': True,
            'inclusionHeight': None,
            'height': None,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        
        # Ensure we have proper input/output structures
        for i, input_box in enumerate(formatted_tx['inputs']):
            if isinstance(input_box, str):
                formatted_tx['inputs'][i] = {'boxId': input_box}
                
        return formatted_tx