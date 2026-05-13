import random
import numpy as np
from optimizer import OptimizerBase

class Algorithm(OptimizerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pop_size = self.args.iter_per_gen
        self.selection_method = self.args.selection_method
        self.sp = self.args.sp
        self.generation = 1
        self.population = []
        self.fitnesses = []
        self.rng = random.Random(42)

    def _random_design(self):
        d = {}
        for key, (lo, hi) in self.variable_bounds.items():
            val = self.rng.uniform(lo, hi)
            if key in self.integer_genes:
                val = int(round(val))
            d[key] = val
        return d

    def _crossover(self, p1, p2):
        child = {}
        for key in p1:
            alpha = self.rng.random()
            val = alpha * p1[key] + (1 - alpha) * p2[key]
            if key in self.integer_genes:
                val = int(round(val))
            child[key] = val
        return child

    def _mutate(self, design):
        mutation_rate = max(0.05, 0.25 * (0.9 ** (self.generation - 1)))
        mutation_strength = max(0.02, 0.25 / np.sqrt(self.generation))
        for key, (lo, hi) in self.variable_bounds.items():
            if self.rng.random() < mutation_rate:
                if key in self.integer_genes:
                    shift = self.rng.choice([-1, 1])
                    design[key] = int(np.clip(design[key] + shift, lo, hi))
                else:
                    noise = self.rng.gauss(0, mutation_strength * (hi - lo))
                    design[key] = np.clip(design[key] + noise, lo, hi)

    def _select_parent(self):
        n = len(self.population)
        if n == 0:
            return self._random_design()
        if self.selection_method == 'rank':
            sorted_idx = sorted(range(n), key=lambda i: self.fitnesses[i], reverse=True)
            probs = []
            for rank_i, idx in enumerate(sorted_idx):
                rank = n - 1 - rank_i
                prob = (2 - self.sp) / n + (2 * rank * (self.sp - 1)) / (n * (n - 1))
                probs.append(prob)
            chosen = self.rng.choices(range(n), weights=probs, k=1)[0]
            return self.population[chosen]
        elif self.selection_method == 'boltzmann':
            t0 = 5.0
            decay = 0.95
            temperature = t0 * (decay ** (self.generation - 1))
            max_fit = max(self.fitnesses) if self.fitnesses else 1.0
            norm_fit = np.array(self.fitnesses) / max_fit if max_fit > 0 else np.zeros(n)
            exp_fit = np.exp(norm_fit / max(temperature, 1e-6))
            probs = exp_fit / (np.sum(exp_fit) + 1e-12)
            chosen = self.rng.choices(range(n), weights=probs, k=1)[0]
            return self.population[chosen]
        else:
            tournament = self.rng.sample(range(n), min(3, n))
            best = max(tournament, key=lambda i: self.fitnesses[i])
            return self.population[best]

    def run_generation(self, evaluator):
        if self.generation == 1:
            self.population = [self._random_design() for _ in range(self.pop_size)]
        else:
            new_pop = [self.population[np.argmax(self.fitnesses)].copy()]  # elitism
            while len(new_pop) < self.pop_size:
                p1 = self._select_parent()
                p2 = self._select_parent()
                child = self._crossover(p1, p2)
                self._mutate(child)
                new_pop.append(child)
            self.population = new_pop

        results = evaluator.evaluate_batch(self.population)
        self.fitnesses = [fit for (_, fit, _) in results]
        self.generation += 1
        return results