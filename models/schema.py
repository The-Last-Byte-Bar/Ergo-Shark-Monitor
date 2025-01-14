# models/schema.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Union

@dataclass
class Token:
    """Represents a token in a transaction"""
    token_id: str
    amount: int
    name: Optional[str] = None
    decimals: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            'token_id': self.token_id,
            'amount': self.amount,
            'name': self.name,
            'decimals': self.decimals
        }

    def get_formatted_amount(self) -> float:
        """Get amount formatted according to decimals"""
        if self.decimals is not None:
            return self.amount / (10 ** self.decimals)
        return float(self.amount)

@dataclass
class Transaction:
    """Represents an Ergo blockchain transaction"""
    tx_id: str
    tx_type: str  # "In", "Out", or "Mixed"
    value: float  # Amount in ERG (can be negative for outgoing)
    timestamp: datetime
    block: Optional[int] = None
    fee: float = 0.0
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    tokens: List[Token] = field(default_factory=list)
    status: str = "Confirmed"  # "Pending" or "Confirmed"

    def to_dict(self) -> Dict:
        return {
            'tx_id': self.tx_id,
            'type': self.tx_type,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'block': self.block,
            'fee': self.fee,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'tokens': [token.to_dict() for token in self.tokens],
            'status': self.status
        }

@dataclass
class TokenBalance:
    """Represents a token balance"""
    token_id: str
    amount: int
    name: Optional[str] = None
    usd_value: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'token_id': self.token_id,
            'amount': self.amount,
            'name': self.name,
            'usd_value': self.usd_value
        }

@dataclass
class WalletBalance:
    """Represents a wallet's complete balance"""
    erg_balance: float = 0.0
    tokens: Dict[str, TokenBalance] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'erg_balance': self.erg_balance,
            'tokens': {
                token_id: token.to_dict() 
                for token_id, token in self.tokens.items()
            },
            'last_updated': self.last_updated.isoformat()
        }

    def update_token_balance(self, token: Token):
        """Update the balance of a specific token"""
        if token.token_id in self.tokens:
            self.tokens[token.token_id].amount += token.amount
            if token.name and not self.tokens[token.token_id].name:
                self.tokens[token.token_id].name = token.name
        else:
            self.tokens[token.token_id] = TokenBalance(
                token_id=token.token_id,
                amount=token.amount,
                name=token.name
            )

@dataclass
class AddressInfo:
    """Information about a monitored address"""
    address: str
    nickname: str
    last_check: datetime
    last_height: int
    balance: WalletBalance = field(default_factory=WalletBalance)
    report_balance: bool = True

    def to_dict(self) -> Dict:
        return {
            'address': self.address,
            'nickname': self.nickname,
            'last_check': self.last_check.isoformat(),
            'last_height': self.last_height,
            'balance': self.balance.to_dict(),
            'report_balance': self.report_balance
        }

@dataclass
class AnalyticsQuery:
    """Represents an analytics query"""
    query_text: str
    address: str
    timestamp: datetime = field(default_factory=datetime.now)
    days_back: int = 30
    user_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'query_text': self.query_text,
            'address': self.address,
            'timestamp': self.timestamp.isoformat(),
            'days_back': self.days_back,
            'user_id': self.user_id
        }

@dataclass
class AnalyticsResult:
    """Results from an analytics query"""
    query: AnalyticsQuery
    result_text: str
    executed_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    metrics: Dict[str, Union[float, int, str]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'query': self.query.to_dict(),
            'result': self.result_text,
            'executed_at': self.executed_at.isoformat(),
            'error': self.error,
            'metrics': self.metrics
        }

# Utility function for working with models
def create_transaction_from_dict(data: Dict) -> Transaction:
    """Create a Transaction object from a dictionary"""
    return Transaction(
        tx_id=data['tx_id'],
        tx_type=data['type'],
        value=float(data['value']),
        timestamp=datetime.fromisoformat(data['timestamp']),
        block=data.get('block'),
        fee=float(data.get('fee', 0.0)),
        from_address=data.get('from_address'),
        to_address=data.get('to_address'),
        tokens=[
            Token(**token) if isinstance(token, dict) else token 
            for token in data.get('tokens', [])
        ],
        status=data.get('status', 'Confirmed')
    )

@dataclass
class TokenBalance:
    """Represents a token balance"""
    token_id: str
    amount: int
    name: Optional[str] = None
    decimals: Optional[int] = None  # Added decimals field
    usd_value: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'token_id': self.token_id,
            'amount': self.amount,
            'name': self.name,
            'decimals': self.decimals,  # Include decimals in dict representation
            'usd_value': self.usd_value
        }

    def get_formatted_amount(self) -> float:
        """Get amount formatted according to decimals"""
        if self.decimals is not None:
            return self.amount / (10 ** self.decimals)
        return float(self.amount)