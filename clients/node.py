# clients/node.py
from typing import Dict, Optional, List
import aiohttp
import logging
import asyncio
import time
import json
from .base import BaseClient

class NodeClient(BaseClient):
    """Client for interacting with Ergo Node API"""
    
    def __init__(self, node_url: str, api_key: Optional[str] = None, max_retries: int = 3, retry_delay: float = 5.0):
        super().__init__()
        self.node_url = node_url.rstrip('/')
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
        self.logger = logging.getLogger(__name__)
        
    async def get_data(self, *args, **kwargs) -> Dict:
        """Implementation of abstract get_data method from BaseClient"""
        if 'address' in kwargs:
            return await self.get_balance(kwargs['address'])
        return {}

    async def get_balance(self, address: str) -> Dict:
        """Get balance for an address using node API"""
        try:
            self.logger.debug(f"Getting balance from node for address: {address}")
            response = await self._make_request(
                f"{self.node_url}/blockchain/balance",
                method="POST",
                data=json.dumps(address)
            )
            return response
        except Exception as e:
            self.logger.error(f"Error getting balance from node: {str(e)}")
            return {}
            
    async def _make_request(self, url: str, method: str = "GET", params: Dict = None, data: str = None) -> Dict:
        """Make a request with retry logic and rate limiting"""
        if not self.session:
            await self.init_session()

        headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            headers['api_key'] = self.api_key

        for attempt in range(self.max_retries):
            try:
                # Implement rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_request_time
                if time_since_last_request < self.min_request_interval:
                    await asyncio.sleep(self.min_request_interval - time_since_last_request)

                # Make the request
                request_kwargs = {
                    'params': params,
                    'headers': headers
                }
                if data:
                    request_kwargs['data'] = data

                if method.upper() == "POST":
                    async with self.session.post(url, **request_kwargs) as response:
                        return await self._handle_response(response, url, attempt)
                else:
                    async with self.session.get(url, **request_kwargs) as response:
                        return await self._handle_response(response, url, attempt)

            except aiohttp.ClientConnectorError as e:
                self.logger.error(f"Connection error: {str(e)}")
                await asyncio.sleep(self.retry_delay)
            except Exception as e:
                self.logger.error(f"Request failed: {str(e)}")
                await asyncio.sleep(self.retry_delay)

        return {}

    async def _handle_response(self, response, url: str, attempt: int) -> Dict:
        """Handle API response"""
        self.last_request_time = time.time()
        
        if response.status == 200:
            return await response.json()
        elif response.status == 429:  # Too Many Requests
            retry_after = float(response.headers.get('Retry-After', self.retry_delay))
            self.logger.warning(f"Rate limited, waiting {retry_after} seconds")
            await asyncio.sleep(retry_after)
            return None  # Signal retry needed
        elif response.status >= 500:  # Server error
            self.logger.warning(f"Server error {response.status}, attempt {attempt + 1}/{self.max_retries}")
            await asyncio.sleep(self.retry_delay)
            return None  # Signal retry needed
        else:
            error_text = await response.text()
            self.logger.error(f"Request failed with status {response.status}: {url}\nError: {error_text}")
            return {}