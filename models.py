# models.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict

@dataclass
class Token:
    token_id: str
    amount: int
    name: Optional[str] = None

@dataclass
class Transaction:
    tx_type: str
    value: float
    fee: float
    from_address: Optional[str]
    to_address: Optional[str]
    tokens: List[Token]
    tx_id: str
    block: Optional[int]
    timestamp: datetime
    status: str

@dataclass
class AddressInfo:
    address: str
    nickname: str
    last_check: datetime
    last_height: int

@dataclass
class TokenBalance:
    token_id: str
    amount: int
    name: Optional[str] = None

@dataclass
class WalletBalance:
    erg_balance: float = 0.0
    tokens: Dict[str, TokenBalance] = field(default_factory=dict)

@dataclass
class AddressInfo:
    address: str
    nickname: str
    last_check: datetime
    last_height: int
    balance: WalletBalance = field(default_factory=WalletBalance)
    report_balance: bool = True 
