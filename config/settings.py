# config/settings.py
import json
import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """
    Загрузка конфигурации из файла config.json
    
    Returns:
        Dict[str, Any]: Словарь с настройками конфигурации
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Файл конфигурации {config_path} не найден. Используются настройки по умолчанию.")
        return get_default_config()
    except json.JSONDecodeError:
        print(f"Ошибка парсинга JSON в файле {config_path}. Используются настройки по умолчанию.")
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """
    Возвращает конфигурацию по умолчанию
    
    Returns:
        Dict[str, Any]: Словарь с настройками конфигурации по умолчанию
    """
    return {
        "testnet": True,
        "symbol": "BTCUSDT",
        "timeframe": "5",
        "account_type": "UNIFIED",
        "generation_duration_minutes": 5,
        "population_size": 50,
        "initial_balance": 1000.0,
        "global_trade_percentage": 0.1,
        "fitness_weights": {
            "profit": 1.0,
            "sharpe_ratio": 0.5,
            "max_drawdown": -0.5
        }
    }

# Для тестирования
if __name__ == "__main__":
    config = load_config()
    print("Загруженная конфигурация:")
    print(json.dumps(config, indent=2))