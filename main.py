from __future__ import annotations
import asyncio
import logging
from utils.config import ConfigManager
from utils.logging import setup_logging
from clients import ExplorerClient, NodeClient 
from notifications import (
    LogHandler, 
    TelegramHandler, 
    TelegramConfig, 
    TelegramDestination,
    CommandHandler
)
from services import (
    ErgoTransactionMonitor, 
    LLMService,
    PriceService
)
from analytics import (
    AnalyticsService,
    FlowMetrics,
    TokenMetrics,
    PortfolioMetrics,
    StandardPromptConstructor
)

async def main():
    # Initialize configuration and logging
    config = ConfigManager("config.yaml").load()
    setup_logging(
        log_level=config.get_nested('logging', 'level', default=logging.INFO),
        log_dir=config.get_nested('logging', 'directory', default="logs")
    )
    
    logger = logging.getLogger(__name__)
    
    # Initialize explorer client
    explorer_client = ExplorerClient(
        explorer_url=config.get_nested('explorer', 'url', default="https://api.ergoplatform.com/api/v1"),
        max_retries=config.get_nested('explorer', 'max_retries', default=5),
        retry_delay=config.get_nested('explorer', 'retry_delay', default=3.0)
    )
    await explorer_client.init_session()

    # Initialize node client if configured
    node_client = None
    node_config = config.get('node')
    if node_config and node_config.get('url'):
        node_client = NodeClient(
            node_url=node_config['url'],
            api_key=node_config.get('api_key'),
            max_retries=node_config.get('max_retries', 3),
            retry_delay=node_config.get('retry_delay', 1.0)
        )
        await node_client.init_session()
        logger.info("Node client initialized")
    
    # Initialize analytics with proper prompt constructor
    analytics_service = AnalyticsService()
    analytics_service.register_metric(FlowMetrics())
    analytics_service.register_metric(TokenMetrics())
    analytics_service.register_metric(PortfolioMetrics())
    analytics_service.register_prompt_constructor(StandardPromptConstructor())
    
    # Initialize LLM service if configured
    llm_config = config.get('llm')
    llm_service = None
    if llm_config and llm_config.get('api_key'):
        llm_service = LLMService(
            explorer_client=explorer_client,
            llm_api_key=llm_config['api_key'],
            max_tokens=llm_config.get('max_tokens', 1000),
            node_client=node_client 
        )
        await llm_service.init_session()
        logger.info("LLM service initialized")
    else:
        logger.warning("No LLM API key configured, LLM features will be disabled")
    
    # Process all addresses first
    address_configs = {}
    address_map = {}
    
    # Build complete address mapping
    for addr_config in config.get('addresses', []):
        address = addr_config['address']
        nickname = addr_config.get('nickname')
        
        # Add to address map if nickname is provided
        if nickname:
            address_map[nickname] = address
            logger.debug(f"Added address mapping: {nickname} -> {address}")
            
        # Process Telegram configuration if present
        if 'telegram_destinations' in addr_config:
            destinations = [
                TelegramDestination(
                    chat_id=dest['chat_id'],
                    topic_id=dest.get('topic_id')
                )
                for dest in addr_config['telegram_destinations']
            ]
            address_configs[address] = TelegramConfig(
                destinations=destinations
            )
    
    # Initialize command handler with complete address map
    command_handler = CommandHandler(llm_service, analytics_service, node_client)
    command_handler.set_address_map(address_map)
    logger.info(f"Command handler initialized with {len(address_map)} addresses")
    
    # Initialize notification handlers
    handlers = [LogHandler()]
    
    # Configure Telegram if enabled
    telegram_config = config.get('telegram')
    if telegram_config and telegram_config.get('bot_token'):
        telegram_handler = TelegramHandler(
            bot_token=telegram_config['bot_token'],
            address_configs=address_configs,
            default_chat_id=telegram_config.get('default_chat_id'),
            llm_service=llm_service,
            command_handler=command_handler
        )
        await telegram_handler.init_session()
        handlers.append(telegram_handler)
        logger.info("Telegram handler initialized")
    
    # Initialize and run monitor
    try:
        monitor = ErgoTransactionMonitor(
            explorer_client=explorer_client,
            transaction_handlers=handlers,
            analytics_service=analytics_service,
            daily_report_hour=config.get_nested('monitoring', 'daily_report_hour', default=12)
        )
        
        # Add configured addresses to monitor
        for addr_config in config.get('addresses', []):
            address = addr_config['address']
            nickname = addr_config.get('nickname')
            
            monitor.add_address(
                address=address,
                nickname=nickname,
                hours_lookback=config.get_nested('monitoring', 'hours_lookback', default=24)
            )
            logger.info(f"Added address {nickname or address[:8]} to monitoring")
        
        # Start monitoring
        logger.info("Starting monitor loop")
        await monitor.monitor_loop(
            check_interval=config.get_nested('monitoring', 'check_interval', default=15)
        )
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        raise
    finally:
        # Cleanup
        await explorer_client.close_session()
        if llm_service:
            await llm_service.close_session()
        for handler in handlers:
            await handler.close_session()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
        raise