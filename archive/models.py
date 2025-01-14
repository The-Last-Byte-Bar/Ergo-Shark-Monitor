# models.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Union

@dataclass
class Token:
    token_id: str
    amount: int
    name: Optional[str] = None

@dataclass
class Transaction:
    tx_type: str  # "In", "Out", or "Mixed"
    value: float  # Amount in ERG
    fee: float
    from_address: Optional[str]
    to_address: Optional[str]
    tokens: List[Token]
    tx_id: str
    block: Optional[int]
    timestamp: datetime
    status: str  # "Pending" or "Confirmed"

@dataclass
class TokenBalance:
    token_id: str
    amount: int
    name: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'token_id': self.token_id,
            'amount': self.amount,
            'name': self.name
        }

@dataclass
class WalletBalance:
    erg_balance: float = 0.0
    tokens: Dict[str, TokenBalance] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'erg_balance': self.erg_balance,
            'tokens': {
                token_id: token.to_dict() 
                for token_id, token in self.tokens.items()
            }
        }

@dataclass
class AddressInfo:
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
    query_text: str
    address: str
    timestamp: datetime = field(default_factory=datetime.now)
    days_back: int = 30
    user_id: Optional[str] = None

@dataclass
class AnalyticsResult:
    query: AnalyticsQuery
    result_text: str
    executed_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    metrics: Dict[str, Union[float, int, str]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'query': {
                'text': self.query.query_text,
                'address': self.query.address,
                'timestamp': self.query.timestamp.isoformat(),
                'days_back': self.query.days_back,
                'user_id': self.query.user_id
            },
            'result': self.result_text,
            'executed_at': self.executed_at.isoformat(),
            'error': self.error,
            'metrics': self.metrics
        }