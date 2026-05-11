class Printer:
    def __init__(self, variable_bounds, fixed_genes, target_apogee):
        self.variable_bounds = variable_bounds
        self.fixed_genes = fixed_genes
        self.target_apogee = target_apogee

    def print_header(self):
        print("=" * 60)
        print("ROCKET DESIGN OPTIMIZATION")
        print("=" * 60)
        print("Fixed parameters:")
        for key, value in self.fixed_genes.items():
            print(f"  {key.replace('_', ' ').capitalize():20} {value}")
        print("\nVariable parameters (evolved):")
        for key, (lo, hi) in self.variable_bounds.items():
            print(f"  {key.replace('_', ' ').capitalize():20} [{lo:.3f}, {hi:.3f}]")
        print(f"\nTarget apogee: {self.target_apogee} m")
        print("=" * 60)

    def print_generation(self, gen, best_fitness, best_design, best_metrics):
        print(f"\n--- Generation {gen} ---")
        print(f"Best fitness:       {best_fitness:.2f}")
        print(f"Apogee:             {best_metrics['apogee']:.2f} m")
        print(f"Drift:              {best_metrics['drift']:.2f} m")
        print(f"Stability margin:   {best_metrics['sm']:.2f}")
        print("Optimized parameters:")
        for key in self.variable_bounds:
            print(f"  {key.replace('_', ' ').capitalize():20} {best_design[key]:8.3f}")