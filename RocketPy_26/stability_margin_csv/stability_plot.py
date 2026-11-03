import glob
import os
import re
import pandas as pd
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Marge statique : dossier du script (stability_margin_csv)
MARGIN_DIR = SCRIPT_DIR
# Angles : dossier angles_csv (à adapter si besoin)
ANGLES_DIR = r"C:\Users\vthue\OneDrive\Documents\GitHub\2026_C_FD_SIM_Rocketpy\RocketPy_26\angles_csv"
OUT_DIR = SCRIPT_DIR

labels = {
    "baseline": "without shift",
    "shiftm1": "with shift: m_copv = 2.6 kg",
    "shiftm2": "with shift: m_copv = 3.6 kg",
    "shiftm3": "with shift: m_copv = 4.6 kg",
}

def get_key(filename):
    """Extrait 'baseline', 'shiftm1', ... du nom de fichier."""
    m = re.search(r"(baseline|shiftm\d+)", filename)
    return m.group(1) if m else os.path.splitext(filename)[0]

def read_csv(path):
    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    return df

def load_folder(folder, required_cols):
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        df = read_csv(path)
        name = os.path.basename(path)
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            print(f"[ignoré] {name} : colonnes absentes {missing} (présentes : {list(df.columns)})")
            continue
        out[get_key(name)] = df
        print(f"[ok]     {name}")
    return out

print("--- Marge statique ---", MARGIN_DIR)
margin_data = load_folder(MARGIN_DIR, ["time_s", "stability_margin_cal"])
print("--- Angles ---", ANGLES_DIR)
angle_data = load_folder(ANGLES_DIR, ["time_s", "phi_deg", "theta_deg", "psi_deg"])

# ---------- Figure 1 : marge statique ----------
if margin_data:
    plt.figure(figsize=(9, 5))
    for key, df in margin_data.items():
        plt.plot(df["time_s"], df["stability_margin_cal"], label=labels.get(key, key))
    plt.axhline(0, color="black", linewidth=0.8, linestyle="--")
    plt.xlabel("Time [s]")
    plt.ylabel("Static margin [calibers]")
    plt.title("Stability Margin vs Time")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(OUT_DIR, "stability_margin_comparison.png"), dpi=150, bbox_inches="tight")
else:
    print("Aucune donnée de marge statique trouvée.")

# ---------- Figure 2 : angles ----------
if angle_data:
    angles = [("phi_deg", r"$\phi$"), ("theta_deg", r"$\theta$"), ("psi_deg", r"$\psi$")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5), sharex=True)
    for ax, (col, title) in zip(axes, angles):
        for key, df in angle_data.items():
            ax.plot(df["time_s"], df[col], label=labels.get(key, key))
        ax.set_title(title)
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Angle [deg]")
        ax.grid(True, alpha=0.3)
    handles, lbls = axes[0].get_legend_handles_labels()
    fig.legend(handles, lbls, loc="lower center", ncol=len(lbls), frameon=False)
    fig.suptitle("Euler angles vs Time")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(os.path.join(OUT_DIR, "euler_angles_comparison.png"), dpi=150, bbox_inches="tight")
else:
    print("Aucune donnée d'angles trouvée.")

plt.show()