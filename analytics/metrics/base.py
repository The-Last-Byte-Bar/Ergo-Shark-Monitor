# analytics/metrics/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseMetric(ABC):
    """Base class for all metrics calculators"""
    
    @abstractmethod
    def calculate(self, transactions: List[Dict], current_balance: Dict) -> Dict[str, Any]:
        """Calculate the metric from transaction data"""
        pass

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Return the name of this metric"""
        pass