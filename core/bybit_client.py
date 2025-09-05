# core/bybit_client.py
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv
import logging
from typing import Dict, Any  # Добавляем необходимые импорты
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()

logger = logging.getLogger('bybit_client')

class BybitClient:
    def __init__(self, testnet=True):
        self.testnet = testnet
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        # Инициализация сессии
        self.session = HTTP(
            testnet=self.testnet,
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        
        logger.info("BybitClient инициализирован")
    
    def get_account_balance(self):
        """Получение баланса аккаунта"""
        try:
            response = self.session.get_wallet_balance(accountType="UNIFIED")
            if response and 'result' in response:
                # Для Unified Trading Account баланс находится по этому пути
                total_balance = response['result']['list'][0]['totalWalletBalance']
                return float(total_balance)
            return 0.0
        except Exception as e:
            logger.error(f"Ошибка при получении баланса: {e}")
            return 0.0
    
    def get_ticker(self, symbol):
        """Получение информации о тикере"""
        try:
            response = self.session.get_tickers(
                category="linear",
                symbol=symbol
            )
            print(f"Raw ticker response: {response}")  # Для отладки
            
            if (response and 'result' in response and 
                'list' in response['result'] and 
                response['result']['list']):
                return response
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении тикера: {e}")
            return None
    
    def get_klines(self, symbol, interval, limit=100):
        """Получение исторических данных (свечей)"""
        try:
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            if response and 'result' in response:
                return response['result']['list']
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении свечей: {e}")
            return []
    
    def place_order(self, symbol: str, side: str, order_type: str, qty: float, price: float = None) -> Dict[str, Any]:
        """Размещение ордера с гибкой проверкой минимального объема"""
        try:
            # Добавим логирование перед размещением
            logger.info(f"Попытка размещения ордера: {side} {qty} {symbol} по цене {price}")
            # Определяем минимальный объем в зависимости от символа
            min_qty_rules = {
                'BTCUSDT': 0.001,   # Минимальный объем для BTCUSDT
                'DOGEUSDT': 100.0,   # Минимальный объем для DOGEUSDT (100 DOGE)
                # Добавьте другие пары по мере необходимости
            }
            
            # Получаем минимальный объем для символа или используем значение по умолчанию
            min_qty = min_qty_rules.get(symbol, 1.0)  # Значение по умолчанию - 1
            
            if qty < min_qty:
                logger.warning(f"Объем {qty} меньше минимального {min_qty} для {symbol}")
                # Для некоторых пар можно увеличить объем до минимального
                qty = min_qty
                
            # Проверяем, что цена указана для лимитных ордеров
            if order_type == "Limit" and price is None:
                logger.error("Для лимитного ордера должна быть указана цена")
                return {}
            
            # Проверяем, что цена положительная
            if price is not None and price <= 0:
                logger.error(f"Некорректная цена: {price}")
                return {}
            
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(qty),
                "timeInForce": "GTC"
            }
            
            if price:
                order_params["price"] = str(price)
                
            response = self.session.place_order(**order_params)
            if response and 'result' in response:
                logger.info(f"Ордер размещен: {response['result']['orderId']}")
                return response['result']
            return {}
        except Exception as e:
            # Убираем emoji из сообщения об ошибке для избежания проблем с кодировкой
            error_msg = str(e).replace('✅', '').replace('💰', '').replace('→', '->')
            logger.error(f"Ошибка при размещении ордера: {error_msg}")
            return {}
    
    def get_open_orders(self, symbol):
        """Получение списка открытых ордеров"""
        try:
            response = self.session.get_open_orders(
                category="linear",
                symbol=symbol
            )
            if response and 'result' in response:
                return response['result']['list']
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении ордеров: {e}")
            return []
    
    def cancel_order(self, symbol, order_id):
        """Отмена ордера"""
        try:
            response = self.session.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            if response and 'result' in response:
                logger.info(f"Ордер отменен: {response['result']}")
                return response['result']
            return None
        except Exception as e:
            logger.error(f"Ошибка при отмене ордера: {e}")
            return None
    
    def get_positions(self, symbol):
        """Получение информации о позициях"""
        try:
            response = self.session.get_positions(
                category="linear",
                symbol=symbol
            )
            if response and 'result' in response:
                return response['result']['list']
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении позиций: {e}")
            return []
    
    def get_api_key_info(self):
        """Получение информации о API ключе"""
        try:
            response = self.session.get_api_key_information()
            if response and 'result' in response:
                return response['result']
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении информации о API ключе: {e}")
            return None
        
    def get_market_data(self) -> Dict[str, Any]:
        """Получение текущих рыночных данных (временная заглушка)"""
        try:
            # Пытаемся получить реальные данные
            ticker = self.client.get_ticker(self.config['symbol'])
            
            if ticker and 'result' in ticker and 'list' in ticker['result'] and ticker['result']['list']:
                ticker_data = ticker['result']['list'][0]
                current_price = float(ticker_data.get('lastPrice', 50000.0))
            else:
                # Используем заглушку если не удалось получить данные
                current_price = 50000.0 + (self.generation * 100)  # Имитируем движение цены
                logger.warning("Используются тестовые данные")
            
            # Расчет дополнительных показателей
            global_params = {
                'current_price': current_price,
                'trend_direction': 'bullish' if current_price > 50000 else 'bearish',
                'volatility': 0.02,
                'support_level': current_price * 0.98,
                'resistance_level': current_price * 1.02,
                'timestamp': datetime.now()
            }
            
            return global_params
            
        except Exception as e:
            logger.error(f"Ошибка при получении рыночных данных: {e}")
            # Возвращаем тестовые данные
            return {
                'current_price': 50000.0 + (self.generation * 100),
                'trend_direction': 'bullish',
                'volatility': 0.02,
                'support_level': 49000.0,
                'resistance_level': 51000.0,
                'timestamp': datetime.now()
            }