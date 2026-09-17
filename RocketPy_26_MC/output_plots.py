"""
output_plots.py

Génère des graphes PNG à partir du dict de résultats produit par
simulator.run_simulation(). Utilisé par la fenêtre d'export de app.py.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # pas d'affichage interactif, juste sauvegarde fichier
import matplotlib.pyplot as plt


def _save(fig, directory: str | Path, filename: str) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_euler_angles(result: dict, directory: str | Path) -> Path:
    data = result["euler_angles"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(data["time"], data["phi"], label="φ — Spin")
    ax.plot(data["time"], data["theta"], label="θ — Nutation")
    ax.plot(data["time"], data["psi"], label="ψ — Precession")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Angle (°)")
    ax.set_title("Euler Angles")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return _save(fig, directory, "euler_angles.png")


def plot_stability_margin(result: dict, directory: str | Path) -> Path:
    data = result["static_margin"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(data["time"], data["margin"], color="firebrick")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.axvline(result["out_of_rail_time"], color="gray", linestyle=":", label="Rail exit")
    ax.axvline(result["time_to_apogee"], color="gray", linestyle="-.", label="Apogee")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Static margin (calibers)")
    ax.set_title("Stability Margin vs Time")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return _save(fig, directory, "stability_margin.png")


def plot_trajectory(result: dict, directory: str | Path) -> Path:
    data = result["trajectory"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(data["time"], data["altitude"], color="steelblue")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Altitude AGL (m)")
    ax.set_title("Altitude vs Time")
    ax.grid(True, alpha=0.3)
    return _save(fig, directory, "trajectory.png")


def plot_velocity(result: dict, directory: str | Path) -> Path:
    data = result["velocity"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(data["time"], data["speed"], color="darkorange")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (m/s)")
    ax.set_title("Speed vs Time")
    ax.grid(True, alpha=0.3)
    return _save(fig, directory, "velocity.png")


def plot_acceleration(result: dict, directory: str | Path) -> Path:
    data = result["acceleration"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(data["time"], data["accel"], color="seagreen")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Acceleration (m/s²)")
    ax.set_title("Acceleration vs Time")
    ax.grid(True, alpha=0.3)
    return _save(fig, directory, "acceleration.png")


def plot_thrust_curve(result: dict, directory: str | Path) -> Path:
    data = result["thrust_curve"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(data["time"], data["thrust"], color="crimson")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Thrust (N)")
    ax.set_title("Thrust Curve")
    ax.grid(True, alpha=0.3)
    return _save(fig, directory, "thrust_curve.png")


PLOT_REGISTRY = {
    "euler_angles": ("Euler angles", plot_euler_angles),
    "stability_margin": ("Stability margin", plot_stability_margin),
    "trajectory": ("Trajectory (altitude)", plot_trajectory),
    "velocity": ("Velocity", plot_velocity),
    "acceleration": ("Acceleration", plot_acceleration),
    "thrust_curve": ("Thrust curve", plot_thrust_curve),
}
