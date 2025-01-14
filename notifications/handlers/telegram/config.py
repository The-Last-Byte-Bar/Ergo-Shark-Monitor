# notifications/handlers/telegram/config.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TelegramDestination:
    chat_id: str
    topic_id: Optional[int] = None
    
    def __post_init__(self):
        self.chat_id = str(self.chat_id)
        if not self.chat_id.startswith('-100'):
            self.chat_id = f"-100{self.chat_id.lstrip('-')}"

@dataclass
class TelegramConfig:
    destinations: List[TelegramDestination]
