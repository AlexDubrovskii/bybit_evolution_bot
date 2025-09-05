import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

class RaceVisualizer:
    def __init__(self, evolution_manager):
        self.em = evolution_manager
        self.fig, self.ax = plt.subplots(figsize=(15, 8))
        self.scatter = None
        self.annotation = None
        
    def setup_plot(self):
        self.ax.set_xlim(0, 100)
        self.ax.set_ylim(0, 100)
        self.ax.set_title('Эволюционная гонка торговых роботов')
        self.ax.set_xlabel('Производительность')
        self.ax.set_ylabel('Роботы')
        
    def update(self, frame):
        if not self.em.population:
            return
            
        # Обновляем данные
        profits = [robot.current_profit for robot in self.em.population]
        sizes = [abs(profit) * 1000 for profit in profits]  # Размер точки зависит от прибыли
        cycles = [robot.survived_cycles for robot in self.em.population]
        children = [robot.children_count for robot in self.em.population]
        ids = [robot.robot_id for robot in self.em.population]
        
        # Очищаем и перерисовываем
        self.ax.clear()
        self.setup_plot()
        
        scatter = self.ax.scatter(profits, range(len(profits)), s=sizes, alpha=0.5)
        
        # Добавляем аннотации
        for i, (profit, cycle, child, id_val) in enumerate(zip(profits, cycles, children, ids)):
            self.ax.annotate(f"ID:{id_val}\nC:{cycle}\nCh:{child}", 
                            (profit, i), fontsize=8)
        
        return scatter,
        
    def animate(self):
        ani = FuncAnimation(self.fig, self.update, interval=1000, blit=True)
        plt.show()

class MetricsVisualizer:
    def plot_generation_metrics(self, evolution_manager):
        generations = range(evolution_manager.generation + 1)
        best_fitness = [gen['best_fitness'] for gen in evolution_manager.history]
        avg_fitness = [gen['avg_fitness'] for gen in evolution_manager.history]
        
        plt.figure(figsize=(12, 6))
        plt.plot(generations, best_fitness, label='Лучшая приспособленность', marker='o')
        plt.plot(generations, avg_fitness, label='Средняя приспособленность', marker='s')
        plt.xlabel('Поколение')
        plt.ylabel('Приспособленность')
        plt.title('Эволюция приспособленности по поколениям')
        plt.legend()
        plt.grid(True)
        plt.savefig('fitness_evolution.png')
        plt.close()