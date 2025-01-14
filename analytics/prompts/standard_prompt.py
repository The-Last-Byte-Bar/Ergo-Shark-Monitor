# analytics/prompts/standard_prompt.py
import json
from typing import Dict, Any
from .base import BasePromptConstructor

class StandardPromptConstructor(BasePromptConstructor):
    """Standard prompt constructor for general analytics"""
    
    @property
    def prompt_name(self) -> str:
        return "standard"
    
    def construct(self, query: str, context_data: Dict) -> str:
        """Construct a prompt for analysis"""
        portfolio = context_data.get('metrics', {}).get('portfolio_analysis', {}).get('portfolio_value', {})
        flow = context_data.get('metrics', {}).get('flow_analysis', {})
        tokens = context_data.get('metrics', {}).get('token_analysis', {})
        current_balance = context_data.get('current_balance', {})
        
        return f"""You are a blockchain analytics assistant analyzing Ergo blockchain data.
Answer the following query using the provided context data.

Portfolio Analysis:
{self._format_portfolio_section(portfolio)}

Current Balance:
{self._format_balance_section(current_balance)}

Flow Analysis:
{self._format_flow_section(flow)}

Token Analysis:
{self._format_token_section(tokens)}

User Query: {query}

Please provide a clear and concise analysis based on this data.
Format your response appropriately for a Telegram message."""

    def _format_portfolio_section(self, portfolio: Dict) -> str:
        if not portfolio:
            return "No portfolio data available"
            
        lines = [
            f"- Total Value: ${portfolio.get('total_value', 0):.2f}",
            f"- ERG Value: ${portfolio.get('erg_value', 0):.2f}",
            f"- Token Value: ${portfolio.get('token_value', 0):.2f}"
        ]
        
        token_breakdown = portfolio.get('token_breakdown', {})
        if token_breakdown:
            lines.append("- Token Breakdown:")
            for token_id, data in token_breakdown.items():
                name = data.get('name', token_id[:8])
                value = data.get('value', 0)
                lines.append(f"  - {name}: ${value:.2f}")
                
        return "\n".join(lines)

    def _format_balance_section(self, balance: Dict) -> str:
        if not balance:
            return "No balance data available"
            
        lines = [
            f"- ERG Balance: {balance.get('erg_balance', 0):.8f}"
        ]
        
        tokens = balance.get('tokens', {})
        if tokens:
            lines.append("- Token Balances:")
            for token_id, data in tokens.items():
                name = data.get('name', token_id[:8])
                amount = data.get('amount', 0)
                lines.append(f"  - {name}: {amount}")
                
        return "\n".join(lines)

    def _format_flow_section(self, flow: Dict) -> str:
        if not flow:
            return "No flow data available"
            
        lines = [
            f"- Total Inflow: {flow.get('inflow', 0):.8f} ERG",
            f"- Total Outflow: {flow.get('outflow', 0):.8f} ERG",
            f"- Net Flow: {flow.get('net_flow', 0):.8f} ERG"
        ]
        
        daily_flows = flow.get('daily_flows', {})
        if daily_flows:
            recent_days = sorted(daily_flows.items(), reverse=True)[:7]  # Last 7 days
            lines.append("\n- Recent Daily Flows:")
            for date, values in recent_days:
                net = values.get('in', 0) - values.get('out', 0)
                lines.append(f"  - {date}: {net:+.8f} ERG")
                
        return "\n".join(lines)

    def _format_token_section(self, tokens: Dict) -> str:
        if not tokens:
            return "No token data available"
            
        lines = [
            f"- Total Unique Tokens: {tokens.get('unique_tokens', 0)}"
        ]
        
        movements = tokens.get('movements', {})
        if movements:
            lines.append("- Token Movements:")
            for token_id, data in movements.items():
                name = data.get('name', token_id[:8])
                total_in = data.get('total_in', 0)
                total_out = data.get('total_out', 0)
                net = total_in - total_out
                lines.append(f"  - {name}: {net:+} (In: {total_in}, Out: {total_out})")
                
        return "\n".join(lines)