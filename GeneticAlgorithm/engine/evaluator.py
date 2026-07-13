# evaluator.py
import numpy as np
import random
from concurrent.futures import ProcessPoolExecutor
from rocketpy import Environment, Flight
from rocket_builder import RocketBuilder
from fitness import FitnessFunction
from environment_settings import build_environment

FIXED_GENES = {'motor_type': 'liquid'}

_worker_env = None
_worker_fitness_fn = None

def _init_worker(target_apogee, height_tolerance, env_params):
    """Initialise each worker with its own environment, identical to the main one."""
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="rocketpy.motors.motor")
    warnings.filterwarnings("ignore", message=".*Exact chosen launch time is not available.*")
    warnings.filterwarnings("ignore", message=".*loadtxt: input contained no data.*")

    global _worker_env, _worker_fitness_fn
    _worker_env = build_environment(env_params)
    _worker_fitness_fn = FitnessFunction(target_apogee, height_tolerance)


def _simulate_single(design_dict):
    """Run one simulation using the worker's environment."""
    full = {**FIXED_GENES, **design_dict}
    try:
        builder = RocketBuilder(full)
        rocket = builder.build()
        sm = float(rocket.static_margin(0))

        if sm < 1.5 or sm > 5.0:
            fit = _worker_fitness_fn.invalid_design_fitness(sm)
            return design_dict, fit, {'apogee': 0.0, 'drift': 0.0, 'sm': sm}

        flight = Flight(
            rocket=rocket, environment=_worker_env,
            rail_length=11.65, inclination=85, heading=144,
            terminate_on_apogee=True
        )
        fit, metrics = _worker_fitness_fn.evaluate(rocket, flight)
        return design_dict, fit, metrics

    except Exception:
        return design_dict, 1e-5/(1+random.random()), {'apogee':0.0, 'drift':0.0, 'sm':0.0}


class Evaluator:
    def __init__(self, env_params, target_apogee, height_tolerance):
        self.env_params = env_params
        self.env = build_environment(env_params)          # for single-thread evaluations
        self.fitness_fn = FitnessFunction(target_apogee, height_tolerance)
        self.target_apogee = target_apogee
        self.height_tolerance = height_tolerance

    def evaluate_batch(self, designs):
        """Parallel evaluation of a list of design dicts."""
        with ProcessPoolExecutor(
            initializer=_init_worker,
            initargs=(self.target_apogee, self.height_tolerance, self.env_params)
        ) as executor:
            futures = [executor.submit(_simulate_single, d) for d in designs]
            results = [f.result() for f in futures]
        return results

    def evaluate_single(self, design_dict):
        """Sequential evaluation (used by local search etc.)."""
        full = {**FIXED_GENES, **design_dict}
        try:
            builder = RocketBuilder(full)
            rocket = builder.build()
            sm = float(rocket.static_margin(0))

            if sm < 1.5 or sm > 5.0:
                fit = self.fitness_fn.invalid_design_fitness(sm)
                return design_dict, fit, {'apogee': 0.0, 'drift': 0.0, 'sm': sm}

            flight = Flight(
                rocket=rocket, environment=self.env,
                rail_length=11.65, inclination=85, heading=144,
                terminate_on_apogee=True
            )
            fit, metrics = self.fitness_fn.evaluate(rocket, flight)
            return design_dict, fit, metrics

        except Exception:
            return design_dict, 1e-5/(1+random.random()), {'apogee':0.0, 'drift':0.0, 'sm':0.0}