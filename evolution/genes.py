import numpy as np
import random

def mutate(gene: dict) -> dict:
    """Мутация гена робота"""
    mutated_gene = gene.copy()
    
    # Мутация торгового процента
    if random.random() < 0.3:  # 30% вероятность мутации
        mutated_gene['trade_percentage'] = np.random.uniform(0.01, 0.1)
    
    # Мутация склонности к риску
    if random.random() < 0.3:
        mutated_gene['risk_appetite'] = np.clip(
            gene['risk_appetite'] + np.random.normal(0, 0.1), 0.1, 0.9
        )
    
    # Мутация дерева решений
    if random.random() < 0.4:
        if len(mutated_gene['decision_tree']) > 2:
            # Удаляем случайное условие
            if random.random() < 0.5:
                del mutated_gene['decision_tree'][random.randint(0, len(mutated_gene['decision_tree']) - 1)]
            # Добавляем новое условие
            else:
                new_condition = {
                    'indicator': random.choice(['rsi', 'price_above_ema', 'volume']),
                    'operator': random.choice(['<', '>', '==']),
                    'value': random.randint(20, 80),
                    'action': random.choice(['buy', 'sell'])
                }
                mutated_gene['decision_tree'].append(new_condition)
    
    return mutated_gene

def crossover(gene1: dict, gene2: dict) -> dict:
    """Скрещивание двух генов"""
    child_gene = {}
    
    # Скрещивание торгового процента
    child_gene['trade_percentage'] = (gene1['trade_percentage'] + gene2['trade_percentage']) / 2
    
    # Скрещивание склонности к риску
    child_gene['risk_appetite'] = (gene1['risk_appetite'] + gene2['risk_appetite']) / 2
    
    # Скрещивание дерева решений
    child_gene['decision_tree'] = gene1['decision_tree'][:len(gene1['decision_tree'])//2] + \
                                 gene2['decision_tree'][len(gene2['decision_tree'])//2:]
    
    return child_gene