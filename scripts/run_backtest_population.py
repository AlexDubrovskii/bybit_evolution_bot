import argparse
import os
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd

# Ensure imports from repo
import sys
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backtest.engine import BacktestEngine
from backtest.strategies.gene_driven import GeneDrivenBtStrategy
from config.settings import load_config


def load_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    colmap = {c.lower(): c for c in df.columns}
    def pick(name):
        return colmap.get(name, name)
    if 'open_time' in colmap:
        dt_col = pick('open_time')
        df['open_time'] = pd.to_datetime(df[dt_col])
    elif 'datetime' in colmap:
        dt_col = pick('datetime')
        df['open_time'] = pd.to_datetime(df[dt_col])
    else:
        df['open_time'] = pd.to_datetime(df.iloc[:, 0])
    df = df.rename(columns={
        pick('open'): 'open',
        pick('high'): 'high',
        pick('low'): 'low',
        pick('close'): 'close',
        pick('volume'): 'volume',
    })
    df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']].copy()
    return df


def load_bybit_klines(symbol: str, interval: str, limit: int = 3000, page_size: int = 1000) -> pd.DataFrame:
    from core.bybit_client import BybitClient
    client = BybitClient(testnet=True)
    all_items = []
    fetched = 0
    end_ts = None
    while fetched < limit:
        req_size = min(page_size, limit - fetched)
        raw = client.get_klines(symbol, interval, limit=req_size, end=end_ts) or []
        if not raw:
            break
        try:
            raw.sort(key=lambda x: int(x[0]))
        except Exception:
            pass
        all_items = raw + all_items
        fetched = len(all_items)
        try:
            earliest_ts = int(raw[0][0])
            end_ts = earliest_ts - 1
        except Exception:
            break
        if req_size > 0 and len(raw) < req_size:
            break
    uniq = {}
    for it in all_items:
        try:
            ts = int(it[0]); uniq[ts] = it
        except Exception:
            continue
    ordered = [uniq[k] for k in sorted(uniq.keys())]
    rows = []
    for it in ordered:
        try:
            ts = int(it[0])
            o, h, l, c, v = map(float, [it[1], it[2], it[3], it[4], it[5]])
            rows.append({'open_time': datetime.utcfromtimestamp(ts/1000.0), 'open': o, 'high': h, 'low': l, 'close': c, 'volume': float(v)})
        except Exception:
            continue
    return pd.DataFrame(rows)


def build_population_report(df: pd.DataFrame, results: List[Dict[str, Any]], out_path: str) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.25, 0.15], vertical_spacing=0.03,
                        subplot_titles=("Price", "Equity (top N)", "Volume"))
    # Candles
    fig.add_candlestick(row=1, col=1,
                        x=df['open_time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
                        name='Candles')
    # Signals per robot
    for r in results:
        rid = r['robot_id']
        color = r['color']
        # BUY
        if r['buy_signals']:
            xs = [p[0] for p in r['buy_signals']]
            ys = [p[1] for p in r['buy_signals']]
            hover = [f"Robot {rid}<br>BUY<br>Price: {y:.2f}" for y in ys]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', name=f"R{rid} BUY",
                                     marker=dict(color=color, symbol='triangle-up', size=8, line=dict(width=1, color='black')),
                                     hovertext=hover, hoverinfo='text', legendgroup=f"R{rid}"), row=1, col=1)
        # SELL
        if r['sell_signals']:
            xs = [p[0] for p in r['sell_signals']]
            ys = [p[1] for p in r['sell_signals']]
            hover = [f"Robot {rid}<br>SELL<br>Price: {y:.2f}" for y in ys]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', name=f"R{rid} SELL",
                                     marker=dict(color=color, symbol='triangle-down', size=8, line=dict(width=1, color='black')),
                                     hovertext=hover, hoverinfo='text', legendgroup=f"R{rid}"), row=1, col=1)
        # EXIT
        if r['exit_signals']:
            xs = [p[0] for p in r['exit_signals']]
            ys = [p[1] for p in r['exit_signals']]
            hover = [f"Robot {rid}<br>EXIT<br>Price: {y:.2f}" for y in ys]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', name=f"R{rid} EXIT",
                                     marker=dict(color=color, symbol='x', size=9, line=dict(width=2, color='white')),
                                     hovertext=hover, hoverinfo='text', legendgroup=f"R{rid}"), row=1, col=1)
    # Equity (optional top N)
    for r in results:
        if r.get('equity_curve'):
            xs = [p[0] for p in r['equity_curve']]
            ys = [p[1] for p in r['equity_curve']]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines', name=f"R{r['robot_id']} Equity",
                                     line=dict(color=r['color'], width=1.5), legendgroup=f"R{r['robot_id']}"), row=2, col=1)
    # Volume
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(df['close'], df['open'])]
    fig.add_bar(row=3, col=1, x=df['open_time'], y=df['volume'], marker_color=colors, name='Volume')
    fig.update_layout(template='plotly_dark', title='Population Backtest Report', xaxis_rangeslider_visible=False)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.write_html(out_path)


