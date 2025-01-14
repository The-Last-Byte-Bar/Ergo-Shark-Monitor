# utils/config.py
from typing import Dict, Any, Optional
import yaml
from pathlib import Path
import logging

class ConfigManager:
    """Manage application configuration"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        
    def load(self) -> 'ConfigManager':
        """Load configuration from file"""
        try:
            if not Path(self.config_path).exists():
                self.logger.warning(f"Config file {self.config_path} not found. Using defaults.")
                return self
                
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            return self
            
        except Exception as e:
            self.logger.error(f"Error loading config file: {str(e)}")
            self._config = {}
            return self
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
        
    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get nested configuration value"""
        current = self._config
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current
        
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value
        
    def save(self) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self._config, f, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"Error saving config file: {str(e)}")

    @property
    def config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary"""
        return self._config.copy()