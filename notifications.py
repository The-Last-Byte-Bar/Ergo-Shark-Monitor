# notifications.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Optional, Dict, List
import logging
from models import Transaction
import aiohttp
import asyncio

class TransactionHandler(Protocol):
    """Protocol defining the interface for transaction handlers"""
    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        """Handle a transaction notification"""
        ...

class LogHandler(TransactionHandler):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        """Handle transaction notification with logging"""
        tx_direction = "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
        wallet_name = next((info.nickname for info in monitor.watched_addresses.values() if info.address == address), address[:8])
        
        message = [
            f"=== {wallet_name} Transaction ===",
            f"Type: {tx_direction}",
            f"Block: {transaction.block}",
            f"Amount: {transaction.value:+.8f} ERG"
        ]
        
        if transaction.fee > 0:
            message.append(f"Fee: {transaction.fee:.8f} ERG")
        
        if transaction.from_address:
            message.append(f"From: {transaction.from_address}")
        if transaction.to_address:
            message.append(f"To: {transaction.to_address}")
            
        message.append(f"Block: {transaction.block}")
        message.append(f"Status: {transaction.status}")
        message.append(f"Tx ID: {transaction.tx_id}")
        
        if transaction.tokens:
            message.append("Tokens:")
            for token in sorted(transaction.tokens, key=lambda x: abs(x.amount), reverse=True):
                token_name = token.name or f"[{token.token_id[:12]}...]"
                message.append(f"  {token.amount:+} {token_name}")
        
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

