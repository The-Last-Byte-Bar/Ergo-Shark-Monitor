from typing import Dict, Optional, List
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from services import TransactionAnalyzer, BalanceTracker
from models import Transaction, Token
from price_service import PriceService

class LLMService:
    def __init__(self, explorer_client, llm_api_key: str):
        self.explorer_client = explorer_client
        self.llm_api_key = llm_api_key
        self.price_service = PriceService()
        self.logger = logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self.price_service.init_session()

    async def close_session(self):
        if self._session:
            await self._session.close()
            self._session = None
        self.price_service.close_session()

    def calculate_pnl_metrics(self, transactions: List[Dict], current_balance: Dict) -> Dict:
        """Calculate profit and loss metrics - now synchronous"""
        metrics = {
            'realized_profit': 0.0,
            'unrealized_profit': 0.0,
            'total_fees_usd': 0.0,
            'best_trade': None,
            'worst_trade': None
        }
        
        # Get current prices synchronously
        erg_price = self.price_service.get_erg_price() or 0
            
        # Calculate realized P&L from completed transactions
        for tx in transactions:
            if tx['type'] == 'out':
                metrics['realized_profit'] += tx['value'] * erg_price
            metrics['total_fees_usd'] += tx.get('fee', 0) * erg_price
            
            # Track best/worst trades
            profit_usd = tx.get('profit_usd')
            if profit_usd:
                if not metrics['best_trade'] or profit_usd > metrics['best_trade']['profit']:
                    metrics['best_trade'] = {
                        'timestamp': tx['timestamp'],
                        'profit': profit_usd
                    }
                if not metrics['worst_trade'] or profit_usd < metrics['worst_trade']['profit']:
                    metrics['worst_trade'] = {
                        'timestamp': tx['timestamp'],
                        'profit': profit_usd
                    }
        
        # Calculate unrealized P&L from current holdings
        portfolio_value = self.price_service.calculate_portfolio_value(
            current_balance['erg'],
            current_balance.get('tokens', [])
        )
        metrics['unrealized_profit'] = portfolio_value['total_value']
        
        return metrics

    async def gather_context_data(self, address: str, days_back: int) -> Dict:
        """Gather relevant blockchain data for context"""
        try:
            # Get current balance
            current_balance = await BalanceTracker.get_current_balance(
                self.explorer_client, 
                address
            )
            if current_balance is None:
                current_balance = WalletBalance()
            
            # Get current prices (synchronously)
            erg_price = self.price_service.get_erg_price() or 0
            current_prices = {
                'erg_usd': erg_price,
                'erg_change_24h': 0
            }
            
            # Calculate portfolio value (synchronously)
            portfolio_value = self.price_service.calculate_portfolio_value(
                current_balance.erg_balance,
                [
                    {'id': token_id, 'amount': token.amount}
                    for token_id, token in current_balance.tokens.items()
                ] if current_balance.tokens else []
            )
            
            # Get transactions
            transactions = await self.explorer_client.get_address_transactions(address)
            if not transactions:
                transactions = []
            
            processed_txs = []
            lookback_time = datetime.now() - timedelta(days=days_back)
            
            for tx_data in transactions:
                if not isinstance(tx_data, dict):
                    continue
                    
                try:
                    tx = TransactionAnalyzer.extract_transaction_details(tx_data, address)
                    tx_time = datetime.fromtimestamp(tx_data.get('timestamp', 0) / 1000)
                    
                    if tx_time < lookback_time:
                        break
                        
                    processed_txs.append({
                        'type': 'in' if tx.value > 0 else 'out',
                        'value': abs(tx.value),
                        'fee': tx.fee,
                        'timestamp': tx_time.isoformat(),
                        'tokens': [
                            {'id': t.token_id, 'amount': t.amount, 'name': t.name}
                            for t in (tx.tokens or [])
                        ]
                    })
                except Exception as e:
                    self.logger.warning(f"Error processing transaction: {str(e)}")
                    continue
            
            metrics = self.calculate_metrics(processed_txs, current_balance)
            pnl_metrics = self.calculate_pnl_metrics(processed_txs, {
                'erg': current_balance.erg_balance,
                'tokens': [
                    {'id': token_id, 'amount': token.amount}
                    for token_id, token in current_balance.tokens.items()
                ] if current_balance.tokens else []
            })
            
            return {
                'address': address,
                'current_balance': {
                    'erg': current_balance.erg_balance,
                    'erg_usd': current_balance.erg_balance * erg_price,
                    'tokens': [
                        {
                            'id': token_id,
                            'amount': token.amount,
                            'name': token.name
                        }
                        for token_id, token in current_balance.tokens.items()
                    ] if current_balance.tokens else []
                },
                'current_prices': current_prices,
                'portfolio_value': portfolio_value,
                'pnl_metrics': pnl_metrics,
                'metrics': metrics,
                'recent_transactions': processed_txs[:10]
            }
            
        except Exception as e:
            self.logger.error(f"Error gathering context data: {str(e)}")
            # Return minimal context data
            return {
                'address': address,
                'current_balance': {'erg': 0, 'erg_usd': 0, 'tokens': []},
                'current_prices': {'erg_usd': 0, 'erg_change_24h': 0},
                'portfolio_value': {'total_value': 0, 'erg_value': 0, 'token_value': 0},
                'pnl_metrics': {'realized_profit': 0, 'unrealized_profit': 0, 'total_fees_usd': 0},
                'metrics': {'total_transactions': 0, 'total_value_in': 0, 'total_value_out': 0, 'token_movements': {}, 'active_days': 0},
                'recent_transactions': []
            }

    def calculate_metrics(self, transactions: List[Dict], current_balance: Dict) -> Dict:
        """Calculate aggregate metrics from transactions"""
        try:
            metrics = {
                'total_transactions': len(transactions),
                'total_value_in': sum(tx['value'] for tx in transactions if tx.get('type') == 'in'),
                'total_value_out': sum(tx['value'] for tx in transactions if tx.get('type') == 'out'),
                'token_movements': {},
                'active_days': len(set(tx.get('timestamp', '')[:10] for tx in transactions))
            }
            
            for tx in transactions:
                for token in tx.get('tokens', []):
                    if not isinstance(token, dict):
                        continue
                        
                    token_id = token.get('id')
                    if not token_id:
                        continue
                        
                    if token_id not in metrics['token_movements']:
                        metrics['token_movements'][token_id] = {
                            'name': token.get('name'),
                            'total_in': 0,
                            'total_out': 0
                        }
                    
                    if tx.get('type') == 'in':
                        metrics['token_movements'][token_id]['total_in'] += token.get('amount', 0)
                    else:
                        metrics['token_movements'][token_id]['total_out'] += token.get('amount', 0)
            
            return metrics
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            return {
                'total_transactions': 0,
                'total_value_in': 0,
                'total_value_out': 0,
                'token_movements': {},
                'active_days': 0
            }

    async def process_query(self, query: str, address: str, days_back: int = 30) -> str:
        """Process a natural language query about an address's activity"""
        try:
            context_data = await self.gather_context_data(address, days_back)
            prompt = self.construct_prompt(query, context_data)
            response = await self.get_llm_response(prompt)
            return response
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return f"Sorry, I encountered an error processing your query: {str(e)}"

    def construct_prompt(self, query: str, context_data: Dict) -> str:
        """Construct prompt with context data"""
        portfolio_value = context_data.get('portfolio_value', {})
        pnl_data = context_data.get('pnl_metrics', {})
        current_prices = context_data.get('current_prices', {})
        
        return f"""You are a blockchain analytics assistant analyzing Ergo blockchain data.
Answer the following query using the provided context data.

Context Data:
Address: {context_data['address']}

Current Portfolio Value:
- Total Value: ${portfolio_value.get('total_value', 0):.2f}
- ERG Value: ${portfolio_value.get('erg_value', 0):.2f}
- Token Value: ${portfolio_value.get('token_value', 0):.2f}

Current Balance:
- ERG: {context_data['current_balance']['erg']:.8f} (${context_data['current_balance'].get('erg_usd', 0):.2f})
- Tokens: {json.dumps(context_data['current_balance']['tokens'], indent=2)}

Performance Metrics:
- Realized P&L: ${pnl_data.get('realized_profit', 0):.2f}
- Unrealized P&L: ${pnl_data.get('unrealized_profit', 0):.2f}
- Total Fees Paid: ${pnl_data.get('total_fees_usd', 0):.2f}

Current Prices:
- ERG/USD: ${current_prices.get('erg_usd', 0):.2f}
- 24h Change: {current_prices.get('erg_change_24h', 0):.2f}%

Recent Activity Metrics:
- Total Transactions: {context_data['metrics']['total_transactions']}
- Total Value In: {context_data['metrics']['total_value_in']:.8f} ERG
- Total Value Out: {context_data['metrics']['total_value_out']:.8f} ERG
- Active Days: {context_data['metrics']['active_days']}

Token Movements:
{json.dumps(context_data['metrics']['token_movements'], indent=2)}

Recent Transactions:
{json.dumps(context_data['recent_transactions'], indent=2)}

User Query: {query}

Please provide a clear and concise analysis based on this data. Format your response for a Telegram message,
using appropriate markdown formatting. If calculating values, show your work. If making observations about
patterns or profitability, explain your reasoning."""

    async def get_llm_response(self, prompt: str) -> str:
        """Get response from Claude API"""
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
                "max_tokens": 1000
            }
            
            try:
                async with self._session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['content'][0]['text']
                    elif response.status == 401:
                        self.logger.error("Invalid API key. Please check your Anthropic API key.")
                        return "Error: Invalid API key. Please check your configuration."
                    else:
                        error_text = await response.text()
                        self.logger.error(f"LLM API error response: {error_text}")
                        raise Exception(f"API error: {response.status} - {error_text}")
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error calling LLM API: {str(e)}")
                return "Error: Unable to connect to the LLM service. Please try again later."
                        
        except Exception as e:
            self.logger.error(f"Error getting LLM response: {str(e)}")
            raise