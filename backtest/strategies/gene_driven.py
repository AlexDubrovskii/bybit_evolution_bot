import backtrader as bt

class GeneDrivenBtStrategy(bt.Strategy):
    params = dict(
        # Map of gene-like parameters. Tune these from your evolution gene.
        trade_perc=0.1,          # fraction of cash per trade
        rsi_period=14,
        rsi_buy=30.0,
        rsi_sell=70.0,
        ema_fast=12,
        ema_slow=26,
        volume_sma_period=20,
        decision_tree=None,      # List[ {indicator, operator, value, action} ]
        max_bars_in_pos=0,       # 0 disables time-based exit; >0 closes after N bars
        force_first_entry=False,  # testing aid: take first available entry
        printlog=False,
    )

    def __init__(self):
        # Indicators (common baselines)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        self.ema_fast = bt.indicators.EMA(self.data.close, period=self.p.ema_fast)
        self.ema_slow = bt.indicators.EMA(self.data.close, period=self.p.ema_slow)
        self.vol_sma = bt.indicators.SMA(self.data.volume, period=self.p.volume_sma_period)

        # Track pending order to avoid stacking
        self.order = None
        self.bars_in_pos = 0
        self.did_first_entry = False

    def log(self, txt):
        if self.p.printlog:
            dt = self.datas[0].datetime.datetime(0)
            print(f"{dt} - {txt}")

    def _eval_condition(self, cond) -> bool:
        ind = cond.get('indicator')
        op = cond.get('operator')
        val = cond.get('value')
        # Map indicators to current values
        current = None
        if ind == 'rsi':
            current = float(self.rsi[0])
        elif ind == 'price_above_ema':
            current = float(self.data.close[0] > self.ema_slow[0])
        elif ind == 'price_below_ema':
            current = float(self.data.close[0] < self.ema_slow[0])
        elif ind in ('high_volume', 'volume'):
            # Treat as ratio vs SMA
            if self.vol_sma[0] != 0:
                current = float(self.data.volume[0] / self.vol_sma[0])
            else:
                current = 0.0
        elif ind == 'trend_alignment':
            current = float(self.ema_fast[0] > self.ema_slow[0])
        else:
            return False

        # If condition expects boolean equality
        if op == '==' and isinstance(val, bool):
            return bool(current) == val

        # Numeric comparisons
        try:
            current_val = float(current)
            target = float(val)
        except Exception:
            return False

        if op == '<':
            return current_val < target
        if op == '>':
            return current_val > target
        if op == '==':
            return current_val == target
        return False

    def _decide_action(self) -> str:
        # If no decision_tree provided, fall back to simple RSI/EMA rule
        tree = self.p.decision_tree or []
        if not tree:
            if (self.rsi[0] < self.p.rsi_buy) and (self.ema_fast[0] > self.ema_slow[0]):
                return 'buy'
            if (self.rsi[0] > self.p.rsi_sell) and self.position.size > 0:
                return 'sell'
            return 'hold'
        # Evaluate all conditions; if any action mapped conditions satisfied, choose first match
        for cond in tree:
            try:
                if self._eval_condition(cond):
                    return cond.get('action', 'hold')
            except Exception:
                continue
        return 'hold'

    def next(self):
        if self.order:
            return  # wait for order resolution

        cash = self.broker.getcash()
        price = float(self.data.close[0])
        if price <= 0:
            return

        # Time-based exit
        if self.position:
            self.bars_in_pos += 1
            if int(self.p.max_bars_in_pos) > 0 and self.bars_in_pos >= int(self.p.max_bars_in_pos):
                self.order = self.close()
                self.log(f"TIME EXIT size={self.position.size} price={price:.2f} bars={self.bars_in_pos}")
                self.bars_in_pos = 0
                return
        else:
            self.bars_in_pos = 0

        action = self._decide_action()

        # Optional forced first entry for testing
        if self.p.force_first_entry and not self.did_first_entry and not self.position:
            action = 'buy'

        if action == 'buy' and not self.position:
            stake_value = cash * float(self.p.trade_perc)
            size = stake_value / price  # allow fractional crypto sizing
            if size > 0:
                self.order = self.buy(size=size)
                self.did_first_entry = True
                self.log(f"BUY size={size:.6f} price={price:.2f}")
        elif action == 'sell' and self.position:
            self.order = self.close()
            self.log(f"SELL EXIT size={self.position.size} price={price:.2f}")
        else:
            # hold
            pass

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Rejected, order.Margin]:
            self.order = None
