# notifications/handlers/telegram/client.py
import logging
from typing import Optional, List, Dict, Callable, Awaitable
import aiohttp
import asyncio

class TelegramClient:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._update_id = None
        self._is_polling = False

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None
            self._is_polling = False

    async def send_message(self, text: str, chat_id: str, topic_id: Optional[int] = None) -> bool:
        """Send a message to Telegram"""
        try:
            await self.init_session()
            
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            if topic_id is not None:
                payload["message_thread_id"] = topic_id
                
            async with self.session.post(f"{self.base_url}/sendMessage", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"Error sending message: {error_text}")
                return response.status == 200
                
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            return False

    async def start_polling(self, message_handler: Callable[[Dict], Awaitable[None]], poll_interval: int = 1):
        """Start polling for updates"""
        self._is_polling = True
        self.logger.info("Starting Telegram update polling")
        
        while self._is_polling:
            try:
                updates = await self._get_updates()
                for update in updates:
                    try:
                        if 'message' in update:
                            await message_handler(update['message'])
                            
                        # Update the offset
                        self._update_id = update['update_id'] + 1
                            
                    except Exception as e:
                        self.logger.error(f"Error processing update: {str(e)}")
                        continue
                        
                await asyncio.sleep(poll_interval)
                
            except asyncio.CancelledError:
                self.logger.info("Polling cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in polling loop: {str(e)}")
                await asyncio.sleep(poll_interval)

    def stop_polling(self):
        """Stop polling for updates"""
        self._is_polling = False
        self.logger.info("Stopping Telegram update polling")

    async def _get_updates(self) -> List[Dict]:
        """Get updates (new messages) from Telegram"""
        try:
            await self.init_session()
            
            params = {
                "timeout": 30,
                "allowed_updates": ["message"]
            }
            if self._update_id is not None:
                params["offset"] = self._update_id
                
            async with self.session.get(f"{self.base_url}/getUpdates", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.debug(f"Received {len(data.get('result', []))} updates")
                    return data.get('result', [])
                else:
                    error_text = await response.text()
                    self.logger.error(f"Error getting updates: {error_text}")
                    return []
                    
        except Exception as e:
            self.logger.error(f"Error getting updates: {str(e)}")
            return []