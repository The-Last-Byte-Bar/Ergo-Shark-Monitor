74101# notifications/handlers/command_handler.py
import re
from typing import Optional, Tuple, Dict, AsyncGenerator
from services import LLMService
from analytics import AnalyticsService
import logging

class CommandHandler:
    """Handle command processing for the bot"""
    
    def __init__(self, llm_service: LLMService, analytics_service: AnalyticsService, node_client):
        self.llm_service = llm_service
        self.analytics_service = analytics_service
        self.node_client = node_client
        self.logger = logging.getLogger(__name__)
        self.address_map: Dict[str, str] = {}
        
    async def handle_command(self, message: str) -> Optional[str]:
        """Process commands starting with /"""
        if not message.startswith('/'):
            return "Unknown command. Available commands: /analyze"
            
        # Split command and arguments
        parts = message.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == '/analyze':
            if not args:
                # List available wallets
                if not self.address_map:
                    return "No wallets available for analysis. Please check configuration."
                    
                wallet_list = "\n".join([
                    f"- {nickname}" 
                    for nickname in sorted(self.address_map.keys())
                ])
                return (
                    "Available wallets for analysis:\n"
                    f"{wallet_list}\n\n"
                    "Usage: /analyze <wallet name> - <your question>"
                )
                
            return await self._handle_analyze(args)
            
        return "Unknown command. Available commands: /analyze"
        
    async def _handle_analyze(self, args: str) -> str:
        """Handle the analyze command"""
        try:
            wallet_name, query = self._parse_analyze_args(args)
            if not wallet_name or not query:
                return "Please provide both wallet name and query. Format: /analyze <wallet name> - <query>"
            
            address = self.address_map.get(wallet_name)
            if not address:
                available_wallets = "\n".join([f"- {name}" for name in self.address_map.keys()])
                return (
                    f"Unknown wallet name: {wallet_name}\n"
                    f"Available wallets:\n{available_wallets}"
                )
            
            # Get analytics results first
            analysis_result = await self.analytics_service.analyze(
                query=query,
                transactions=[],  # Will be fetched by LLM service
                current_balance={},  # Will be fetched by LLM service
                prompt_type="standard"
            )
            
            # Then get LLM response with analytics context
            response = await self.llm_service.process_query(
                query=query,
                address=address,
                days_back=30,
                analytics_context=analysis_result.get('metrics', {})
            )
            
            return response or "Sorry, I couldn't generate an analysis for your query."
            
        except ValueError as e:
            self.logger.error(f"Error parsing analyze command: {str(e)}")
            return str(e)
        except Exception as e:
            self.logger.error(f"Error processing analyze command: {str(e)}")
            return f"Error processing analysis: {str(e)}"
            
    def _parse_analyze_args(self, args: str) -> Tuple[str, str]:
        """Parse wallet name and query from analyze command arguments"""
        parts = args.split('-', 1)
        if len(parts) != 2:
            raise ValueError(
                "Please separate wallet name and query with a hyphen (-)\n"
                "Example: /analyze Mining Wallet - What is my current balance?"
            )
            
        wallet_name = parts[0].strip()
        query = parts[1].strip()
        
        if not wallet_name or not query:
            raise ValueError("Both wallet name and query are required")
            
        return wallet_name, query
        
    def set_address_map(self, address_map: Dict[str, str]):
        """Update the address map"""
        self.logger.info(f"Updating address map with {len(address_map)} entries")
        self.address_map = address_map