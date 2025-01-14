# services/token_service.py
from typing import Dict, Optional, List
import aiohttp
import json
import logging
from pathlib import Path

class TokenService:
    """Service for handling token-related operations"""
    
    # Known Ergo ecosystem tokens
    DEFAULT_TOKENS = {
        'ERG': 'ergo',
        'RSN': 'rosen-bridge',
        'SPECT': 'spectrum-finance',
        'NETA': 'neta',
        'SIGUSD': 'sigusd'
    }

    def __init__(self, debug: bool = False):
        self.logger = logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self.debug = debug
        self._token_map: Dict = {}
        self._coingecko_ids: Dict = {}

    async def init_session(self):
        """Initialize aiohttp session"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        await self._load_token_mappings()

    async def close_session(self):
        """Close aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None

    async def _load_token_mappings(self):
        """Load token mappings from various sources"""
        try:
            # Load default mappings
            self._token_map = self.DEFAULT_TOKENS.copy()
            
            # Load from Spectrum API
            await self._load_spectrum_tokens()
            
            # Load custom mappings
            await self._load_custom_mappings()
            
            self.logger.info(f"Loaded {len(self._token_map)} token mappings")
            
        except Exception as e:
            self.logger.error(f"Error loading token mappings: {str(e)}")

    async def _load_spectrum_tokens(self):
        """Load token information from Spectrum Finance API"""
        try:
            if not self._session:
                await self.init_session()

            # Get token list from Spectrum
            async with self._session.get("https://api.spectrum.fi/v1/tokens") as response:
                if response.status == 200:
                    tokens = await response.json()
                    for token in tokens:
                        token_id = token.get('id')
                        if token_id and token_id not in self._token_map:
                            self._token_map[token_id] = {
                                'symbol': token.get('symbol'),
                                'name': token.get('name'),
                                'decimals': token.get('decimals', 0)
                            }
            
        except Exception as e:
            self.logger.error(f"Error loading Spectrum tokens: {str(e)}")

    async def _load_custom_mappings(self):
        """Load custom token mappings from local file"""
        try:
            custom_mappings_file = Path("token_mappings.json")
            if custom_mappings_file.exists():
                with open(custom_mappings_file, 'r') as f:
                    custom_mappings = json.load(f)
                self._token_map.update(custom_mappings)
                
        except Exception as e:
            self.logger.error(f"Error loading custom mappings: {str(e)}")

    def save_custom_mapping(self, token_id: str, mapping_data: Dict):
        """Save a custom token mapping"""
        try:
            custom_mappings_file = Path("token_mappings.json")
            
            # Load existing mappings
            existing_mappings = {}
            if custom_mappings_file.exists():
                with open(custom_mappings_file, 'r') as f:
                    existing_mappings = json.load(f)
            
            # Update with new mapping
            existing_mappings[token_id] = mapping_data
            
            # Save back to file
            with open(custom_mappings_file, 'w') as f:
                json.dump(existing_mappings, f, indent=2)
            
            # Update in-memory mappings
            self._token_map[token_id] = mapping_data
            
        except Exception as e:
            self.logger.error(f"Error saving custom mapping: {str(e)}")

    def get_token_info(self, token_id: str) -> Optional[Dict]:
        """Get all information for a token"""
        return self._token_map.get(token_id)

    def get_token_name(self, token_id: str, default: str = None) -> str:
        """Get human-readable name for a token"""
        token_info = self._token_map.get(token_id, {})
        return token_info.get('name') or default or token_id[:8]

    def get_token_decimals(self, token_id: str) -> int:
        """Get number of decimals for a token"""
        token_info = self._token_map.get(token_id, {})
        return token_info.get('decimals', 0)

    def get_coingecko_id(self, token_id: str) -> Optional[str]:
        """Get CoinGecko ID for a token if available"""
        token_info = self._token_map.get(token_id, {})
        return token_info.get('coingecko_id')

    def format_token_amount(self, token_id: str, amount: int) -> float:
        """Format raw token amount according to its decimals"""
        decimals = self.get_token_decimals(token_id)
        return amount / (10 ** decimals)

    def get_all_tokens(self) -> Dict[str, Dict]:
        """Get all known tokens and their information"""
        return self._token_map.copy()