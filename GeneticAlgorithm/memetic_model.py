import numpy as np
import random
import copy
import datetime
from rocketpy import Environment, Flight
from rocket_builder import RocketBuilder

warnings.filterwarnings("ignore", category=UserWarning, module="rocketpy.motors.motor")

VARIABLE_GENE_BOUNDS = {
    'fin_span': (0.01, 1.5),         # m
    'fin_root_chord': (0.1, 1.0),    # m
    'fuel_mass': (3.0, 12.0),        # kg
    'oxidizer_mass': (3.0, 16.0),    # kg
    'fin_tip_chord': (0.05, 0.3),    # m
    'fin_sweep_length': (0.3, 0.8),  # m
    'tail_top_radius': (0.09, 0.20), # m
    'tail_bottom_radius': (0.05, 0.12), # m
    'nose_length': (0.8, 1.3),       # m
    'tail_length': (0.3, 0.6),       # m
    'fin_count': (3, 6),             # integer
}

FIXED_GENES = {
    'motor_type': 'liquid',
}

INTEGER_GENES = ['fin_count']

TARGET_APOGEE = 3000.0 # m
HEIGHT_DEVIATION_ALLOWED = 200.0 # m

now = datetime.datetime.now(datetime.timezone.utc)
env = Environment(latitude=38.9627778, longitude=-8.96277777, elevation=160, date=(now.year, now.month, now.day, now.hour))
env.set_atmospheric_model(type="forecast", file="GFS")

class DNA:
    def __init__(self, genes=None):
        if genes:
            self.genes = genes
        else:
            self.genes = {}
            for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
                val = random.uniform(min_val, max_val)
                if key in INTEGER_GENES:
                    self.genes[key] = int(round(val))
                else:
                    self.genes[key] = val

    def crossover(self, partner):
        new_genes = {}
        for key in self.genes.keys():
            if random.random() < 0.5:
                alpha = random.random()
                val = alpha * self.genes[key] + (1 - alpha) * partner.genes[key]
            else:
                val = random.choice([self.genes[key], partner.genes[key]])
            if key in INTEGER_GENES:
                new_genes[key] = int(round(val))
            else:
                new_genes[key] = val
        return DNA(new_genes)

    def mutate(self, mutation_rate=0.4, mutation_strength=0.3):
        for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
            if random.random() < mutation_rate:
                if key in INTEGER_GENES:
                    shift = random.choice([-1, 1])
                    self.genes[key] += shift
                    self.genes[key] = int(max(min_val, min(max_val, self.genes[key])))
                else:
                    range_span = max_val - min_val
                    noise = random.gauss(0, mutation_strength * range_span)
                    self.genes[key] += noise
                    self.genes[key] = max(min_val, min(max_val, self.genes[key]))

class RocketPhenotype:
    def __init__(self, dna):
        self.dna = dna
        self.fitness = 0.0
        self.apogee = 0.0
        self.drift = 0.0
        self.drift_x = 0.0
        self.drift_y = 0.0
        self.sm = 0.0
        self.evaluated = False

    def evaluate(self):
        if self.evaluated:
            return
        full_params = {**FIXED_GENES, **self.dna.genes}

        try:
            builder = RocketBuilder(full_params)
            rocket = builder.build()

            self.sm = rocket.static_margin(0)
            if self.sm < 1.5 or self.sm > 5.0:
                dist = min(abs(self.sm - 1.5), abs(self.sm - 5.0))
                self.fitness = 1e-3 / (1.0 + dist)
                self.evaluated = True
                return

            flight = Flight(
                rocket=rocket,
                environment=env,
                rail_length=11.65,
                inclination=85,
                heading=144,
                terminate_on_apogee=True
            )

            self.apogee = flight.apogee
            t_ap = flight.apogee_time
            x_ap = flight.x(t_ap)
            y_ap = flight.y(t_ap)
            self.drift_x = x_ap
            self.drift_y = y_ap
            self.drift = np.sqrt(x_ap**2 + y_ap**2)

            z_error = abs(self.apogee - TARGET_APOGEE)
            self.fitness = 10000.0 / (1.0 + z_error + (self.drift * 0.1))
            
            if z_error <= HEIGHT_DEVIATION_ALLOWED:
                self.fitness *= 2

            sm_penalty = 0.0
            if self.sm < 1.5:
                sm_penalty = 1.5 - self.sm
            elif self.sm > 2.0:
                sm_penalty = self.sm - 2.0
            
            self.fitness /= (1.0 + sm_penalty * 5.0)
            self.evaluated = True

        except Exception as e:
            self.fitness = 1e-5 / (1 + random.random())

class EvolutionPrinter:
    def __init__(self, variable_bounds, fixed_genes, target_apogee):
        self.variable_bounds = variable_bounds
        self.fixed_genes = fixed_genes
        self.target_apogee = target_apogee

    def print_header(self):
        print("Fixed parameters (constant across all individuals):")
        for key, value in self.fixed_genes.items():
            print(f"  { key.replace('_', ' ').capitalize()}: {value}")
        print("\nVariable parameters (evolved):")
        for key, (minv, maxv) in self.variable_bounds.items():
            print(f"  { key.replace('_', ' ').capitalize()}: [{minv}, {maxv}]")
        print(f"\nTarget apogee: {self.target_apogee} m\n")

    def print_generation_summary(self, generation, best_rocket):
        apogee_error = abs(best_rocket.apogee - self.target_apogee)

        print(f"\n--- Generation {generation} ---")
        print(f"Best fitness:       {best_rocket.fitness:.2f}")
        print(f"Apogee:             {best_rocket.apogee:.2f} m (Error: {apogee_error:.2f} m)")
        print(f"Drift (total):      {best_rocket.drift:.2f} m")
        print(f"Stability Margin:   {best_rocket.sm:.2f}")

        print("\nOptimized parameters:")
        for key in self.variable_bounds.keys():
            value = best_rocket.dna.genes[key]
            display_name = key.replace('_', ' ').capitalize()
            print(f"  {display_name:20} {value:8.3f}")

