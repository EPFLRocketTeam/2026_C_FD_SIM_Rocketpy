# single_flight.py
"""Single flight with standard atmosphere, robust wind, and working plots."""

import numpy as np
import argparse
from rocketpy import Environment, Flight, Function
from rocket_builder import RocketBuilder

# ----- Best design from Gen 15 -----
DESIGN = {
    'fin_span': 0.429,
    'fin_root_chord': 0.243,
    'fuel_mass': 11.778,
    'oxidizer_mass': 10.081,
    'fin_tip_chord': 0.119,
    'fin_sweep_length': 0.487,
    'tail_top_radius': 0.166,
    'tail_bottom_radius': 0.075,
    'nose_length': 1.231,
    'tail_length': 0.379,
    'fin_count': 3,
    'motor_type': 'liquid',
}

# ----- Location -----
LATITUDE = 38.9627778
LONGITUDE = -8.96277777
ELEVATION = 160           # m ASL
DATE = (2026, 3, 5, 12, 0)

# Default wind profile
WIND_HEIGHTS = np.array([0, 100, 500, 1000, 2000, 3500])
WIND_SPEEDS  = np.array([5, 8, 10, 12, 15, 18])
WIND_DIRS    = np.array([180, 180, 190, 200, 210, 220])

def set_wind(env, heights_agl, speeds, directions):
    """Assign wind components in a robust way."""
    z_asl = heights_agl + env.elevation
    u = []; v = []
    for s, d in zip(speeds, directions):
        rad = np.radians(d)
        u.append(-s * np.sin(rad))   # eastward
        v.append(-s * np.cos(rad))   # northward

    wind_u_fn = Function(
        np.column_stack([z_asl, u]),
        inputs="Height (m)", outputs="Wind U (m/s)",
        extrapolation="constant"
    )
    wind_v_fn = Function(
        np.column_stack([z_asl, v]),
        inputs="Height (m)", outputs="Wind V (m/s)",
        extrapolation="constant"
    )

    # Set both possible attribute names – RocketPy may use either
    env.wind_u = wind_u_fn
    env.wind_v = wind_v_fn
    env.wind_velocity_x = wind_u_fn
    env.wind_velocity_y = wind_v_fn

    # Diagnostic
    for alt_agl in [0, 1500, 3000]:
        z = alt_agl + env.elevation
        print(f"Wind at {alt_agl} m AGL: U={env.wind_u(z):.2f}, V={env.wind_v(z):.2f}")

def create_environment(random_wind=False, strong_wind=False, seed=None):
    env = Environment(latitude=LATITUDE, longitude=LONGITUDE, elevation=ELEVATION, date=DATE)
    env.set_atmospheric_model(type="standard_atmosphere")

    if strong_wind:
        print("50 m/s constant wind from 270°")
        set_wind(env, np.array([0, 5000]), np.array([50, 50]), np.array([270, 270]))
    elif random_wind:
        if seed is not None:
            np.random.seed(seed)
            print(f"Random wind with seed {seed}")
        else:
            print("Random wind (no seed, different each run)")
        heights = np.sort(np.random.uniform(0, 3500, 20))
        heights[0] = 0; heights[-1] = 3500
        speeds = np.random.uniform(0, 20, 20)
        dirs = np.random.uniform(0, 360, 20)
        set_wind(env, heights, speeds, dirs)
    else:
        print("Fixed wind profile")
        set_wind(env, WIND_HEIGHTS, WIND_SPEEDS, WIND_DIRS)
    return env

def run_single_flight(args):
    """Build rocket, run flight, show plots."""
    builder = RocketBuilder(DESIGN)
    rocket = builder.build()
    print(f"Static margin: {rocket.static_margin(0):.2f}")

    env = create_environment(args.random_wind, args.strong_wind)

    inclination = 90 if args.upright else 85
    heading = 144

    flight = Flight(
        rocket=rocket, environment=env,
        rail_length=11.65, inclination=inclination, heading=heading,
        terminate_on_apogee=True
    )

    print("\n--- Flight Summary ---")
    print(f"Apogee: {flight.apogee:.2f} m")
    print(f"Apogee time: {flight.apogee_time:.2f} s")
    drift = np.sqrt(flight.x(flight.apogee_time)**2 + flight.y(flight.apogee_time)**2)
    print(f"Drift at apogee: {drift:.2f} m")

    # Plots that exist in most RocketPy versions
    flight.plots.trajectory_3d()
    flight.plots.trajectory()
    flight.plots.velocity()
    flight.plots.aerodynamic_forces()
    flight.plots.stability_margin()
    try:
        flight.plots.angle_of_attack()
    except AttributeError:
        print("Angle of attack plot not available in this RocketPy version.")

    return flight

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--random-wind', action='store_true', help='Random wind layers')
    parser.add_argument('--strong-wind', action='store_true', help='50 m/s constant wind')
    parser.add_argument('--upright', action='store_true', help='Launch vertically (inclination=90°)')
    args = parser.parse_args()
    _ = run_single_flight(args)