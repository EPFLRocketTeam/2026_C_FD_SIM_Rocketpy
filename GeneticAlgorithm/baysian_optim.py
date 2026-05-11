import numpy as np
import random
import copy
import datetime
import warnings
import os
from concurrent.futures import ProcessPoolExecutor

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel
from scipy.optimize import minimize

from rocketpy import Environment, Flight
from rocket_builder import RocketBuilder

warnings.filterwarnings("ignore", category=UserWarning, module="rocketpy.motors.motor")

ENV = None

VARIABLE_GENE_BOUNDS = {
    'fin_span': (0.01, 1.5),
    'fin_root_chord': (0.1, 1.0),
    'fuel_mass': (3.0, 12.0),
    'oxidizer_mass': (3.0, 16.0),
    'fin_tip_chord': (0.05, 0.3),
    'fin_sweep_length': (0.3, 0.8),
    'tail_top_radius': (0.09, 0.20),
    'tail_bottom_radius': (0.05, 0.12),
    'nose_length': (0.8, 1.3),
    'tail_length': (0.3, 0.6),
    'fin_count': (3, 6),
}

FIXED_GENES = {
    'motor_type': 'liquid',
}

INTEGER_GENES = ['fin_count']

TARGET_APOGEE = 3000.0
HEIGHT_DEVIATION_ALLOWED = 200.0

def _init_worker_env(lat, lon, elev, year, month, day, hour):
    global ENV
    date = (year, month, day, hour)
    env = Environment(latitude=lat, longitude=lon, elevation=elev, date=date)
    env.set_atmospheric_model(type="forecast", file="GFS")
    ENV = env
    warnings.filterwarnings("ignore", category=UserWarning, module="rocketpy.motors.motor")
    warnings.filterwarnings("ignore", message=".*Exact chosen launch time is not available.*")
    warnings.filterwarnings("ignore", message=".*loadtxt: input contained no data.*")


def _eval_rocket(rocket):
    rocket.evaluate()
    return rocket


