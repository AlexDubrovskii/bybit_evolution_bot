"""
Backtrader integration: lightweight engine and PandasData mapping for offline backtests.
"""
import os
import sys
# Workaround: if a broken 'talib' package is present, prevent Backtrader from importing it
# so it falls back to numpy-based indicators.
if 'talib' in sys.modules:
    del sys.modules['talib']
os.environ.setdefault('BTA_NO_TALIB', '1')

import backtrader as bt
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any, Type, Optional


class PandasData(bt.feeds.PandasData):
    """Map our common OHLCV DataFrame to Backtrader feed.
    Expected columns:
      - open_time (datetime-like)
      - open, high, low, close, volume
    """
    params = (
        ("datetime", "open_time"),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", None),
    )


@dataclass
class BacktestResult:
    strategy_name: str
    final_value: float
    pnl: float
    return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate_pct: float
    parameters: Dict[str, Any]


class BacktestEngine:
    def __init__(self, initial_cash: float = 1000.0, commission: float = 0.0006):
        self.initial_cash = float(initial_cash)
        self.commission = float(commission)

    def run(self,
            strategy_cls: Type[bt.Strategy],
            data: pd.DataFrame,
            strategy_params: Optional[Dict[str, Any]] = None,
            timeframe: str = "5m",
            printlog: bool = False) -> BacktestResult:
        cerebro = bt.Cerebro()
        cerebro.adddata(PandasData(dataname=data))
        cerebro.broker.setcash(self.initial_cash)
        cerebro.broker.setcommission(commission=self.commission)

        if strategy_params:
            cerebro.addstrategy(strategy_cls, **strategy_params)
        else:
            cerebro.addstrategy(strategy_cls)

        # Analyzers for metrics similar to our fitness
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        strat = cerebro.run()[0]

        final_value = float(cerebro.broker.getvalue())
        pnl = final_value - self.initial_cash
        ret_pct = (pnl / self.initial_cash) * 100.0 if self.initial_cash else 0.0
        sharpe = float(strat.analyzers.sharpe.get_analysis().get("sharperatio", 0) or 0)
        dd = strat.analyzers.dd.get_analysis()
        max_dd_pct = float((dd.get("max", {}) or {}).get("drawdown", 0) or 0)
        ta = strat.analyzers.trades.get_analysis()
        total_trades = int((ta.get('total', {}) or {}).get('closed', 0) or 0)
        won_trades = int((ta.get('won', {}) or {}).get('total', 0) or 0)
        win_rate = (won_trades / total_trades * 100.0) if total_trades else 0.0

        if printlog:
            print("=== Backtest summary ===")
            print(f"Strategy: {strategy_cls.__name__}")
            print(f"Timeframe: {timeframe}")
            print(f"Final value: {final_value:.2f}")
            print(f"PnL: {pnl:.2f} ({ret_pct:.2f}%)")
            print(f"Sharpe: {sharpe:.3f}")
            print(f"Max DD: {max_dd_pct:.2f}%")
            print(f"Trades: {total_trades} (Win rate {win_rate:.2f}%)")

        return BacktestResult(
            strategy_name=strategy_cls.__name__,
            final_value=final_value,
            pnl=pnl,
            return_pct=ret_pct,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd_pct,
            total_trades=total_trades,
            win_rate_pct=win_rate,
            parameters=strategy_params or {},
        )