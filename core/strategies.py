import talib
import random
import numpy as np
from utils.logger import setup_logger
logger = setup_logger('robot')

class SimpleStrategy:
    def __init__(self, client):
        self.client = client
        self.name = "simple_random"
        
    def generate_signal(self, symbol, market_data, robot=None):
        """Генерация торгового сигнала с использованием % от баланса"""
        current_price = market_data['current_price']
        
        # Увеличим частоту торгов для более volatile актива like DOGE
        decision = random.choice(['buy', 'sell', 'hold', 'buy', 'sell'])  # Чаще торгуем
              
         # Увеличим базовый процент торговли для DOGE
        base_trade_percentage = 0.1  # 10% вместо 5%

        # Определяем объем в зависимости от символа
        if symbol == "DOGEUSDT":
            trade_percentage = robot.gene.get('trade_percentage', 0.1)  # 10% для DOGE
            usd_amount = robot.balance * trade_percentage
            qty = usd_amount / current_price
            qty = round(qty, 0)  # Округляем до целого числа DOGE
        else:
            # Логика для других символов (BTCUSDT)
            trade_percentage = robot.gene.get('trade_percentage', 0.05)
            usd_amount = robot.balance * trade_percentage
            qty = usd_amount / current_price
            qty = round(qty, 4)  # 4 знака для BTC

        if robot:
            # Используем персональный процент робота или базовый
            trade_percentage = robot.gene.get('trade_percentage', base_trade_percentage)
            usd_amount = robot.balance * trade_percentage
            
            # В метод generate_signal после расчета объема
            logger.debug(f"Робот {robot.robot_id if robot else 'N/A'}: "
                        f"баланс={robot.balance if robot else 'N/A'}, "
                        f"процент={trade_percentage}, "
                        f"объем={qty} {symbol}")

            # Для DOGE убедимся, что объем не меньше минимального
            if symbol == "DOGEUSDT":
                min_usd_amount = 100 * current_price  # Минимальная сумма в USDT для 100 DOGE
                if usd_amount < min_usd_amount:
                    usd_amount = min_usd_amount * 1.2  # Добавляем 20% запаса
                
            qty = usd_amount / current_price
            
            # Округляем объем в зависимости от символа
            if symbol == "DOGEUSDT":
                qty = round(qty)  # Целое число для DOGE
            else:
                qty = round(qty, 4)  # 4 знака для BTC
        else:
            # Запасной вариант
            qty = 100  # Минимальный объем для DOGE
        
        if decision == 'buy':
            buy_price = round(current_price * 0.99, 2)
            return {
                'action': 'buy',
                'price': buy_price,
                'qty': qty,
                'reason': f'buy_signal_at_{buy_price}'
            }
        elif decision == 'sell':
            sell_price = round(current_price * 1.01, 2)
            return {
                'action': 'sell',
                'price': sell_price,
                'qty': qty,
                'reason': f'sell_signal_at_{sell_price}'
            }
        else:
           return {
            'action': 'hold',
            'price': current_price,  # ✅ Добавляем цену даже для hold
            'qty': 0,
            'reason': 'no_clear_signal'
        }

class AdvancedStrategy:
    def __init__(self, client):
        self.client = client
        self.name = "advanced_technical"
        
    def calculate_indicators(self, historical_data):
        closes = np.array([float(x[4]) for x in historical_data])
        
        # RSI
        rsi = talib.RSI(closes, timeperiod=14)
        
        # MACD
        macd, macd_signal, macd_hist = talib.MACD(closes)
        
        # Bollinger Bands
        upper_band, middle_band, lower_band = talib.BBANDS(closes)
        
        return {
            'rsi': rsi[-1],
            'macd': macd[-1],
            'macd_signal': macd_signal[-1],
            'bb_upper': upper_band[-1],
            'bb_middle': middle_band[-1],
            'bb_lower': lower_band[-1]
        }
    
    def generate_signal(self, symbol, market_data, robot=None):
        # Получаем исторические данные
        klines = self.client.get_klines(symbol, "5", limit=50)
        indicators = self.calculate_indicators(klines)
        
        # Создаем сложное правило на основе индикаторов
        signal = self.complex_decision(indicators, market_data, robot)
        return signal