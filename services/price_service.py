# price_service.py
from pycoingecko import CoinGeckoAPI
import pandas as pd
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta

class PriceService:
    # Known Ergo ecosystem tokens and their CoinGecko IDs
    ERGO_TOKENS = {
        'ERG': 'ergo',
        'RSN': 'rosen-bridge',
        'SPECT': 'spectrum-finance',
        'NETA': 'neta',
        'SIGUSD': 'sigusd',
        'ERDOGE': 'ergodex',
        'COMET': 'comet',
    }

    def __init__(self, debug: bool = False):
        self.logger = logging.getLogger(__name__)
        self.cg = CoinGeckoAPI()
        self.debug = debug
        self._cache = {}
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)

    def init_session(self):
        """Compatibility method for async services"""
        pass

    def close_session(self):
        """Compatibility method for async services"""
        pass

    def _should_update_cache(self) -> bool:
        """Check if cache needs updating"""
        if not self._cache_time:
            return True
        return datetime.now() - self._cache_time > self._cache_duration

    def get_prices(self, tokens: List[str] = None) -> Dict[str, float]:
        """Get current prices for specified tokens or all known tokens"""
        try:
            if self.debug:
                return {token: 10.0 for token in (tokens or self.ERGO_TOKENS.keys())}

            if self._should_update_cache():
                # Get all token prices at once
                coingecko_ids = [
                    self.ERGO_TOKENS[token] 
                    for token in (tokens or self.ERGO_TOKENS.keys())
                    if token in self.ERGO_TOKENS
                ]
                
                prices = self.cg.get_price(
                    ids=coingecko_ids,
                    vs_currencies='usd'
                )
                
                # Update cache
                self._cache = {
                    symbol: prices[cg_id]['usd']
                    for symbol, cg_id in self.ERGO_TOKENS.items()
                    if cg_id in prices
                }
                self._cache_time = datetime.now()
                
                # Save to CSV for analysis
                df = pd.DataFrame([self._cache])
                df.to_csv('price_data.csv', index=False)
                
                self.logger.info(f"Updated prices for {len(self._cache)} tokens")

            return self._cache

        except Exception as e:
            self.logger.error(f"Error fetching prices: {str(e)}")
            return {}

    def get_erg_price(self) -> Optional[float]:
        """Get current ERG price"""
        try:
            prices = self.get_prices(['ERG'])
            return prices.get('ERG')
        except Exception as e:
            self.logger.error(f"Error fetching ERG price: {str(e)}")
            return None

    def get_token_price(self, token: str) -> Optional[float]:
        """Get price for a specific token"""
        try:
            if token in self.ERGO_TOKENS:
                prices = self.get_prices([token])
                return prices.get(token)
            self.logger.warning(f"Unknown token: {token}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching price for {token}: {str(e)}")
            return None

    def calculate_token_values(self, tokens: List[Dict]) -> Dict[str, Dict[str, float]]:
        """Calculate USD values for a list of tokens"""
        token_values = {}
        prices = self.get_prices()
        
        for token in tokens:
            token_id = token.get('id')
            if token_id in prices:
                token_values[token_id] = {
                    'usd_price': prices[token_id],
                    'usd_value': prices[token_id] * token.get('amount', 0)
                }
        
        return token_values

    def calculate_portfolio_value(self, erg_amount: float, tokens: List[Dict]) -> Dict:
        """Calculate total portfolio value in USD"""
        erg_price = self.get_erg_price() or 0
        token_values = self.calculate_token_values(tokens)
        
        erg_value = erg_price * erg_amount
        token_total = sum(v['usd_value'] for v in token_values.values())
        
        return {
            'erg_value': erg_value,
            'token_value': token_total,
            'total_value': erg_value + token_total,
            'token_breakdown': token_values,
            'last_updated': datetime.now().isoformat()
        }

    def add_token(self, symbol: str, coingecko_id: str):
        """Add a new token mapping"""
        self.ERGO_TOKENS[symbol.upper()] = coingecko_id
        self._cache = {}  # Reset cache
        self.logger.info(f"Added new token mapping: {symbol} -> {coingecko_id}")