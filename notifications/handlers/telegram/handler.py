# notifications/handlers/telegram/handler.py
import logging
from typing import Dict, List, Optional
import asyncio
from core import NotificationHandler
from ...formatters import TelegramFormatter
from .client import TelegramClient
from .config import TelegramConfig, TelegramDestination
from models import Transaction
from services import LLMService
from ..command_handler import CommandHandler

class TelegramHandler(NotificationHandler):
    def __init__(
        self, 
        bot_token: str, 
        address_configs: Dict[str, TelegramConfig],
        default_chat_id: Optional[str] = None, 
        llm_service: Optional[LLMService] = None,
        command_handler: Optional[CommandHandler] = None
    ):
        self.client = TelegramClient(bot_token)
        self.address_configs = address_configs
        self.default_chat_id = default_chat_id
        self.llm_service = llm_service
        self.command_handler = command_handler
        self.formatter = TelegramFormatter()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.monitor = None
        self._polling_task: Optional[asyncio.Task] = None

    async def init_session(self):
        """Initialize Telegram session and start polling"""
        self.logger.info("Initializing Telegram session")
        await self.client.init_session()
        # Start polling in a separate task
        self._polling_task = asyncio.create_task(
            self.client.start_polling(self.handle_message)
        )
        self.logger.info("Started Telegram polling")

    async def close_session(self):
        """Close Telegram session and stop polling"""
        self.logger.info("Closing Telegram session")
        if self._polling_task:
            self.client.stop_polling()
            try:
                await asyncio.wait_for(self._polling_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("Polling task didn't stop gracefully")
            self._polling_task = None
        await self.client.close_session()

    def get_destinations(self, address: str) -> List[TelegramDestination]:
        """Get destinations for an address"""
        if address in self.address_configs:
            return self.address_configs[address].destinations
        elif self.default_chat_id:
            return [TelegramDestination(chat_id=self.default_chat_id)]
        return []

    async def handle_transaction(self, address: str, transaction: Transaction, monitor) -> None:
        """Handle transaction notifications"""
        if transaction is None:
            # This might be a daily report or other non-transaction update
            if address == "daily_report":
                await self._send_daily_report()
            return
            
        # Store monitor reference for use in command handling
        if monitor and not self.monitor:
            self.logger.info("Setting up monitor reference for command handling")
            self.monitor = monitor
            # Update command handler with current address map
            if self.command_handler:
                address_map = {
                    info.nickname: info.address 
                    for info in monitor.watched_addresses.values()
                }
                self.command_handler.set_address_map(address_map)
        
        wallet_name = next(
            (info.nickname for info in monitor.watched_addresses.values() if info.address == address),
            address[:8]
        )
        
        message = self.formatter.format_transaction(transaction, wallet_name)
        destinations = self.get_destinations(address)
        
        for dest in destinations:
            success = await self.client.send_message(message, dest.chat_id, dest.topic_id)
            if not success:
                self.logger.error(f"Failed to send message to {dest.chat_id}")
                
    async def handle_message(self, message: Dict) -> None:
        """Handle incoming messages and commands"""
        try:
            if not self.command_handler:
                self.logger.warning("No command handler configured")
                return
                
            text = message.get('text', '')
            chat_id = str(message.get('chat', {}).get('id'))
            topic_id = message.get('message_thread_id')
            
            self.logger.info(f"Received message: {text} from chat {chat_id}")
            
            if text and text.startswith('/'):
                # Send "processing" message for analyze commands
                if text.startswith('/analyze'):
                    self.logger.info("Processing analyze command")
                    await self.client.send_message(
                        "Processing your request...",
                        chat_id,
                        topic_id
                    )
                
                response = await self.command_handler.handle_command(text)
                if response:
                    self.logger.debug(f"Sending command response: {response[:100]}...")
                    await self.client.send_message(response, chat_id, topic_id)
                else:
                    self.logger.warning("No response received from command handler")
            
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await self.client.send_message(
                f"Error processing command: {str(e)}", 
                chat_id, 
                topic_id
            )
            
    async def _send_daily_report(self):
        """Send daily balance report"""
        if not self.monitor:
            self.logger.warning("No monitor available for daily report")
            return
            
        self.logger.info("Preparing daily balance report")
        message = self.formatter.format_balance_report({
            addr: info for addr, info in self.monitor.watched_addresses.items()
            if info.report_balance
        })
        
        # Send to all configured destinations
        sent_to = set()
        for config in self.address_configs.values():
            for dest in config.destinations:
                key = (dest.chat_id, dest.topic_id)
                if key not in sent_to:
                    self.logger.debug(f"Sending daily report to {dest.chat_id}")
                    await self.client.send_message(message, dest.chat_id, dest.topic_id)
                    sent_to.add(key)
        
        # Send to default chat if configured
        if self.default_chat_id:
            self.logger.debug(f"Sending daily report to default chat {self.default_chat_id}")
            await self.client.send_message(message, self.default_chat_id)