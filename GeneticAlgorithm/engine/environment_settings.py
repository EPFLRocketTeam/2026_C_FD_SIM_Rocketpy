# environment_settings.py
"""Create a standard atmosphere environment with custom wind layers."""

import numpy as np
from rocketpy import Environment, Function

# Default location and date (date is unused for standard atmosphere)
LAT = 38.9627778
LON = -8.96277777
ELEV = 160                     # m ASL
DATE = (2026, 3, 5, 12, 0)     # arbitrary, standard atmosphere ignores it

# Default fixed wind profile
DEFAULT_WIND_HEIGHTS = np.array([0, 100, 500, 1000, 2000, 3500])
DEFAULT_WIND_SPEEDS  = np.array([5, 8, 10, 12, 15, 18])
DEFAULT_WIND_DIRS    = np.array([180, 180, 190, 200, 210, 220])


def set_wind(env, heights_agl, speeds, directions):
    """Apply wind components to the environment.
    
    Parameters
    ----------
    heights_agl : ndarray
        Altitudes above ground level (m).
    speeds : ndarray
        Wind speeds (m/s).
    directions : ndarray
        Meteorological directions FROM which the wind blows (degrees, 0=North, 90=East).
    """
    z_asl = heights_agl + env.elevation
    u, v = [], []
    for s, d in zip(speeds, directions):
        rad = np.radians(d)
        u.append(-s * np.sin(rad))   # eastward component
        v.append(-s * np.cos(rad))   # northward component

    wind_u = Function(
        np.column_stack([z_asl, u]),
        inputs="Height (m)", outputs="Wind U (m/s)",
        extrapolation="constant"
    )
    wind_v = Function(
        np.column_stack([z_asl, v]),
        inputs="Height (m)", outputs="Wind V (m/s)",
        extrapolation="constant"
    )

    # Assign to both possible attribute names (covers different RocketPy versions)
    env.wind_u = wind_u
    env.wind_v = wind_v
    env.wind_velocity_x = wind_u
    env.wind_velocity_y = wind_v


def get_environment_parameters(args):
    """Parse command‑line arguments and return a dict that fully describes the environment.
    
    This dict can be safely passed to workers and used to rebuild the identical environment.
    """
    params = {
        'lat': LAT,
        'lon': LON,
        'elev': ELEV,
        'date': DATE,
        'wind_type': 'fixed',
        'wind_heights': DEFAULT_WIND_HEIGHTS.copy(),
        'wind_speeds':  DEFAULT_WIND_SPEEDS.copy(),
        'wind_dirs':    DEFAULT_WIND_DIRS.copy(),
    }

    # Optional flags (attach them to args if you want)
    if hasattr(args, 'random_wind') and args.random_wind:
        seed = getattr(args, 'seed', None)
        if seed is not None:
            np.random.seed(seed)
        heights = np.sort(np.random.uniform(0, 3500, 20))
        heights[0] = 0
        heights[-1] = 3500
        speeds = np.random.uniform(0, 20, 20)
        dirs = np.random.uniform(0, 360, 20)
        params['wind_type'] = 'random'
        params['wind_heights'] = heights
        params['wind_speeds']  = speeds
        params['wind_dirs']    = dirs

    elif hasattr(args, 'strong_wind') and args.strong_wind:
        params['wind_type'] = 'strong'
        params['wind_heights'] = np.array([0, 5000])
        params['wind_speeds']  = np.array([50, 50])
        params['wind_dirs']    = np.array([270, 270])

    return params


def build_environment(params):
    """Create a RocketPy Environment from a parameter dict (as returned by get_environment_parameters)."""
    env = Environment(
        latitude=params['lat'],
        longitude=params['lon'],
        elevation=params['elev'],
        date=params['date']
    )
    env.set_atmospheric_model(type="standard_atmosphere")
    set_wind(env, params['wind_heights'], params['wind_speeds'], params['wind_dirs'])
    return env