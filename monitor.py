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
        self.processed_mempool_txs: Set[str] = set()
        self.processed_confirmed_txs: Set[str] = set()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def check_transactions(self, address: str) -> List[Transaction]:
        address_info = self.watched_addresses[address]
        new_transactions = []

        try:
            transactions = await self.explorer_client.get_address_transactions(address)
            current_time = datetime.now()
            
            for tx in transactions:
                tx_id = tx.get('id')
                is_mempool = tx.get('mempool', False)
                
                # Determine if we should process this transaction
                should_process = False
                
                if is_mempool:
                    if tx_id not in self.processed_mempool_txs:
                        should_process = True
                        self.processed_mempool_txs.add(tx_id)
                else:
                    if (tx_id not in self.processed_confirmed_txs or 
                        tx_id in self.processed_mempool_txs):
                        should_process = True
                        self.processed_mempool_txs.discard(tx_id)
                        self.processed_confirmed_txs.add(tx_id)
                
                if should_process:
                    tx_time = datetime.fromtimestamp(tx.get('timestamp', 0) / 1000)
                    
                    if tx_time > address_info.last_check:
                        tx_details = TransactionAnalyzer.extract_transaction_details(tx, address)
                        
                        if abs(tx_details.value) > 0.0001 or tx_details.tokens:
                            new_transactions.append(tx_details)
                            
                            # Keep processed transaction sets from growing too large
                            if len(self.processed_confirmed_txs) > 1000:
                                self.processed_confirmed_txs = set(
                                    list(self.processed_confirmed_txs)[-1000:]
                                )
                            if len(self.processed_mempool_txs) > 100:
                                self.processed_mempool_txs = set(
                                    list(self.processed_mempool_txs)[-100:]
                                )
                    else:
                        break
            
            # Update the last check time if we successfully processed transactions
            if new_transactions or not transactions:
                self.watched_addresses[address] = AddressInfo(
                    address=address_info.address,
                    nickname=address_info.nickname,
                    last_check=current_time,
                    last_height=max(
                        [tx.get('height', 0) for tx in transactions[:1]] 
                        or [address_info.last_height]
                    )
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
                                # Handle the main transaction
                                for handler in self.transaction_handlers:
                                    await handler.handle_transaction(address, tx, self)
                                
                                # Check if we need to generate a mirrored notification for another watched address
                                if tx.from_address or tx.to_address:
                                    for other_addr, other_info in self.watched_addresses.items():
                                        if other_addr != address:
                                            # Format the address for comparison
                                            other_addr_short = f"{other_addr[:10]}...{other_addr[-4:]}"
                                            
                                            # Check if the other address is involved in this transaction
                                            if ((tx.from_address and other_addr_short in tx.from_address) or
                                                (tx.to_address and other_addr_short in tx.to_address)):
                                                
                                                # Get the original transaction data
                                                original_tx_data = None
                                                for t in transactions:
                                                    if t.tx_id == tx.tx_id:
                                                        original_tx_data = next(
                                                            t for t in await self.explorer_client.get_address_transactions(address)
                                                            if t.get('id') == tx.tx_id
                                                        )
                                                        break
                                                
                                                if original_tx_data:
                                                    # Generate mirrored transaction for the other address
                                                    mirrored_tx = TransactionAnalyzer.extract_transaction_details(
                                                        original_tx_data,
                                                        other_addr
                                                    )
                                                    
                                                    # Notify handlers about the mirrored transaction
                                                    for handler in self.transaction_handlers:
                                                        await handler.handle_transaction(
                                                            other_addr,
                                                            mirrored_tx,
                                                            self
                                                        )
                    
                    except Exception as e:
                        self.logger.error(f"Error processing address {address}: {str(e)}")
                
                await asyncio.sleep(check_interval)
        finally:
            await self.explorer_client.close_session()
            
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

