# tests/config.py
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class TestConfig:
    # Test addresses with known balances and transactions
    test_addresses = {
        'mining_wallet': '',
        # Add more test addresses as needed
    }
    
    # Expected test results (for validation)
    expected_results = {
        'mining_wallet': {
            'min_balance': 47000,  # Minimum expected ERG balance
            'min_transactions': 50,  # Minimum expected number of transactions
            'known_tokens': [
                # List of known token IDs that should be present
            ]
        }
    }
    
    # Explorer API configuration
    explorer_config = {
        'url': 'https://api.ergoplatform.com/api/v1',
        'max_retries': 3,
        'retry_delay': 1.0
    }
    
    # Test timeframes
    timeframes = {
        'short': 7,    # 7 days
        'medium': 30,  # 30 days
        'long': 90     # 90 days
    }