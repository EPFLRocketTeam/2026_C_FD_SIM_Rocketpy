import numpy as np
import random
import copy
from rocketpy import Environment, SolidMotor, Rocket, Flight
import datetime

GENE_BOUNDS = {
    'dry_mass': (40.0, 100.0),       # kg (motorless)
    'fin_span': (0.1, 0.4),          # m
    'fin_root_chord': (0.3, 0.8),    # m
    'propellant_mass': (10.0, 50.0), # kg
    'burn_time': (3.0, 8.0)          # s
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
            for key, (min_val, max_val) in GENE_BOUNDS.items():
                self.genes[key] = random.uniform(min_val, max_val)
                
    def crossover(self, partner):
        new_genes = {}
        for key in self.genes.keys():
            alpha = random.random()
            new_genes[key] = alpha * self.genes[key] + (1 - alpha) * partner.genes[key]
        return DNA(new_genes)

    def mutate(self, mutation_rate=0.1, mutation_strength=0.1):
        for key, (min_val, max_val) in GENE_BOUNDS.items():
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
        genes = self.dna.genes
        
        try:
            # solid, must become liquid
            motor = SolidMotor(
                thrust_source=lambda t: (genes['propellant_mass'] * 2000) / genes['burn_time'],
                dry_mass=5.0,
                dry_inertia=(0.1, 0.1, 0.01),
                nozzle_radius=0.05,
                grain_number=4,
                grain_density=1815,
                grain_outer_radius=0.075,
                grain_initial_inner_radius=0.03,
                grain_initial_height=0.3,
                grain_separation=0.005,
                grains_center_of_mass_position=0.5,
                center_of_dry_mass_position=0.5,
                nozzle_position=0,
                burn_time=genes['burn_time'],
                coordinate_system_orientation="nozzle_to_combustion_chamber",
            )

            # rocket, bad dimensions & positioning
            rocket = Rocket(
                radius=0.1215,
                mass=genes['dry_mass'],
                inertia=(100.0, 100.0, 1.0, 0, 0, 0),
                power_off_drag=0.38,
                power_on_drag=0.38,
                center_of_mass_without_motor=1.5,
                coordinate_system_orientation="tail_to_nose",
            )
            rocket.add_motor(motor, position=0)
            rocket.set_rail_buttons(0.3, 0.8)
            rocket.add_nose(length=1.0, kind="powerseries", power=0.5, position=3.0)
            rocket.add_trapezoidal_fins(
                n=4, 
                span=genes['fin_span'], 
                root_chord=genes['fin_root_chord'], 
                tip_chord=0.1, 
                position=0.5
            )

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

            # z drift
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
        
        best_rocket = self.rockets[0]
        new_rockets.append(RocketPhenotype(copy.deepcopy(best_rocket.dna)))

        while len(new_rockets) < self.pop_size:
            parent_a = self.select_parent().dna
            parent_b = self.select_parent().dna
            
            child_dna = parent_a.crossover(parent_b)
            # reduce mutation over time
            mutation_strength = max(0.01, 0.2 / self.generation)
            child_dna.mutate(mutation_rate=0.2, mutation_strength=mutation_strength)
            
            new_rockets.append(RocketPhenotype(child_dna))
            
        self.rockets = new_rockets
        self.generation += 1


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
        print(f"Rocket Mass:  {best.dna.genes['dry_mass']:.2f} kg | Propellant: {best.dna.genes['propellant_mass']:.2f} kg")
        print(f"Fin Span:     {best.dna.genes['fin_span']:.3f} m")
        
        if gen < GENERATIONS:
            pop.evolve()

    print("\nOptimization Complete.")
    print("\n" + "="*40)
    print("FINAL WINNER VISUALIZATION")
    print("="*40)

    best_genes = pop.rockets[0].dna.genes

    best_motor = SolidMotor(
        thrust_source=lambda t: (best_genes['propellant_mass'] * 2000) / best_genes['burn_time'],
        dry_mass=5.0,
        dry_inertia=(0.1, 0.1, 0.01),
        nozzle_radius=0.05,
        grain_number=4,
        grain_density=1815,
        grain_outer_radius=0.075,
        grain_initial_inner_radius=0.03,
        grain_initial_height=0.3,
        grain_separation=0.005,
        grains_center_of_mass_position=0.5,
        center_of_dry_mass_position=0.5,
        nozzle_position=0,
        burn_time=best_genes['burn_time'],
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )

    best_rocket = Rocket(
        radius=0.1215,
        mass=best_genes['dry_mass'],
        inertia=(100.0, 100.0, 1.0, 0, 0, 0),
        power_off_drag=0.38,
        power_on_drag=0.38,
        center_of_mass_without_motor=1.5,
        coordinate_system_orientation="tail_to_nose",
    )
    best_rocket.add_motor(best_motor, position=0)
    best_rocket.set_rail_buttons(0.3, 0.8)
    best_rocket.add_nose(length=1.0, kind="powerseries", power=0.5, position=3.0)
    best_rocket.add_trapezoidal_fins(
        n=4, 
        span=best_genes['fin_span'], 
        root_chord=best_genes['fin_root_chord'], 
        tip_chord=0.1, 
        position=0.5
    )

    best_flight = Flight(
        rocket=best_rocket, 
        environment=env, 
        rail_length=5.2, 
        inclination=85, 
        heading=0,
        terminate_on_apogee=False 
    )

    best_rocket.draw()
    best_flight.plots.trajectory_3d()