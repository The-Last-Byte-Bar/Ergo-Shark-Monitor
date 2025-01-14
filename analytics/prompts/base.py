# analytics/prompts/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BasePromptConstructor(ABC):
    """Base class for prompt constructors"""
    
    @abstractmethod
    def construct(self, query: str, context_data: Dict) -> str:
        """Construct a prompt from the context data"""
        pass
    
    @property
    @abstractmethod
    def prompt_name(self) -> str:
        """Return the name of this prompt constructor"""
        pass