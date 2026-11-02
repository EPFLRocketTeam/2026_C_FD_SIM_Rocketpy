import glob
import os
import pandas as pd
import matplotlib.pyplot as plt

# Dossier du script (là où se trouvent aussi les CSV)
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

labels = {
    "baseline": "without shift",
    "shiftm1": "with shift: m_copv = 2.6 kg",
    "shiftm2": "with shift: m_copv = 3.6 kg",
    "shiftm3": "with shift: m_copv = 4.6 kg"
}

plt.figure(figsize=(9, 5))
for path in sorted(glob.glob(os.path.join(DATA_DIR, "stability_margin_*.csv"))):
    df = pd.read_csv(path)
    key = os.path.basename(path).replace("stability_margin_", "").replace(".csv", "")
    plt.plot(df["time_s"], df["stability_margin_cal"], label=labels.get(key, key))

plt.axhline(0, color="black", linewidth=0.8, linestyle="--")
plt.xlabel("Time [s]"); plt.ylabel("Static margin [calibers]")
plt.title("Stability Margin vs Time")
plt.grid(True, alpha=0.3)
plt.legend()
plt.savefig(os.path.join(DATA_DIR, "stability_margin_comparison.png"), dpi=150, bbox_inches="tight")
plt.show()