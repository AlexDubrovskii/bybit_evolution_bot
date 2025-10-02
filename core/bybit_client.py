# core/bybit_client.py
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv
import logging
from typing import Dict, Any, List  # Добавляем необходимые импорты
from datetime import datetime
import time
from decimal import Decimal, ROUND_DOWN

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

        # Cache for instrument filters to avoid repetitive API calls
        self._filters_cache: Dict[str, Dict[str, Any]] = {}
        
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
            # Убрали шумный вывод сырого тикера
            if (response and 'result' in response and 
                'list' in response['result'] and 
                response['result']['list']):
                return response
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении тикера: {e}")
            return None

    def _get_symbol_filters(self, symbol: str) -> Dict[str, Decimal]:
        """Получить фильтры инструмента (шаг и минимум для количества и цены) и кешировать их."""
        if symbol in self._filters_cache:
            return self._filters_cache[symbol]
        try:
            info = self.session.get_instruments_info(category="linear", symbol=symbol)
            item = None
            if info and 'result' in info and info['result'].get('list'):
                item = info['result']['list'][0]
            if not item:
                raise RuntimeError("Пустой ответ get_instruments_info")
            lot = item.get('lotSizeFilter', {}) or {}
            price_filter = item.get('priceFilter', {}) or {}
            qty_step = Decimal(str(lot.get('qtyStep', '1')))
            min_qty = Decimal(str(lot.get('minOrderQty', '1')))
            tick_size = Decimal(str(price_filter.get('tickSize', '0.01')))
        except Exception as e:
            logger.warning(f"Не удалось получить фильтры инструмента {symbol}: {e}")
            defaults = {
                'BTCUSDT': (Decimal('0.001'), Decimal('0.001'), Decimal('0.1')),
                'DOGEUSDT': (Decimal('1'), Decimal('100'), Decimal('0.0001')),
            }
            qty_step, min_qty, tick_size = defaults.get(symbol, (Decimal('1'), Decimal('1'), Decimal('0.01')))
        filters = {'qty_step': qty_step, 'min_qty': min_qty, 'tick_size': tick_size}
        self._filters_cache[symbol] = filters
        return filters

    def _format_decimal(self, value: Decimal) -> str:
        """Форматировать Decimal без экспоненты и лишних нулей."""
        s = format(value.normalize(), 'f')
        if s.startswith('.'):
            s = '0' + s
        if s == '-0':
            s = '0'
        return s

    def _quantize_to_step(self, value: Decimal, step: Decimal) -> Decimal:
        if step <= 0:
            return value
        # Округляем вниз к ближайшему кратному шагу
        return (value // step) * step

    def _quantize_qty(self, symbol: str, qty: float) -> str:
        filters = self._get_symbol_filters(symbol)
        step = filters['qty_step']
        min_qty = filters['min_qty']
        q = Decimal(str(qty))
        quantized = self._quantize_to_step(q, step)
        if quantized < min_qty:
            quantized = min_qty
        return self._format_decimal(quantized)

    def _quantize_price(self, symbol: str, price: float) -> str:
        filters = self._get_symbol_filters(symbol)
        ts = filters['tick_size']
        p = Decimal(str(price))
        quantized = self._quantize_to_step(p, ts)
        return self._format_decimal(quantized)

    def _get_top_of_book_price(self, symbol: str, side: str) -> float:
        """Возвращает лучшую цену из тикера: для Buy -> ask1Price, для Sell -> bid1Price."""
        ticker = self.get_ticker(symbol)
        try:
            if ticker and 'result' in ticker and 'list' in ticker['result'] and ticker['result']['list']:
                item = ticker['result']['list'][0]
                if side.lower() == 'buy':
                    p = item.get('ask1Price')
                else:
                    p = item.get('bid1Price')
                return float(p) if p is not None and p != '' else None
        except Exception:
            pass
        return None
    
    def get_klines(self, symbol, interval, limit=100, start: int = None, end: int = None):
        """Получение исторических данных (свечей).
        start и end в миллисекундах (UTC). Если не заданы — вернутся последние свечи.
        """
        try:
            params = dict(category="linear", symbol=symbol, interval=interval, limit=limit)
            if start is not None:
                params["start"] = int(start)
            if end is not None:
                params["end"] = int(end)
            response = self.session.get_kline(**params)
            if response and 'result' in response:
                return response['result']['list']
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении свечей: {e}")
            return []
    
    def _get_executed_price(self, symbol: str, order_id: str, retries: int = 5, delay: float = 0.3) -> float:
        """Получение средней цены исполнения ордера по orderId (VWAP по исполненным сделкам)."""
        try:
            for _ in range(retries):
                # Пытаемся получить список исполнений
                execs = self.session.get_executions(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                )
                if execs and 'result' in execs and execs['result'].get('list'):
                    fills: List[dict] = execs['result']['list']
                    total_qty = 0.0
                    total_notional = 0.0
                    for fill in fills:
                        # execQty и execPrice приходят строками
                        qty = float(fill.get('execQty', 0) or 0)
                        price = float(fill.get('execPrice', 0) or 0)
                        total_qty += qty
                        total_notional += qty * price
                    if total_qty > 0:
                        return total_notional / total_qty
                time.sleep(delay)
        except Exception as e:
            logger.warning(f"Не удалось получить executions для ордера {order_id}: {e}")
        
        # Фолбэк: пытаемся взять из истории ордеров (avgPrice)
        try:
            history = self.session.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            if history and 'result' in history and history['result'].get('list'):
                item = history['result']['list'][0]
                avg_price = item.get('avgPrice') or item.get('price')
                if avg_price is not None:
                    return float(avg_price)
        except Exception as e:
            logger.warning(f"Не удалось получить историю ордера {order_id}: {e}")
        
        return 0.0
    
    def place_order(self, symbol: str, side: str, order_type: str, qty: float, price: float = None, reduce_only: bool = False) -> Dict[str, Any]:
        """Размещение ордера. Возвращает результат с полем executedPrice для рыночных ордеров.
        Мягко обходит защиту 30208 на тестнете: рыночный ордер = IOC; при отказе 30208 -> лимит IOC по лучшей цене стакана.
        reduce_only=True ограничит ордер только уменьшением позиции (не откроет реверс/новую).
        """
        try:
            # Добавим логирование перед размещением
            logger.info(f"Попытка размещения ордера: {side} {qty} {symbol} по цене {price}")
            # Корректируем объем под биржевые ограничения (minQty, qtyStep)
            q_before = Decimal(str(qty))
            qty_str = self._quantize_qty(symbol, qty)
            q_after = Decimal(qty_str)
            if q_after != q_before:
                logger.info(f"Корректировка объема: {q_before} -> {qty_str} по правилам биржи")

            # Проверяем, что цена указана для лимитных ордеров
            if order_type == "Limit" and price is None:
                logger.error("Для лимитного ордера должна быть указана цена")
                return {}
            
            # Проверяем, что цена положительная
            if price is not None and price <= 0:
                logger.error(f"Некорректная цена: {price}")
                return {}
            
            # Базовые параметры
            tif = "IOC" if order_type.lower() == "market" else "GTC"
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": qty_str,
                "timeInForce": tif,
            }
            if reduce_only:
                # reduceOnly поддерживается для линейных контрактов
                order_params["reduceOnly"] = True
            
            if price is not None:
                # Приводим цену к шагу цены при необходимости (для Limit)
                order_params["price"] = self._quantize_price(symbol, price)
                
            used_params = order_params
            try:
                response = self.session.place_order(**order_params)
            except Exception as e:
                # Проверка на 30208 -> fallback
                if "30208" in str(e):
                    tob_price = self._get_top_of_book_price(symbol, side)
                    if tob_price is None:
                        logger.error("Fallback невозможен: нет лучшей цены стакана")
                        raise
                    order_params_fallback = dict(order_params)
                    order_params_fallback.update({
                        "orderType": "Limit",
                        "price": self._quantize_price(symbol, tob_price),
                        "timeInForce": "IOC",
                    })
                    if reduce_only:
                        order_params_fallback["reduceOnly"] = True
                    used_params = order_params_fallback
                    logger.info(f"Fallback 30208 -> Limit IOC @ {order_params_fallback['price']}")
                    response = self.session.place_order(**order_params_fallback)
                else:
                    # Короткое сообщение об ошибке заказа (без не-ASCII символов)
                    safe_msg = str(e).replace('✅', '').replace('💰', '').replace('→', '->')
                    logger.error(f"Ошибка размещения ордера: {safe_msg[:200]}")
                    raise
            
            if response and 'result' in response:
                result = response['result']
                order_id = result.get('orderId')
                # Для рыночного ордера или лимит-IOC fallback получаем фактическую цену исполнения
                exec_price = self._get_executed_price(symbol, order_id)
                executed_price = exec_price if exec_price > 0 else None
                
                # Короткое сводное сообщение об ордере
                summary_price = used_params.get("price") if isinstance(used_params.get("price"), str) else str(used_params.get("price", ""))
                logger.info(
                    f"ORDER: id={order_id} side={side} symbol={symbol} type={used_params.get('orderType')} "
                    f"tif={used_params.get('timeInForce')} qty={used_params.get('qty')} price={summary_price or '-'} "
                    f"execPrice={executed_price if executed_price is not None else '-'}"
                )
                
                # Возвращаем расширенный результат
                enriched = dict(result)
                if executed_price is not None:
                    enriched['executedPrice'] = executed_price
                return enriched
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

    def close_all_longs(self, symbol: str) -> bool:
        """Закрыть все длинные позиции по инструменту reduceOnly Market ордером.
        Возвращает True, если позиций нет или ордер отправлен успешно.
        """
        try:
            positions = self.get_positions(symbol)
            long_qty_total = 0.0
            for p in positions:
                side = (p.get('side') or '').lower()
                # В V5 long обычно side='Buy'
                if side == 'buy' or side == 'long':
                    size = p.get('size') or p.get('qty') or p.get('positionQty') or 0
                    try:
                        long_qty_total += float(size)
                    except Exception:
                        pass
            if long_qty_total <= 0:
                logger.info(f"Нет длинных позиций для закрытия по {symbol}")
                return True

            # Отправляем reduceOnly Market Sell на весь объем
            logger.info(f"Закрываем long по {symbol}: qty={long_qty_total}")
            res = self.place_order(
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=long_qty_total,
                reduce_only=True,
            )
            ok = bool(res)
            if ok:
                logger.info(f"Запрос на закрытие long по {symbol} отправлен: {res.get('orderId', '-')}")
            else:
                logger.error(f"Не удалось отправить ордер на закрытие long по {symbol}")
            return ok
        except Exception as e:
            logger.error(f"Ошибка при закрытии long по {symbol}: {e}")
            return False
    
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
