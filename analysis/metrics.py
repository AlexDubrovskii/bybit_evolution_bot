import numpy as np
from typing import List, Dict, Any

class AdvancedMetrics:
    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        return (np.mean(returns) - risk_free_rate) / np.std(returns) * np.sqrt(365 * 24 * 12)  # Годовая доходность с учетом минутных данных

    @staticmethod
    def calculate_max_drawdown(balances: List[float]) -> float:
        peak = balances[0]
        max_drawdown = 0
        for balance in balances:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown

    @staticmethod
    def calculate_profit_factor(trades: List[Dict[str, Any]]) -> float:
        gross_profit = sum(trade.get('revenue', 0) for trade in trades if trade.get('action') == 'sell')
        gross_loss = abs(sum(trade.get('cost', 0) for trade in trades if trade.get('action') == 'buy'))
        
        if gross_loss == 0:
            return 10.0  # Если нет убытков
        return gross_profit / gross_loss

    @staticmethod
    def calculate_win_rate(trades: List[Dict[str, Any]]) -> float:
        if not trades:
            return 0.0
        profitable_trades = sum(1 for trade in trades if trade.get('revenue', 0) > trade.get('cost', 0))
        return profitable_trades / len(trades)

    @staticmethod
    def calculate_consistency(returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        return 1 - (np.std(returns) / np.mean(returns)) if np.mean(returns) != 0 else 0.0