class TelegramHandler(TransactionHandler):
    def __init__(self, bot_token: str, address_configs: Dict[str, TelegramConfig], 
                 default_chat_id: Optional[str] = None, llm_service: Optional[LLMService] = None):
        self.bot_token = bot_token
        self.address_configs = address_configs
        self.default_chat_id = default_chat_id
        self.llm_service = llm_service  # Add LLM service support
        if default_chat_id:
            self.default_destination = TelegramDestination(chat_id=default_chat_id)
        else:
            self.default_destination = None
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_update_id = 0
        self.monitor = None  # Will be set after monitor initialization

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def start_polling(self):
        """Start polling for updates from Telegram"""
        self.logger.info("Starting Telegram polling...")
        while True:
            try:
                await self.init_session()
                updates = await self._get_updates()
                
                for update in updates:
                    try:
                        message = update.get('message', {})
                        if not message:
                            continue
                            
                        chat_id = str(message.get('chat', {}).get('id'))
                        message_text = message.get('text', '')
                        message_thread_id = message.get('message_thread_id')
                        
                        if message_text:
                            await self.handle_message(chat_id, message_text, message_thread_id)
                            
                    except Exception as e:
                        self.logger.error(f"Error processing update: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Error in polling loop: {str(e)}")
            
            await asyncio.sleep(1)  # Poll every second
            
    async def _get_updates(self) -> List[Dict]:
        """Get updates from Telegram"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                "offset": self._last_update_id + 1,
                "timeout": 30
            }
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                
                if data.get('ok') and data.get('result'):
                    updates = data['result']
                    if updates:
                        self._last_update_id = updates[-1]['update_id']
                    return updates
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting updates: {str(e)}")
            return []

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

    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        """Handle transaction notification"""
        tx_direction = "Received" if transaction.value > 0 else "Sent" if transaction.value < 0 else "Mixed"
        wallet_name = next((info.nickname for info in monitor.watched_addresses.values() if info.address == address), address[:8])

        if transaction is None:  # This is a command/message
            return
        
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
                prefix = "+" if token.amount > 0 else ""
                message.append(f"`{prefix}{token.amount}` {token_name}")
        
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

    def _escape_markdown(self, text: str) -> str:
        """Escape Telegram markdown special characters"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        escaped_text = text
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        return escaped_text

    def _preprocess_message(self, text: str) -> str:
        """Preprocess message to ensure valid markdown"""
        # Start with plain text if too many formatting characters
        if text.count('*') > 10 or text.count('`') > 10:
            return text.replace('*', '').replace('`', '').replace('_', '')
            
        # Remove any extra whitespace
        text = text.strip()
        
        # Basic sanitization
        text = text.replace('\\', '')
        text = text.replace('\n\n\n', '\n\n')
        
        return text
    async def send_message(self, text: str, destination: TelegramDestination) -> bool:
        """Send a message to a Telegram chat"""
        try:
            await self.init_session()
            url = f"{self.base_url}/sendMessage"
            
            # Preprocess the message text
            processed_text = self._preprocess_message(text)
            
            # First try with basic Markdown
            payload = {
                "chat_id": destination.chat_id,
                "text": processed_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            if destination.topic_id is not None:
                payload["message_thread_id"] = int(destination.topic_id)
            
            self.logger.debug(f"Attempting to send message with Markdown...")
            
            async with self.session.post(url, json=payload) as response:
                response_data = await response.json()
                if response.status == 200 and response_data.get('ok'):
                    self.logger.info(f"Successfully sent Telegram message to chat_id: {destination.chat_id}")
                    return True
                
                # If markdown fails, try without any formatting by simply removing parse_mode
                if response.status == 400:
                    self.logger.warning("Markdown parsing failed, retrying without formatting...")
                    plain_text = processed_text.replace('*', '').replace('`', '').replace('_', '')
                    payload["text"] = plain_text
                    # Remove parse_mode instead of setting to None
                    del payload["parse_mode"]
                    
                    async with self.session.post(url, json=payload) as retry_response:
                        retry_data = await retry_response.json()
                        if retry_response.status == 200 and retry_data.get('ok'):
                            self.logger.info("Successfully sent message without formatting")
                            return True
                        else:
                            error_msg = retry_data.get('description', 'Unknown error')
                            self.logger.error(f"Failed to send plain text message. Status: {retry_response.status}, "
                                           f"Error: {error_msg}")
                            # One final attempt with minimal payload
                            try:
                                minimal_payload = {
                                    "chat_id": destination.chat_id,
                                    "text": plain_text
                                }
                                if destination.topic_id is not None:
                                    minimal_payload["message_thread_id"] = int(destination.topic_id)
                                
                                self.logger.debug("Making final attempt with minimal payload...")
                                async with self.session.post(url, json=minimal_payload) as final_response:
                                    return final_response.status == 200
                            except Exception as e:
                                self.logger.error(f"Final attempt failed: {str(e)}")
                                return False
                            
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}", exc_info=True)
            return False

    async def handle_message(self, chat_id: str, message_text: str, topic_id: Optional[int] = None) -> None:
        """Handle incoming messages and commands"""
        try:
            if not message_text.startswith('/'):
                return
                
            command_parts = message_text.split()
            command = command_parts[0].lower()
            
            if command == '/analyze':
                if not self.llm_service:
                    await self.send_message(
                        "Analytics service is not configured.",
                        TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                    )
                    return
                    
                if len(command_parts) < 3:
                    await self.send_message(
                        "Usage: /analyze <wallet_name> <question>",
                        TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                    )
                    return
                
                # Extract nickname and query
                possible_nicknames = [info.nickname for info in self.monitor.watched_addresses.values()]
                message_after_command = ' '.join(command_parts[1:])
                
                # Find the longest matching nickname
                found_nickname = None
                query = message_after_command
                
                for nickname in sorted(possible_nicknames, key=len, reverse=True):
                    if message_after_command.lower().startswith(nickname.lower()):
                        found_nickname = nickname
                        query = message_after_command[len(nickname):].strip()
                        break
                
                if not found_nickname:
                    await self.send_message(
                        f"Available wallets: {', '.join(possible_nicknames)}",
                        TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                    )
                    return
                
                # Find corresponding address
                address = None
                for addr, info in self.monitor.watched_addresses.items():
                    if info.nickname.lower() == found_nickname.lower():
                        address = addr
                        break
                
                if not address:
                    await self.send_message(
                        f"Internal error: Could not find address for {found_nickname}",
                        TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                    )
                    return
                
                await self.send_message(
                    "Analyzing... Please wait.",
                    TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                )
                
                try:
                    response = await self.llm_service.process_query(query, address)
                    await self.send_message(
                        response,
                        TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                    )
                except Exception as e:
                    self.logger.error(f"Error processing query: {str(e)}")
                    await self.send_message(
                        "Sorry, I encountered an error processing your request.",
                        TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                    )
                    
            elif command == '/help':
                help_text = """Available commands:
/analyze <wallet_name> <question> - Ask about wallet activity
/help - Show this help message

Example: /analyze Main Wallet What was my total incoming ERG last week?"""
                
                await self.send_message(
                    help_text,
                    TelegramDestination(chat_id=chat_id, topic_id=topic_id)
                )
                
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
            await self.send_message(
                "Sorry, I encountered an error processing your request.",
                TelegramDestination(chat_id=chat_id, topic_id=topic_id)
            )

