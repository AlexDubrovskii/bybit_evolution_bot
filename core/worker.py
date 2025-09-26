import random
from datetime import datetime
from time import time
from typing import Any, Dict
from utils.logger import setup_logger
logger = setup_logger('robot')

class Robot:
    def __init__(self, robot_id, generation_born, initial_balance, strategy, gene=None):
        self.robot_id = robot_id
        self.generation_born = generation_born
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.strategy = strategy
        self.gene = gene if gene else self._generate_random_gene()
        # Список позиций: [{'symbol': str, 'qty': float, 'avg_price': float}]
        self.positions = []
        self.trades = []
        self.children_count = 0
        self.current_profit = 0.0
        self.survived_cycles = 0
        self.fitness = 0.0
        self.balance_history = [initial_balance]
        self.returns = []
        self.trades = []  # Более детальная информация о сделках
        
    def _get_position(self, symbol):
        for p in self.positions:
            if p['symbol'] == symbol:
                return p
        return None

    def _update_position_on_buy(self, symbol: str, qty: float, price: float):
        pos = self._get_position(symbol)
        if pos is None:
            self.positions.append({'symbol': symbol, 'qty': qty, 'avg_price': price})
            return
        total_qty = pos['qty'] + qty
        if total_qty <= 0:
            # Защита от аномалий
            pos['qty'] = 0.0
            pos['avg_price'] = 0.0
            return
        pos['avg_price'] = (pos['avg_price'] * pos['qty'] + price * qty) / total_qty
        pos['qty'] = total_qty

    def _update_position_on_sell(self, symbol: str, qty: float):
        pos = self._get_position(symbol)
        if pos is None:
            return
        pos['qty'] -= qty
        if pos['qty'] <= 1e-12:
            # Удаляем позицию если закрыта
            self.positions = [p for p in self.positions if p['symbol'] != symbol]

    def _min_qty_for_symbol(self, symbol: str) -> float:
        # Минимальные объемы для отправки ордеров (для проверки до запроса)
        rules = {
            'BTCUSDT': 0.001,
            'DOGEUSDT': 100.0,
        }
        return rules.get(symbol, 1.0)
        
    def trade(self, symbol, market_data):
        """Выполнение торговой операции с проверкой баланса и управлением позицией"""
        # Запоминаем последний символ для служебных операций (закрытие и т.п.)
        self.last_symbol = symbol
        # Передаем self (робота) в метод generate_signal
        signal = self.strategy.generate_signal(symbol, market_data, self)
        
        action = signal['action']
        desired_qty = float(signal['qty'])
        price_hint = float(signal['price'])
        min_qty = self._min_qty_for_symbol(symbol)

        # Оценка стоимости ордера по сигналу (предварительная)
        est_order_cost = price_hint * desired_qty
        
        # Проверяем достаточно ли средств по оценочной цене
        if action == 'buy' and est_order_cost > self.balance:
            logger.debug(f"Робот {self.robot_id}: недостаточно средств. Нужно {est_order_cost}, есть {self.balance}")
            return False
            
        if action == 'sell':
            pos = self._get_position(symbol)
            if pos is None or pos['qty'] <= 0:
                logger.debug(f"Робот {self.robot_id}: нет позиции для продажи")
                return False
            # Корректируем объем продажи не больше доступной позиции
            desired_qty = min(desired_qty, pos['qty'])
            # Защита: если меньше минимального лота — пропускаем
            if desired_qty < min_qty:
                logger.debug(f"Робот {self.robot_id}: объем продажи {desired_qty} меньше минимального {min_qty}")
                return False
        
        try:
            if action == 'buy':
                order = self.strategy.client.place_order(
                    symbol=symbol,
                    side="Buy",
                    order_type="Market",
                    qty=desired_qty,
                )
                if order:
                    # Используем фактическую цену исполнения, если она есть
                    executed_price = float(order.get('executedPrice', price_hint))
                    order_cost = executed_price * desired_qty
                    # Вычитаем стоимость из баланса по фактической цене
                    self.balance -= order_cost
                    # Обновляем позицию
                    self._update_position_on_buy(symbol, desired_qty, executed_price)
                    # Лог сделки
                    self.trades.append({
                        'action': 'buy',
                        'price': executed_price,
                        'qty': desired_qty,
                        'timestamp': datetime.now(),
                        'cost': order_cost,
                        'orderId': order.get('orderId')
                    })
                    return True
                    
            elif action == 'sell':
                order = self.strategy.client.place_order(
                    symbol=symbol,
                    side="Sell",
                    order_type="Market",
                    qty=desired_qty,
                    reduce_only=True,
                )
                if order:
                    executed_price = float(order.get('executedPrice', price_hint))
                    # Добавляем выручку к балансу по фактической цене
                    revenue = executed_price * desired_qty
                    self.balance += revenue
                    # Обновляем позицию (уменьшаем)
                    self._update_position_on_sell(symbol, desired_qty)
                    # Лог сделки
                    self.trades.append({
                        'action': 'sell',
                        'price': executed_price,
                        'qty': desired_qty,
                        'timestamp': datetime.now(),
                        'revenue': revenue,
                        'orderId': order.get('orderId')
                    })
                    return True
                    
        except Exception as e:
            logger.warning(f"Робот {self.robot_id} не смог разместить ордер: {str(e)[:100]}...")
            
        return False
        
    def update_profit(self, current_price):
        """Обновление информации о прибыли"""
        # Здесь будет логика расчета текущей прибыли
        # Пока просто случайное значение для теста
        self.current_profit = random.uniform(-0.05, 0.1) * self.initial_balance
        return self.current_profit
    
    def update_after_trade(self, trade_result: Dict[str, Any]):
        self.trades.append(trade_result)
        current_balance = self.balance
        previous_balance = self.balance_history[-1]
        
        # Расчет доходности
        if previous_balance > 0:
            returns = (current_balance - previous_balance) / previous_balance
            self.returns.append(returns)
        
        self.balance_history.append(current_balance)

    def stop(self):
        self.is_running = False

    def close_all_positions(self):
            """Закрыть все открытые длинные позиции по последнему символу через клиента (reduceOnly Market)."""
            try:
                client = getattr(self.strategy, 'client', None)
                symbol = getattr(self, 'last_symbol', None)
                if not client or not symbol:
                    return
                # Закрываем длинные позиции на бирже
                client.close_all_longs(symbol)
                # Синхронно очищаем локальные позиции по этому символу
                self.positions = [p for p in self.positions if p['symbol'] != symbol]
            except Exception as e:
                logger.error(f"Робот {self.robot_id}: Ошибка при принудительном закрытии позиций: {e}")
