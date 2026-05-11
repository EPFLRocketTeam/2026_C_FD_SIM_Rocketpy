import csv
import os
from datetime import datetime

class Logger:
    def __init__(self, param_names, algo="unknown"):
        self.param_names = list(param_names)
        self.algo = algo

        self.output_dir = "backtests"
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.filename = f"backtest_{timestamp}_{self.algo}.csv"
        self.filepath = os.path.join(self.output_dir, self.filename)

        self.file = open(self.filepath, 'w', newline='')
        self.writer = csv.DictWriter(
            self.file,
            fieldnames=['gen', 'iter', 'fitness', 'apogee', 'drift', 'sm'] + self.param_names
        )
        self.writer.writeheader()
        print(f"Logging to {self.filepath}")

    def log(self, gen, idx, fitness, metrics, param_dict):
        row = {
            'gen': gen,
            'iter': idx,
            'fitness': fitness,
            'apogee': metrics['apogee'],
            'drift': metrics['drift'],
            'sm': metrics['sm']
        }
        row.update(param_dict)
        self.writer.writerow(row)
        self.file.flush()

    def close(self):
        self.file.close()