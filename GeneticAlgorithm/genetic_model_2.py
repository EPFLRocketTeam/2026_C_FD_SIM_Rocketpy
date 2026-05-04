import numpy as np
import random
import copy
from rocketpy import Environment, SolidMotor, Rocket, Flight
import datetime
from rocket_builder import RocketBuilder

VARIABLE_GENE_BOUNDS = {
    'fin_span': (0.01, 1.5),          # m
    'fin_root_chord': (0.1, 1.0),    # m
    'fuel_mass': (3.0, 12.0),
    'oxidizer_mass': (3.0, 16.0),
    'fin_tip_chord': (0.05, 0.3),    # m
    'fin_sweep_length': (0.3, 0.8),  # m
    'tail_top_radius': (0.09, 0.20),     # m
    'tail_bottom_radius': (0.05, 0.12),  # m
    'nose_length': (0.8, 1.3),           # m
    'tail_length': (0.3, 0.6),           # m
    'fin_count': (3, 6),
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

# env = Environment(latitude=38.9627778, longitude=-8.96277777, elevation=160)
# env.set_atmospheric_model(type="standard_atmosphere")

class DNA:
    def __init__(self, genes=None):
        if genes:
            self.genes = genes
        else:
            self.genes = {}
            for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
                val = self.genes[key] = random.uniform(min_val, max_val)
                if key in INTEGER_GENES:
                    self.genes[key] = int(round(val))
                else:
                    self.genes[key] = val

    def crossover(self, partner):
        new_genes = {}
        for key in self.genes.keys():
            alpha = random.random()
            val = alpha * self.genes[key] + (1 - alpha) * partner.genes[key]
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

    def evaluate(self):
        full_params = {**FIXED_GENES, **self.dna.genes}

        try:
            builder = RocketBuilder(full_params)
            rocket = builder.build()

            self.sm = rocket.static_margin(0)
            if self.sm < 1.5 or self.sm > 5.0:
                dist = min(abs(self.sm - 1.5), abs(self.sm - 5.0))
                self.fitness = 1e-3 / (1.0 + dist)
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
            # z_error = abs(self.apogee - TARGET_APOGEE)
            # z_fitness = np.exp(-((z_error / 150.0) ** 4))
            # if z_error > HEIGHT_DEVIATION_ALLOWED:
            #     total = max(z_fitness, 1e-4)
            # else:
            #     drift_fitness = np.exp(-((self.drift / 150.0) ** 2))
            #     total = max(z_fitness * drift_fitness, 1e-4)

            # self.fitness = 10000.0 * total

        except Exception as e:
            self.fitness = 1e-5/(1+random.random())
            print(e)

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
        print(f"Best fitness:    {best_rocket.fitness:.2f}")
        print(f"Apogee:          {best_rocket.apogee:.2f} m (Error: {apogee_error:.2f} m)")
        print(f"Drift (total):   {best_rocket.drift:.2f} m")
        print(f"Stability Margin:   {best_rocket.sm:.2f}")

        if hasattr(best_rocket, 'drift_x') and hasattr(best_rocket, 'drift_y'):
            print(f"  - X drift:    {best_rocket.drift_x:.2f} m")
            print(f"  - Y drift:    {best_rocket.drift_y:.2f} m")

        print("\nOptimized parameters:")
        for key in self.variable_bounds.keys():
            value = best_rocket.dna.genes[key]
            display_name = key.replace('_', ' ').capitalize()
            print(f"  {display_name:20} {value:8.3f}")

class Population:
    def __init__(self, pop_size):
        self.pop_size = pop_size
        self.rockets = [RocketPhenotype(DNA()) for _ in range(pop_size)]
        self.generation = 1

    def evaluate_all(self):
        for r in self.rockets:
            r.evaluate()
        self.rockets.sort(key=lambda x: x.fitness, reverse=True)

    def select_parent(self, tournament_size=3):
        tournament = random.sample(self.rockets, tournament_size)
        return max(tournament, key=lambda r: r.fitness)

    # def evolve(self):
    #     new_rockets = []
    #     new_rockets.append(RocketPhenotype(copy.deepcopy(self.rockets[0].dna)))

    #     while len(new_rockets) < self.pop_size:
    #         parent_a = self.select_parent().dna
    #         parent_b = self.select_parent().dna
    #         child_dna = parent_a.crossover(parent_b)
    #         mutation_strength = max(0.01, 0.2 / self.generation)
    #         child_dna.mutate(mutation_rate=0.2, mutation_strength=mutation_strength)
    #         new_rockets.append(RocketPhenotype(child_dna))

    #     self.rockets = new_rockets
    #     self.generation += 1
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

    def evolve(self, selection_method='rank', sp=1.5):
        new_rockets = []
        new_rockets.append(RocketPhenotype(copy.deepcopy(self.rockets[0].dna)))

        if selection_method == 'rank':
            select_func = lambda: self.rank_select_parent(sp=sp)
        elif selection_method == 'boltzmann':
            select_func = lambda: self.boltzmann_select_parent()
        else:
            def tournament():
                print("!!!FALLING TO NORMAL TOURNAMENT NOT GOOD!!!")
                tournament_size = 3
                tournament = random.sample(self.rockets, tournament_size)
                return max(tournament, key=lambda r: r.fitness).dna
            select_func = tournament

        while len(new_rockets) < self.pop_size:
            parent_a = select_func()
            parent_b = select_func()
            child_dna = parent_a.crossover(parent_b)

            mutation_strength = max(0.02, 0.25 / np.sqrt(self.generation))
            mutation_rate = max(0.05, 0.25 * (0.9 ** (self.generation - 1)))
            child_dna.mutate(mutation_rate=mutation_rate, mutation_strength=mutation_strength)

            new_rockets.append(RocketPhenotype(child_dna))

        self.rockets = new_rockets
        self.generation += 1

if __name__ == "__main__":
    POPULATION_SIZE = 30
    GENERATIONS = 8

    printer = EvolutionPrinter(VARIABLE_GENE_BOUNDS, FIXED_GENES, TARGET_APOGEE)
    printer.print_header()

    pop = Population(POPULATION_SIZE)

    for gen in range(1, GENERATIONS + 1):
        pop.evaluate_all()
        best = pop.rockets[0]

        printer.print_generation_summary(gen, best)

        if gen < GENERATIONS:
            pop.evolve()

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
    print("\nOptimization Complete.")