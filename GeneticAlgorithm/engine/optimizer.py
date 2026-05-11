from abc import ABC, abstractmethod

class OptimizerBase(ABC):
    def __init__(self, variable_bounds, fixed_genes, integer_genes, target_apogee, height_tolerance, args):
        self.variable_bounds = variable_bounds
        self.fixed_genes = fixed_genes
        self.integer_genes = integer_genes
        self.target_apogee = target_apogee
        self.height_tolerance = height_tolerance
        self.args = args

    # @abstractmethod
    # def initial_population(self, batch_size):
    #     """Return a list of param dicts for the first generation."""
    #     pass

    # @abstractmethod
    # def suggest_batch(self, batch_size):
    #     """Return a list of new param dicts to evaluate."""
    #     pass

    # @abstractmethod
    # def add_observation(self, design_dict, fitness):
    #     """Feed back a completed evaluation."""
    #     pass

    # from abc import ABC, abstractmethod

    @abstractmethod
    def run_generation(self, evaluator):
        """
        Execute one generation: return a list of (design_dict, fitness, metrics) for all individuals.
        """
        pass