import numpy as np
from utils.logger import setup_logger

logger = setup_logger('evolution_manager')
def select_parents(population, elite_size=5):
    """Отбор родителей для следующего поколения с обработкой отрицательных fitness"""
    # Отбираем элитных особей
    elites = population[:elite_size]
    
    # Получаем значения приспособленности
    fitnesses = np.array([robot.fitness for robot in population])
    
    # Обрабатываем отрицательные значения fitness
    min_fitness = np.min(fitnesses)
    if min_fitness < 0:
        # Сдвигаем все значения, чтобы минимальное было равно 0
        shifted_fitnesses = fitnesses - min_fitness + 1e-10  # Добавляем маленькое значение для избежания деления на 0
    else:
        shifted_fitnesses = fitnesses + 1e-10  # Добавляем маленькое значение для избежания деления на 0
    
    # Вычисляем вероятности выбора
    total_fitness = np.sum(shifted_fitnesses)
    probabilities = shifted_fitnesses / total_fitness
    
    # Проверяем, что все вероятности неотрицательные
    if np.any(probabilities < 0):
        # Если есть отрицательные вероятности, используем равномерное распределение
        probabilities = np.ones(len(population)) / len(population)
        logger.warning("Обнаружены отрицательные вероятности, используется равномерное распределение")
    
    # Отбираем родителей
    selected = list(np.random.choice(
        population, 
        size=len(population) - elite_size, 
        p=probabilities,
        replace=False
    ))
    
    return elites + selected