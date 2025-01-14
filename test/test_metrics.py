# tests/test_metrics.py
import sys
import os
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.metrics import FlowMetrics, BalanceMetrics
from clients import ExplorerClient, NodeClient
from utils.logging import setup_logging

async def test_balance_metrics(address: str, explorer_client: ExplorerClient, node_client: NodeClient = None):
    """Test balance metrics calculation"""
    print("\n=== Testing Balance Metrics ===")
    
    try:
        balance_metrics = BalanceMetrics()
        
        # Test Node API balance
        if node_client:
            print("\nTesting Node API Balance:")
            node_balance = await balance_metrics.get_current_balance(explorer_client, address, node_client)
            if node_balance:
                print(f"Node API ERG Balance: {node_balance.erg_balance:.8f}")
                print("\nNode API Tokens:")
                for token_id, token in node_balance.tokens.items():
                    print(f"- {token.name or token_id[:8]}: {token.amount}")
                    if token.decimals:
                        print(f"  (Decimals: {token.decimals})")
        
        # Test Explorer API balance
        print("\nTesting Explorer API Balance:")
        explorer_balance = await balance_metrics.get_current_balance(explorer_client, address)
        if explorer_balance:
            print(f"Explorer API ERG Balance: {explorer_balance.erg_balance:.8f}")
            print("\nExplorer API Tokens:")
            for token_id, token in explorer_balance.tokens.items():
                print(f"- {token.name or token_id[:8]}: {token.amount}")
            
        # Return node balance if available, otherwise explorer balance
        return node_balance if node_client and node_balance else explorer_balance
        
    except Exception as e:
        print(f"Error testing balance metrics: {str(e)}")
        return None

async def test_flow_metrics(address: str, explorer_client: ExplorerClient):
    """Test flow metrics calculation"""
    print("\n=== Testing Flow Metrics ===")
    
    try:
        # Get transactions
        transactions = await explorer_client.get_address_transactions(address)
        print(f"\nFound {len(transactions)} transactions")
        
        # Calculate flow metrics
        flow_metrics = FlowMetrics()
        metrics = flow_metrics.calculate(
            transactions=transactions,
            current_balance={'address': address}
        )
        
        print("\nFlow Analysis Results:")
        print(f"Total Inflow:  {metrics['inflow']:.8f} ERG")
        print(f"Total Outflow: {metrics['outflow']:.8f} ERG")
        print(f"Net Flow:      {metrics['net_flow']:.8f} ERG")
        
        if metrics['daily_flows']:
            print("\nRecent Daily Flows:")
            recent_days = sorted(metrics['daily_flows'].items(), reverse=True)[:5]
            for date, flows in recent_days:
                print(f"{date}: In={flows['in']:.8f}, Out={flows['out']:.8f}")
                
        return metrics
        
    except Exception as e:
        print(f"Error testing flow metrics: {str(e)}")
        return None

async def test_transaction_analysis(address: str, explorer_client: ExplorerClient):
    """Analyze specific transactions in detail"""
    print("\n=== Testing Transaction Analysis ===")
    
    try:
        transactions = await explorer_client.get_address_transactions(address)
        print(f"\nAnalyzing last 5 transactions:")
        
        for tx in transactions[:5]:  # Look at last 5 transactions
            print(f"\nTransaction ID: {tx.get('id')}")
            
            # Analyze inputs
            inputs_value = sum(
                box.get('value', 0) / 1e9
                for box in tx.get('inputs', [])
                if box.get('address') == address
            )
            
            # Analyze outputs
            outputs_value = sum(
                box.get('value', 0) / 1e9
                for box in tx.get('outputs', [])
                if box.get('address') == address
            )
            
            print(f"Input Value:  {inputs_value:.8f} ERG")
            print(f"Output Value: {outputs_value:.8f} ERG")
            print(f"Net Change:   {outputs_value - inputs_value:.8f} ERG")
            
            # Look at token transfers
            for box in tx.get('outputs', []):
                if box.get('address') == address and box.get('assets'):
                    print("\nToken Transfers:")
                    for asset in box['assets']:
                        print(f"- {asset.get('name', asset.get('tokenId')[:8])}: {asset.get('amount')}")
            
    except Exception as e:
        print(f"Error analyzing transactions: {str(e)}")

async def main():
    # Setup logging
    setup_logging(log_level=logging.INFO)
    
    # Initialize explorer client
    explorer_client = ExplorerClient(
        explorer_url="https://api.ergoplatform.com/api/v1",
        max_retries=3,
        retry_delay=1.0
    )
    await explorer_client.init_session()
    
    # Initialize node client
    node_client = NodeClient(
        node_url="http://0.0.0.0:9053",  # Replace with your node URL
        max_retries=3,
        retry_delay=1.0
    )
    await node_client.init_session()
    
    try:
        # Test address
        address = ""  # Replace with your test address
        
        # Run tests
        balance = await test_balance_metrics(address, explorer_client, node_client)
        flow_metrics = await test_flow_metrics(address, explorer_client)
        await test_transaction_analysis(address, explorer_client)
        
        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'address': address,
            'balance': balance.to_dict() if balance else None,
            'flow_metrics': flow_metrics
        }
        
        # Save to file
        os.makedirs('test_results', exist_ok=True)
        with open('test_results/metrics_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
            
    finally:
        await explorer_client.close_session()
        await node_client.close_session()

if __name__ == "__main__":
    asyncio.run(main())