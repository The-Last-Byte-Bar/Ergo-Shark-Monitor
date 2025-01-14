# token_mapping.py
from typing import Dict, Optional
import json
import logging
from pathlib import Path
import aiohttp

class TokenMapper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._token_map: Dict = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Load initial mappings
        self.default_mappings = {
            # Token ID -> {coingecko_id, symbol, name}
            "1fd6e032e8476c4aa54c18c1a308dce83940e8f4a28f576440513ed7326ad489": {
                "coingecko_id": "spectrum-finance",
                "symbol": "SPECT",
                "name": "Spectrum"
            },
            "003bd19d0187117f130b62e1bcab0939929ff5c7709f843c5c4dd158949285d0": {
                "coingecko_id": "signum",
                "symbol": "SigRSV",
                "name": "SigmaRSV"
            },
            "03faf2cb329f2e90d6d23b58d91bbb6c046aa143261cc21f52fbe2824bfcbf04": {
                "coingecko_id": "sigusd",
                "symbol": "SigUSD",
                "name": "SigUSD"
            },
            "e91cbc48016eb390f8f872aa2962772863e2e840708517d1ab85e57451f91bed": {
                "coingecko_id": "rosen-bridge",
                "symbol": "RSN",
                "name": "Rosen"
            }
            # Add more default mappings here
        }

    async def init_session(self):
        """Initialize aiohttp session"""
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None

    async def load_token_mappings(self):
        """Load token mappings from various sources"""
        try:
            # Load default mappings
            self._token_map = self.default_mappings.copy()
            
            # Load from Spectrum API
            await self._load_spectrum_tokens()
            
            # Load from local file if exists
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
                                "symbol": token.get('symbol'),
                                "name": token.get('name'),
                                "coingecko_id": None  # We'll need to map this separately
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

    def get_coingecko_id(self, token_id: str) -> Optional[str]:
        """Get CoinGecko ID for a token"""
        token_info = self._token_map.get(token_id)
        return token_info.get('coingecko_id') if token_info else None

    def get_token_info(self, token_id: str) -> Optional[Dict]:
        """Get all token information"""
        return self._token_map.get(token_id)

    def get_all_mappings(self) -> Dict:
        """Get all token mappings"""
        return self._token_map.copy()

    def search_by_symbol(self, symbol: str) -> Optional[str]:
        """Search for token ID by symbol"""
        symbol = symbol.upper()
        for token_id, info in self._token_map.items():
            if info.get('symbol', '').upper() == symbol:
                return token_id
        return None