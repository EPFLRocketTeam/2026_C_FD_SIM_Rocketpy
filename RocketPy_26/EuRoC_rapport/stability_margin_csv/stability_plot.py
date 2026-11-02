import glob
import os
import pandas as pd
import matplotlib.pyplot as plt

plt.figure(figsize=(9, 5))
for path in sorted(glob.glob(os.path.join(DATA_DIR, "stability_margin_*.csv"))):
    df = pd.read_csv(path)
    label = os.path.basename(path).replace("stability_margin_", "").replace(".csv", "")
    plt.plot(df["time_s"], df["stability_margin_cal"], label=label)

plt.axhline(0, color="black", linewidth=0.8, linestyle="--")
plt.xlabel("Time [s]"); plt.ylabel("Static margin [calibers]")
plt.title("Stability Margin vs Time")
plt.grid(True, alpha=0.3)
plt.legend()
plt.show()