# services/monitor_service.py
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
from models import AddressInfo, Transaction, WalletBalance
from clients import ExplorerClient
from core import NotificationHandler
from analytics import AnalyticsService

class ErgoTransactionMonitor:
    """Main service for monitoring Ergo transactions"""
    
    def __init__(
        self,
        explorer_client: ExplorerClient,
        transaction_handlers: List[NotificationHandler],
        analytics_service: Optional[AnalyticsService] = None,
        daily_report_hour: int = 12,
        batch_size: int = 50  # Process transactions in batches
    ):
        self.explorer_client = explorer_client
        self.transaction_handlers = transaction_handlers
        self.analytics_service = analytics_service
        self.watched_addresses: Dict[str, AddressInfo] = {}
        self.processed_txs: Set[str] = set()
        self.last_daily_report = None
        self.daily_report_hour = daily_report_hour
        self.batch_size = batch_size
        self.logger = logging.getLogger(self.__class__.__name__)
        self._processing_lock = asyncio.Lock()
        
    def add_address(
        self, 
        address: str, 
        nickname: Optional[str] = None,
        hours_lookback: int = 24
    ):
        """Add an address to monitor"""
        if not address or len(address) < 40:
            raise ValueError(f"Invalid Ergo address: {address}")
            
        lookback_time = datetime.now() - timedelta(hours=hours_lookback)
        
        self.watched_addresses[address] = AddressInfo(
            address=address,
            nickname=nickname or address[:8],
            last_check=lookback_time,
            last_height=0,
            balance=WalletBalance()
        )
        
        self.logger.info(f"Added address {nickname or address[:8]} to monitoring")

    async def update_balances(self):
        """Update balances for all watched addresses"""
        for address in list(self.watched_addresses.keys()):
            try:
                boxes = await self.explorer_client.get_unspent_boxes(address)
                balance = WalletBalance()
                
                for box in boxes:
                    # Update ERG balance
                    balance.erg_balance += box.get('value', 0) / 1e9
                    
                    # Update token balances
                    for asset in box.get('assets', []):
                        token_id = asset.get('tokenId')
                        amount = asset.get('amount', 0)
                        if token_id:
                            if token_id not in balance.tokens:
                                balance.tokens[token_id] = {
                                    'amount': amount,
                                    'name': asset.get('name')
                                }
                            else:
                                balance.tokens[token_id]['amount'] += amount
                
                self.watched_addresses[address].balance = balance
                
            except Exception as e:
                self.logger.error(f"Error updating balance for {address}: {str(e)}")
                
    async def process_transactions(self, address: str) -> List[Transaction]:
        """Process new transactions for an address with improved efficiency"""
        address_info = self.watched_addresses[address]
        new_transactions = []

        try:
            # Use pagination to fetch transactions in smaller chunks
            offset = 0
            while True:
                transactions = await self.explorer_client.get_address_transactions(
                    address, 
                    offset=offset,
                )
                
                if not transactions:
                    break

                current_time = datetime.now()
                processed_count = 0
                
                for tx in transactions:
                    tx_id = tx.get('id')
                    if tx_id in self.processed_txs:
                        continue
                        
                    tx_time = datetime.fromtimestamp(tx.get('timestamp', 0) / 1000)
                    if tx_time <= address_info.last_check:
                        return new_transactions  # We've reached older transactions
                        
                    # Process transaction details
                    tx_details = self._process_transaction(tx, address)
                    if tx_details:
                        new_transactions.append(tx_details)
                        self.processed_txs.add(tx_id)
                        processed_count += 1

                if processed_count < self.batch_size:
                    break  # No more new transactions to process
                    
                offset += self.batch_size

            # Update last check time only if we found new transactions
            if new_transactions:
                self.watched_addresses[address].last_check = current_time

            # Keep processed set from growing too large using LRU-style cleanup
            if len(self.processed_txs) > 10000:  # Increased cache size
                self.processed_txs = set(list(self.processed_txs)[-5000:])
                
        except Exception as e:
            self.logger.error(f"Error processing transactions for {address}: {str(e)}")
            
        return new_transactions

    def _process_transaction(self, tx: Dict, address: str) -> Optional[Transaction]:
        """Process a single transaction"""
        try:
            # Extract basic transaction info
            tx_id = tx.get('id')
            height = tx.get('inclusionHeight')
            timestamp = datetime.fromtimestamp(tx.get('timestamp', 0) / 1000)
            
            # Calculate value changes
            value_in = sum(
                box.get('value', 0) / 1e9 
                for box in tx.get('outputs', [])
                if box.get('address') == address
            )
            
            value_out = sum(
                box.get('value', 0) / 1e9 
                for box in tx.get('inputs', [])
                if box.get('address') == address
            )
            
            # Determine transaction type and net value
            if value_in > 0 and value_out == 0:
                tx_type = "In"
                value = value_in
            elif value_out > 0 and value_in == 0:
                tx_type = "Out"
                value = -value_out
            else:
                tx_type = "Mixed"
                value = value_in - value_out
            
            # Create transaction object
            return Transaction(
                tx_id=tx_id,
                tx_type=tx_type,
                value=value,
                timestamp=timestamp,
                block=height,
                status="Confirmed" if height else "Pending"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing transaction {tx.get('id')}: {str(e)}")
            return None

    async def monitor_loop(self, check_interval: int = 15):
        """Improved monitoring loop with concurrent processing"""
        self.logger.info("Starting monitoring loop...")
        
        try:
            while True:
                current_time = datetime.now()
                
                # Check for daily report
                if (self.last_daily_report is None or 
                    current_time.date() > self.last_daily_report.date()):
                    if current_time.hour == self.daily_report_hour:
                        await self.send_daily_report()
                        self.last_daily_report = current_time
                
                # Process addresses concurrently
                async with self._processing_lock:  # Prevent concurrent updates
                    await self.update_balances()
                    
                    # Process addresses in parallel
                    tasks = []
                    for address in list(self.watched_addresses.keys()):
                        task = asyncio.create_task(self._process_address(address))
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks)
                
                await asyncio.sleep(check_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Monitor loop cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in monitor loop: {str(e)}")
            raise

    async def _process_address(self, address: str):
        """Process a single address concurrently"""
        try:
            transactions = await self.process_transactions(address)
            
            for tx in sorted(transactions, key=lambda x: x.timestamp):
                # Process handlers concurrently
                handler_tasks = []
                for handler in self.transaction_handlers:
                    task = asyncio.create_task(
                        handler.handle_transaction(address, tx, self)
                    )
                    handler_tasks.append(task)
                
                await asyncio.gather(*handler_tasks)
                
                # Run analytics if configured
                if self.analytics_service:
                    await self.analytics_service.process_transaction(address, tx)
                    
        except Exception as e:
            self.logger.error(f"Error processing address {address}: {str(e)}")

    async def send_daily_report(self):
        """Send daily balance report with proper null checking"""
        try:
            # Update balances first
            await self.update_balances()
            
            # Filter addresses where report_balance is True and has valid data
            report_addresses = {
                addr: info for addr, info in self.watched_addresses.items()
                if getattr(info, 'report_balance', True) and info.balance is not None
            }
    
            # Check if we have any addresses to report
            if not report_addresses:
                self.logger.warning("No addresses with valid balances found for daily report")
                return
    
            # Check that each address has required attributes
            for addr, info in report_addresses.items():
                if not hasattr(info.balance, 'erg_balance'):
                    info.balance.erg_balance = 0.0
                if not hasattr(info.balance, 'tokens'):
                    info.balance.tokens = {}
    
            # Send report through handlers
            for handler in self.transaction_handlers:
                try:
                    await handler.handle_transaction(
                        address="daily_report",
                        transaction=None,
                        monitor=self
                    )
                except Exception as e:
                    self.logger.error(f"Error sending daily report through handler: {str(e)}")
                    
            self.logger.info("Daily report sent successfully")
                
        except Exception as e:
            self.logger.error(f"Error sending daily report: {str(e)}", exc_info=True)