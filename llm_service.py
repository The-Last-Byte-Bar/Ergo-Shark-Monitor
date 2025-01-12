# llm_service.py
from typing import Dict, Optional, List
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from services import TransactionAnalyzer, BalanceTracker
from models import Transaction, Token

class LLMService:
    def __init__(self, explorer_client, llm_api_key: str):
        self.explorer_client = explorer_client
        self.llm_api_key = llm_api_key
        self.logger = logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close_session(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def process_query(self, query: str, address: str, days_back: int = 30) -> str:
        """Process a natural language query about an address's activity"""
        try:
            # Gather relevant data
            context_data = await self._gather_context_data(address, days_back)
            
            # Construct prompt with context
            prompt = self._construct_prompt(query, context_data)
            
            # Get LLM response
            response = await self._get_llm_response(prompt)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return f"Sorry, I encountered an error processing your query: {str(e)}"

    async def _gather_context_data(self, address: str, days_back: int) -> Dict:
        """Gather relevant blockchain data for context"""
        try:
            current_balance = await BalanceTracker.get_current_balance(
                self.explorer_client, 
                address
            )
            
            transactions = await self.explorer_client.get_address_transactions(address)
            
            processed_txs = []
            lookback_time = datetime.now() - timedelta(days=days_back)
            
            for tx_data in transactions:
                tx = TransactionAnalyzer.extract_transaction_details(tx_data, address)
                tx_time = datetime.fromtimestamp(tx_data.get('timestamp', 0) / 1000)
                
                if tx_time < lookback_time:
                    break
                    
                processed_txs.append({
                    'type': 'in' if tx.value > 0 else 'out',
                    'value': abs(tx.value),
                    'timestamp': tx_time.isoformat(),
                    'tokens': [
                        {'id': t.token_id, 'amount': t.amount, 'name': t.name}
                        for t in tx.tokens
                    ] if tx.tokens else []
                })
            
            metrics = self._calculate_metrics(processed_txs, current_balance)
            
            return {
                'address': address,
                'current_balance': {
                    'erg': current_balance.erg_balance,
                    'tokens': [
                        {
                            'id': token_id,
                            'amount': token.amount,
                            'name': token.name
                        }
                        for token_id, token in current_balance.tokens.items()
                    ]
                },
                'metrics': metrics,
                'recent_transactions': processed_txs[:10]
            }
            
        except Exception as e:
            self.logger.error(f"Error gathering context data: {str(e)}")
            raise

    def _calculate_metrics(self, transactions: List[Dict], current_balance: Dict) -> Dict:
        """Calculate aggregate metrics from transactions"""
        metrics = {
            'total_transactions': len(transactions),
            'total_value_in': sum(tx['value'] for tx in transactions if tx['type'] == 'in'),
            'total_value_out': sum(tx['value'] for tx in transactions if tx['type'] == 'out'),
            'token_movements': {},
            'active_days': len(set(tx['timestamp'][:10] for tx in transactions))
        }
        
        for tx in transactions:
            for token in tx['tokens']:
                if token['id'] not in metrics['token_movements']:
                    metrics['token_movements'][token['id']] = {
                        'name': token['name'],
                        'total_in': 0,
                        'total_out': 0
                    }
                
                if tx['type'] == 'in':
                    metrics['token_movements'][token['id']]['total_in'] += token['amount']
                else:
                    metrics['token_movements'][token['id']]['total_out'] += token['amount']
        
        return metrics

    def _construct_prompt(self, query: str, context_data: Dict) -> str:
        """Construct a detailed prompt for the LLM"""
        return f"""You are a blockchain analytics assistant analyzing Ergo blockchain data. 
        Answer the following query using the provided context data.
        
        Context Data:
        Address: {context_data['address']}
        
        Current Balance:
        - ERG: {context_data['current_balance']['erg']:.8f}
        - Tokens: {json.dumps(context_data['current_balance']['tokens'], indent=2)}
        
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
        
        Please provide a clear and concise analysis based on this data. Format your response for a Telegram message, using appropriate markdown formatting.
        If calculating values, show your work. If making observations about patterns, explain your reasoning.
        """

    async def _get_llm_response(self, prompt: str) -> str:
        """Get response from Claude API"""
        try:
            await self.init_session()
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.llm_api_key,
                "anthropic-version": "2023-06-01"  # Added required API version header
            }
            
            payload = {
                "messages": [{
                    "role": "user",
                    "content": prompt
                }],
                "model": "claude-3-opus-20240229",
                "max_tokens": 1000
            }
            
            async with self._session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['content'][0]['text']
                else:
                    error_text = await response.text()
                    self.logger.error(f"LLM API error response: {error_text}")
                    raise Exception(f"API error: {response.status} - {error_text}")
                    
        except Exception as e:
            self.logger.error(f"Error getting LLM response: {str(e)}")
            raise

    def _construct_prompt(self, query: str, context_data: Dict) -> str:
        """Construct a detailed prompt for the LLM"""
        return f"""You are a blockchain analytics assistant analyzing Ergo blockchain data. 
        Answer the following query using the provided context data. Format your response for a Telegram message using simple Markdown (only basic *bold* and `code` formatting).
        Keep the response concise and focused on answering the query.
        
        Context Data:
        Address: {context_data['address']}
        
        Current Balance:
        - ERG: {context_data['current_balance']['erg']:.8f}
        - Tokens: {json.dumps(context_data['current_balance']['tokens'], indent=2)}
        
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
        
        Please provide a clear and concise analysis based on this data. Format your response as a Telegram message using only:
        - *asterisks* for bold text
        - `backticks` for numbers and addresses
        Do not use any other markdown formatting. Keep responses focused and brief."""