# main.py
from core.bybit_client import BybitClient
from core.master import EvolutionManager
from analysis.visualizer import RaceVisualizer, MetricsVisualizer
from config.settings import load_config
import logging
import time
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/evolution.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Создаем папки для данных если их нет
        os.makedirs('logs', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        # Загрузка конфигурации
        logger.info("Загрузка конфигурации...")
        config = load_config()
        
        # Инициализация клиента API
        logger.info("Инициализация клиента API...")
        client = BybitClient(testnet=config['testnet'])
        
        # Проверка подключения
        logger.info("Проверка подключения к API...")
        key_info = client.get_api_key_info()
        if key_info:
            logger.info(f"[УСПЕХ] API Key информация получена:")
            logger.info(f"   - Права: {key_info.get('permissions', {})}")
            logger.info(f"   - UTA статус: {key_info.get('uta', 'N/A')} (1 = UTA аккаунт)")
        else:
            logger.warning("Не удалось получить информацию о API ключе")
        
        # Проверка баланса
        logger.info("Проверка баланса...")
        balance = client.get_account_balance()
        logger.info(f"[БАЛАНС] Баланс кошелька: {balance} USDT")
        
        # Проверка минимального баланса
        min_balance = 100.0
        if balance < min_balance:
            logger.error(f"Недостаточный баланс: {balance} < {min_balance}. Пополните тестовый счет.")
            return
        
        # Тестирование получения тикера
        logger.info("Тестирование получения данных тикера...")
        ticker = client.get_ticker(config['symbol'])
        logger.info(f"Данные тикера получены: {bool(ticker)}")
        
        # Создание мастера эволюции
        logger.info("Создание мастера эволюции...")
        evolution_manager = EvolutionManager(config, client)
        
        # Создание визуализаторов
        logger.info("Создание визуализаторов...")
        race_visualizer = RaceVisualizer(evolution_manager)
        metrics_visualizer = MetricsVisualizer()
        
        # Основной цикл эволюции
        logger.info("Запуск основного цикла эволюции...")
        generation_count = 0
        max_generations = 10  # Увеличим количество поколений
        
        while generation_count < max_generations and evolution_manager.should_continue_evolution():
            logger.info(f"=== ПОКОЛЕНИЕ {generation_count} ===")
            
            try:
                # Запуск поколения
                evolution_manager.run_generation()
                logger.info(f"Поколение {generation_count} завершено успешно")
                
                # Обновление визуализации
                race_visualizer.update()
                
                # Визуализация метрик
                metrics_visualizer.plot_generation_metrics(evolution_manager)
                
                # Сохранение лучших роботов если превышен порог fitness
                if (evolution_manager.best_robots and 
                    evolution_manager.best_robots[-1].fitness > config.get('fitness_threshold', 0.15)):
                    evolution_manager.save_best_robots()
                
            except Exception as e:
                logger.error(f"Ошибка в поколении {generation_count}: {e}")
                import traceback
                traceback.print_exc()
                # Продолжаем выполнение несмотря на ошибку
            
            generation_count += 1
            time.sleep(2)  # Пауза между поколениями
        
        # Финальный отчет
        logger.info("=== ЭВОЛЮЦИЯ ЗАВЕРШЕНА ===")
        
        if hasattr(evolution_manager, 'best_robots') and evolution_manager.best_robots:
            best_robot = evolution_manager.best_robots[-1]
            logger.info(f"Лучший робот: ID {best_robot.robot_id}")
            logger.info(f"Прибыль: {best_robot.current_profit:.2f} USDT")
            logger.info(f"Фитнес: {best_robot.fitness:.6f}")
            logger.info(f"Поколение рождения: {best_robot.generation_born}")
            logger.info(f"Пережито циклов: {best_robot.survived_cycles}")
        else:
            logger.info("Нет данных о лучших роботах")
            
        # Сохранение финальных результатов
        evolution_manager.save_final_results()
        
    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()