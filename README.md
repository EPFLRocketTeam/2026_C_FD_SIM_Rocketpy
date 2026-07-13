# 2026_C_FD_SIM_Rocketpy

## FD Rocketpy
# Euroc Simulations
TODO:
# Excel
TODO:
# RocketPy_26
TODO:
# Genetic Algorithm

## Rocket Design Optimization Engine

Liquid and solid rocket design using algorithmic evolution. Reach a target apogee while minimizing drift and ensuring static stability. Built on [RocketPy](https://github.com/RocketPy-Team/RocketPy). Supports genetic, memetic, and Bayesian optimization with customizable wind layers.

## Project Structure

```text
GeneticAlgorithm/
├── archive
├── engine/
│   ├── algorithms/             # genetic.py, memetic.py, bayesian.py
│   ├── backtests/              # CSV logs from optimization runs
│   ├── data/                   # thrust curves, ullage CSVs, fluid properties
│   ├── environment_settings.py  # Environment factory and wind management
│   ├── evaluator.py            # Parallel evaluation and worker pool
│   ├── fitness.py              # Fitness function (apogee error, drift, stability)
│   ├── logger.py               # CSV logger
│   ├── main.py                 # Optimization entry point
│   ├── optimizer.py            # Abstract base class for algorithms
│   ├── printer.py              # Console output
│   ├── rocket_builder.py       # Rocket and motor assembly
│   ├── single_flight.py        # Single-design flight simulation
│   └── visualizer.py           # Post-run analysis and plotting
└── misc
```

## Requirements

- Python 3.10+
- RocketPy >= 1.3.0
- NumPy, SciPy, scikit-learn, pandas, matplotlib, seaborn

```bash
pip install rocketpy numpy scipy scikit-learn pandas matplotlib seaborn
```

# Usage

## Running the Optimizer

```bash
python main.py [--algo {genetic,memetic,bayesian}] [options]
```

## Key options:

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--algo` | Algorithm: genetic, memetic, bayesian | `bayesian` |
| `--max_gen` | Number of generations | `15` |
| `--iter_per_gen` | Population size per generation | `20` |
| `--selection_method` | Parent selection: rank, boltzmann, tournament | `rank` |
| `--sp` | Selection pressure (rank only) | `1.5` |
| `--local_search_prob` | Local search probability (memetic only) | `0.35` |
| `--local_search_evals` | Max local search steps (memetic only) | `12` |
| `--random-wind` | Use random wind layers (different each run unless seed is set) | `off` |
| `--strong-wind` | Apply constant 50 m/s wind for drift testing | `off` |
| `--seed` | Integer seed for reproducible random wind | `None` |

Examples:

```bash
# Genetic algorithm, 10 generations, default population
python main.py --algo genetic --max_gen 10

# Bayesian optimization with 30 samples per generation
python main.py --algo bayesian --iter_per_gen 30

# Memetic algorithm with random wind layers
python main.py --algo memetic --random-wind

# Strong wind test (50 m/s from West)
python main.py --algo genetic --max_gen 5 --strong-wind

# Reproducible random wind using a seed
python main.py --algo bayesian --random-wind --seed 42
```

## Testing a Single Design

Edit the DESIGN dictionary in single_flight.py to set your parameters, then:

```bash
python single_flight.py [--random-wind] [--strong-wind] [--upright] [--seed N]
```

# Visualizing Results
Each run saves a CSV in backtests/. To plot:

```bash
# Auto-select latest log
python visualizer.py

# Specific file
python visualizer.py backtests/backtest_20260713181149_bayesian.csv
```

Generated plots: best fitness, mean fitness with error bars, best apogee, drift and stability margin evolution, parameter traces, correlation heatmap, fitness vs apogee scatter, feasible/infeasible counts.

# How It Works
* **Initialization**: The algorithm creates an initial population of random designs within predefined bounds. Bayesian optimizer starts with a few random points before fitting its surrogate model.
* **Evaluation**: Each design is converted into a RocketPy rocket and simulated in parallel in a standard atmosphere with wind (if specified).
* **Fitness**: Rewards designs approaching the target apogee (3000 m) with low drift (bonus within 200 m), penalizing stability margins outside 1.5–5.0.
* **Variation & Selection**: Genetic/memetic algorithms apply crossover, mutation, and selection (memetic adds local random walk). Bayesian optimizer maximizes Expected Improvement via a Gaussian process.
* **Elitism**: The best individual is carried to the next generation.
* **Logging**: All evaluated designs are written to a timestamped CSV in `backtests/`.

# Customization & Extension
* **Add parameters**: Extend `VARIABLE_GENE_BOUNDS` and `INTEGER_GENES` in `main.py`, then update `RocketBuilder` to use them.
* **Change fitness**: Modify `fitness.py` to adjust weights or add objectives.
* **New wind models**: Add cases in `environment_settings.py`'s `get_environment_parameters()` function.
* **New algorithm**: Create a class in `algorithms/` that inherits from `OptimizerBase` and implements `run_generation(evaluator)` to be automatically available via `--algo`.

# License
This project is provided for educational and research purposes. Refer to the RocketPy license for its terms.

# License
This project is provided for educational and research purposes. Refer to the RocketPy license for its terms.