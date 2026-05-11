import random
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel
from scipy.optimize import minimize
from scipy.stats import norm
from optimizer import OptimizerBase

class Algorithm(OptimizerBase):
    def __init__(self, variable_bounds, fixed_genes, integer_genes,
                 target_apogee, height_tolerance, args):
        super().__init__(variable_bounds, fixed_genes, integer_genes,
                         target_apogee, height_tolerance, args)
        self.param_names = list(variable_bounds.keys())
        self.bounds = np.array([variable_bounds[p] for p in self.param_names])
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
            random_state=42
        )

        self.X_scaled = np.empty((0, self.n_params))
        self.y = np.empty(0)
        self.best_y = -1e9
        self.best_x_scaled = None
        self.batch_size = args.iter_per_gen

    def _scale(self, X_real):
        return (X_real - self.lb) / self.range_

    def _unscale(self, X_scaled):
        return X_scaled * self.range_ + self.lb

    def _round_integers(self, X_real):
        X = X_real.copy()
        for i, is_int in enumerate(self.integer_mask):
            if is_int:
                X[..., i] = np.clip(np.round(X[..., i]), self.lb[i], self.ub[i])
        return X

    def _expected_improvement(self, x_scaled, gp, y_best):
        x = np.atleast_2d(x_scaled)
        mu, sigma = gp.predict(x, return_std=True)
        mu = mu[0]
        sigma = sigma[0]
        if sigma < 1e-12:
            return 0.0
        z = (mu - y_best) / sigma
        ei = (mu - y_best) * norm.cdf(z) + sigma * norm.pdf(z)
        return ei

    def _optimize_ei(self, gp, y_best):
        best_x = None
        best_ei = -1e9
        bounds_scaled = [(0.0, 1.0)] * self.n_params
        def neg_ei(x):
            return -self._expected_improvement(x, gp, y_best)
        for _ in range(50):
            x0 = np.random.uniform(0, 1, self.n_params)
            res = minimize(neg_ei, x0, bounds=bounds_scaled, method='L-BFGS-B')
            if res.success and -res.fun > best_ei:
                best_ei = -res.fun
                best_x = res.x
        if best_x is None:
            best_x = x0
        return best_x

    def run_generation(self, evaluator):
        if len(self.y) < 2:
            designs = []
            for _ in range(self.batch_size):
                x_real = np.array([np.random.uniform(*b) for b in self.bounds])
                x_real = self._round_integers(x_real)
                designs.append({p: x_real[i] for i, p in enumerate(self.param_names)})
            batch = designs
        else:
            self.gp.fit(self.X_scaled, self.y)
            y_best = self.best_y
            batch_scaled = []
            batch_dicts = []
            kernel_fixed = self.gp.kernel_
            for b in range(self.batch_size):
                if b == 0:
                    gp_work = self.gp
                else:
                    X_aug = np.vstack([self.X_scaled, np.array(batch_scaled)])
                    y_aug = np.concatenate([self.y, np.full(len(batch_scaled), y_best * 0.95)])
                    gp_work = GaussianProcessRegressor(
                        kernel=kernel_fixed,
                        normalize_y=True,
                        optimizer=None
                    )
                    gp_work.fit(X_aug, y_aug)
                x_scaled_new = self._optimize_ei(gp_work, y_best)
                x_real_new = self._unscale(x_scaled_new)
                x_real_new = self._round_integers(x_real_new)
                x_scaled_rounded = self._scale(x_real_new)
                batch_scaled.append(x_scaled_rounded)
                batch_dicts.append({p: x_real_new[i] for i, p in enumerate(self.param_names)})
            batch = batch_dicts

        results = evaluator.evaluate_batch(batch)

        for (design, fitness, metrics) in results:
            x = np.array([design[p] for p in self.param_names])
            x = self._round_integers(x)
            x_scaled = self._scale(x)
            self.X_scaled = np.vstack([self.X_scaled, x_scaled])
            self.y = np.append(self.y, fitness)
            if fitness > self.best_y:
                self.best_y = fitness
                self.best_x_scaled = x_scaled

        return results