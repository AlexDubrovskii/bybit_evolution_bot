import random
from datetime import datetime
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
        self.positions = []
        self.trades = []
        self.children_count = 0
        self.current_profit = 0.0
        self.survived_cycles = 0
        self.fitness = 0.0
        self.balance_history = [initial_balance]
        self.returns = []
        self.trades = []  # Более детальная информация о сделках
        
    def trade(self, symbol, market_data):
        """Выполнение торговой операции с проверкой баланса"""
        # Передаем self (робота) в метод generate_signal
        signal = self.strategy.generate_signal(symbol, market_data, self)
        
        # Рассчитываем стоимость ордера
        order_cost = signal['price'] * signal['qty']
        
        # Проверяем достаточно ли средств
        if signal['action'] == 'buy' and order_cost > self.balance:
            logger.debug(f"Робот {self.robot_id}: недостаточно средств. Нужно {order_cost}, есть {self.balance}")
            return False
            
        if signal['action'] == 'sell' and not any(p['symbol'] == symbol for p in self.positions):
            logger.debug(f"Робот {self.robot_id}: нет позиции для продажи")
            return False
        
        try:
            if signal['action'] == 'buy':
                order = self.strategy.client.place_order(
                    symbol=symbol,
                    side="Buy",
                    order_type="Limit",
                    qty=signal['qty'],
                    price=signal['price']
                )
                if order:
                    # Вычитаем стоимость из баланса
                    self.balance -= order_cost
                    self.trades.append({
                        'action': 'buy',
                        'price': signal['price'],
                        'qty': signal['qty'],
                        'timestamp': datetime.now(),
                        'cost': order_cost
                    })
                    return True
                    
            elif signal['action'] == 'sell':
                order = self.strategy.client.place_order(
                    symbol=symbol,
                    side="Sell",
                    order_type="Limit",
                    qty=signal['qty'],
                    price=signal['price']
                )
                if order:
                    # Добавляем выручку к балансу
                    revenue = signal['price'] * signal['qty']
                    self.balance += revenue
                    self.trades.append({
                        'action': 'sell',
                        'price': signal['price'],
                        'qty': signal['qty'],
                        'timestamp': datetime.now(),
                        'revenue': revenue
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