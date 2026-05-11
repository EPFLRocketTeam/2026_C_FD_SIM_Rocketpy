import argparse
import datetime
import importlib
from rocketpy import Environment, Flight
from rocket_builder import RocketBuilder
from evaluator import Evaluator
from logger import Logger
from printer import Printer

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
FIXED_GENES = {'motor_type': 'liquid'}
INTEGER_GENES = ['fin_count']
TARGET_APOGEE = 3000.0
HEIGHT_DEVIATION_ALLOWED = 200.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--algo', type=str, default='bayesian', choices=['genetic','memetic','bayesian'])
    parser.add_argument('--max_gen', type=int, default=15)
    parser.add_argument('--iter_per_gen', type=int, default=20)
    parser.add_argument('--local_search_prob', type=float, default=0.35)
    parser.add_argument('--local_search_evals', type=int, default=12)
    parser.add_argument('--selection_method', type=str, default='rank')
    parser.add_argument('--sp', type=float, default=1.5)
    args = parser.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    env = Environment(
        latitude=38.9627778, longitude=-8.96277777, elevation=160,
        date=(now.year, now.month, now.day, now.hour)
    )
    env.set_atmospheric_model(type="forecast", file="GFS")

    printer = Printer(VARIABLE_GENE_BOUNDS, FIXED_GENES, TARGET_APOGEE)
    printer.print_header()

    algo_module = importlib.import_module(f'algorithms.{args.algo}')
    AlgorithmClass = getattr(algo_module, 'Algorithm')
    optimizer = AlgorithmClass(VARIABLE_GENE_BOUNDS, FIXED_GENES, INTEGER_GENES,
                               TARGET_APOGEE, HEIGHT_DEVIATION_ALLOWED, args)

    evaluator = Evaluator(env, TARGET_APOGEE, HEIGHT_DEVIATION_ALLOWED)
    logger = Logger(VARIABLE_GENE_BOUNDS.keys(), algo=args.algo)

    global_best_fitness = -1
    global_best_design = None
    global_best_metrics = None

    for gen in range(1, args.max_gen + 1):
        results = optimizer.run_generation(evaluator)

        for idx, (design, fit, metrics) in enumerate(results):
            logger.log(gen, idx, fit, metrics, design)
            if fit > global_best_fitness:
                global_best_fitness = fit
                global_best_design = design
                global_best_metrics = metrics

        printer.print_generation(gen, global_best_fitness, global_best_design, global_best_metrics)

    logger.close()

    best_params = {**FIXED_GENES, **global_best_design}
    builder = RocketBuilder(best_params)
    rocket = builder.build()
    flight = Flight(
        rocket=rocket, environment=env, rail_length=11.65,
        inclination=85, heading=144, terminate_on_apogee=True
    )
    builder.show()
    flight.plots.trajectory_3d()
    print("\nCompleted Optimization.")

if __name__ == '__main__':
    main()