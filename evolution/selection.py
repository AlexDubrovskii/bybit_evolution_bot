import numpy as np
from utils.logger import setup_logger

logger = setup_logger('evolution_manager')
def select_parents(population, elite_size=5):
    """Отбор родителей для следующего поколения с защитой от некорректных размеров выборки."""
    n = len(population)
    if n == 0:
        logger.warning("select_parents: пустая популяция")
        return []

    # Приводим elite_size к допустимому диапазону
    elite_size = max(0, min(int(elite_size), n))

    # Отбираем элитных особей (ожидается, что популяция уже отсортирована по fitness)
    elites = population[:elite_size]

    # Если больше никого отбирать не нужно
    remaining = n - elite_size
    if remaining <= 0:
        return elites

    # Фитнесы и кандидаты (без элиты)
    fitnesses = np.array([float(robot.fitness) for robot in population], dtype=float)
    candidates = population[elite_size:]
    cand_fitness = fitnesses[elite_size:]

    # Если вдруг кандидатов нет
    if len(candidates) == 0:
        return elites

    # Сдвиг fitness к неотрицательным значениям
    min_fit = float(np.min(cand_fitness)) if cand_fitness.size > 0 else 0.0
    if min_fit < 0.0:
        shifted = cand_fitness - min_fit + 1e-12
    else:
        shifted = cand_fitness + 1e-12

    total = float(np.sum(shifted))
    if not np.isfinite(total) or total <= 0.0:
        # Равномерное распределение, если сумма фитнесов некорректна
        probabilities = np.ones(len(candidates), dtype=float) / len(candidates)
        logger.warning("select_parents: некорректная сумма фитнесов, используется равномерное распределение")
    else:
        probabilities = shifted / total
        # Если вдруг какое-то p < 0 из-за численной нестабильности — нормализуем
        probabilities = np.clip(probabilities, 0.0, None)
        s = probabilities.sum()
        probabilities = probabilities / (s if s > 0 else 1.0)

    # Размер выборки равен количеству неконкурентных мест
    sample_size = min(remaining, len(candidates))
    if sample_size <= 0:
        return elites

    selected = list(np.random.choice(candidates, size=sample_size, p=probabilities, replace=False))

    return elites + selected