class BayesianOptimizer:
    """
    Gaussian Process Bayesian Optimization for rocket design.
    Uses ARD Matérn 5/2 kernel, Expected Improvement acquisition,
    and a constant‑liar batch strategy for parallel evaluations.
    """
    def __init__(self, variable_bounds, integer_genes, random_state=42):
        self.param_names = list(variable_bounds.keys())
        self.bounds = np.array([variable_bounds[p] for p in self.param_names])  # (n,2)
        self.integer_mask = np.array([p in integer_genes for p in self.param_names], dtype=bool)
        self.n_params = len(self.param_names)

        self.lb = self.bounds[:, 0]
        self.ub = self.bounds[:, 1]
        self.range_ = self.ub - self.lb

        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
            length_scale=np.ones(self.n_params),
            length_scale_bounds=(1e-3, 1e3),
            nu=2.5
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=15,
            normalize_y=True,
            random_state=random_state
        )

        self.X_real = np.empty((0, self.n_params))
        self.y = np.empty(0)

        self.best_y = -1e9
        self.best_x_real = None

    def _scale(self, X_real):
        return (X_real - self.lb) / self.range_

    def _unscale(self, X_scaled):
        return X_scaled * self.range_ + self.lb

    def _round_integers(self, X_real):
        X = X_real.copy()
        for i in range(self.n_params):
            if self.integer_mask[i]:
                low, high = self.bounds[i]
                X[..., i] = np.clip(np.round(X[..., i]), low, high)
        return X

    def add_observation(self, design_dict, fitness):
        x = np.array([design_dict[p] for p in self.param_names], dtype=np.float64)
        x = self._round_integers(x)
        self.X_real = np.vstack([self.X_real, x])
        self.y = np.append(self.y, fitness)

        if fitness > self.best_y:
            self.best_y = fitness
            self.best_x_real = x

    def _expected_improvement(self, x_scaled, gp, y_best):
        x_scaled = np.atleast_2d(x_scaled)
        mu, sigma = gp.predict(x_scaled, return_std=True)
        sigma = sigma[0]
        mu = mu[0]

        if sigma < 1e-12:
            return 0.0

        z = (mu - y_best) / sigma
        from scipy.stats import norm
        ei = (mu - y_best) * norm.cdf(z) + sigma * norm.pdf(z)
        return ei

    def _optimize_ei(self, gp, y_best, n_restarts=50):
        best_x = None
        best_ei = -1e9
        bounds_scaled = [(0.0, 1.0)] * self.n_params

        def neg_ei(x_scaled):
            return -self._expected_improvement(x_scaled, gp, y_best)

        for _ in range(n_restarts):
            x0 = np.random.uniform(0.0, 1.0, self.n_params)
            res = minimize(neg_ei, x0, bounds=bounds_scaled, method='L-BFGS-B')
            if res.success and -res.fun > best_ei:
                best_ei = -res.fun
                best_x = res.x

        if best_x is None:
            best_x = x0
        return best_x

    def suggest_batch(self, batch_size):
        """
        Return a batch of parameter sets (dicts) using the constant‑liar batch strategy.
        """
        if len(self.y) < 2:
            return [{p: np.random.uniform(*self.bounds[i]) for i,p in enumerate(self.param_names)}
                    for _ in range(batch_size)]

        X_scaled = self._scale(self.X_real)
        self.gp.fit(X_scaled, self.y)

        y_best = self.best_y
        batch_scaled = []
        batch_dicts = []

        kernel_final = self.gp.kernel_
        X_real_base = self.X_real.copy()
        y_base = self.y.copy()

        for b in range(batch_size):
            if b == 0:
                gp_work = self.gp
            else:
                X_aug = np.vstack([X_scaled, np.array(batch_scaled)])
                y_aug = np.concatenate([y_base, np.full(len(batch_scaled), y_best * 0.95)])
                gp_work = GaussianProcessRegressor(
                    kernel=kernel_final,
                    normalize_y=True,
                    optimizer=None,
                    random_state=self.gp.random_state
                )
                gp_work.fit(X_aug, y_aug)

            x_scaled_new = self._optimize_ei(gp_work, y_best)
            x_real_new = self._unscale(x_scaled_new)
            x_real_new = self._round_integers(x_real_new)
            x_scaled_rounded = self._scale(x_real_new)

            batch_scaled.append(x_scaled_rounded)
            batch_dicts.append({p: x_real_new[i] for i, p in enumerate(self.param_names)})

        return batch_dicts


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

            self.sm = float(rocket.static_margin(0))
            if self.sm < 1.5 or self.sm > 5.0:
                dist = min(abs(self.sm - 1.5), abs(self.sm - 5.0))
                self.fitness = 1e-3 / (1.0 + dist)
                self.evaluated = True
                return

            flight = Flight(
                rocket=rocket,
                environment=ENV,
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

        except Exception:
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


if __name__ == "__main__":
    POPULATION_SIZE = 25
    GENERATIONS = 15

    now = datetime.datetime.now(datetime.timezone.utc)
    env = Environment(
        latitude=38.9627778,
        longitude=-8.96277777,
        elevation=160,
        date=(now.year, now.month, now.day, now.hour)
    )
    env.set_atmospheric_model(type="forecast", file="GFS")
    ENV = env

    printer = EvolutionPrinter(VARIABLE_GENE_BOUNDS, FIXED_GENES, TARGET_APOGEE)
    printer.print_header()

    bo = BayesianOptimizer(VARIABLE_GENE_BOUNDS, INTEGER_GENES)

    print("Collecting initial random population...")
    initial_rockets = [RocketPhenotype(DNA()) for _ in range(POPULATION_SIZE)]

    num_workers = min(os.cpu_count(), POPULATION_SIZE)
    with ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=_init_worker_env,
        initargs=(38.9627778, -8.96277777, 160, now.year, now.month, now.day, now.hour)
    ) as executor:

        initial_rockets = [executor.submit(_eval_rocket, r) for r in initial_rockets]
        initial_rockets = [f.result() for f in initial_rockets]

        global_best_rocket = None
        global_best_fitness = -1.0

        for rocket in initial_rockets:
            bo.add_observation(rocket.dna.genes, rocket.fitness)
            if rocket.fitness > global_best_fitness:
                global_best_fitness = rocket.fitness
                global_best_rocket = rocket

        printer.print_generation_summary(0, global_best_rocket)

        for gen in range(1, GENERATIONS):
            batch_dicts = bo.suggest_batch(POPULATION_SIZE)
            new_rockets = [RocketPhenotype(DNA(genes)) for genes in batch_dicts]

            futures = [executor.submit(_eval_rocket, r) for r in new_rockets]
            new_rockets = [f.result() for f in futures]

            for rocket in new_rockets:
                bo.add_observation(rocket.dna.genes, rocket.fitness)
                if rocket.fitness > global_best_fitness:
                    global_best_fitness = rocket.fitness
                    global_best_rocket = rocket

            printer.print_generation_summary(gen, global_best_rocket)

    best_params = {**FIXED_GENES, **global_best_rocket.dna.genes}
    best_builder = RocketBuilder(best_params)
    best_rocket = best_builder.build()

    best_flight = Flight(
        rocket=best_rocket,
        environment=ENV,
        rail_length=11.65,
        inclination=85,
        heading=144,
        terminate_on_apogee=True
    )

    best_builder.show()
    best_flight.plots.trajectory_3d()
    print("\nBayesian Optimization Complete.")