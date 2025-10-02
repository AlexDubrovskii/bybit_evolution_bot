import argparse
import os
import sys
from datetime import datetime
import pandas as pd

# Ensure repo root on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backtest.engine import BacktestEngine
from backtest.strategies.gene_driven import GeneDrivenBtStrategy
from config.settings import load_config


def load_csv(csv_path: str, timeframe_hint: str = "5m") -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Expect columns: open_time, open, high, low, close, volume
    # Try common variants
    colmap = {c.lower(): c for c in df.columns}
    def pick(name):
        return colmap.get(name, name)
    # Normalize datetime
    if 'open_time' in colmap:
        dt_col = pick('open_time')
        df['open_time'] = pd.to_datetime(df[dt_col])
    elif 'datetime' in colmap:
        dt_col = pick('datetime')
        df['open_time'] = pd.to_datetime(df[dt_col])
    else:
        # If there's a time column at index 0
        df['open_time'] = pd.to_datetime(df.iloc[:, 0])
    df = df.rename(columns={
        pick('open'): 'open',
        pick('high'): 'high',
        pick('low'): 'low',
        pick('close'): 'close',
        pick('volume'): 'volume',
    })
    # Ensure ordering
    df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']].copy()
    return df


def load_bybit_klines(symbol: str, interval: str, limit: int = 1000, page_size: int = 1000) -> pd.DataFrame:
    # Lazy import to avoid dependency when not needed
    from core.bybit_client import BybitClient
    client = BybitClient(testnet=True)

    all_items = []
    fetched = 0
    end_ts = None  # we will page backwards in time using 'end'

    while fetched < limit:
        req_size = min(page_size, limit - fetched)
        raw = client.get_klines(symbol, interval, limit=req_size, end=end_ts) or []
        if not raw:
            break
        # Ensure ascending by time
        try:
            raw.sort(key=lambda x: int(x[0]))
        except Exception:
            pass
        all_items = raw + all_items  # prepend older data to the front if end was used
        fetched = len(all_items)
        # Prepare next page end (earliest ts - 1 ms)
        try:
            earliest_ts = int(raw[0][0])
            end_ts = earliest_ts - 1
        except Exception:
            break
        # Safety: stop if no progress
        if req_size > 0 and len(raw) < req_size:
            break

    # Deduplicate by timestamp and keep ascending order
    uniq = {}
    for it in all_items:
        try:
            ts = int(it[0])
            uniq[ts] = it
        except Exception:
            continue
    ordered = [uniq[k] for k in sorted(uniq.keys())]

    rows = []
    for it in ordered:
        try:
            ts = int(it[0])
            open_, high, low, close, volume = map(float, [it[1], it[2], it[3], it[4], it[5]])
            rows.append({
                'open_time': datetime.utcfromtimestamp(ts/1000.0),
                'open': open_, 'high': high, 'low': low, 'close': close, 'volume': float(volume)
            })
        except Exception:
            continue
    df = pd.DataFrame(rows)
    return df


def main():
    parser = argparse.ArgumentParser(description="Run a Backtrader backtest for the gene-driven strategy")
    parser.add_argument('--csv', type=str, help='Path to CSV OHLCV file (columns: open_time/open/high/low/close/volume)')
    parser.add_argument('--symbol', type=str, help='Symbol for Bybit fetch (e.g., BTCUSDT)')
    parser.add_argument('--interval', type=str, default=None, help='Bybit interval (e.g., 5) if fetching')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--printlog', action='store_true')
    args = parser.parse_args()

    cfg = load_config()

    # Data source selection
    if args.csv and os.path.exists(args.csv):
        df = load_csv(args.csv)
        timeframe = 'csv'
    else:
        symbol = args.symbol or cfg.get('symbol', 'BTCUSDT')
        interval = args.interval or cfg.get('timeframe', '5')
        # Pull more data with pagination
        df = load_bybit_klines(symbol, interval, limit=max(args.limit, 3000))
        timeframe = interval

    if df.empty:
        raise SystemExit('No data loaded for backtest')

    engine = BacktestEngine(
        initial_cash=float(cfg.get('initial_balance', 1000.0)),
        commission=0.0006,
    )

    # Map config/gene defaults to strategy params (adjust as needed)
    strat_params = dict(
        trade_perc=float(cfg.get('global_trade_percentage', 0.1)),
        rsi_period=14,
        rsi_buy=35.0,   # используем для fallback-логики
        rsi_sell=65.0,  # порог выхода по RSI
        ema_fast=12,
        ema_slow=26,
        max_bars_in_pos=12,   # держим позицию дольше (около часа для 5м)
        force_first_entry=False,
        decision_tree=[
            # Входы: тренд по EMA и недоперекупленность по RSI
            {'indicator': 'trend_alignment', 'operator': '==', 'value': True, 'action': 'buy'},
            {'indicator': 'rsi', 'operator': '<', 'value': 35, 'action': 'buy'},
            # Выходы: слом тренда или перекупленность
            {'indicator': 'price_below_ema', 'operator': '==', 'value': True, 'action': 'sell'},
            {'indicator': 'rsi', 'operator': '>', 'value': 65, 'action': 'sell'},
        ],
        printlog=args.printlog,
    )

    result = engine.run(GeneDrivenBtStrategy, df, strat_params, timeframe=str(timeframe), printlog=args.printlog)

    print("\nBacktest finished")
    print(f"Final Value: {result.final_value:.2f}")
    print(f"PnL: {result.pnl:.2f} ({result.return_pct:.2f}%)")
    print(f"Sharpe: {result.sharpe_ratio:.3f}")
    print(f"Max DD: {result.max_drawdown_pct:.2f}%")
    print(f"Trades: {result.total_trades}, WinRate: {result.win_rate_pct:.2f}%")


if __name__ == '__main__':
    main()