import numpy as np

class FitnessFunction:
    def __init__(self, target_apogee=3000.0, height_tolerance=200.0):
        self.target_apogee = target_apogee
        self.height_tolerance = height_tolerance

    def evaluate(self, rocket, flight):
        sm = float(rocket.static_margin(0))
        apogee = flight.apogee
        t_ap = flight.apogee_time
        drift = np.sqrt(flight.x(t_ap)**2 + flight.y(t_ap)**2)

        z_error = abs(apogee - self.target_apogee)
        fitness = 10000.0 / (1.0 + z_error + drift * 0.1)
        if z_error <= self.height_tolerance:
            fitness *= 2

        sm_penalty = 0.0
        if sm < 1.5:
            sm_penalty = 1.5 - sm
        elif sm > 2.0:
            sm_penalty = sm - 2.0
        fitness /= (1.0 + sm_penalty * 5.0)

        metrics = {
            'apogee': apogee,
            'drift': drift,
            'sm': sm
        }
        return fitness, metrics

    def invalid_design_fitness(self, sm):
        dist = min(abs(sm - 1.5), abs(sm - 5.0))
        return 1e-3 / (1.0 + dist)