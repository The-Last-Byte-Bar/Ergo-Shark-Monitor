# main.py
from __future__ import annotations
import logging
import asyncio
from clients import ExplorerClient
from notifications import LogHandler
from monitor import ErgoTransactionMonitor

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ergo_monitor.log'),
            logging.StreamHandler()
        ]
    )

async def main():
    setup_logging()
    
    explorer_client = ExplorerClient("https://api.ergoplatform.com/api/v1",
                                    max_retries=5,
                                    retry_delay=3.0)
    handlers = [LogHandler()]
    
    monitor = ErgoTransactionMonitor(explorer_client, handlers)
    
    # Add addresses to monitor with 24h lookback
    monitor.add_address(
        "9f3AaAirSTGYKWqDcw8hEa4Pk4hYiS96VC3Kpcr7CKTuqTiwjCy",
        "MyWallet",
        hours_lookback=1
    )

    monitor.add_address(
        "9hxEvxV6BqPJmWDesy8P1kFoXeQ3wF9ZGxvjak6TAiezr5tu4Sc",
        "GridTradingBot",
        hours_lookback=1
    )
    
    try:
        await monitor.monitor_loop(check_interval=15)
    except KeyboardInterrupt:
        await explorer_client.close_session()
        print("\nMonitoring stopped")

if __name__ == "__main__":
    asyncio.run(main())