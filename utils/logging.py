# utils/logging.py
import logging
from pathlib import Path
from typing import Optional

def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    log_format: Optional[str] = None
) -> None:
    """Setup application logging"""
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(exist_ok=True)
    
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_dir_path / 'ergo_monitor.log'),
            logging.StreamHandler()
        ]
    )