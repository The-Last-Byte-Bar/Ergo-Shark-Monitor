from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Optional, List, Dict
import logging
from models import Transaction
import aiohttp

class TransactionHandler(Protocol):
    async def handle_transaction(self, address: str, transaction: Transaction) -> None:
        pass

class LogHandler(TransactionHandler):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def handle_transaction(self, address: str, transaction: Transaction, monitor: ErgoTransactionMonitor) -> None:
        """Handle transaction notification with decimal-aware token amounts"""
        tx_direction = "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
        wallet_name = next((info.nickname for info in monitor.watched_addresses.values() if info.address == address), address[:8])
        
        message = [
            f"=== {wallet_name} Transaction ===",
            f"Type: {tx_direction}",
            f"Block: {transaction.block}",
            f"Status: {transaction.status}",
            f"Amount: {transaction.value:+.8f} ERG",
        ]
        
        if transaction.fee > 0:
            message.append(f"Fee: {transaction.fee:.8f} ERG")
        
        if transaction.from_address:
            message.append(f"From: {transaction.from_address}")
        if transaction.to_address:
            message.append(f"To: {transaction.to_address}")
            
        if transaction.tokens:
            message.append("Tokens:")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = token.name or f"[{token.token_id[:12]}...]"
                formatted_amount = token.get_formatted_amount()
                message.append(f"  {'+' if token.amount > 0 else ''}{formatted_amount} {token_name}")
        
        message.append(f"Tx ID: {transaction.tx_id}")
        
        self.logger.info("\n".join(message) + "\n")


@dataclass
class TelegramDestination:
    chat_id: str
    topic_id: Optional[int] = None
    
    def __post_init__(self):
        # Ensure chat_id is a string and properly formatted
        self.chat_id = str(self.chat_id)
        if not self.chat_id.startswith('-100'):
            self.chat_id = f"-100{self.chat_id.lstrip('-')}"

@dataclass
class TelegramConfig:
    destinations: List[TelegramDestination]

class MultiTelegramHandler(TransactionHandler):
    def __init__(self, bot_token: str, address_configs: Dict[str, TelegramConfig], default_chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.address_configs = address_configs
        self.default_chat_id = default_chat_id
        if default_chat_id:
            self.default_destination = TelegramDestination(chat_id=default_chat_id)
        else:
            self.default_destination = None
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def get_destinations_for_address(self, address: str) -> List[TelegramDestination]:
        """Get all destinations that should receive notifications for this address"""
        destinations = []
        
        # Add address-specific destinations if they exist
        if address in self.address_configs:
            destinations.extend(self.address_configs[address].destinations)
        
        # Add default destination if no specific destinations were found
        if not destinations and self.default_destination:
            destinations.append(self.default_destination)
        
        return destinations

    async def handle_transaction(self, address: str, transaction: Transaction, monitor: ErgoTransactionMonitor) -> None:
        """Handle Telegram transaction notification without balance information"""
        tx_direction = "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
        wallet_name = next((info.nickname for info in monitor.watched_addresses.values() if info.address == address), address[:8])
        
        message = [
            f"🔄 *{wallet_name} Transaction*",
            f"Type: {tx_direction}",
            f"Status: {'⏳' if transaction.status == 'Pending' else '✅'} {transaction.status}",
            f"Amount: `{transaction.value:+.8f}` ERG"
        ]
        
        if transaction.block:
            message.append(f"Block: `{transaction.block}`")
        
        if transaction.fee > 0:
            message.append(f"Fee: `{transaction.fee:.8f}` ERG")
        
        if transaction.from_address:
            message.append(f"From: `{transaction.from_address}`")
        if transaction.to_address:
            message.append(f"To: `{transaction.to_address}`")
        
        if transaction.tokens:
            message.append("\n*Tokens:*")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = token.name or f"[{token.token_id[:12]}...]"
                # Use formatted amount with decimals
                formatted_amount = token.get_formatted_amount()
                prefix = "+" if token.amount > 0 else ""
                message.append(f"`{prefix}{formatted_amount}` {token_name}")
        
        message.append(f"\n[View Transaction](https://explorer.ergoplatform.com/en/transactions/{transaction.tx_id})")

        message_text = "\n".join(message)
        destinations = self.get_destinations_for_address(address)
        
        for dest in destinations:
            try:
                success = await self.send_message(message_text, dest)
                if not success:
                    self.logger.error(f"Failed to send message to chat ID: {dest.chat_id}")
            except Exception as e:
                self.logger.error(f"Error sending message to chat ID {dest.chat_id}: {str(e)}")
    async def send_message(self, text: str, destination: TelegramDestination) -> bool:
        try:
            await self.init_session()
            url = f"{self.base_url}/sendMessage"
            
            payload = {
                "chat_id": destination.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            # Add message_thread_id for forum topics
            if destination.topic_id is not None:
                payload["message_thread_id"] = int(destination.topic_id)
            
            self.logger.debug(f"Sending Telegram message with payload: {payload}")
            
            async with self.session.post(url, json=payload) as response:
                response_data = await response.json()
                if response.status == 200 and response_data.get('ok'):
                    self.logger.info(f"Successfully sent Telegram message to chat_id: {destination.chat_id}" + 
                                   (f" topic_id: {destination.topic_id}" if destination.topic_id else ""))
                    return True
                else:
                    error_msg = response_data.get('description', 'Unknown error')
                    self.logger.error(f"Failed to send Telegram message. Status: {response.status}, "
                                   f"Error: {error_msg}, "
                                   f"Chat ID: {destination.chat_id}, "
                                   f"Topic ID: {destination.topic_id}")
                    return False
                        
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}", exc_info=True)
            return False