def main():
    parser = argparse.ArgumentParser(description='Run backtests for N robots and build a combined report')
    parser.add_argument('--csv', type=str, help='Path to CSV OHLCV file')
    parser.add_argument('--symbol', type=str, help='Symbol, e.g., BTCUSDT')
    parser.add_argument('--interval', type=str, default=None, help='Bybit interval, e.g., 5')
    parser.add_argument('--limit', type=int, default=3000)
    parser.add_argument('--count', type=int, default=5, help='Number of robots to simulate')
    parser.add_argument('--report', type=str, required=True, help='Output HTML path')
    parser.add_argument('--printlog', action='store_true')
    args = parser.parse_args()

    cfg = load_config()
    # Load data
    if args.csv and os.path.exists(args.csv):
        df = load_csv(args.csv)
        timeframe = 'csv'
    else:
        symbol = args.symbol or cfg.get('symbol', 'BTCUSDT')
        interval = args.interval or cfg.get('timeframe', '5')
        df = load_bybit_klines(symbol, interval, limit=max(args.limit, 3000))
        timeframe = interval
    if df.empty:
        raise SystemExit('No data loaded')

    # Engine
    engine = BacktestEngine(initial_cash=float(cfg.get('initial_balance', 1000.0)), commission=0.0006)

    # Simple color palette
    palette = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]

    # Common decision tree and params (you can randomize per robot if needed)
    base_params = dict(
        trade_perc=float(cfg.get('global_trade_percentage', 0.1)),
        rsi_period=14,
        rsi_buy=35.0,
        rsi_sell=65.0,
        ema_fast=12,
        ema_slow=26,
        max_bars_in_pos=12,
        force_first_entry=False,
        decision_tree=[
            {'indicator': 'trend_alignment', 'operator': '==', 'value': True, 'action': 'buy'},
            {'indicator': 'rsi', 'operator': '<', 'value': 35, 'action': 'buy'},
            {'indicator': 'price_below_ema', 'operator': '==', 'value': True, 'action': 'sell'},
            {'indicator': 'rsi', 'operator': '>', 'value': 65, 'action': 'sell'},
        ],
    )

    results_for_plot: List[Dict[str, Any]] = []

    for rid in range(args.count):
        params = dict(base_params)
        params['robot_id'] = rid
        res = engine.run(GeneDrivenBtStrategy, df, params, timeframe=str(timeframe), printlog=args.printlog)
        results_for_plot.append({
            'robot_id': rid,
            'color': palette[rid % len(palette)],
            'buy_signals': res.buy_signals,
            'sell_signals': res.sell_signals,
            'exit_signals': res.exit_signals,
            'equity_curve': res.equity_curve,
        })

    build_population_report(df, results_for_plot, args.report)
    print(f"Saved population report to {args.report}")


if __name__ == '__main__':
    main()