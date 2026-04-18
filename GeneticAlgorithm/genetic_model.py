import numpy as np
import random
import copy
from rocketpy import Environment, SolidMotor, Rocket, Flight
import datetime
from rocket_builder import RocketBuilder

VARIABLE_GENE_BOUNDS = {
    'fin_span': (0.1, 0.4),          # m
    'fin_root_chord': (0.3, 0.8),    # m
    'propellant_mass': (6.0, 10.0), # kg
    'burn_time': (3.0, 8.0)          # s
}

FIXED_GENES = {
    'motor_type': 'liquid',
    # 'body_length': 3.0,
    # 'cg_without_motor': 1.5,
}

TARGET_APOGEE = 3000.0 # m
# tryout real time weather
#now = datetime.datetime.now(datetime.timezone.utc)
#env = Environment(latitude=38.9627778, longitude=-8.96277777, elevation=160, date=(now.year, now.month, now.day, now.hour))
#env.set_atmospheric_model(type="forecast", file="GFS")
#env.info()
# std atmosphere -> too simple
env = Environment(latitude=38.9627778, longitude=-8.96277777, elevation=160)
env.set_atmospheric_model(type="standard_atmosphere")

class DNA:
    def __init__(self, genes=None):
        if genes:
            self.genes = genes
        else:
            self.genes = {}
            for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
                self.genes[key] = random.uniform(min_val, max_val)
                
    def crossover(self, partner):
        new_genes = {}
        for key in self.genes.keys():
            alpha = random.random()
            new_genes[key] = alpha * self.genes[key] + (1 - alpha) * partner.genes[key]
        return DNA(new_genes)

    def mutate(self, mutation_rate=0.1, mutation_strength=0.1):
        for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
            if random.random() < mutation_rate:
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
        self.is_stable = True

    def evaluate(self):
        full_params = {**FIXED_GENES, **self.dna.genes}
        
        try:
            builder = RocketBuilder(full_params)
            rocket = builder.build()

            # check stability (static margin)
            sm = rocket.static_margin(0)
            if sm < 1.5 or sm > 5.0:
                self.is_stable = False
                self.fitness = 0.01
                return

            flight = Flight(
                rocket=rocket, 
                environment=env, 
                rail_length=5.2, 
                inclination=85,
                heading=0,
                terminate_on_apogee=True 
            )

            # fitness
            self.apogee = flight.apogee
            self.drift = np.sqrt(flight.x(flight.apogee_time)**2 + flight.y(flight.apogee_time)**2)
            z_error = abs(self.apogee - TARGET_APOGEE)
            
            self.fitness = 10000.0 / (1.0 + z_error + (self.drift * 0.5))

        except Exception as e:
            self.fitness = 0.0001
            self.is_stable = False

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

    def evolve(self):
        new_rockets = []
        new_rockets.append(RocketPhenotype(copy.deepcopy(self.rockets[0].dna)))

        while len(new_rockets) < self.pop_size:
            parent_a = self.select_parent().dna
            parent_b = self.select_parent().dna
            
            child_dna = parent_a.crossover(parent_b)
            mutation_strength = max(0.01, 0.2 / self.generation)
            child_dna.mutate(mutation_rate=0.2, mutation_strength=mutation_strength)
            
            new_rockets.append(RocketPhenotype(child_dna))
            
        self.rockets = new_rockets
        self.generation += 1

# if __name__ == "__main__":
#     # genes = {}
#     # for key, (min_val, max_val) in VARIABLE_GENE_BOUNDS.items():
#     #     genes[key] = random.uniform(min_val, max_val)
#     # RocketBuilder({**FIXED_GENES, **genes, 'motor_type':'liquid'}).show()
#     builder = RocketBuilder({
#         'motor_type': 'liquid',
#         'propellant_mass': 8.82,
#     })

#     rocket = builder.build()
#     rocket.draw()
if __name__ == "__main__":
    POPULATION_SIZE = 30
    GENERATIONS = 10

    print(f"Starting evolution: target apogee = {TARGET_APOGEE}m")
    pop = Population(POPULATION_SIZE)

    for gen in range(1, GENERATIONS + 1):
        pop.evaluate_all()
        best = pop.rockets[0]
        
        print(f"\n--- Generation {gen} ---")
        print(f"Best fitness: {best.fitness:.2f}")
        print(f"Apogee:       {best.apogee:.2f} m (Error: {abs(best.apogee-TARGET_APOGEE):.2f} m)")
        print(f"Drift:        {best.drift:.2f} m")
        print(f"Fin Span:     {best.dna.genes['fin_span']:.3f} m")
        print(f"Fin Root Chord: {best.dna.genes['fin_root_chord']:.3f} m")
        print(f"Propellant Mass: {best.dna.genes['propellant_mass']:.2f} kg")
        print(f"Burn Time:    {best.dna.genes['burn_time']:.2f} s")
        
        if gen < GENERATIONS:
            pop.evolve()

    best_params = {**FIXED_GENES, **pop.rockets[0].dna.genes}
    best_builder = RocketBuilder(best_params)
    best_rocket = best_builder.build()
    
    best_flight = Flight(
        rocket=best_rocket,
        environment=env,
        rail_length=5.2,
        inclination=85,
        heading=0,
        terminate_on_apogee=False
    )
    best_builder.show()
    best_flight.plots.trajectory_3d()
    print("\nOptimization Complete.")
    