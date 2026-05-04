import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def read_prop_budget_cdr(file: str, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(file,
        sheet_name=sheet,
        header=None,
        index_col=0,
        skiprows=[2],
        usecols='B:M'
    )
    return df


def compute_thrust_curve(ipt, plot: bool = True):
    """Build the engine's thrust profile over time and compute total impulse.

    Returns:
        (t_total, F, total_impulse, slope_ramp_up, slope_derating, slope_shutdown)
        where t_total and F are numpy arrays representing the curve.
    """
    # --- Compute slopes for each linear segment ---
    slope_ramp_up = ipt.F_full_thrust / ipt.t_full_thrust
    slope_derating = (ipt.F_ramp_down - ipt.F_derating) / (ipt.t_ramp_down - ipt.t_derating)
    slope_shutdown = (ipt.F_shutdown - ipt.F_ramp_down) / (ipt.t_shutdown - ipt.t_ramp_down)

    # --- Build time vector and thrust profile ---
    t_total = np.linspace(0, ipt.t_shutdown, ipt.N_points)
    F = np.zeros_like(t_total)

    for i, t in enumerate(t_total):
        if t <= ipt.t_full_thrust:
            F[i] = slope_ramp_up * t
        elif t <= ipt.t_derating:
            F[i] = ipt.F_derating
        elif t <= ipt.t_ramp_down:
            F[i] = ipt.F_derating + slope_derating * (t - ipt.t_derating)
        else:
            F[i] = ipt.F_ramp_down + slope_shutdown * (t - ipt.t_ramp_down)

    # --- Compute total impulse (area under curve) ---
    total_impulse = np.trapezoid(F, t_total)

    # --- Plot thrust curve (only if requested) ---
    if plot:
        plt.figure(figsize=(8, 5))
        plt.plot(t_total, F, label='Thrust Curve (Nominal)', color='dodgerblue', linewidth=2)
        plt.title('Thrust Curve (Nominal)')
        plt.xlabel('Time [s]')
        plt.ylabel('Thrust [N]')
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.legend()
        plt.tight_layout()
        plt.show()

    return (t_total, F, total_impulse, slope_ramp_up, slope_derating, slope_shutdown)