# monitor.py
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
from models import AddressInfo, Transaction
from clients import ExplorerClient
from services import TransactionAnalyzer
from notifications import TransactionHandler

class ErgoTransactionMonitor:
    def __init__(
        self,
        explorer_client: ExplorerClient,
        transaction_handlers: List[TransactionHandler]
    ):
        self.explorer_client = explorer_client
        self.transaction_handlers = transaction_handlers
        self.watched_addresses: Dict[str, AddressInfo] = {}
        self.processed_txs: Set[str] = set()  # Track processed transaction IDs
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_address(self, address: str, nickname: Optional[str] = None, hours_lookback: int = 1):
        if not address or len(address) < 40:
            raise ValueError(f"Invalid Ergo address format: {address}")
        
        lookback_time = datetime.now() - timedelta(hours=hours_lookback)
        lookback_time = lookback_time.replace(minute=0, second=0, microsecond=0)
        
        self.watched_addresses[address] = AddressInfo(
            address=address,
            nickname=nickname or address[:8],
            last_check=lookback_time,
            last_height=0
        )
        
        self.logger.info(
            f"Added address {nickname or address[:8]} to monitoring list "
            f"with {hours_lookback}h lookback from {lookback_time}"
        )

    async def check_transactions(self, address: str) -> List[Transaction]:
        address_info = self.watched_addresses[address]
        new_transactions = []

        try:
            transactions = await self.explorer_client.get_address_transactions(address)
            current_time = datetime.now()
            
            for tx in transactions:
                tx_id = tx.get('id')
                
                # Skip if we've already processed this transaction
                if tx_id in self.processed_txs:
                    continue
                    
                tx_time = datetime.fromtimestamp(tx.get('timestamp', 0) / 1000)
                
                # Check if transaction is new enough to process
                if tx_time > address_info.last_check:
                    tx_details = TransactionAnalyzer.extract_transaction_details(tx, address)
                    
                    # Only include meaningful transactions (non-zero value or token transfers)
                    if abs(tx_details.value) > 0.0001 or tx_details.tokens:
                        new_transactions.append(tx_details)
                        self.processed_txs.add(tx_id)  # Mark as processed
                        
                        # Keep processed tx set from growing too large
                        if len(self.processed_txs) > 1000:
                            self.processed_txs = set(list(self.processed_txs)[-1000:])
                else:
                    break  # Stop processing older transactions
            
            # Only update the last check time if we successfully processed transactions
            if new_transactions or not transactions:
                self.watched_addresses[address] = AddressInfo(
                    address=address_info.address,
                    nickname=address_info.nickname,
                    last_check=current_time,
                    last_height=max([tx.get('height', 0) for tx in transactions[:1]] or [address_info.last_height])
                )
            
        except Exception as e:
            self.logger.error(f"Error checking transactions for {address}: {str(e)}")
        
        return new_transactions

    async def monitor_loop(self, check_interval: int = 60):
        self.logger.info("Starting monitoring loop...")
        
        try:
            while True:
                for address in list(self.watched_addresses.keys()):
                    try:
                        transactions = await self.check_transactions(address)
                        
                        if transactions:
                            for tx in sorted(transactions, key=lambda x: x.timestamp):
                                for handler in self.transaction_handlers:
                                    await handler.handle_transaction(address, tx, self)
                    
                    except Exception as e:
                        self.logger.error(f"Error processing address {address}: {str(e)}")
                
                await asyncio.sleep(check_interval)
        finally:
            await self.explorer_client.close_session()