import time
import json
from datetime import datetime
from typing import List, Dict, Any
from analysis.metrics import AdvancedMetrics
import numpy as np
from .worker import Robot
from .strategies import SimpleStrategy
from .bybit_client import BybitClient
from evolution.genes import mutate, crossover
from evolution.selection import select_parents
from utils.logger import setup_logger

logger = setup_logger('evolution_manager')

class EvolutionManager:
    def __init__(self, config: Dict[str, Any], client: BybitClient):
        self.config = config
        self.client = client  # Используем переданный клиент
        self.population: List[Robot] = []
        self.generation = 0

        # Оба поля оставляем: history — сводки по поколениям, best_robots — список лучших (serializable dict)
        self.history: List[Dict[str, Any]] = []
        self.best_robots: List[Dict[str, Any]] = []

        # Инициализация стратегии
        self.strategy = SimpleStrategy(self.client)
        
        # Создание начальной популяции
        self.create_initial_population()
        
    def create_initial_population(self):
        """Создание начальной популяции роботов"""
        logger.info(f"Создание начальной популяции из {self.config['population_size']} роботов")
        
        for i in range(self.config['population_size']):
            robot = Robot(
                robot_id=i,
                generation_born=self.generation,
                initial_balance=self.config['initial_balance'],
                strategy=self.strategy,
                gene=self._generate_random_gene()
            )
            self.population.append(robot)
            
        logger.info("Начальная популяция создана")
    
    def _generate_random_gene(self) -> Dict[str, Any]:
        """Генерация случайного гена для робота"""
        return {
            'strategy_type': 'decision_tree',
            'decision_tree': self._generate_random_decision_tree(),
            'trade_percentage': np.random.uniform(0.01, 0.1),  # Случайный % от баланса
            'risk_appetite': np.random.uniform(0.1, 0.9),     # Уровень склонности к риску
            'max_trade_duration': np.random.randint(1, 10)    # Макс. длительность сделки в минутах
        }
    
    def _generate_random_decision_tree(self) -> List[Dict[str, Any]]:
        """Генерация случайного дерева решений"""
        conditions = [
            {'indicator': 'rsi', 'operator': '<', 'value': 30, 'action': 'buy'},
            {'indicator': 'rsi', 'operator': '>', 'value': 70, 'action': 'sell'},
            {'indicator': 'price_above_ema', 'operator': '==', 'value': True, 'action': 'buy'},
            {'indicator': 'price_below_ema', 'operator': '==', 'value': True, 'action': 'sell'},
            {'indicator': 'high_volume', 'operator': '==', 'value': True, 'action': 'buy'},
            {'indicator': 'trend_alignment', 'operator': '==', 'value': True, 'action': 'buy'},
        ]
        
        # Выбираем случайное подмножество условий
        num_conditions = np.random.randint(2, len(conditions))
        return list(np.random.choice(conditions, num_conditions, replace=False))
    
    def run_generation(self):
        """Запуск одного поколения (торгового цикла)"""
        logger.info(f"Запуск поколения {self.generation}")
        start_time = datetime.now()
        
        # Запуск торговли для всех роботов
        for minute in range(self.config['generation_duration_minutes']):
            logger.info(f"Минута {minute + 1} из {self.config['generation_duration_minutes']}")
            
            # Получение текущих рыночных данных
            market_data = self.get_market_data()
            
            for robot in self.population:
                # Каждый робот принимает торговое решение
                robot.trade(self.config['symbol'], market_data)
                
                # Обновляем информацию о прибыли
                robot.update_profit(market_data['current_price'])
            
            # Пауза между минутами (в реальной торговле нужно использовать точное время)
            time.sleep(5)  # Для теста используем 1 секунду вместо 1 минуты
        
        logger.info("Принудительное закрытие всех открытых позиций...")
        for robot in self.population:
            robot.close_all_positions()
        # Оценка результатов поколения
        self.evaluate_generation()
        
        # Создание нового поколения
        self.create_new_generation()
        
        # Сохранение истории
        self.save_generation_history(start_time)
        
        logger.info(f"Поколение {self.generation} завершено")
        self.generation += 1
    
    def get_market_data(self) -> Dict[str, Any]:
        """Получение текущих рыночных данных"""
        try:
            ticker = self.client.get_ticker(self.config['symbol'])
            
            # Получаем текущую цену из правильного поля
            # Структура ответа: {'result': {'list': [{'lastPrice': '50000.00', ...}]}}
            if ticker and 'result' in ticker and 'list' in ticker['result']:
                ticker_data = ticker['result']['list'][0]
                current_price = float(ticker_data.get('lastPrice', 0))
            else:
                current_price = 0
                logger.warning("Не удалось получить данные тикера")
            
            # Получаем исторические данные
            klines = self.client.get_klines(
                self.config['symbol'], 
                self.config['timeframe'], 
                limit=50
            )
            
            # Расчет дополнительных показателей (заглушки для теста)
            global_params = {
                'current_price': current_price,
                'trend_direction': 'bullish',  # Заглушка
                'volatility': 0.02,            # Заглушка
                'support_level': current_price * 0.98,
                'resistance_level': current_price * 1.02,
                'ticker_data': ticker_data if 'ticker_data' in locals() else {}
            }
            
            return global_params
            
        except Exception as e:
            logger.error(f"Ошибка при получении рыночных данных: {e}")
            # Возвращаем данные по умолчанию в случае ошибки
            return {
                'current_price': 50000.0,  # Значение по умолчанию
                'trend_direction': 'bullish',
                'volatility': 0.02,
                'support_level': 49000.0,
                'resistance_level': 51000.0
            }
    
    def evaluate_generation(self):
        """Расширенная оценка результатов поколения с multiple метриками"""
        logger.info("Расширенная оценка результатов поколения")
        
        for robot in self.population:
            # Расчет основных метрик
            profit = robot.current_profit
            returns = robot.returns
            
            # Расширенные метрики
            sharpe_ratio = AdvancedMetrics.calculate_sharpe_ratio(returns)
            max_drawdown = AdvancedMetrics.calculate_max_drawdown(robot.balance_history)
            profit_factor = AdvancedMetrics.calculate_profit_factor(robot.trades)
            win_rate = AdvancedMetrics.calculate_win_rate(robot.trades)
            consistency = AdvancedMetrics.calculate_consistency(returns)
            
            # Базовые компоненты
            profit_component = profit / robot.initial_balance
            risk_component = 1 - max_drawdown
            
            # Взвешенная fitness функция
            robot.fitness = (
                self.config['fitness_weights']['profit'] * profit_component +
                self.config['fitness_weights']['sharpe_ratio'] * sharpe_ratio +
                self.config['fitness_weights']['max_drawdown'] * risk_component +
                self.config['fitness_weights']['profit_factor'] * profit_factor +
                self.config['fitness_weights']['win_rate'] * win_rate +
                self.config['fitness_weights']['consistency'] * consistency
            )
            
            # Логирование метрик для отладки
            logger.debug(f"Робот {robot.robot_id}: "
                        f"Прибыль={profit:.2f}, "
                        f"Шарп={sharpe_ratio:.3f}, "
                        f"Просадка={max_drawdown:.3f}, "
                        f"Проф. фактор={profit_factor:.3f}, "
                        f"Винрейт={win_rate:.3f}, "
                        f"Консистентность={consistency:.3f}, "
                        f"Фитнес={robot.fitness:.6f}")
        
        # Сортировка по fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # Отбор лучших
        best_robot = self.population[0]
        logger.info(f"Лучший робот поколения: ID {best_robot.robot_id}, "
                   f"Фитнес: {best_robot.fitness:.6f}, "
                   f"Прибыль: {best_robot.current_profit:.2f}")
    
    def create_new_generation(self):
        """Создание нового поколения роботов"""
        logger.info("Создание нового поколения")
        
        # Отбор родителей
        parents = select_parents(self.population, elite_size=5)
        
        # Создание нового поколения
        new_population = []
        
        # Добавляем элитных роботов без изменений
        for i in range(min(5, len(parents))):
            elite_robot = parents[i]
            elite_robot.survived_cycles += 1
            new_population.append(elite_robot)
        
        # Создаем потомков от лучших роботов
        while len(new_population) < self.config['population_size']:
            parent_pool = parents[:min(10, len(parents))]
            if len(parent_pool) == 0:
                logger.warning("Недостаточно родителей для создания нового поколения; завершаем досрочно")
                break
            if len(parent_pool) >= 2:
                parent1, parent2 = np.random.choice(parent_pool, 2, replace=False)
            else:
                # Если только один родитель доступен — используем его дважды
                parent1 = parent_pool[0]
                parent2 = parent_pool[0]

            child_gene = crossover(parent1.gene, parent2.gene)
            child_gene = mutate(child_gene)
            
            child = Robot(
                robot_id=len(new_population),
                generation_born=self.generation + 1,
                initial_balance=self.config['initial_balance'],
                strategy=self.strategy,
                gene=child_gene
            )
            
            # Наследование "опыта" от родителей
            child.survived_cycles = max(parent1.survived_cycles, parent2.survived_cycles) - 1
            
            new_population.append(child)
        
        self.population = new_population
    
    def save_generation_history(self, start_time):
        """Сохранение истории поколения"""
        generation_info = {
            'generation': self.generation,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'best_robot': {
                'id': self.population[0].robot_id,
                'profit': self.population[0].current_profit,
                'fitness': self.population[0].fitness
            },
            'avg_profit': np.mean([r.current_profit for r in self.population]),
            'avg_fitness': np.mean([r.fitness for r in self.population])
        }
        
        self.history.append(generation_info)
        
        # Сохранение в файл
        with open(f'data/generation_{self.generation}.json', 'w') as f:
            json.dump(generation_info, f, indent=2)
    
    def save_final_results(self):
        """Сохранение финальных результатов эволюции"""
        last_best = self.best_robots[-1] if self.best_robots else {}
        results = {
            'total_generations': self.generation,
            'best_fitness': float(last_best.get('fitness', 0)) if isinstance(last_best, dict) else 0,
            'best_profit': float(last_best.get('profit', 0)) if isinstance(last_best, dict) else 0,
            'final_population_size': len(self.population),
            'execution_time': (datetime.now() - getattr(self, 'start_time', datetime.now())).total_seconds()
        }
        
        with open('data/final_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    def should_continue_evolution(self):
        """Определение необходимости продолжения эволюции"""
        if self.generation >= self.config.get('max_generations', 20):
            return False
            
        if (self.best_robots and 
            self.best_robots[-1].fitness > self.config.get('target_fitness', 0.3)):
            return False
            
        return True

    def should_continue_evolution(self) -> bool:
        """Проверка условий продолжения эволюции"""
        if self.generation >= 100:  # Максимальное количество поколений
            return False
        
        # Проверка целевой прибыли
        if len(self.best_robots) > 0:
            last_profit = self.best_robots[-1].current_profit
            if last_profit >= self.config['initial_balance'] * 0.1:  # 10% прибыли
                return True
        
        return True