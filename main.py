from __future__ import annotations
import logging
import asyncio
import yaml
from pathlib import Path
from clients import ExplorerClient
from notifications import LogHandler, MultiTelegramHandler, TelegramConfig, TelegramDestination
from monitor import ErgoTransactionMonitor

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Error loading config file: {str(e)}")

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'ergo_monitor.log'),
            logging.StreamHandler()
        ]
    )

async def main():
    # Load configuration
    config = load_config()
    setup_logging()
    logger = logging.getLogger("main")
    
    # Initialize explorer client
    explorer_config = config.get('explorer', {})
    explorer_client = ExplorerClient(
        explorer_config.get('url', "https://api.ergoplatform.com/api/v1"),
        max_retries=explorer_config.get('max_retries', 5),
        retry_delay=explorer_config.get('retry_delay', 3.0)
    )
    
    # Initialize notification handlers
    handlers = [LogHandler()]
    
    # Add Telegram handler if configured
    telegram_config = config.get('telegram', {})
    if telegram_config and telegram_config.get('bot_token'):
        try:
            # Create address-specific telegram configs
            address_configs = {}
            for addr_config in config.get('addresses', []):
                if 'telegram_destinations' in addr_config:
                    destinations = [
                        TelegramDestination(
                            chat_id=dest['chat_id'],
                            topic_id=dest.get('topic_id')
                        )
                        for dest in addr_config['telegram_destinations']
                    ]
                    address_configs[addr_config['address']] = TelegramConfig(
                        destinations=destinations
                    )
            
            telegram_handler = MultiTelegramHandler(
                bot_token=telegram_config['bot_token'],
                address_configs=address_configs,
                default_chat_id=telegram_config.get('default_chat_id')
            )
            handlers.append(telegram_handler)
            logger.info("Telegram handler initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Telegram handler: {str(e)}")
    else:
        logger.warning("Telegram configuration missing or incomplete. Skipping Telegram notifications.")
    
    # Initialize monitor
    monitor = ErgoTransactionMonitor(explorer_client, handlers)
    
    # Initialize monitor with configured daily report hour
    monitoring_config = config.get('monitoring', {})
    hours_lookback = monitoring_config.get('hours_lookback', 1)
    daily_report_hour = monitoring_config.get('daily_report_hour', 12)
    
    monitor = ErgoTransactionMonitor(
        explorer_client, 
        handlers,
        daily_report_hour=daily_report_hour
    )
    
    # Add addresses from config with balance reporting configuration
    for addr_config in config.get('addresses', []):
        try:
            monitor.add_address(
                addr_config['address'],
                addr_config.get('nickname'),
                hours_lookback=hours_lookback,
                report_balance=addr_config.get('report_balance', True)  # Default to True if not specified
            )
        except Exception as e:
            logger.error(f"Error adding address {addr_config.get('nickname', 'unknown')}: {str(e)}")
    
    try:
        check_interval = monitoring_config.get('check_interval', 15)
        await monitor.monitor_loop(check_interval=check_interval)
    except KeyboardInterrupt:
        logger.info("Shutting down monitor...")
        await explorer_client.close_session()
        # Close Telegram handler session if it exists
        for handler in handlers:
            if isinstance(handler, MultiTelegramHandler):
                await handler.close_session()
        logger.info("Monitor stopped")

if __name__ == "__main__":
    asyncio.run(main())