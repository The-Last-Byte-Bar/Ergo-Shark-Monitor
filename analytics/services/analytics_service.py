# analytics/services/analytics_service.py
import logging
from typing import Dict, Any, List, Optional
from ..metrics import BaseMetric
from ..prompts import BasePromptConstructor
from models import Transaction

class AnalyticsService:
    """Main service for blockchain analytics"""
    
    def __init__(self):
        self.metrics: Dict[str, BaseMetric] = {}
        self.prompt_constructors: Dict[str, BasePromptConstructor] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def register_metric(self, metric: BaseMetric):
        """Register a new metric calculator"""
        self.metrics[metric.metric_name] = metric
        
    def register_prompt_constructor(self, constructor: BasePromptConstructor):
        """Register a new prompt constructor"""
        self.prompt_constructors[constructor.prompt_name] = constructor
    
    async def analyze(self, 
                     query: str,
                     transactions: List[Dict],
                     current_balance: Dict,
                     prompt_type: str = "standard") -> Dict[str, Any]:
        """Perform analysis using registered metrics and prompt constructors"""
        
        # Calculate all registered metrics
        metrics_results = {}
        for metric in self.metrics.values():
            try:
                metrics_results[metric.metric_name] = metric.calculate(
                    transactions, current_balance
                )
            except Exception as e:
                self.logger.error(f"Error calculating {metric.metric_name}: {str(e)}")
        
        # Construct context with all metrics
        context = {
            'metrics': metrics_results,
            'current_balance': current_balance
        }
        
        # Get appropriate prompt constructor
        constructor = self.prompt_constructors.get(
            prompt_type,
            self.prompt_constructors['standard']
        )
        
        # Construct prompt and return results
        prompt = constructor.construct(query, context)
        return {
            'prompt': prompt,
            'metrics': metrics_results
        }

    async def process_transaction(self, address: str, transaction: Transaction) -> None:
        """Process a new transaction for analytics"""
        try:
            # Convert transaction to dict format
            tx_dict = transaction.to_dict()

            # Get current balance (if needed)
            current_balance = {}  # This would typically come from a balance tracking service

            # Calculate metrics for this single transaction
            metrics_results = {}
            for metric in self.metrics.values():
                try:
                    metrics_results[metric.metric_name] = metric.calculate(
                        [tx_dict], current_balance
                    )
                except Exception as e:
                    self.logger.error(f"Error calculating {metric.metric_name} for transaction: {str(e)}")

            # Log or store the results as needed
            self.logger.debug(f"Processed transaction {transaction.tx_id} with metrics: {metrics_results}")

        except Exception as e:
            self.logger.error(f"Error processing transaction {transaction.tx_id}: {str(e)}")

    def get_metrics_results(self) -> Dict[str, Any]:
        """Get the latest metrics results"""
        return {name: metric for name, metric in self.metrics.items()}