# services/llm_service.py
from typing import Dict, Optional, List
import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta
from analytics.metrics import TransactionAnalyzer, BalanceMetrics, FlowMetrics
from models import Transaction, Token, WalletBalance
from .price_service import PriceService

class LLMService:
    def __init__(self, explorer_client, llm_api_key: str, max_tokens: int = 1000, node_client=None):
        self.explorer_client = explorer_client
        self.llm_api_key = llm_api_key
        self.max_tokens = max_tokens
        self.node_client = node_client
        self.price_service = PriceService()
        self.logger = logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self.transaction_analyzer = TransactionAnalyzer()
        self.balance_metrics = BalanceMetrics()
        self.flow_metrics = FlowMetrics()

    async def init_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self.price_service.init_session()

    async def close_session(self):
        if self._session:
            await self._session.close()
            self._session = None
        self.price_service.close_session()


    async def process_query(
        self, 
        query: str, 
        address: str, 
        days_back: int = 30,
        analytics_context: Dict = None
    ) -> str:
        """Process a natural language query about an address's activity"""
        try:
            # Use instance node_client by default
            context_data = await self.gather_context_data(address, days_back)
            prompt = self.construct_prompt(query, context_data, analytics_context)
            response = await self.get_llm_response(prompt)
            return response
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return f"Sorry, I encountered an error processing your query: {str(e)}"

    async def gather_context_data(self, address: str, days_back: int) -> Dict:
        """Gather relevant blockchain data with optimized context size"""
        try:
            # Initialize flow metrics calculator
            flow_metrics = FlowMetrics()
    
            # Get current balance
            current_balance = await self.balance_metrics.get_current_balance(
                explorer_client=self.explorer_client,
                address=address,
                node_client=self.node_client if hasattr(self, 'node_client') else None
            )
            
            if current_balance is None:
                current_balance = WalletBalance()
            
            erg_price = self.price_service.get_erg_price() or 0
            total_usd_value = current_balance.erg_balance * erg_price
    
            # Get recent transactions
            transactions = await self.explorer_client.get_address_transactions(address)
            self.logger.info(f"Retrieved {len(transactions)} transactions for {address}")
            
            # Calculate flow metrics
            flow_analysis = flow_metrics.calculate(
                transactions=transactions,
                current_balance={'address': address}
            )
            
            processed_txs = []
            lookback_time = datetime.now() - timedelta(days=days_back)
            
            for tx_data in transactions[:20]:  # Limit to 20 most recent transactions
                if not isinstance(tx_data, dict):
                    continue
                    
                try:
                    tx = self.transaction_analyzer.extract_transaction_details(tx_data, address)
                    if not tx:
                        continue
                        
                    if hasattr(tx, 'timestamp'):
                        tx_time = tx.timestamp
                    else:
                        tx_time = datetime.fromtimestamp(tx_data.get('timestamp', 0) / 1000)
                    
                    if tx_time < lookback_time:
                        break
                        
                    processed_txs.append(tx.to_dict())
                except Exception as e:
                    self.logger.warning(f"Error processing transaction: {str(e)}")
                    continue
    
            # Format tokens (limit to top 10 by value)
            formatted_tokens = {}
            sorted_tokens = sorted(
                current_balance.tokens.items(),
                key=lambda x: x[1].amount * (x[1].get_formatted_amount() if hasattr(x[1], 'get_formatted_amount') else 1),
                reverse=True
            )[:10]
            
            for token_id, token in sorted_tokens:
                try:
                    formatted_amount = token.get_formatted_amount() if hasattr(token, 'get_formatted_amount') else token.amount
                    formatted_tokens[token_id] = {
                        'amount': token.amount,
                        'name': token.name or token_id[:8],
                        'decimals': token.decimals,
                        'formatted_amount': formatted_amount
                    }
                except Exception as e:
                    self.logger.warning(f"Error formatting token {token_id}: {str(e)}")
                    continue
            
            return {
                'address': address,
                'transactions': processed_txs,
                'current_balance': {
                    'erg_balance': current_balance.erg_balance,
                    'erg_value_usd': current_balance.erg_balance * erg_price,
                    'tokens': formatted_tokens,
                    'total_value_usd': total_usd_value
                },
                'erg_price': erg_price,
                'flow_analysis': flow_analysis  # Add flow analysis to context
            }
                
        except Exception as e:
            self.logger.error(f"Error gathering context data: {str(e)}")
            raise

    def construct_prompt(self, query: str, context_data: Dict, analytics_context: Dict = None) -> str:
        """Construct prompt with context and analytics data"""
        current_balance = context_data.get('current_balance', {})
        erg_price = context_data.get('erg_price', 0)
        flow_analysis = context_data.get('flow_analysis', {})  # Get flow analysis from context_data
        
        def format_number(value: float, decimals: int = 8) -> str:
            return f"{value:,.{decimals}f}"
    
        prompt_parts = [
            "You are a blockchain analytics assistant analyzing Ergo blockchain data. Format all responses carefully for Telegram markdown.",
            "When showing numeric values:",
            "- Use code blocks with backticks for all numbers",
            "- Show ERG amounts with 8 decimal places",
            "- Show USD amounts with 2 decimal places",
            "- Use commas as thousand separators",
            "\nCurrent wallet status:",
            f"Address: {context_data['address']}",
            f"ERG Balance: `{format_number(current_balance.get('erg_balance', 0))}` ERG",
            f"USD Value: $`{format_number(current_balance.get('erg_value_usd', 0), 2)}`",
            f"Current ERG Price: $`{format_number(erg_price, 2)}`"
        ]
    
        # Add token balances if present
        if 'tokens' in current_balance and current_balance['tokens']:
            prompt_parts.append("\nToken Balances:")
            for token_id, token_data in current_balance['tokens'].items():
                name = token_data.get('name', token_id[:8])
                amount = token_data.get('formatted_amount', token_data.get('amount', 0))
                prompt_parts.append(f"- {name}: `{format_number(float(amount), 0)}`")
    
        # Add flow analysis from context_data
        if flow_analysis:
            prompt_parts.extend([
                "\nFlow Analysis (last 30 days):",
                f"- Inflow: `{format_number(flow_analysis.get('inflow', 0))}` ERG",
                f"- Outflow: `{format_number(flow_analysis.get('outflow', 0))}` ERG",
                f"- Net Flow: `{format_number(flow_analysis.get('net_flow', 0))}` ERG"
            ])
    
            # Add daily flows if available
            if flow_analysis.get('daily_flows'):
                prompt_parts.append("\nRecent Daily Flows:")
                recent_days = sorted(flow_analysis['daily_flows'].items(), reverse=True)[:5]
                for date, flows in recent_days:
                    prompt_parts.append(f"- {date}: In=`{format_number(flows['in'])}`, Out=`{format_number(flows['out'])}`")
    
        prompt_parts.extend([
            "\nUser Question:",
            query,
            "\nPlease provide a clear and concise analysis. Your response should:",
            "1. Answer the user's question directly",
            "2. Format all numbers inside code blocks using backticks",
            "3. Use proper decimal places (8 for ERG, 2 for USD)",
            "4. Include thousand separators in large numbers",
            "Example response format: The wallet has `1,234.56789012` ERG worth $`2,469.13`.",
            "Focus on accuracy and clarity. Avoid using special characters or emojis."
        ])
    
        return "\n".join(prompt_parts)

    async def get_llm_response(self, prompt: str, max_retries: int = 3, retry_delay: float = 2.0) -> str:
        """Get response from Claude API with retry logic"""
        for attempt in range(max_retries):
            try:
                await self.init_session()
                
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": self.llm_api_key,
                    "anthropic-version": "2023-06-01"
                }
                
                payload = {
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }],
                    "model": "claude-3-opus-20240229",
                    "max_tokens": self.max_tokens
                }
                
                self.logger.debug(f"Sending request to LLM API (attempt {attempt + 1}/{max_retries})")
                
                async with self._session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        raw_response = result['content'][0]['text']
                        return self._format_telegram_response(raw_response)
                        
                    elif response.status == 401:
                        self.logger.error("Invalid API key. Please check your Anthropic API key.")
                        return "Error: Invalid API key. Please check your configuration."
                        
                    elif response.status == 429 or response.status == 529:  # Rate limit or overloaded
                        retry_after = float(response.headers.get('Retry-After', retry_delay))
                        self.logger.warning(f"API overloaded/rate limited. Retrying in {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    else:
                        error_text = await response.text()
                        self.logger.error(f"LLM API error response: {error_text}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                            continue
                        raise Exception(f"API error: {response.status} - {error_text}")
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error calling LLM API: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                return "Error: Unable to connect to the LLM service. Please try again later."
                
            except Exception as e:
                self.logger.error(f"Error getting LLM response: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise
                
        return "Sorry, the service is currently experiencing high load. Please try again in a few minutes."

    def _format_telegram_response(self, text: str) -> str:
        """Format response for Telegram with proper markdown escaping"""
        # Escape special characters not in code blocks
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        # Split by code blocks
        parts = text.split('`')
        for i in range(0, len(parts), 2):  # Only process non-code parts
            for char in special_chars:
                parts[i] = parts[i].replace(char, '\\' + char)
        
        return '`'.join(parts)