def local_search(dna, max_evaluations=12):
    best_genes = copy.deepcopy(dna.genes)
    current_p = RocketPhenotype(DNA(best_genes))
    current_p.evaluate()
    best_fitness = current_p.fitness

    if best_fitness <= 0.01: 
        return dna

    step_factor = 0.05

    for _ in range(max_evaluations):
        new_genes = copy.deepcopy(best_genes)
        
        for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
            if key in INTEGER_GENES:
                if random.random() < step_factor * 5: 
                    shift = random.choice([-1, 1])
                    new_genes[key] = int(np.clip(new_genes[key] + shift, min_val, max_val))
            else:
                range_span = max_val - min_val
                noise = random.gauss(0, step_factor * range_span)
                new_genes[key] = np.clip(new_genes[key] + noise, min_val, max_val)

        test_dna = DNA(new_genes)
        test_p = RocketPhenotype(test_dna)
        test_p.evaluate()

        if test_p.fitness > best_fitness:
            best_fitness = test_p.fitness
            best_genes = new_genes
            step_factor = min(0.2, step_factor * 1.5)
        else:
            step_factor = max(0.001, step_factor * 0.8)

    return DNA(best_genes)

class MemeticPopulation:
    def __init__(self, pop_size):
        self.pop_size = pop_size
        self.rockets = [RocketPhenotype(DNA()) for _ in range(pop_size)]
        self.generation = 1

    def evaluate_all(self):
        for r in self.rockets:
            if r.fitness == 0:
                r.evaluate()
        self.rockets.sort(key=lambda x: x.fitness, reverse=True)

    def rank_select_parent(self, sp=1.5):
        n = len(self.rockets)
        probs = []
        for i in range(n):
            rank = n - 1 - i
            prob = (2 - sp) / n + (2 * rank * (sp - 1)) / (n * (n - 1))
            probs.append(prob)
        chosen_idx = np.random.choice(n, p=probs)
        return self.rockets[chosen_idx].dna

    def boltzmann_select_parent(self, temperature=None):
        if temperature is None:
            t0 = 5.0
            decay = 0.95
            temperature = t0 * (decay ** (self.generation - 1))
        
        fitnesses = np.array([r.fitness for r in self.rockets])
        max_fit = np.max(fitnesses)
        norm_fitnesses = fitnesses / max_fit if max_fit > 0 else fitnesses

        exp_fit = np.exp(norm_fitnesses / max(temperature, 1e-6))
        probs = exp_fit / np.sum(exp_fit)
        chosen_idx = np.random.choice(len(self.rockets), p=probs)
        return self.rockets[chosen_idx].dna

    def evolve(self, selection_method='rank', sp=1.5, local_search_evals=10, local_search_prob=0.4):
        new_rockets = []
        new_rockets.append(RocketPhenotype(copy.deepcopy(self.rockets[0].dna)))

        if selection_method == 'rank':
            select_func = lambda: self.rank_select_parent(sp=sp)
        elif selection_method == 'boltzmann':
            select_func = lambda: self.boltzmann_select_parent()
        else:
            select_func = lambda: max(random.sample(self.rockets, 3), key=lambda r: r.fitness).dna

        while len(new_rockets) < self.pop_size:
            parent_a = select_func()
            parent_b = select_func()
            child_dna = parent_a.crossover(parent_b)

            mutation_strength = max(0.02, 0.25 / np.sqrt(self.generation))
            mutation_rate = max(0.05, 0.25 * (0.9 ** (self.generation - 1)))
            child_dna.mutate(mutation_rate=mutation_rate, mutation_strength=mutation_strength)

            if random.random() < local_search_prob:
                improved_dna = local_search(child_dna, max_evaluations=local_search_evals)
                child_phenotype = RocketPhenotype(improved_dna)
            else:
                child_phenotype = RocketPhenotype(child_dna)

            new_rockets.append(child_phenotype)

        self.rockets = new_rockets
        self.generation += 1

if __name__ == "__main__":
    POPULATION_SIZE = 25
    GENERATIONS = 6
    LOCAL_SEARCH_PROB = 0.35 
    LOCAL_SEARCH_EVALS = 12

    printer = EvolutionPrinter(VARIABLE_GENE_BOUNDS, FIXED_GENES, TARGET_APOGEE)
    printer.print_header()

    print("Initializing Memetic Population...")
    pop = MemeticPopulation(POPULATION_SIZE)

    for gen in range(1, GENERATIONS + 1):
        pop.evaluate_all()
        best = pop.rockets[0]

        printer.print_generation_summary(gen, best)

        if gen < GENERATIONS:
            pop.evolve(
                selection_method='rank', 
                local_search_evals=LOCAL_SEARCH_EVALS, 
                local_search_prob=LOCAL_SEARCH_PROB
            )

    best_params = {**FIXED_GENES, **pop.rockets[0].dna.genes}
    best_builder = RocketBuilder(best_params)
    best_rocket = best_builder.build()

    best_flight = Flight(
        rocket=best_rocket,
        environment=env,
        rail_length=11.65,
        inclination=85,
        heading=144,
        terminate_on_apogee=True
    )
    
    best_builder.show()
    best_flight.plots.trajectory_3d()
    print("\nMemetic Optimization Complete.")