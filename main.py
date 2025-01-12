# main.py
from __future__ import annotations
import logging
import asyncio
import yaml
from pathlib import Path
from datetime import datetime
from clients import ExplorerClient
from notifications import LogHandler, TelegramHandler, TelegramConfig, TelegramDestination
from monitor import ErgoTransactionMonitor
from llm_service import LLMService

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
    
    try:
        # Initialize explorer client
        explorer_config = config.get('explorer', {})
        explorer_client = ExplorerClient(
            explorer_url=explorer_config.get('url', "https://api.ergoplatform.com/api/v1"),
            max_retries=explorer_config.get('max_retries', 5),
            retry_delay=explorer_config.get('retry_delay', 3.0)
        )
        await explorer_client.init_session()
        logger.info("Explorer client initialized successfully")
        
        # Initialize LLM service if configured
        llm_service = None
        llm_config = config.get('llm', {})
        if llm_config.get('api_key'):
            llm_service = LLMService(
                explorer_client=explorer_client,
                llm_api_key=llm_config['api_key']
            )
            await llm_service.init_session()
            logger.info("LLM service initialized successfully")
        else:
            logger.warning("LLM service not configured - analytics features will be disabled")
        
        # Initialize handlers
        handlers = [LogHandler()]
        telegram_handler = None
        
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
                
                telegram_handler = TelegramHandler(
                    bot_token=telegram_config['bot_token'],
                    address_configs=address_configs,
                    default_chat_id=telegram_config.get('default_chat_id'),
                    llm_service=llm_service
                )
                await telegram_handler.init_session()
                handlers.append(telegram_handler)
                logger.info("Telegram handler initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing Telegram handler: {str(e)}")
        
        # Initialize monitor with configured settings
        monitoring_config = config.get('monitoring', {})
        hours_lookback = monitoring_config.get('hours_lookback', 24)
        daily_report_hour = monitoring_config.get('daily_report_hour', 12)
        
        monitor = ErgoTransactionMonitor(
            explorer_client=explorer_client,
            transaction_handlers=handlers,
            daily_report_hour=daily_report_hour
        )
        if telegram_handler:
            telegram_handler.monitor = monitor
        
        # Add addresses from config
        for addr_config in config.get('addresses', []):
            try:
                monitor.add_address(
                    address=addr_config['address'],
                    nickname=addr_config.get('nickname', addr_config['address'][:8]),
                    hours_lookback=hours_lookback,
                    report_balance=addr_config.get('report_balance', True)
                )
                logger.info(f"Added address {addr_config.get('nickname', addr_config['address'][:8])} for monitoring")
            except Exception as e:
                logger.error(f"Error adding address {addr_config.get('nickname', 'unknown')}: {str(e)}")
        
        # Start monitoring tasks
        tasks = []
        
        # Start Telegram polling if configured
        if telegram_handler:
            logger.info("Starting Telegram polling...")
            telegram_task = asyncio.create_task(telegram_handler.start_polling())
            tasks.append(telegram_task)
        
        # Start the monitor
        try:
            check_interval = monitoring_config.get('check_interval', 15)
            logger.info(f"Starting monitor with {check_interval}s check interval...")
            monitor_task = asyncio.create_task(monitor.monitor_loop(check_interval=check_interval))
            tasks.append(monitor_task)
            
            # Wait for all tasks
            await asyncio.gather(*tasks)
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal...")
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
        finally:
            # Cancel all tasks
            for task in tasks:
                task.cancel()
            
            # Cleanup
            logger.info("Shutting down...")
            await explorer_client.close_session()
            
            # Close handler sessions
            for handler in handlers:
                if isinstance(handler, TelegramHandler):
                    await handler.close_session()
            
            if llm_service:
                await llm_service.close_session()
            
            logger.info("Cleanup complete")
            
    except Exception as e:
        logger.error(f"Fatal error in main function: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        raise