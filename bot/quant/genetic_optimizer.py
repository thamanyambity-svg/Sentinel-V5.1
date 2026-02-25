import random
import numpy as np
from typing import List, Tuple, Callable, Any
from dataclasses import dataclass

@dataclass
class StrategyParams:
    rsi_period: int
    rsi_oversold: int
    rsi_overbought: int
    ema_fast: int
    ema_slow: int
    
    def mutate(self, mutation_rate: float = 0.1):
        """Mutation aléatoire des paramètres"""
        if random.random() < mutation_rate:
            self.rsi_period = max(5, min(50, self.rsi_period + random.randint(-2, 2)))
        if random.random() < mutation_rate:
            self.rsi_oversold = max(10, min(45, self.rsi_oversold + random.randint(-2, 2)))
        if random.random() < mutation_rate:
            self.rsi_overbought = max(55, min(90, self.rsi_overbought + random.randint(-2, 2)))
        if random.random() < mutation_rate:
            self.ema_fast = max(5, min(50, self.ema_fast + random.randint(-2, 2)))
        if random.random() < mutation_rate:
            self.ema_slow = max(20, min(200, self.ema_slow + random.randint(-5, 5)))
        
        # Correction logic
        if self.ema_fast >= self.ema_slow:
            self.ema_slow = self.ema_fast + 2
    
    @staticmethod
    def random():
        """Génère des paramètres aléatoires"""
        return StrategyParams(
            rsi_period=random.randint(10, 30),
            rsi_oversold=random.randint(20, 40),
            rsi_overbought=random.randint(60, 80),
            ema_fast=random.randint(5, 20),
            ema_slow=random.randint(20, 100)
        )

class GeneticOptimizer:
    def __init__(self, fitness_function: Callable[[StrategyParams], float], population_size: int = 50):
        self.fitness_function = fitness_function
        self.population_size = population_size
        self.population = [StrategyParams.random() for _ in range(population_size)]
        self.generation = 0
    
    def evaluate_population(self) -> List[Tuple[StrategyParams, float]]:
        """Évalue toute la population"""
        results = []
        for params in self.population:
            fitness = self.fitness_function(params)
            results.append((params, fitness))
        
        # Sort by fitness descending
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def select_parents(self, ranked_population: List[Tuple[StrategyParams, float]]) -> List[StrategyParams]:
        """Sélection des parents (tournoi)"""
        parents = []
        # Select enough parents to create next gen (usually half pop size, producing 2 children each)
        num_parents = self.population_size // 2
        
        for _ in range(num_parents):
            # Tournoi : sélectionner 3 candidats aléatoirement et garder le meilleur
            # Tournament size 3 adds slightly more pressure than 2
            candidates = random.sample(ranked_population, 3)
            winner = max(candidates, key=lambda x: x[1])[0]
            parents.append(winner)
        return parents
    
    def crossover(self, parent1: StrategyParams, parent2: StrategyParams) -> Tuple[StrategyParams, StrategyParams]:
        """Croisement de deux parents (Uniform Crossover)"""
        # Child 1 takes some from p1, some from p2
        child1 = StrategyParams(
            rsi_period=random.choice([parent1.rsi_period, parent2.rsi_period]),
            rsi_oversold=random.choice([parent1.rsi_oversold, parent2.rsi_oversold]),
            rsi_overbought=random.choice([parent1.rsi_overbought, parent2.rsi_overbought]),
            ema_fast=random.choice([parent1.ema_fast, parent2.ema_fast]),
            ema_slow=random.choice([parent1.ema_slow, parent2.ema_slow])
        )
        # Child 2 inverse or random mix
        child2 = StrategyParams(
            rsi_period=random.choice([parent1.rsi_period, parent2.rsi_period]),
            rsi_oversold=random.choice([parent1.rsi_oversold, parent2.rsi_oversold]),
            rsi_overbought=random.choice([parent1.rsi_overbought, parent2.rsi_overbought]),
            ema_fast=random.choice([parent1.ema_fast, parent2.ema_fast]),
            ema_slow=random.choice([parent1.ema_slow, parent2.ema_slow])
        )
        return child1, child2
    
    def evolve(self, generations: int = 20, verbose: bool = True):
        """Fait évoluer la population"""
        history = []
        
        for generation in range(generations):
            self.generation = generation
            
            # Évaluation
            ranked = self.evaluate_population()
            best_params, best_fitness = ranked[0]
            history.append(best_fitness)
            
            if verbose:
                print(f"🧬 Gen {generation}: Best Score = {best_fitness:.4f} | {best_params}")
            
            # Sélection
            parents = self.select_parents(ranked)
            
            # Création nouvelle génération
            new_population = []
            
            # Élitisme : garder le top 2 absulument
            new_population.append(ranked[0][0])
            new_population.append(ranked[1][0])
            
            # Remplir le reste
            while len(new_population) < self.population_size:
                if len(parents) < 2:
                    break # Should not happen
                p1, p2 = random.sample(parents, 2)
                c1, c2 = self.crossover(p1, p2)
                c1.mutate()
                c2.mutate()
                new_population.extend([c1, c2])
            
            self.population = new_population[:self.population_size]
        
        return ranked[0]

if __name__ == "__main__":
    # Test
    def dummy_fitness(p: StrategyParams) -> float:
        # Target: RSI period 14, overbought 70
        score = 0
        score -= abs(p.rsi_period - 14)
        score -= abs(p.rsi_overbought - 70)
        return score # higher is better (closer to 0)

    print("🧬 Starting Genetic Optimization Demo...")
    opt = GeneticOptimizer(dummy_fitness, population_size=20)
    best_p, best_s = opt.evolve(generations=10)
    print(f"\n🏆 Winner: {best_p}\n⭐️ Score: {best_s}")
